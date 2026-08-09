"""Defender for Cloud recommendations must never be invented (B4).

``ControlMapping.defender_recommendations`` is filled by Azure OpenAI
structured output purely because the field exists on the schema - the mapping
prompt never asks for it, and there is no live Defender for Cloud subscription
to check against at mapping time (mapping happens per-control, at
framework-analysis time, before any Azure scope is chosen). Whatever the model
returned there was therefore always invented, and it reached customers via
every exported initiative and manual register. See docs/BACKLOG.md B4.
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

import asyncio
from types import SimpleNamespace

import pytest

from app.models.control import ExternalControl
from app.models.mapping import ControlMapping
from app.services.ai_mapping_service import AIMappingService
from app.services.control_classification_service import unknown_classification
from app.services.sovereignty_service import get_sovereignty_service


def test_strip_clears_an_invented_recommendation():
    mapping = SimpleNamespace(defender_recommendations=["Enable MFA for all users"])
    AIMappingService._strip_ungrounded_defender_recommendations(mapping)
    assert mapping.defender_recommendations == []


def test_strip_is_a_no_op_when_already_empty():
    mapping = SimpleNamespace(defender_recommendations=[])
    AIMappingService._strip_ungrounded_defender_recommendations(mapping)
    assert mapping.defender_recommendations == []


def test_fallback_mapping_never_carries_a_recommendation():
    """The engine-failure path already returns an empty list; lock it."""
    control = ExternalControl(
        control_id="1.1",
        control_name="Encrypt data at rest",
        description="All customer data must be encrypted at rest.",
    )
    mapping = AIMappingService._create_fallback_mapping(
        object.__new__(AIMappingService), control, "boom"
    )
    assert mapping.defender_recommendations == []


def test_map_control_discards_a_recommendation_the_model_invented(monkeypatch):
    """End to end through map_control, with only the model call mocked.

    If the model insists on inventing a Defender recommendation - which is
    exactly what happened before this fix, since nothing prompts it not to -
    the service must still return an empty list to the caller.
    """
    svc = object.__new__(AIMappingService)
    svc.catalog = None
    svc.mcsb_service = SimpleNamespace(
        get_controls_for_external_control=lambda *a, **k: []
    )
    svc.control_classification = SimpleNamespace(
        classify=lambda *a, **k: _async_return(unknown_classification())
    )
    svc.sovereignty_service = get_sovereignty_service()

    async def fake_search_azure_policies(*args, **kwargs):
        return ""

    def fake_sovereignty_context(*args, **kwargs):
        return ""

    svc._search_azure_policies = fake_search_azure_policies
    svc._get_sovereignty_context = fake_sovereignty_context

    invented = ControlMapping(
        external_control_id="AC-1",
        external_control_name="Access control",
        mcsb_control_id="IM-1",
        mcsb_control_name="Protect identities",
        mcsb_domain="Identity",
        confidence_score=0.9,
        reasoning="Relevant",
        mapping_type="exact",
        defender_recommendations=["Enable MFA for all users"],
    )
    svc._request_mapping = lambda external_control, user_prompt: invented

    control = ExternalControl(
        control_id="AC-1",
        control_name="Access control",
        description="Enforce access control.",
    )

    result = asyncio.run(svc.map_control(control))

    assert result.defender_recommendations == []


def _async_return(value):
    async def _coro():
        return value

    return _coro()


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
