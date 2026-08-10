"""The pipeline mapper must reach the whole catalog, and say what it cannot do.

These tests exist because ``policy_mapper.py`` used to carry a hand-written menu
of 34 policy GUIDs - six of which were not real - and asked the model to recall
identifiers from memory. Against ~2,467 shipped definitions that is a reach of
1.38%, on the path that Page 8 Diff Compare and the skill CLI both use to
produce downloadable, deployable artifacts.

Every assertion here is about a **rule**, never a count. The counts in any one
framework are a property of that document; the rules hold for all of them.
"""

import asyncio
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.pipeline import policy_mapper  # noqa: E402
from app.pipeline.models import (  # noqa: E402
    ControlExtractionResult,
    ExtractedControl,
)
from app.services import coverage  # noqa: E402

REAL_GUID = "404c3081-a854-4457-ae30-26a93ef643f9"
OTHER_GUID = "7595c971-233d-4bcf-bd18-596129188c49"

# A GUID that appears nowhere in the deleted 34-entry menu. If mappings can only
# ever contain menu entries, the menu is back.
OFF_MENU_GUID = "1a5b4dca-0b6f-4cf5-907c-56316bc1bf3d"


# -- Doubles ------------------------------------------------------------------

class _FakeCatalog:
    """Stands in for the shipped policy catalog."""

    def __init__(self, definitions=None, available=True, count=2467):
        self._definitions = definitions or {
            REAL_GUID: {
                "display_name": "Secure transfer to storage accounts should be enabled",
                "description": "Audit requirement of Secure transfer in your storage account.",
            },
            OFF_MENU_GUID: {
                "display_name": "Storage accounts should restrict network access",
                "description": "Network access to storage accounts should be restricted.",
            },
        }
        self._available = available
        self._count = count

    def get(self, name):
        return self._definitions.get(name)

    @property
    def available(self):
        return self._available

    @property
    def count(self):
        return self._count

    def exists(self, name):
        return name in self._definitions


class _FakeMapping:
    """Duck-typed services ``ControlMapping``."""

    def __init__(self, control_id, **kwargs):
        self.external_control_id = control_id
        self.external_control_name = kwargs.get("name", f"Control {control_id}")
        self.policy_category = kwargs.get("policy_category", "Data Protection")
        self.confidence_score = kwargs.get("confidence", 0.9)
        self.reasoning = kwargs.get("reasoning", "Relevant control")
        self.azure_policy_ids = kwargs.get("policy_ids", [])
        self.defender_recommendations = kwargs.get("defender", [])
        self.coverage_category = kwargs.get("category")
        self.coverage_display = kwargs.get("display")
        self.coverage_reason = kwargs.get("reason")
        self.azure_enforceable = kwargs.get("enforceable", False)
        self.coverage_gap = kwargs.get("gap", False)
        self.outside_step = kwargs.get("outside_step")
        self.responsibility = kwargs.get("responsibility")
        self.enforcement_plane = kwargs.get("plane")
        self.policy_effects = kwargs.get("effects", [])
        self.available_effects = kwargs.get("available_effects", [])
        self.policy_type = kwargs.get("policy_type")
        self.evidence_source = kwargs.get("evidence")
        self.attestation = kwargs.get("attestation")
        self.attestation_gap = kwargs.get("attestation_gap", False)
        self.dropped_policy_ids = kwargs.get("dropped", [])


class _FakeBatch:
    def __init__(self, mappings):
        self.mappings = mappings
        self.unmapped_controls = []


class _FakeService:
    """Records what it was asked to map, and by whom."""

    def __init__(self, mappings, record=None):
        self._mappings = mappings
        self.record = record if record is not None else {}

    async def map_controls_batch(self, controls, progress_callback=None, concurrency=1):
        self.record["controls"] = list(controls)
        self.record["concurrency"] = concurrency
        if progress_callback:
            progress_callback(len(controls), len(controls))
        return _FakeBatch(self._mappings)


def _control(control_id, **kwargs):
    return ExtractedControl(
        control_id=control_id,
        control_title=kwargs.get("title", f"Control {control_id}"),
        control_description=kwargs.get("description", "A requirement."),
        domain=kwargs.get("domain", "Data Protection"),
        control_type=kwargs.get("control_type", "Technical"),
        sub_controls=kwargs.get("sub_controls", []),
    )


def _extraction(controls):
    return ControlExtractionResult(
        framework_name="Test Framework",
        controls=controls,
        summary="A test framework.",
    )


def _config(batch_size=5):
    return types.SimpleNamespace(batch_size=batch_size)


def _install(monkeypatch, mappings, catalog=None, record=None):
    catalog = catalog or _FakeCatalog()
    service = _FakeService(mappings, record=record)
    monkeypatch.setattr(
        "app.services.ai_mapping_service.get_ai_mapping_service",
        lambda: service,
    )
    monkeypatch.setattr(
        "app.services.policy_catalog_service.get_policy_catalog_service",
        lambda: catalog,
    )
    return service, catalog


# -- The menu is gone ---------------------------------------------------------

def test_the_hardcoded_guid_menu_is_gone():
    """The module must contain no policy GUID literals at all.

    A menu is not a bug that can be partly fixed. Any GUID hardcoded here is
    either a candidate the model is steered towards or an answer it is handed,
    and both cap the reachable catalog. The engine gets its identifiers from
    retrieval over the catalog snapshot, so this file needs none.
    """
    import re

    source = Path(policy_mapper.__file__).read_text(encoding="utf-8")
    guids = re.findall(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        source,
    )
    assert guids == [], f"policy GUIDs are hardcoded again: {guids}"


def test_the_mapper_makes_no_model_call_of_its_own(monkeypatch):
    """All model work goes through the shared engine.

    A second prompt in this module would mean a second taxonomy, a second set
    of validation rules, and two answers to the same question that drift apart.
    """
    source = Path(policy_mapper.__file__).read_text(encoding="utf-8")
    assert "chat.completions" not in source
    assert "SYSTEM_PROMPT" not in source


def test_mappings_can_carry_identifiers_from_outside_the_old_menu(monkeypatch):
    """The whole catalog must be reachable, not a curated shortlist."""
    _install(monkeypatch, [
        _FakeMapping("C-1", policy_ids=[OFF_MENU_GUID], category=coverage.COVERAGE_A,
                     enforceable=True),
    ])

    results = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1")]), _config()
    )

    assert [p.policy_definition_id for p in results[0].azure_policies] == [OFF_MENU_GUID]


# -- Names are catalog facts --------------------------------------------------

def test_policy_names_are_read_from_the_catalog_not_authored(monkeypatch):
    """The old prompt let the model supply the display name alongside the GUID,
    so a name could describe something the identifier did not do. Names and
    descriptions are catalog facts; they are read."""
    _install(monkeypatch, [
        _FakeMapping("C-1", policy_ids=[REAL_GUID], category=coverage.COVERAGE_A,
                     enforceable=True),
    ])

    results = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1")]), _config()
    )
    policy = results[0].azure_policies[0]

    assert policy.policy_name == "Secure transfer to storage accounts should be enabled"
    assert "Secure transfer" in policy.policy_description


def test_an_identifier_absent_from_the_catalog_still_reports_its_id(monkeypatch):
    """Falling back to the GUID is better than inventing a name for it."""
    _install(monkeypatch, [
        _FakeMapping("C-1", policy_ids=[OTHER_GUID], category=coverage.COVERAGE_A,
                     enforceable=True),
    ])

    results = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1")]), _config()
    )
    policy = results[0].azure_policies[0]

    assert policy.policy_definition_id == OTHER_GUID
    assert policy.policy_name == OTHER_GUID


# -- The taxonomy reaches the pipeline ----------------------------------------

def test_the_coverage_taxonomy_survives_the_conversion(monkeypatch):
    """Page 8 and the skill CLI produced initiatives with no statement of what
    Azure cannot do, because none of the taxonomy existed on this path."""
    _install(monkeypatch, [
        _FakeMapping(
            "C-1",
            policy_ids=[REAL_GUID],
            category=coverage.COVERAGE_B,
            display="Azure/Entra config - partial",
            reason="Covered in part by policy; complete with Conditional Access.",
            enforceable=True,
            outside_step="A Conditional Access policy requiring compliant devices",
            responsibility="Customer",
            plane="Azure Policy + Entra ID",
            effects=["Audit"],
            available_effects=["Audit", "Deny"],
            policy_type="Built-in",
            evidence="Azure Policy compliance state",
        ),
    ])

    result = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1")]), _config()
    )[0]

    assert result.coverage_category == coverage.COVERAGE_B
    assert result.coverage_display == "Azure/Entra config - partial"
    assert result.outside_step.startswith("A Conditional Access policy")
    assert result.responsibility == "Customer"
    assert result.available_effects == ["Audit", "Deny"]
    assert result.evidence_source == "Azure Policy compliance state"


def test_a_partial_control_keeps_its_policies_and_names_its_outside_step(monkeypatch):
    """B is 'partial', not 'unenforceable'. Stripping its policies deleted a
    whole class of the deliverable."""
    _install(monkeypatch, [
        _FakeMapping("C-1", policy_ids=[REAL_GUID], category=coverage.COVERAGE_B,
                     enforceable=True, outside_step="Enable Customer Lockbox"),
    ])

    result = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1")]), _config()
    )[0]

    assert result.azure_policies
    assert result.is_automatable is True
    assert "Customer Lockbox" in result.manual_attestation_note


def test_a_process_control_carries_its_reason_into_the_manual_note(monkeypatch):
    """C and D never enter the initiative, so the note is the whole answer."""
    _install(monkeypatch, [
        _FakeMapping("C-1", category=coverage.COVERAGE_C,
                     reason="Requires a documented incident response procedure."),
    ])

    result = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1", control_type="Governance")]), _config()
    )[0]

    assert result.azure_policies == []
    assert result.is_automatable is False
    assert "incident response procedure" in result.manual_attestation_note


def test_an_attested_control_carries_its_citation(monkeypatch):
    """The citation is what the customer hands to the auditor."""
    _install(monkeypatch, [
        _FakeMapping(
            "C-1",
            category=coverage.COVERAGE_D,
            reason="Microsoft attests this.",
            attestation={
                "status": "grounded",
                "citation": "ISO/IEC 27001:2022 clause 9.2 (Internal audit)",
                "evidence_location": "https://servicetrust.microsoft.com",
                "access_condition": "No NDA required",
            },
        ),
    ])

    result = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1", control_type="Governance")]), _config()
    )[0]

    assert result.attestation["citation"].startswith("ISO/IEC 27001:2022 clause 9.2")
    assert result.attestation_gap is False


def test_an_ungrounded_attestation_arrives_as_a_gap(monkeypatch):
    """A sovereign requirement Microsoft does not attest must not be absorbed
    into a generic pass on this path either."""
    _install(monkeypatch, [
        _FakeMapping("C-1", category=coverage.COVERAGE_D, attestation_gap=True,
                     attestation={"status": "unattested",
                                  "reason": "no attestation covers UAE clearance"}),
    ])

    result = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1", control_type="Governance")]), _config()
    )[0]

    assert result.attestation_gap is True


def test_rejected_identifiers_survive_the_conversion(monkeypatch):
    """The workbook's mistyped `17k78e20-...` was silently dropped in
    transcription. Whatever validation rejects has to arrive here."""
    _install(monkeypatch, [
        _FakeMapping("C-1", category=coverage.COVERAGE_A, enforceable=True,
                     policy_ids=[REAL_GUID],
                     dropped=[{"policy_id": "17k78e20-9358-41c9-923c-fb736d382a12",
                               "reason": "malformed"}]),
    ])

    result = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1")]), _config()
    )[0]

    assert result.dropped_policy_ids[0]["policy_id"].startswith("17k78e20")
    assert result.dropped_policy_ids[0]["reason"] == "malformed"


# -- Nothing is dropped -------------------------------------------------------

def test_a_control_the_engine_could_not_map_is_reported_not_omitted(monkeypatch):
    """Omitting it shortens the output and makes the run look cleaner while
    removing a control the customer is legally bound by."""
    _install(monkeypatch, [_FakeMapping("C-1", category=coverage.COVERAGE_A,
                                        enforceable=True, policy_ids=[REAL_GUID])])

    results = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1"), _control("C-2")]), _config()
    )

    assert [r.control_id for r in results] == ["C-1", "C-2"]
    unmapped = results[1]
    assert unmapped.coverage_gap is True
    assert unmapped.confidence_score == 0.0
    assert unmapped.azure_policies == []
    assert "could not process" in unmapped.mapping_rationale


def test_output_order_follows_the_extracted_controls(monkeypatch):
    """The register is read alongside the regulation, so it keeps its order."""
    _install(monkeypatch, [
        _FakeMapping("C-3", category=coverage.COVERAGE_C),
        _FakeMapping("C-1", category=coverage.COVERAGE_C),
        _FakeMapping("C-2", category=coverage.COVERAGE_C),
    ])

    results = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1"), _control("C-2"), _control("C-3")]), _config()
    )

    assert [r.control_id for r in results] == ["C-1", "C-2", "C-3"]


def test_an_unavailable_catalog_fails_loudly(monkeypatch):
    """Every mapping would come back empty and be reported as a gap. That is
    honest but useless, and looks like a framework Azure cannot help with."""
    _install(monkeypatch, [], catalog=_FakeCatalog(available=False))

    with pytest.raises(RuntimeError, match="catalog is unavailable"):
        policy_mapper.map_controls_to_azure_policies(
            _extraction([_control("C-1")]), _config()
        )


def test_no_controls_is_not_an_error(monkeypatch):
    _install(monkeypatch, [])
    assert policy_mapper.map_controls_to_azure_policies(_extraction([]), _config()) == []


# -- Conversion ---------------------------------------------------------------

def test_sub_controls_reach_the_engine_as_requirements(monkeypatch):
    """Sub-controls are usually where the testable requirement actually is;
    dropping them costs retrieval its best signal."""
    record = {}
    _install(monkeypatch, [_FakeMapping("C-1", category=coverage.COVERAGE_C)],
             record=record)

    policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1", sub_controls=["Encrypt in transit",
                                                   "Rotate keys annually"])]),
        _config(),
    )

    assert record["controls"][0].requirements == "Encrypt in transit; Rotate keys annually"


def test_batch_size_is_reused_as_concurrency(monkeypatch):
    """Mapping is per-control now, so the old batch size has no other meaning -
    but silently serialising every run would make the 14-PDF sweep unusable."""
    record = {}
    _install(monkeypatch, [_FakeMapping("C-1", category=coverage.COVERAGE_C)],
             record=record)

    policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1")]), _config(batch_size=8)
    )

    assert record["concurrency"] == 8


def test_progress_is_reported(monkeypatch):
    seen = []
    _install(monkeypatch, [_FakeMapping("C-1", category=coverage.COVERAGE_C)])

    policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1")]), _config(),
        progress_callback=lambda current, total: seen.append((current, total)),
    )

    assert seen == [(1, 1)]


# -- Loop safety --------------------------------------------------------------

def test_it_runs_from_a_thread_with_no_loop(monkeypatch):
    """``pipeline.py`` calls this from a background task."""
    _install(monkeypatch, [_FakeMapping("C-1", category=coverage.COVERAGE_C)])

    results = policy_mapper.map_controls_to_azure_policies(
        _extraction([_control("C-1")]), _config()
    )
    assert len(results) == 1


def test_it_runs_from_inside_a_running_loop(monkeypatch):
    """``comparison.py`` calls it via ``asyncio.to_thread`` from a live request.
    Assuming that thread never has a loop is how an intermittent 'this event
    loop is already running' appears months later."""
    _install(monkeypatch, [_FakeMapping("C-1", category=coverage.COVERAGE_C)])

    async def driver():
        # Deliberately call the sync function directly on the loop thread,
        # which is the worst case the helper has to survive.
        return policy_mapper.map_controls_to_azure_policies(
            _extraction([_control("C-1")]), _config()
        )

    results = asyncio.run(driver())
    assert len(results) == 1


def test_an_error_inside_the_loop_helper_reaches_the_caller(monkeypatch):
    """Swallowing it would produce an empty mapping set that looks like a
    framework with no Azure coverage."""
    class _Exploding:
        async def map_controls_batch(self, *args, **kwargs):
            raise ValueError("Azure OpenAI is unreachable")

    monkeypatch.setattr(
        "app.services.ai_mapping_service.get_ai_mapping_service", lambda: _Exploding()
    )
    monkeypatch.setattr(
        "app.services.policy_catalog_service.get_policy_catalog_service",
        lambda: _FakeCatalog(),
    )

    async def driver():
        return policy_mapper.map_controls_to_azure_policies(
            _extraction([_control("C-1")]), _config()
        )

    with pytest.raises(ValueError, match="unreachable"):
        asyncio.run(driver())
