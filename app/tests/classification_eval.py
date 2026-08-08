"""Measure coverage-classification accuracy against the NCSP v2.0 gold mapping.

Requirement 2 of the mapping rework is the claim that the engine can tell a
policy-enforceable control from an operational one. That claim is only worth
anything if it is measured, so this module scores the blind classification stage
against the expert-built gold workbook's own category assignments.

Two modes:

* **Live** — calls the classification service for every gold control. Needs Azure
  OpenAI credentials, so it is opt-in (``run_live``) and never runs in CI.
* **Frozen** — replays ``app/tests/fixtures/ncsp_v2_classifications.json``, a
  captured set of live results, so the measured numbers are reproducible offline
  and regressions in the *scoring* logic are caught even without credentials.

The gold split is deliberately lopsided (24 A / 21 B / 21 D / 71 C), so plain
accuracy flatters a classifier that guesses ``C_Process`` for everything: that
alone scores 51.8%. The metric that matters is therefore the per-class recall and
above all the **enforceable/not-enforceable confusion**, because attaching a
policy to a governance control is the failure the user actually cares about.
"""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
GOLD_PATH = FIXTURE_DIR / "ncsp_v2_gold_mapping.json"
FROZEN_PATH = FIXTURE_DIR / "ncsp_v2_classifications.json"

CATEGORIES = ("A_AzurePolicy", "B_AzureConfig", "C_Process", "D_MicrosoftAttestation")

# Categories for which the engine is allowed to attach Azure Policy IDs.
ENFORCEABLE = frozenset({"A_AzurePolicy", "B_AzureConfig"})


def load_gold() -> List[dict]:
    """The 137 gold controls, each carrying the expert's coverage category."""
    with GOLD_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)["controls"]


def load_frozen() -> Dict[str, dict]:
    """Captured live classifications keyed by control_id, or ``{}`` if absent."""
    if not FROZEN_PATH.exists():
        return {}
    with FROZEN_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)["classifications"]


def confusion_matrix(
    gold: Sequence[dict], predictions: Dict[str, str]
) -> Dict[str, Counter]:
    """Map gold category -> Counter of predicted categories.

    Controls with no prediction are skipped rather than counted as wrong: an
    absent prediction means the stage was not run for that control, which is a
    coverage question, not an accuracy one.
    """
    matrix: Dict[str, Counter] = {c: Counter() for c in CATEGORIES}
    for control in gold:
        predicted = predictions.get(control["control_id"])
        if not predicted:
            continue
        matrix.setdefault(control["coverage_category"], Counter())[predicted] += 1
    return matrix


def accuracy(matrix: Dict[str, Counter]) -> float:
    """Exact 4-class agreement with the expert."""
    total = sum(sum(row.values()) for row in matrix.values())
    if not total:
        return 0.0
    correct = sum(row.get(gold_cat, 0) for gold_cat, row in matrix.items())
    return correct / total


def per_class_recall(matrix: Dict[str, Counter]) -> Dict[str, float]:
    """Fraction of each gold category the classifier recovered."""
    recalls = {}
    for gold_cat, row in matrix.items():
        total = sum(row.values())
        recalls[gold_cat] = (row.get(gold_cat, 0) / total) if total else 0.0
    return recalls


def enforceability_confusion(matrix: Dict[str, Counter]) -> Dict[str, int]:
    """Collapse to the binary decision that drives whether retrieval runs.

    ``false_enforceable`` is the damaging error: a control the expert says no
    Azure Policy can assert, which the engine would nonetheless try to map,
    producing exactly the false confidence this rework exists to remove.
    """
    counts = {
        "true_enforceable": 0,
        "true_manual": 0,
        "false_enforceable": 0,
        "false_manual": 0,
    }
    for gold_cat, row in matrix.items():
        gold_enforceable = gold_cat in ENFORCEABLE
        for predicted, n in row.items():
            predicted_enforceable = predicted in ENFORCEABLE
            if gold_enforceable and predicted_enforceable:
                counts["true_enforceable"] += n
            elif not gold_enforceable and not predicted_enforceable:
                counts["true_manual"] += n
            elif predicted_enforceable:
                counts["false_enforceable"] += n
            else:
                counts["false_manual"] += n
    return counts


def scope_accuracy(matrix: Dict[str, Counter]) -> float:
    """Accuracy once ``A`` and ``B`` are collapsed into one "in scope" class.

    This is the metric that matches the architecture. The blind stage decides
    whether a control is in scope for Azure enforcement; whether a built-in
    definition actually exists — the A/B split — is a fact about the catalog that
    ``coverage.resolve_coverage`` settles *after* retrieval. Scoring the blind
    stage on the A/B split therefore penalises it for a judgement it is not
    making and, measurably, cannot make: it recovered 4% of gold ``A`` controls
    while correctly keeping 84% of them in scope.
    """
    total = sum(sum(row.values()) for row in matrix.values())
    if not total:
        return 0.0

    def bucket(category: str) -> str:
        return "AB" if category in ENFORCEABLE else category

    correct = 0
    for gold_cat, row in matrix.items():
        for predicted, n in row.items():
            if bucket(gold_cat) == bucket(predicted):
                correct += n
    return correct / total


def majority_baseline(gold: Sequence[dict]) -> float:
    """Accuracy of always predicting the most common gold category.

    The bar any classifier must clear to have earned its LLM call.
    """
    counts = Counter(c["coverage_category"] for c in gold)
    return max(counts.values()) / sum(counts.values()) if counts else 0.0


def run_live(
    gold: Sequence[dict],
    service=None,
    limit: Optional[int] = None,
    concurrency: int = 8,
) -> Dict[str, dict]:
    """Classify gold controls with the real service. Requires credentials."""
    if service is None:
        from app.services.control_classification_service import (
            get_control_classification_service,
        )

        service = get_control_classification_service()

    subset = list(gold)[: limit or len(gold)]

    async def _run() -> Dict[str, dict]:
        semaphore = asyncio.Semaphore(concurrency)

        async def classify_one(control: dict):
            async with semaphore:
                result = await service.classify(
                    control["control_name"],
                    control["description"],
                    control.get("domain", ""),
                )
            return control["control_id"], {
                "coverage_category": result.coverage_category,
                "responsibility": result.responsibility,
                "reason": result.reason,
                "evidence_source": result.evidence_source,
            }

        pairs = await asyncio.gather(*(classify_one(c) for c in subset))
        return dict(pairs)

    return asyncio.run(_run())


def report(matrix: Dict[str, Counter]) -> str:
    """Render the confusion matrix and headline metrics as text."""
    lines = ["gold \\ predicted".ljust(26) + "".join(c.ljust(24) for c in CATEGORIES)]
    for gold_cat in CATEGORIES:
        row = matrix.get(gold_cat, Counter())
        cells = "".join(str(row.get(c, 0)).ljust(24) for c in CATEGORIES)
        lines.append(gold_cat.ljust(26) + cells)
    lines.append("")
    lines.append(f"accuracy (4-class): {accuracy(matrix):.1%}")
    lines.append(f"accuracy (A/B collapsed): {scope_accuracy(matrix):.1%}")
    for cat, recall in per_class_recall(matrix).items():
        lines.append(f"  recall {cat}: {recall:.1%}")
    lines.append(f"enforceability: {enforceability_confusion(matrix)}")
    return "\n".join(lines)
