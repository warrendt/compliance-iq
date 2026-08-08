"""Retrieval recall measurement against the NCSP v2.0 gold mapping.

The mapping engine's single biggest failure mode is *recall*: if the correct
Azure Policy definition is never retrieved, no amount of LLM reasoning
downstream can recover it. This module measures that directly, using the
expert-built gold mapping (``fixtures/ncsp_v2_gold_mapping.json``) as ground
truth.

Two metrics are reported at each retrieval depth ``N``:

* **micro recall** — of all gold (control, policy) pairs, the fraction whose
  policy appears in the control's top-``N``. This is the number that bounds how
  well the engine can possibly do.
* **control all-hit** — the fraction of controls for which *every* gold policy
  is retrieved. Stricter, and the one that matters for producing a complete
  mapping row.

**Query realism matters more than anything else here.** The gold sheet carries a
``how_to_meet`` column: the expert's technical restatement of the control in
Azure vocabulary. That text is *not available at runtime* — it is the analyst's
output, not the regulator's input. Measuring with it included inflates recall
roughly fourfold and is the classic ground-truth leak. ``QUERY_REALISTIC`` is
therefore the metric that gates the work; ``QUERY_WITH_GUIDANCE`` is retained
only as an upper-bound reference for what query expansion is aiming at.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "ncsp_v2_gold_mapping.json"

# Retrieval depths reported. 15 is today's shipped candidate window
# (``policy_catalog_candidate_count``); the tail shows the ceiling.
DEFAULT_DEPTHS: Sequence[int] = (15, 30, 40, 50, 100, 200, 500, 1000, 2465)


def load_gold(path: Path = FIXTURE_PATH) -> dict:
    """Load the gold mapping fixture."""
    return json.loads(path.read_text(encoding="utf-8"))


def controls_with_policies(gold: dict) -> List[dict]:
    """Gold controls that carry at least one Azure Policy GUID.

    Only these can contribute to a recall measurement; the other 96 are the
    process/attestation controls that correctly have no policy.
    """
    return [c for c in gold["controls"] if c["policy_definition_ids"]]


def query_realistic(control: dict) -> str:
    """The text genuinely available at runtime: name, description, domain.

    This is what an ingested regulation actually gives us, and what
    ``ai_mapping_service._search_azure_policies`` builds its query from today.
    """
    return " ".join(
        part
        for part in (
            control.get("control_name", ""),
            control.get("description", ""),
            control.get("domain", ""),
        )
        if part
    )


def query_with_guidance(control: dict) -> str:
    """Realistic text plus the expert's Azure-vocabulary restatement.

    NOT achievable at runtime — this leaks the analyst's own output. Used solely
    as the upper-bound target for LLM query expansion.
    """
    return " ".join(
        part
        for part in (query_realistic(control), control.get("how_to_meet", ""))
        if part
    )


QUERY_REALISTIC = query_realistic
QUERY_WITH_GUIDANCE = query_with_guidance


@dataclass
class RecallReport:
    """Recall of gold policies at a range of retrieval depths."""

    depths: Sequence[int]
    control_count: int
    pair_count: int
    micro_hits: Dict[int, int] = field(default_factory=dict)
    all_hit_controls: Dict[int, int] = field(default_factory=dict)
    unretrievable: int = 0

    def micro_recall(self, depth: int) -> float:
        """Fraction of gold (control, policy) pairs retrieved within ``depth``."""
        if not self.pair_count:
            return 0.0
        return self.micro_hits.get(depth, 0) / self.pair_count

    def all_hit_rate(self, depth: int) -> float:
        """Fraction of controls whose gold policies are *fully* retrieved."""
        if not self.control_count:
            return 0.0
        return self.all_hit_controls.get(depth, 0) / self.control_count

    def format_table(self, title: str = "") -> str:
        lines = []
        if title:
            lines.append(title)
        lines.append(f"{'depth':>7} {'micro recall':>14} {'all-hit':>12}")
        for depth in self.depths:
            lines.append(
                f"{depth:>7} "
                f"{self.micro_recall(depth) * 100:>13.1f}% "
                f"{self.all_hit_rate(depth) * 100:>11.1f}%"
            )
        return "\n".join(lines)


def measure_recall(
    search: Callable[[str, int], Iterable[str]],
    controls: Sequence[dict],
    query_fn: Callable[[dict], str] = QUERY_REALISTIC,
    depths: Sequence[int] = DEFAULT_DEPTHS,
    known: Callable[[str], bool] | None = None,
) -> RecallReport:
    """Measure recall of gold policy GUIDs for an arbitrary ranker.

    Args:
        search: ``(query, top_n) -> ordered GUIDs``. Any retrieval strategy can
            be plugged in, so competing designs are compared on equal terms.
        controls: Gold controls carrying policy GUIDs.
        query_fn: Builds the query string from a gold control.
        depths: Retrieval depths to report.
        known: Optional predicate filtering gold GUIDs to those present in the
            corpus. GUIDs the corpus does not contain are *unretrievable* and
            are excluded from the denominator so the metric measures ranking
            quality rather than catalog staleness; they are counted separately.

    Returns:
        A :class:`RecallReport`.
    """
    max_depth = max(depths)
    report = RecallReport(depths=depths, control_count=len(controls), pair_count=0)
    for depth in depths:
        report.micro_hits[depth] = 0
        report.all_hit_controls[depth] = 0

    for control in controls:
        gold_ids = [g.lower() for g in control["policy_definition_ids"]]
        if known is not None:
            retrievable = [g for g in gold_ids if known(g)]
            report.unretrievable += len(gold_ids) - len(retrievable)
        else:
            retrievable = gold_ids
        report.pair_count += len(retrievable)

        ranked = [g.lower() for g in search(query_fn(control), max_depth)]
        for depth in depths:
            window = set(ranked[:depth])
            found = [g for g in retrievable if g in window]
            report.micro_hits[depth] += len(found)
            if retrievable and len(found) == len(retrievable):
                report.all_hit_controls[depth] += 1

    return report


def catalog_search(catalog, semantic: bool = False) -> Callable[[str, int], List[str]]:
    """Adapt a :class:`PolicyCatalogService` to the ``search`` callable.

    Defaults to ``semantic=False`` so the baseline is deterministic and offline;
    the semantic half of hybrid retrieval needs a live embedding deployment for
    the *query*, which :func:`hybrid_search` supplies from a frozen fixture.
    """

    def _search(query: str, top_n: int) -> List[str]:
        return [
            c.name.lower()
            for c in catalog.search(query, top_n=top_n, semantic=semantic)
        ]

    return _search


# ---------------------------------------------------------------------------
# Offline reproduction of the full retrieval pipeline
# ---------------------------------------------------------------------------

INTENTS_PATH = Path(__file__).resolve().parent / "fixtures" / "ncsp_v2_control_intents.json"
QUERY_VECTORS_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "ncsp_v2_query_embeddings.npz"
)


def load_intents(path: Path = INTENTS_PATH) -> Dict[str, dict]:
    """Frozen LLM expansions of the gold controls, keyed by control id.

    Captured by ``scripts/generate_retrieval_eval_fixture.py`` so that recall of
    the *expanded* query is reproducible without Azure OpenAI credentials.
    """
    return json.loads(path.read_text(encoding="utf-8"))["intents"]


def load_query_vectors(path: Path = QUERY_VECTORS_PATH):
    """Frozen embeddings of the expanded queries, as ``{control_id: vector}``."""
    import numpy as np

    with np.load(path, allow_pickle=False) as bundle:
        vectors = bundle["vectors"].astype(np.float32)
        ids = [str(c) for c in bundle["control_ids"]]
    return {cid: vectors[i] for i, cid in enumerate(ids)}


def expansion_text(intent: dict) -> str:
    """Flatten a stored intent into retrieval text.

    Mirrors ``ControlIntent.expansion_text`` without importing the backend model,
    so the harness stays usable when only the fixtures are present.
    """
    parts = [intent.get("azure_restatement", "")]
    parts.extend(intent.get("azure_services") or [])
    parts.extend(intent.get("security_features") or [])
    return " ".join(p.strip() for p in parts if p and p.strip())


def query_expanded(control: dict, intents: Dict[str, dict]) -> str:
    """The runtime query after LLM expansion: original text plus Azure vocabulary."""
    base = query_realistic(control)
    expansion = expansion_text(intents.get(control["control_id"], {}))
    return f"{base} {expansion}".strip() if expansion else base


def hybrid_rank(
    catalog,
    control: dict,
    intents: Dict[str, dict],
    query_vectors,
    depth: int,
    rrf_k: int = 60,
) -> List[str]:
    """Reproduce ``PolicyCatalogService`` hybrid retrieval offline.

    Fuses the service's own lexical ranking with a dense ranking computed from
    the shipped catalog embeddings and the frozen query embedding, using the same
    Reciprocal Rank Fusion the service uses. This lets CI assert the measured
    recall of the *shipped* configuration without any network calls.
    """
    import numpy as np

    query = query_expanded(control, intents)
    lexical = [c.name.lower() for c in catalog.search(query, top_n=depth, semantic=False)]

    vector = query_vectors[control["control_id"]]
    vector = vector / (np.linalg.norm(vector) or 1.0)
    sims = catalog.embedding_matrix @ vector
    limit = min(depth, sims.shape[0])
    head = np.argpartition(-sims, limit - 1)[:limit]
    dense = [
        catalog.definition_name_at(int(i)).lower() for i in head[np.argsort(-sims[head])]
    ]

    scores: Dict[str, float] = {}
    for ranking in (lexical, dense):
        for rank, name in enumerate(ranking):
            scores[name] = scores.get(name, 0.0) + 1.0 / (rrf_k + rank + 1)
    return [name for name, _ in sorted(scores.items(), key=lambda kv: -kv[1])][:depth]


def main() -> int:
    """Print the recall table for the shipped catalog. Run manually."""
    os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
    os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
    os.environ.setdefault("ENABLE_AUTH", "false")

    from app.services.policy_catalog_service import get_policy_catalog_service

    catalog = get_policy_catalog_service()
    gold = load_gold()
    controls = controls_with_policies(gold)
    search = catalog_search(catalog)
    known = lambda guid: catalog.get(guid) is not None  # noqa: E731

    print(f"catalog: {catalog.count} definitions ({catalog.source})")
    print(f"gold: {len(controls)} controls carrying policy GUIDs\n")

    for label, query_fn in (
        ("REALISTIC (control name + description + domain)", QUERY_REALISTIC),
        ("WITH GUIDANCE (leaks expert restatement - upper bound only)", QUERY_WITH_GUIDANCE),
    ):
        report = measure_recall(search, controls, query_fn=query_fn, known=known)
        print(report.format_table(label))
        print(f"  unretrievable (absent from catalog): {report.unretrievable}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
