"""A failed mapping write must not be audited as a completed mapping run.

``record_mappings`` previously computed its audit count as
``written or len(mappings)``. The fallback is silent and unconditional, so a run
whose every persistence write failed still produced the audit line
*"Mapped 200 controls from 'ADHICS'"* and still bumped the user's lifetime
``mappingCount`` by 200 — for a run that stored nothing at all.

That is the same collapse as the empty-extraction defect, moved into the
compliance record: a failure state that renders identically to success. It
matters more here, because the audit log is the artifact a customer shows when
asked to prove what the system did.

Found while watching a live ADHICS run, where ``ensure_container`` was warning
``Failed to ensure container mapping-results: 'path'`` on every job.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import activity_service


def _mappings(n: int):
    return [
        {"controlId": f"AC-{i}", "controlName": f"Control {i}", "confidence": 0.8}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_failed_writes_are_not_audited_as_a_successful_run():
    """Every write failing must be visible in the audit summary."""
    cosmos = MagicMock()
    cosmos.database = MagicMock()
    cosmos.MAPPING_RESULTS = "mapping-results"
    cosmos.ensure_container = AsyncMock()
    cosmos.upsert_document = AsyncMock(side_effect=RuntimeError("container missing"))

    audit = AsyncMock()
    with patch.object(activity_service, "cosmos_client", cosmos), \
         patch.object(activity_service.audit_service, "write_audit", audit), \
         patch.object(activity_service, "_bump_profile", AsyncMock()) as bump:
        written = await activity_service.record_mappings(
            "dev@example.com", framework="ADHICS", mappings=_mappings(200),
        )

    assert written == 0
    meta = audit.await_args.kwargs["metadata"]

    assert meta["persistedCount"] == 0, "the audit must record what was stored"
    assert "WARNING" in meta["summary"], (
        "A run that stored nothing produced the summary "
        f"{meta['summary']!r}, which reads as a completed mapping run. "
        "The discrepancy has to appear in the summary a reviewer actually reads."
    )
    assert "only 0 of 200" in meta["summary"]

    # The lifetime stat must not outrun the retrievable records.
    bump.assert_awaited_once()
    assert bump.await_args.args[2] == 0


@pytest.mark.asyncio
async def test_a_fully_successful_run_is_unchanged():
    """The honest path must not acquire a warning it does not deserve."""
    cosmos = MagicMock()
    cosmos.database = MagicMock()
    cosmos.MAPPING_RESULTS = "mapping-results"
    cosmos.ensure_container = AsyncMock()
    cosmos.upsert_document = AsyncMock()

    audit = AsyncMock()
    with patch.object(activity_service, "cosmos_client", cosmos), \
         patch.object(activity_service.audit_service, "write_audit", audit), \
         patch.object(activity_service, "_bump_profile", AsyncMock()) as bump:
        written = await activity_service.record_mappings(
            "dev@example.com", framework="ADHICS", mappings=_mappings(5),
        )

    assert written == 5
    meta = audit.await_args.kwargs["metadata"]
    assert meta["controlCount"] == 5
    assert meta["persistedCount"] == 5
    assert "WARNING" not in meta["summary"]
    assert bump.await_args.args[2] == 5


@pytest.mark.asyncio
async def test_partial_writes_report_the_shortfall():
    """Storing some but not all is still an incomplete record, and says so."""
    cosmos = MagicMock()
    cosmos.database = MagicMock()
    cosmos.MAPPING_RESULTS = "mapping-results"
    cosmos.ensure_container = AsyncMock()
    cosmos.upsert_document = AsyncMock(
        side_effect=[None, None, RuntimeError("throttled")]
    )

    audit = AsyncMock()
    with patch.object(activity_service, "cosmos_client", cosmos), \
         patch.object(activity_service.audit_service, "write_audit", audit), \
         patch.object(activity_service, "_bump_profile", AsyncMock()):
        written = await activity_service.record_mappings(
            "dev@example.com", framework="ADHICS", mappings=_mappings(3),
        )

    assert written == 2
    meta = audit.await_args.kwargs["metadata"]
    assert meta["controlCount"] == 3
    assert meta["persistedCount"] == 2
    assert "only 2 of 3" in meta["summary"]


@pytest.mark.asyncio
async def test_no_database_is_not_reported_as_a_persistence_failure():
    """Never attempting to store is different from trying and failing.

    Reporting them identically would train a reviewer to ignore the warning in
    local development, where there is no Cosmos account at all.
    """
    cosmos = MagicMock()
    cosmos.database = None

    audit = AsyncMock()
    with patch.object(activity_service, "cosmos_client", cosmos), \
         patch.object(activity_service.audit_service, "write_audit", audit), \
         patch.object(activity_service, "_bump_profile", AsyncMock()):
        written = await activity_service.record_mappings(
            "dev@example.com", framework="ADHICS", mappings=_mappings(4),
        )

    assert written == 0
    meta = audit.await_args.kwargs["metadata"]
    assert meta["persistenceAttempted"] is False
    assert "WARNING" not in meta["summary"]
    assert meta["controlCount"] == 4
