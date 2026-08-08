"""Tests for the gold mapping fixture and the retrieval recall harness.

Split into two groups:

* **Fixture integrity** — fast, no catalog needed. Guards the shape and the
  distributions of ``fixtures/ncsp_v2_gold_mapping.json``, and asserts that no
  customer identity leaked into the committed file.
* **Recall baseline** — exercises the real 2465-definition catalog against the
  gold mapping. Pins the *measured* recall of each retrieval stage so a change
  that silently regresses recall fails here rather than in production.

Measured on the bundled catalog snapshot (``generated_at 2026-07-23``,
``count 2465``), micro-recall of the expert's policy GUIDs:

    retrieval                              @15     @40    @200    @500
    lexical, raw control text (original) 15.6%   23.3%   46.7%   60.0%
    lexical, expanded query              32.2%   45.6%   72.2%   86.7%
    hybrid,  expanded query (shipped)    38.9%   55.6%   84.4%   92.2%

Two independent changes produce that: restating the control in Azure vocabulary
before retrieval, and fusing a dense ranking with the lexical one. Neither is
window size — lexical retrieval on raw control text tops out at 73.3% even when
the *entire* catalog is scanned, so widening the candidate window could never
have fixed this.

The expanded-query and hybrid rows are reproduced offline from frozen fixtures
(``ncsp_v2_control_intents.json``, ``ncsp_v2_query_embeddings.npz``) captured by
``scripts/generate_retrieval_eval_fixture.py``, so CI needs no Azure OpenAI
credentials. See ``mapping_recall`` for why the ``how_to_meet`` column must not
be used as a query.
"""

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mapping_recall import (  # noqa: E402
    FIXTURE_PATH,
    QUERY_REALISTIC,
    QUERY_WITH_GUIDANCE,
    catalog_search,
    controls_with_policies,
    hybrid_rank,
    load_gold,
    load_intents,
    load_query_vectors,
    measure_recall,
    query_expanded,
)

# Distribution of the expert's four coverage categories over the 137 NCSP
# controls. Only 24/137 (17.5%) are directly Azure-Policy enforceable, which is
# the central fact the mapping engine has to reproduce.
EXPECTED_COVERAGE_COUNTS = {
    "A_AzurePolicy": 24,
    "B_AzureConfig": 21,
    "D_MicrosoftAttestation": 21,
    "C_Process": 71,
}

# Two gold rows carry no Reason text (2.7.3.2, 3.3.1.4). Verified against the
# source workbook 2026-08-08: this is a gap in the expert's sheet, not an
# extraction bug. Pinned so the fixture regenerating with *more* gaps fails.
EXPECTED_CONTROL_COUNT = 137
EXPECTED_CONTROLS_WITH_POLICIES = 41
EXPECTED_DISTINCT_GUIDS = 44

# Two gold rows carry no Reason text. Verified against the source workbook
# 2026-08-08: a gap in the expert's sheet, not an extraction bug.
CONTROLS_WITHOUT_REASON = {"2.7.3.2", "3.3.1.4"}


@pytest.fixture(scope="module")
def gold():
    return load_gold()


# ── Fixture integrity ────────────────────────────────────────────────────────


def test_fixture_exists_and_has_expected_control_count(gold):
    assert gold["control_count"] == EXPECTED_CONTROL_COUNT
    assert len(gold["controls"]) == EXPECTED_CONTROL_COUNT


def test_coverage_distribution_matches_the_expert_workbook(gold):
    counts = {}
    for control in gold["controls"]:
        counts[control["coverage_category"]] = counts.get(control["coverage_category"], 0) + 1
    assert counts == EXPECTED_COVERAGE_COUNTS


def test_most_controls_are_not_azure_policy_enforceable(gold):
    """The headline finding: 69% of real controls cannot be asserted by policy."""
    non_enforceable = sum(
        1 for c in gold["controls"] if c["coverage_category"] != "A_AzurePolicy"
    )
    assert non_enforceable / len(gold["controls"]) > 0.8


def test_only_enforceable_categories_carry_policy_guids(gold):
    """C_Process and D_MicrosoftAttestation must never carry a policy GUID."""
    for control in gold["controls"]:
        if control["coverage_category"] in {"C_Process", "D_MicrosoftAttestation"}:
            assert not control["policy_definition_ids"], (
                f"{control['control_id']} is {control['coverage_category']} "
                "but carries policy GUIDs"
            )


def test_policy_guid_counts(gold):
    with_policies = controls_with_policies(gold)
    assert len(with_policies) == EXPECTED_CONTROLS_WITH_POLICIES
    distinct = {g for c in with_policies for g in c["policy_definition_ids"]}
    assert len(distinct) == EXPECTED_DISTINCT_GUIDS


def test_guids_are_normalised_lowercase(gold):
    for control in gold["controls"]:
        for guid in control["policy_definition_ids"]:
            assert guid == guid.lower()
            assert len(guid) == 36


def test_responsibility_is_neutralised(gold):
    """No customer trading name may be committed to the repo."""
    values = {c["responsibility"] for c in gold["controls"]}
    assert values == {"Customer", "Microsoft"}
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    assert "e&" not in raw
    assert "E&" not in raw


def test_fixture_is_ascii_only(gold):
    """cp1252 smart quotes and dashes are folded, keeping diffs stable."""
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    assert all(ord(ch) < 128 for ch in raw)


def test_every_control_has_a_reason(gold):
    """The Reason column is the reasoning quality bar; it must be populated.

    Two rows in the source workbook are genuinely blank (verified against the
    workbook 2026-08-08). They are pinned so that a regeneration introducing
    *further* gaps fails here.
    """
    missing = {c["control_id"] for c in gold["controls"] if not c["reason"].strip()}
    assert missing == CONTROLS_WITHOUT_REASON, f"unexpected reason gaps: {missing}"


def test_coverage_definitions_carry_all_four_categories(gold):
    assert set(gold["coverage_definitions"]) == set(EXPECTED_COVERAGE_COUNTS)
    for text in gold["coverage_definitions"].values():
        assert len(text) > 40, "legend definitions ground the classifier prompt"


def test_enforcement_plane_vocabulary_is_closed(gold):
    allowed = {
        "SLZ (deploy-time)",
        "Defender (run-time)",
        "SLZ (deploy-time) + Defender (run-time)",
        "None (manual control)",
    }
    assert {c["enforcement_plane"] for c in gold["controls"]} <= allowed


def test_effects_are_empty_exactly_when_plane_is_manual(gold):
    for control in gold["controls"]:
        manual = control["enforcement_plane"] == "None (manual control)"
        assert manual == (not control["effects"]), control["control_id"]


# ── Recall baseline against the real catalog ─────────────────────────────────


@pytest.fixture(scope="module")
def catalog():
    from app.services.policy_catalog_service import get_policy_catalog_service

    service = get_policy_catalog_service()
    if service.count == 0:
        pytest.skip("policy catalog snapshot unavailable")
    return service


def test_all_gold_guids_exist_in_the_shipped_catalog(gold, catalog):
    """Retrieval misses are ranking failures, not catalog-staleness failures."""
    missing = sorted(
        {
            guid
            for control in controls_with_policies(gold)
            for guid in control["policy_definition_ids"]
            if catalog.get(guid) is None
        }
    )
    assert not missing, f"gold GUIDs absent from the catalog snapshot: {missing}"


def test_lexical_baseline_on_raw_control_text_is_poor(gold, catalog):
    """Pins the original defect, and the reason the pipeline was reworked.

    Lexical retrieval on the control's own words — the shipped behaviour before
    query expansion and semantic fusion — sees a small minority of the expert's
    policies. Asserted as a *ceiling* so that if someone ever "fixes" retrieval
    by only widening the window, this test still shows why that is not enough.
    """
    report = measure_recall(
        catalog_search(catalog, semantic=False),
        controls_with_policies(gold),
        query_fn=QUERY_REALISTIC,
        depths=(15, 50, 200),
        known=lambda guid: catalog.get(guid) is not None,
    )
    assert report.micro_recall(15) < 0.25, report.format_table("lexical, raw text")
    assert report.micro_recall(200) < 0.60, report.format_table("lexical, raw text")


def test_widening_the_window_cannot_reach_acceptable_recall(gold, catalog):
    """Scanning the whole catalog still misses a quarter of the gold policies.

    This is the argument for changing the *query* rather than the window size.
    """
    report = measure_recall(
        catalog_search(catalog),
        controls_with_policies(gold),
        query_fn=QUERY_REALISTIC,
        depths=(2465,),
        known=lambda guid: catalog.get(guid) is not None,
    )
    assert report.micro_recall(2465) < 0.80, report.format_table("realistic ceiling")


def test_expert_vocabulary_lifts_recall_dramatically(gold, catalog):
    """Query wording, not window size, is the lever.

    Substituting the expert's Azure-vocabulary restatement of the control lifts
    recall at the *shipped* window far above the realistic query at any window.
    This is the target LLM query expansion is aiming at.
    """
    controls = controls_with_policies(gold)
    known = lambda guid: catalog.get(guid) is not None  # noqa: E731
    search = catalog_search(catalog)

    realistic = measure_recall(search, controls, QUERY_REALISTIC, (15,), known)
    guided = measure_recall(search, controls, QUERY_WITH_GUIDANCE, (15,), known)

    assert guided.micro_recall(15) > realistic.micro_recall(15) * 2.5, (
        f"realistic@15={realistic.micro_recall(15):.3f} "
        f"guided@15={guided.micro_recall(15):.3f}"
    )


def test_recall_report_denominator_excludes_unretrievable_guids(gold, catalog):
    """The metric measures ranking, not catalog coverage."""
    report = measure_recall(
        catalog_search(catalog),
        controls_with_policies(gold),
        depths=(15,),
        known=lambda guid: False,
    )
    assert report.pair_count == 0
    assert report.unretrievable == 90
    assert report.micro_recall(15) == 0.0


# ---------------------------------------------------------------------------
# The shipped retrieval pipeline, reproduced offline
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def intents():
    return load_intents()


@pytest.fixture(scope="module")
def query_vectors():
    return load_query_vectors()


def test_catalog_ships_a_semantic_index(catalog):
    """The embedding artifact must be present, aligned and normalised.

    Without it, retrieval silently falls back to lexical-only, which measured
    72.2% recall@200 instead of 84.4% — a regression that would otherwise only
    show up as worse mappings in production.
    """
    import numpy as np

    matrix = catalog.embedding_matrix
    assert matrix is not None, (
        "no catalog embeddings loaded; run "
        "scripts/generate_policy_catalog_embeddings.py"
    )
    assert matrix.shape[0] == catalog.count
    norms = np.linalg.norm(matrix, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-2), "catalog vectors are not L2-normalised"


def test_expansion_fixture_covers_every_gold_control(gold, intents, query_vectors):
    """The offline fixtures must not drift out of sync with the gold set."""
    expected = {c["control_id"] for c in controls_with_policies(gold)}
    assert set(intents) == expected
    assert set(query_vectors) == expected


def test_query_expansion_roughly_doubles_lexical_recall(gold, catalog, intents):
    """Requirement 1, part one: the query, not the window, was the bottleneck.

    Restating the control in Azure vocabulary before retrieval lifted lexical
    micro-recall@200 from 46.7% to 72.2%. Asserted as a floor a little below the
    measured value to absorb catalog churn.
    """
    controls = controls_with_policies(gold)
    known = lambda guid: catalog.get(guid) is not None  # noqa: E731
    search = catalog_search(catalog, semantic=False)

    raw = measure_recall(search, controls, QUERY_REALISTIC, (15, 200), known)
    expanded = measure_recall(
        search, controls, lambda c: query_expanded(c, intents), (15, 200), known
    )

    assert expanded.micro_recall(200) >= 0.65, expanded.format_table("expanded, lexical")
    assert expanded.micro_recall(200) > raw.micro_recall(200) * 1.3, (
        f"raw@200={raw.micro_recall(200):.3f} "
        f"expanded@200={expanded.micro_recall(200):.3f}"
    )


def test_hybrid_retrieval_meets_the_recall_gate(gold, catalog, intents, query_vectors):
    """Requirement 1, part two: the whole catalog is genuinely reachable.

    Reproduces the shipped configuration — LLM-expanded query, hybrid lexical +
    semantic retrieval, RRF fusion — and asserts the recall gate the design was
    accepted against. Measured: 55.6% @40, 84.4% @200, 92.2% @500, against a
    shipped-baseline 15.6% @15.

    Floors sit below the measured values so catalog refreshes do not fail the
    build for noise, but a structural regression (embeddings not loading, fusion
    broken, expansion dropped) fails it immediately.
    """
    controls = controls_with_policies(gold)
    depths = (40, 200, 500)
    report = measure_recall(
        lambda query, top_n: hybrid_rank(
            catalog, _control_for(controls, query), intents, query_vectors, top_n
        ),
        controls,
        query_fn=lambda c: c["control_id"],
        depths=depths,
        known=lambda guid: catalog.get(guid) is not None,
    )
    table = report.format_table("expanded + hybrid")
    assert report.micro_recall(40) >= 0.48, table
    assert report.micro_recall(200) >= 0.75, table
    assert report.micro_recall(500) >= 0.85, table


def test_hybrid_beats_lexical_at_every_useful_depth(
    gold, catalog, intents, query_vectors
):
    """Semantic fusion is what justifies shipping a 2.4 MB embedding artifact."""
    controls = controls_with_policies(gold)
    known = lambda guid: catalog.get(guid) is not None  # noqa: E731

    lexical = measure_recall(
        catalog_search(catalog, semantic=False),
        controls,
        lambda c: query_expanded(c, intents),
        (200, 500),
        known,
    )
    hybrid = measure_recall(
        lambda query, top_n: hybrid_rank(
            catalog, _control_for(controls, query), intents, query_vectors, top_n
        ),
        controls,
        lambda c: c["control_id"],
        (200, 500),
        known,
    )
    for depth in (200, 500):
        assert hybrid.micro_recall(depth) > lexical.micro_recall(depth), (
            f"depth {depth}: lexical={lexical.micro_recall(depth):.3f} "
            f"hybrid={hybrid.micro_recall(depth):.3f}"
        )


def _control_for(controls, control_id: str) -> dict:
    """Resolve a control by id.

    ``measure_recall`` passes a *query string* to the ranker, but hybrid ranking
    needs the whole control (to look up its frozen expansion and embedding), so
    the harness passes the control id as the query and resolves it here.
    """
    for control in controls:
        if control["control_id"] == control_id:
            return control
    raise KeyError(control_id)
