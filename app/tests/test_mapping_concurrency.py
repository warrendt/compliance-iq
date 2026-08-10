"""Regression tests for quota-safe concurrent AI mapping."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks

from app.api.routes import mapping
from app.models import ControlMapping, ExternalControl, MappingRequest
from app.services.ai_mapping_service import AIMappingService


def _control(index: int) -> ExternalControl:
    return ExternalControl(
        control_id=f"C-{index}",
        control_name=f"Control {index}",
        description="Test control",
    )


def _mapping(control: ExternalControl) -> ControlMapping:
    return ControlMapping(
        external_control_id=control.control_id,
        external_control_name=control.control_name,
        confidence_score=0.8,
        reasoning="Test mapping",
        mapping_type="partial",
    )


@pytest.mark.asyncio
async def test_mapping_batch_respects_the_requested_concurrency():
    """Mapping workers must overlap, but never exceed the supplied bound."""
    service = object.__new__(AIMappingService)
    active_workers = 0
    maximum_active_workers = 0
    progress_updates = []

    async def map_control(control: ExternalControl) -> ControlMapping:
        nonlocal active_workers, maximum_active_workers
        active_workers += 1
        maximum_active_workers = max(maximum_active_workers, active_workers)
        await asyncio.sleep(0.01)
        active_workers -= 1
        return _mapping(control)

    service.map_control = map_control
    result = await service.map_controls_batch(
        [_control(index) for index in range(4)],
        lambda current, _total: progress_updates.append(current),
        concurrency=2,
    )

    assert result.mapped_count == 4
    assert maximum_active_workers == 2
    assert sorted(progress_updates) == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_mapping_job_caps_requested_workers_to_configured_limit(monkeypatch):
    """The durable job route must not let a client exceed the safe quota cap."""
    mapping.mapping_jobs.clear()
    monkeypatch.setattr(mapping, "_persist_job", AsyncMock())

    background_tasks = BackgroundTasks()
    request = MappingRequest(
        framework_name="Framework",
        controls=[_control(1)],
        concurrency=10,
    )

    await mapping.analyze_controls(request, background_tasks)

    task = background_tasks.tasks[-1]
    assert task.func is mapping.process_mapping_job
    assert task.args[2] == 10
