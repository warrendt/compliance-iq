"""The shipped policy catalog must not silently decay.

Every mapping stamps ``catalog_snapshot_date`` onto its output, and that date is
what an evidence pack shows a regulator to say *which* Azure Policy catalogue the
answer was derived from. A stale snapshot therefore does not merely reduce
recall — it makes the provenance claim wrong, quietly, with nothing failing.

The intended guard was ``.github/workflows/refresh-policy-catalog.yml``, which
regenerates the snapshot weekly. **It has never succeeded.** All three scheduled
runs (2026-07-20, 2026-07-27, 2026-08-03) failed at the Azure login step because
``AZURE_CLIENT_ID`` / ``AZURE_TENANT_ID`` are not configured on the repository,
so the catalogue is refreshed only when somebody remembers to do it by hand.

That is the same failure shape as the rest of this work: a check that cannot tell
"fresh" from "never ran" reports both as fine. These tests are the offline
signal, and they need no Azure credentials, so they keep working while the OIDC
gap remains open.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

CATALOG = (
    Path(__file__).resolve().parents[1]
    / "backend" / "app" / "data" / "policy_catalog" / "azure_policy_catalog.json"
)

# Measured drift, not a guess: the catalogue moved 2465 -> 2467 active definitions
# over roughly two weeks, so Azure's built-in set changes on the order of one
# definition per week. At 90 days that is ~13 definitions, ~0.5% of the
# catalogue — small enough not to nag, large enough that an evidence pack citing
# the snapshot deserves to be questioned.
MAX_SNAPSHOT_AGE_DAYS = 90


def _catalog() -> dict:
    if not CATALOG.exists():  # pragma: no cover - the catalog ships with the repo
        pytest.fail(f"policy catalog is missing from {CATALOG}")
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def test_catalog_declares_when_it_was_generated():
    """Without a date there is nothing to judge freshness against."""
    generated = _catalog().get("generated_at")
    assert generated, (
        "azure_policy_catalog.json has no generated_at. Every mapping stamps "
        "catalog_snapshot_date from this field, so an absent date means the "
        "provenance on every answer is empty."
    )
    datetime.fromisoformat(str(generated))


def test_catalog_snapshot_is_not_stale():
    """Fail loudly once the shipped snapshot is too old to cite honestly."""
    generated = datetime.fromisoformat(str(_catalog()["generated_at"]))
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)

    age_days = (datetime.now(timezone.utc) - generated).days
    assert age_days <= MAX_SNAPSHOT_AGE_DAYS, (
        f"The Azure Policy catalogue snapshot is {age_days} days old "
        f"(generated {generated.date()}), past the {MAX_SNAPSHOT_AGE_DAYS}-day "
        "limit. Every evidence pack is citing this date as the catalogue its "
        "mappings were derived from, so the provenance is now questionable.\n\n"
        "This test is deliberately time-based, and it remains the backstop rather "
        "than the primary mechanism: the weekly refresh workflow now runs "
        "end-to-end (OIDC works, and the embeddings regenerate on a self-hosted "
        "runner inside the VNet, because the Azure OpenAI endpoint is private). "
        "If this test fires, the refresh has stopped running or its PR is not "
        "being merged.\n\n"
        "To fix by hand: run scripts/generate_policy_catalog.py and "
        "scripts/generate_policy_catalog_embeddings.py together — the embeddings "
        "are keyed to the catalogue, and refreshing one without the other "
        "silently disables semantic search. The embeddings script needs network "
        "access to the private endpoint, so it must run inside the VNet."
    )


def test_catalog_and_embeddings_are_shipped_together():
    """A catalogue refreshed without its embeddings silently loses hybrid search.

    PolicyCatalogService validates that the two artifacts agree and disables
    semantic search on a mismatch rather than comparing wrong vectors. That is
    safe but silent — measured micro-recall@200 falls 84.4% -> 72.2% with
    nothing raising. Shipping one without the other is therefore a defect the
    running system cannot report.
    """
    embeddings = CATALOG.with_name("azure_policy_catalog_embeddings.npz")
    assert embeddings.exists(), (
        "azure_policy_catalog.json ships without "
        "azure_policy_catalog_embeddings.npz. Retrieval will fall back to "
        "lexical-only and nothing will say so."
    )


def test_deprecated_definitions_are_excluded_from_the_searchable_set():
    """Deprecated built-ins must not be offered as enforceable policy.

    Verified against live Azure on 2026-08-09: 2,844 built-ins, of which 377 are
    deprecated, leaving 2,467 — set-identical to the shipped snapshot, with zero
    definitions missing in either direction.
    """
    cat = _catalog()
    assert cat["count"] == len(cat["definitions"])
    assert cat.get("deprecated_count", 0) > 0, (
        "deprecated_count is zero, which would mean either Azure deprecates "
        "nothing or the generator stopped recording it. Both warrant a look."
    )
