"""Tests that well-formed Azure Policy GUIDs which are **not real built-in
policy definitions** are stripped before an initiative is emitted.

Regression for the observed ARM 400/502 ``PolicyDefinitionNotFound`` where an
LLM-hallucinated-but-syntactically-valid GUID (e.g.
``aeedaca3-0f56-429f-945d-8bb66bd06841``) leaked into ``policyDefinitions`` and
failed the entire deployment. Existence is enforced against the shipped Azure
built-in policy catalog (the same corpus the mapper draws candidates from).
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.models import ControlMapping, PolicyGenerationRequest
from app.services.policy_service import PolicyGenerationService

# Real Azure built-in policy definitions (present in the shipped catalog)
REAL_GUID = "18adea5e-f416-4d0f-8aa8-d24321e3e274"
REAL_GUID_2 = "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"
# Well-formed GUID that is NOT a real built-in (the reported failure)
FAKE_GUID = "aeedaca3-0f56-429f-945d-8bb66bd06841"


class _FakeCatalog:
    """Minimal duck-typed stand-in for PolicyCatalogService."""

    def __init__(self, names, available=True):
        self._names = set(names)
        self._available = available

    @property
    def available(self):
        return self._available

    def exists(self, name):
        if not name:
            return False
        segment = name.strip().rstrip("/").rsplit("/", 1)[-1]
        return segment in self._names

    def is_non_includable(self, name):
        return False

    def requires_parameters(self, name):
        return False

    def get(self, name):
        return None

    def get_required_parameters(self, name):
        return {}


def _mapping(control_id: str, policy_ids: list[str], confidence: float = 0.9) -> ControlMapping:
    return ControlMapping(
        external_control_id=control_id,
        external_control_name=f"Control {control_id}",
        mcsb_control_id="IM-1",
        mcsb_control_name="Protect identities",
        mcsb_domain="Identity",
        confidence_score=confidence,
        reasoning="Relevant control",
        azure_policy_ids=policy_ids,
        mapping_type="exact",
    )


# ── _create_policy_definitions (injected catalog) ─────────────────────────────

def test_create_defs_drops_nonexistent_builtin():
    service = PolicyGenerationService()
    catalog = _FakeCatalog([REAL_GUID])
    defs, _groups, dropped, _ni, _pz, _rq = service._create_policy_definitions(
        [_mapping("CTRL-1", [REAL_GUID, FAKE_GUID])], catalog=catalog
    )
    ids = [d.policy_definition_id for d in defs]
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{REAL_GUID}" in ids
    assert all(FAKE_GUID not in pid for pid in ids)
    assert dropped == [FAKE_GUID]


def test_create_defs_keeps_all_when_catalog_unavailable():
    """Graceful degradation: a missing/empty catalog must not drop everything."""
    service = PolicyGenerationService()
    catalog = _FakeCatalog([], available=False)
    defs, _groups, dropped, _ni, _pz, _rq = service._create_policy_definitions(
        [_mapping("CTRL-1", [REAL_GUID, FAKE_GUID])], catalog=catalog
    )
    ids = [d.policy_definition_id for d in defs]
    # Both well-formed GUIDs survive (format-only enforcement)
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{REAL_GUID}" in ids
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{FAKE_GUID}" in ids
    assert dropped == []


def test_create_defs_still_drops_malformed_when_catalog_unavailable():
    service = PolicyGenerationService()
    catalog = _FakeCatalog([], available=False)
    defs, _groups, dropped, _ni, _pz, _rq = service._create_policy_definitions(
        [_mapping("CTRL-1", ["Not A Guid - Azure Policy", REAL_GUID])], catalog=catalog
    )
    assert dropped == ["Not A Guid - Azure Policy"]
    assert len(defs) == 1


# ── generate_initiative against the REAL shipped catalog ──────────────────────

def test_generate_initiative_strips_hallucinated_guid_real_catalog():
    """End-to-end regression using the real catalog + the reported failure GUID."""
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="UAE National Cloud Security Policy",
        mappings=[
            _mapping("2.3.2.1", [REAL_GUID]),
            _mapping("2.7.1.3", [FAKE_GUID]),
        ],
    )

    response = service.generate_initiative(request)

    emitted = [
        pd.policy_definition_id
        for pd in response.initiative.properties.policy_definitions
    ]
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{REAL_GUID}" in emitted
    assert all(FAKE_GUID not in pid for pid in emitted)
    assert response.included_policies == 1
    assert response.invalid_policies == 1
    assert any(FAKE_GUID in w for w in response.warnings)
    assert any("PolicyDefinitionNotFound" in w for w in response.warnings)


def test_generate_initiative_keeps_real_builtins_real_catalog():
    service = PolicyGenerationService()
    request = PolicyGenerationRequest(
        framework_name="Framework",
        mappings=[_mapping("2.3.2.1", [REAL_GUID, REAL_GUID_2])],
    )

    response = service.generate_initiative(request)

    assert response.invalid_policies == 0
    assert response.included_policies == 2


# ── pipeline initiative_builder._build_policies (injected catalog) ────────────

def _pipeline_mapping(control_id: str, policy_ids: list[str]):
    from app.pipeline.models import AzurePolicyMapping, ControlPolicyMapping

    return ControlPolicyMapping(
        control_id=control_id,
        control_title=f"Control {control_id}",
        domain="Identity",
        mcsb_control_id="IM-1",
        mcsb_control_name="Protect identities",
        confidence_score=0.9,
        mapping_rationale="Relevant",
        azure_policies=[
            AzurePolicyMapping(
                policy_definition_id=pid,
                policy_name="p",
                policy_description="d",
                relevance="high",
            )
            for pid in policy_ids
        ],
        is_automatable=True,
    )


def test_build_policies_drops_nonexistent_builtin():
    from app.pipeline.initiative_builder import _build_policies

    catalog = _FakeCatalog([REAL_GUID])
    refs = _build_policies(
        [
            _pipeline_mapping("2.3.2.1", [REAL_GUID]),
            _pipeline_mapping("CTRL-7", [FAKE_GUID]),
        ],
        catalog=catalog,
    )
    ids = [p["PolicyDefinitionId"] for p in refs]
    assert f"/providers/Microsoft.Authorization/policyDefinitions/{REAL_GUID}" in ids
    assert all(FAKE_GUID not in pid for pid in ids)
    assert len(refs) == 1


def test_build_policies_keeps_all_when_catalog_unavailable():
    from app.pipeline.initiative_builder import _build_policies

    catalog = _FakeCatalog([], available=False)
    refs = _build_policies(
        [_pipeline_mapping("CTRL-7", [REAL_GUID, FAKE_GUID])],
        catalog=catalog,
    )
    assert len(refs) == 2


# ── validator.validate_mappings (injected catalog) ────────────────────────────

def test_validator_warns_on_nonexistent_builtin_without_blocking():
    from app.pipeline.validator import validate_mappings
    from app.pipeline.models import ControlExtractionResult, ExtractedControl

    extraction = ControlExtractionResult(
        framework_name="F",
        summary="s",
        controls=[
            ExtractedControl(
                control_id="CTRL-7",
                control_title="t",
                control_description="d",
                domain="Identity",
                control_type="Technical",
            ),
        ],
    )
    mappings = [_pipeline_mapping("CTRL-7", [FAKE_GUID])]
    catalog = _FakeCatalog([REAL_GUID])

    report = validate_mappings(extraction, mappings, catalog=catalog)

    warnings = [i for i in report.issues if i.severity == "warning"]
    assert any("not a real Azure built-in" in i.message for i in warnings)
    # Non-blocking: a bad built-in reference is a warning, not an error
    assert not any(
        "built-in" in i.message and i.severity == "error" for i in report.issues
    )
