"""Tests for the MCSB download bundle: it must include a README documenting the
audit-only deploy order (set-definition -> assignment w/ identity -> Defender
standard), the Defender CSPM prerequisite, and the System Policy auto-exclusion.
"""

import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.api.routes.policy import _mcsb_version_payload
from app.models import ControlMapping, PolicyGenerationRequest


def _request() -> PolicyGenerationRequest:
    return PolicyGenerationRequest(
        framework_name="UAE National Cloud Security Policy",
        mappings=[
            ControlMapping(
                external_control_id="2.3.2.1",
                external_control_name="Control 2.3.2.1",
                mcsb_control_id="IM-1",
                mcsb_control_name="Protect identities",
                mcsb_domain="Identity",
                confidence_score=0.9,
                reasoning="Relevant",
                azure_policy_ids=["18adea5e-f416-4d0f-8aa8-d24321e3e274"],
                mapping_type="exact",
            )
        ],
    )


def _payload(standard=None) -> dict:
    return _mcsb_version_payload(
        request=_request(),
        initiative_id="init-1",
        initiative_json={"properties": {}},
        bicep_template="// bicep",
        scripts={"powershell": "# ps", "cli": "# cli"},
        standard=standard,
    )


def _readme(payload: dict) -> str:
    files = {f["name"]: f["content"] for f in payload["files"]}
    assert "README.md" in files
    return files["README.md"]


def test_bundle_includes_readme():
    assert "README.md" in {f["name"] for f in _payload()["files"]}


def test_readme_documents_three_step_order_with_standard():
    standard = {"arm_template": "{}", "powershell": "# std"}
    readme = _readme(_payload(standard=standard))
    assert "Policy set definition" in readme
    assert "Assignment" in readme
    assert "system-assigned managed identity" in readme
    assert "securityStandards" in readme
    assert "Defender CSPM" in readme


def test_readme_documents_system_policy_exclusion():
    readme = _readme(_payload())
    assert "System Policy" in readme
    assert "excluded_builtin_policies" in readme


def test_readme_omits_standard_steps_when_no_standard():
    readme = _readme(_payload(standard=None))
    # Steps 1 and 2 always present; the Defender step only with a standard.
    assert "Policy set definition" in readme
    assert "securityStandards" not in readme
