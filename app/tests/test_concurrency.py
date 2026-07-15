"""
Unit tests for real concurrency in batch mapping (fix #6).

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_concurrency.py -q -p no:cacheprovider --noconftest
"""

import asyncio

import pytest

from app.services.ai_mapping_service import AIMappingService
from app.models import ControlMapping, ExternalControl


def _ctrl(cid: str) -> ExternalControl:
    return ExternalControl(
        control_id=cid, control_name=f"name-{cid}",
        description=f"desc-{cid}", domain="Identity",
    )


def _good(cid: str, confidence: float = 0.8) -> ControlMapping:
    return ControlMapping(
        external_control_id=cid, external_control_name=f"name-{cid}",
        mcsb_control_id="IM-6", mcsb_control_name="MFA", mcsb_domain="Identity Management",
        confidence_score=confidence, reasoning="ok",
        azure_policy_ids=[], mapping_type="exact",
    )


def _service_with(map_control):
    svc = AIMappingService.__new__(AIMappingService)
    svc.map_control = map_control  # type: ignore[assignment]
    return svc


@pytest.mark.asyncio
async def test_semaphore_bounds_concurrency():
    in_flight = 0
    max_in_flight = 0

    async def stub(control):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return _good(control.control_id)

    svc = _service_with(stub)
    controls = [_ctrl(f"C{i}") for i in range(6)]
    await svc.map_controls_batch(controls, concurrency=2)
    assert max_in_flight <= 2


@pytest.mark.asyncio
async def test_higher_concurrency_runs_more_in_parallel():
    in_flight = 0
    max_in_flight = 0

    async def stub(control):
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return _good(control.control_id)

    svc = _service_with(stub)
    controls = [_ctrl(f"C{i}") for i in range(6)]
    await svc.map_controls_batch(controls, concurrency=5)
    assert max_in_flight >= 4  # genuinely parallel, not sequential


@pytest.mark.asyncio
async def test_order_preserved_despite_completion_order():
    delays = {"C0": 0.03, "C1": 0.02, "C2": 0.005}

    async def stub(control):
        await asyncio.sleep(delays[control.control_id])
        return _good(control.control_id)

    svc = _service_with(stub)
    controls = [_ctrl("C0"), _ctrl("C1"), _ctrl("C2")]
    batch = await svc.map_controls_batch(controls, concurrency=3)
    # C2 finishes first, C0 last, but output order matches input order.
    assert [m.external_control_id for m in batch.mappings] == ["C0", "C1", "C2"]


@pytest.mark.asyncio
async def test_progress_is_monotonic_and_reaches_total():
    seen = []

    async def stub(control):
        await asyncio.sleep(0.005)
        return _good(control.control_id)

    def progress(done, total):
        seen.append((done, total))

    svc = _service_with(stub)
    controls = [_ctrl(f"C{i}") for i in range(5)]
    await svc.map_controls_batch(controls, progress_callback=progress, concurrency=3)
    assert seen == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]


@pytest.mark.asyncio
async def test_concurrent_batch_separates_failures_in_order():
    async def stub(control):
        await asyncio.sleep(0.005)
        if control.control_id == "BAD":
            raise RuntimeError("kaboom")
        return _good(control.control_id, 0.7)

    svc = _service_with(stub)
    controls = [_ctrl("A"), _ctrl("BAD"), _ctrl("B")]
    batch = await svc.map_controls_batch(controls, concurrency=3)
    assert [m.external_control_id for m in batch.mappings] == ["A", "B"]
    assert batch.unmapped_controls == ["BAD"]
    assert batch.mapped_count == 2


@pytest.mark.asyncio
async def test_concurrency_floor_of_one():
    async def stub(control):
        return _good(control.control_id)

    svc = _service_with(stub)
    batch = await svc.map_controls_batch([_ctrl("A")], concurrency=0)
    assert batch.mapped_count == 1  # clamped to >=1, no ValueError from Semaphore
