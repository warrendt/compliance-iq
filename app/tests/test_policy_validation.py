"""
Unit tests for policy GUID validation (ARM + offline) and cleaning.

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_policy_validation.py -q -p no:cacheprovider --noconftest
"""

import pytest

import app.services.policy_validation_service as pvs
from app.services.policy_validation_service import (
    PolicyValidationService,
    PolicyValidationAuthError,
    clean_policy_ids,
    load_known_good_guids,
    probe_guid,
    annotate_offline,
    annotate_arm,
)
from app.models import ControlMapping


GOOD = "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"
FAKE = "00000000-0000-0000-0000-000000000000"


@pytest.fixture(autouse=True)
def _clear_existence_cache():
    pvs._existence_cache.clear()
    yield
    pvs._existence_cache.clear()


class _FakeResp:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _RoutedClient:
    """Fake httpx.AsyncClient returning a status per GUID parsed from the URL."""

    def __init__(self, status_by_guid: dict, default: int = 404):
        self._status_by_guid = {k.lower(): v for k, v in status_by_guid.items()}
        self._default = default

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None):
        guid = url.split("/policyDefinitions/")[1].split("?")[0].lower()
        return _FakeResp(self._status_by_guid.get(guid, self._default))


def _patch_client(monkeypatch, status_by_guid, default=404):
    monkeypatch.setattr(
        pvs.httpx, "AsyncClient",
        lambda *a, **k: _RoutedClient(status_by_guid, default),
    )


def _mapping(policy_ids):
    return ControlMapping(
        external_control_id="X", external_control_name="x",
        mcsb_control_id="DP-5", mcsb_control_name="CMK", mcsb_domain="Data Protection",
        confidence_score=0.9, reasoning="r",
        azure_policy_ids=policy_ids, mapping_type="exact",
    )


class TestCleanPolicyIds:
    def test_strips_noise_and_dedupes_case_insensitively(self):
        result = clean_policy_ids(
            ["See documentation", GOOD.upper(), GOOD, "not-a-guid", "", "N/A"])
        assert result == [GOOD.upper()]

    def test_preserves_order(self):
        result = clean_policy_ids([FAKE, GOOD])
        assert result == [FAKE, GOOD]


class TestKnownGood:
    def test_index_loads_and_is_lowercased(self):
        known = load_known_good_guids()
        assert len(known) > 90  # 727 GUIDs from the MCSB initiative
        assert all(g == g.lower() for g in known)

    def test_probe_guid_is_member(self):
        assert probe_guid() in load_known_good_guids()


class TestAnnotateOffline:
    def test_flags_unknown_keeps_known(self):
        known_member = next(iter(sorted(load_known_good_guids())))
        mapping = _mapping([known_member.upper(), FAKE, "See documentation"])
        annotate_offline([mapping])
        assert mapping.azure_policy_ids == [known_member.upper(), FAKE]  # cleaned
        assert mapping.unverified_policy_ids == [FAKE]  # unknown flagged, not dropped
        assert mapping.invalid_policy_ids == []
        assert mapping.policy_validation_mode == "offline"


class TestPolicyDefinitionExists:
    @pytest.mark.asyncio
    async def test_returns_true_on_200(self, monkeypatch):
        _patch_client(monkeypatch, {GOOD: 200})
        svc = PolicyValidationService("token")
        assert await svc.policy_definition_exists(GOOD) is True

    @pytest.mark.asyncio
    async def test_returns_false_on_404(self, monkeypatch):
        _patch_client(monkeypatch, {FAKE: 404})
        svc = PolicyValidationService("token")
        assert await svc.policy_definition_exists(FAKE) is False

    @pytest.mark.asyncio
    async def test_raises_auth_error_on_403(self, monkeypatch):
        _patch_client(monkeypatch, {GOOD: 403})
        svc = PolicyValidationService("token")
        with pytest.raises(PolicyValidationAuthError):
            await svc.policy_definition_exists(GOOD)

    @pytest.mark.asyncio
    async def test_result_is_cached(self, monkeypatch):
        calls = {"n": 0}
        original = _RoutedClient.get

        async def counting_get(self, url, headers=None):
            calls["n"] += 1
            return await original(self, url, headers)

        monkeypatch.setattr(_RoutedClient, "get", counting_get)
        _patch_client(monkeypatch, {GOOD: 200})
        svc = PolicyValidationService("token")
        await svc.policy_definition_exists(GOOD)
        await svc.policy_definition_exists(GOOD.upper())
        assert calls["n"] == 1  # second lookup served from cache


class TestCanValidate:
    @pytest.mark.asyncio
    async def test_true_when_arm_reachable(self, monkeypatch):
        _patch_client(monkeypatch, {probe_guid(): 200})
        ok, _reason = await PolicyValidationService("token").can_validate()
        assert ok is True

    @pytest.mark.asyncio
    async def test_false_when_denied(self, monkeypatch):
        _patch_client(monkeypatch, {probe_guid(): 403})
        ok, reason = await PolicyValidationService("token").can_validate()
        assert ok is False
        assert reason


class TestAnnotateArm:
    @pytest.mark.asyncio
    async def test_keeps_existing_drops_missing(self, monkeypatch):
        _patch_client(monkeypatch, {GOOD: 200, FAKE: 404})
        mapping = _mapping([GOOD, FAKE])
        await annotate_arm([mapping], PolicyValidationService("token"))
        assert mapping.azure_policy_ids == [GOOD]
        assert mapping.invalid_policy_ids == [FAKE]
        assert mapping.unverified_policy_ids == []
        assert mapping.policy_validation_mode == "arm"


class TestApplyValidationOrchestration:
    @pytest.mark.asyncio
    async def test_arm_auth_error_falls_back_to_offline(self, monkeypatch):
        import app.services.ai_mapping_service as ai

        async def boom(mappings, validator):
            raise ai.PolicyValidationAuthError("denied")

        used = {"offline": False}

        def offline_spy(mappings):
            used["offline"] = True
            for m in mappings:
                m.policy_validation_mode = "offline"
            return mappings

        monkeypatch.setattr(ai, "annotate_arm", boom)
        monkeypatch.setattr(ai, "annotate_offline", offline_spy)

        svc = ai.AIMappingService.__new__(ai.AIMappingService)
        mapping = _mapping([GOOD])
        await svc._apply_policy_validation([mapping], validate_guids=True, access_token="t")
        assert used["offline"] is True
        assert mapping.policy_validation_mode == "offline"

    @pytest.mark.asyncio
    async def test_offline_when_validation_disabled(self, monkeypatch):
        import app.services.ai_mapping_service as ai

        async def should_not_run(mappings, validator):  # pragma: no cover
            raise AssertionError("ARM validation must not run when disabled")

        monkeypatch.setattr(ai, "annotate_arm", should_not_run)

        svc = ai.AIMappingService.__new__(ai.AIMappingService)
        mapping = _mapping([GOOD, FAKE])
        await svc._apply_policy_validation([mapping], validate_guids=False, access_token=None)
        assert mapping.policy_validation_mode == "offline"
