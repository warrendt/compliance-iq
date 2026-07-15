"""
Unit tests for the generated MCSB dataset and the MCSBService loader.

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_mcsb_dataset.py -q -p no:cacheprovider
"""

import pytest

from app.models import MCSBControl
from app.services.mcsb_service import MCSBService
from scripts.generate_mcsb_dataset import (
    build_controls,
    control_id_from_group,
    domain_prefix,
    parse_initiative,
    split_lines,
)


# --- Committed runtime dataset (loaded via the service) ----------------------


@pytest.fixture(scope="module")
def service() -> MCSBService:
    svc = MCSBService()
    svc.load_controls()
    return svc


class TestGeneratedDataset:
    def test_loads_full_control_set(self, service):
        controls = service.get_all_controls()
        assert len(controls) >= 90  # real MCSB = 92, not the 9-control fallback

    def test_path_is_resolved_absolutely(self, service):
        # A relative configured path must be resolved so loading is CWD-independent.
        assert service.data_path.endswith("app/data/mcsb/mcsb_v1_controls.json")

    def test_every_control_validates_and_has_text(self, service):
        for ctrl in service.get_all_controls():
            assert isinstance(ctrl, MCSBControl)
            assert ctrl.control_name.strip()
            assert ctrl.description.strip()
            assert ctrl.description.upper() != "N/A"

    def test_dp5_carries_customer_managed_key_policy_guids(self, service):
        dp5 = service._controls_by_id["DP-5"]
        assert dp5.domain == "Data Protection"
        # "Storage accounts should use customer-managed key for encryption".
        assert "6fac406b-40ca-413b-bf8e-0bf964659c25" in dp5.azure_policy_ids

    def test_domain_prefixes_map_to_long_names(self, service):
        by_id = service._controls_by_id
        assert by_id["IM-1"].domain == "Identity Management"
        assert by_id["NS-1"].domain == "Network Security"
        assert by_id["AI-1"].domain == "AI Security"

    def test_ai_domain_present(self, service):
        domains = {c.domain for c in service.get_all_controls()}
        assert "AI Security" in domains

    def test_governance_controls_have_no_fabricated_guids(self, service):
        # GS controls are strategy/process controls; they legitimately map to no
        # Azure Policy. Assert the dataset preserves that rather than inventing GUIDs.
        gs1 = service._controls_by_id["GS-1"]
        assert gs1.azure_policy_ids == []
        assert gs1.description.strip() and gs1.description.upper() != "N/A"


class TestFallbackBehaviour:
    def test_missing_dataset_falls_back_to_minimal_set(self, caplog):
        svc = MCSBService(data_path="/nonexistent/mcsb.json")
        with caplog.at_level("ERROR"):
            svc.load_controls()
        controls = svc.get_all_controls()
        # A small, clearly-degraded set - not the full 92-control dataset.
        assert 0 < len(controls) < 20
        assert "IM-1" in {c.control_id for c in controls}
        assert any("fallback" in r.message.lower() for r in caplog.records)


# --- Pure generator helpers (no network / files) ----------------------------


class TestGeneratorHelpers:
    def test_control_id_extraction(self):
        assert control_id_from_group("Azure_Security_Benchmark_v3.0_DP-5") == "DP-5"
        assert control_id_from_group("Azure_Security_Benchmark_v3.0_AI-7") == "AI-7"
        assert control_id_from_group("no-control-here") is None

    def test_domain_prefix(self):
        assert domain_prefix("DP-5") == "DP"
        assert domain_prefix("AI-1") == "AI"

    def test_split_lines_drops_blanks(self):
        assert split_lines("a\n\n b \nc") == ["a", "b", "c"]
        assert split_lines(None) == []

    def test_parse_initiative_aggregates_guids_per_control(self):
        initiative = {
            "properties": {
                "policyDefinitionGroups": [
                    {"name": "Azure_Security_Benchmark_v3.0_DP-5"},
                    {"name": "Azure_Security_Benchmark_v3.0_GS-1"},
                ],
                "policyDefinitions": [
                    {"policyDefinitionId": "/x/guid-a",
                     "groupNames": ["Azure_Security_Benchmark_v3.0_DP-5"]},
                    {"policyDefinitionId": "/x/guid-b",
                     "groupNames": ["Azure_Security_Benchmark_v3.0_DP-5"]},
                ],
            }
        }
        ids, guids = parse_initiative(initiative)
        assert ids == ["DP-5", "GS-1"]
        assert guids["DP-5"] == ["guid-a", "guid-b"]
        assert "GS-1" not in guids  # no policies -> absent (no fabricated GUIDs)

    def test_build_controls_prefers_arm_then_xlsx(self):
        controls, missing = build_controls(
            control_ids=["DP-5"],
            guids_by_control={"DP-5": ["guid-a"]},
            text_by_control={"DP-5": {"control_name": "xlsx name",
                                      "description": "xlsx desc",
                                      "defender_recommendations": ["rec"],
                                      "related_frameworks": {"CIS v8": ["3.11"]}}},
            domain_names={"DP": "Data Protection"},
            arm_by_control={"DP-5": {"control_name": "arm name",
                                     "description": "arm desc", "domain": "Data Protection"}},
        )
        assert missing == []
        control = controls[0]
        assert control["control_name"] == "arm name"  # ARM wins when present
        assert control["description"] == "arm desc"
        assert control["azure_policy_ids"] == ["guid-a"]
        assert control["related_frameworks"] == {"CIS v8": ["3.11"]}

    def test_build_controls_flags_missing_text_with_placeholder(self):
        controls, missing = build_controls(
            control_ids=["ZZ-9"],
            guids_by_control={},
            text_by_control={},
            domain_names={},
            arm_by_control={},
        )
        assert missing == ["ZZ-9"]
        assert controls[0]["control_name"] == "Microsoft cloud security benchmark ZZ-9"
        assert controls[0]["description"] == ""  # never fabricated
