"""
Unit tests for honest failure accounting in batch mapping (fix #5).

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_failure_accounting.py -q -p no:cacheprovider --noconftest
"""

import pytest

import app.services.ai_mapping_service as ai
from app.services.ai_mapping_service import AIMappingService
from app.models import ControlMapping, ExternalControl


def _ctrl(cid: str) -> ExternalControl:
    return ExternalControl(
        control_id=cid, control_name=f"name-{cid}",
        description=f"desc-{cid}", domain="Identity",
    )


def _good(cid: str, confidence: float) -> ControlMapping:
    return ControlMapping(
        external_control_id=cid, external_control_name=f"name-{cid}",
        mcsb_control_id="IM-6", mcsb_control_name="MFA", mcsb_domain="Identity Management",
        confidence_score=confidence, reasoning="ok",
        azure_policy_ids=[], mapping_type="exact",
    )


def _service_with(map_control):
    """Build a bare service instance whose map_control is a supplied stub."""
    svc = AIMappingService.__new__(AIMappingService)
    svc.map_control = map_control  # type: ignore[assignment]
    return svc


def test_fallback_mapping_is_flagged():
    svc = AIMappingService.__new__(AIMappingService)
    fallback = svc._create_fallback_mapping(_ctrl("C1"), "boom")
    assert fallback.mapping_failed is True
    assert fallback.mcsb_control_id == "N/A"
    assert fallback.confidence_score == 0.0
    assert fallback.mapping_type == "none"


@pytest.mark.asyncio
async def test_fallback_counts_as_unmapped_not_mapped():
    async def stub(control):
        if control.control_id == "FAIL":
            return AIMappingService._create_fallback_mapping(
                AIMappingService.__new__(AIMappingService), control, "boom")
        return _good(control.control_id, 0.9)

    svc = _service_with(stub)
    batch = await svc.map_controls_batch([_ctrl("OK"), _ctrl("FAIL")])

    assert batch.mapped_count == 1
    assert batch.unmapped_controls == ["FAIL"]
    assert [m.external_control_id for m in batch.mappings] == ["OK"]
    # avg is over the single success, not dragged down by the 0.0 fallback
    assert batch.avg_confidence == pytest.approx(0.9)
    assert batch.total_controls == 2


@pytest.mark.asyncio
async def test_raised_exception_counts_as_unmapped():
    async def stub(control):
        if control.control_id == "BOOM":
            raise RuntimeError("kaboom")
        return _good(control.control_id, 0.8)

    svc = _service_with(stub)
    batch = await svc.map_controls_batch([_ctrl("OK"), _ctrl("BOOM")])

    assert batch.mapped_count == 1
    assert batch.unmapped_controls == ["BOOM"]
    assert batch.avg_confidence == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_all_success_reports_no_failures():
    async def stub(control):
        return _good(control.control_id, 0.6)

    svc = _service_with(stub)
    batch = await svc.map_controls_batch([_ctrl("A"), _ctrl("B")])

    assert batch.mapped_count == 2
    assert batch.unmapped_controls == []
    assert batch.avg_confidence == pytest.approx(0.6)


@pytest.mark.asyncio
async def test_progress_callback_counts_every_control():
    seen = []

    async def stub(control):
        if control.control_id == "FAIL":
            return AIMappingService._create_fallback_mapping(
                AIMappingService.__new__(AIMappingService), control, "boom")
        return _good(control.control_id, 0.5)

    def progress(done, total):
        seen.append((done, total))

    svc = _service_with(stub)
    await svc.map_controls_batch([_ctrl("OK"), _ctrl("FAIL")], progress_callback=progress)

    assert seen == [(1, 2), (2, 2)]  # progress advances for failures too
