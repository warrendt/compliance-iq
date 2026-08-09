"""SO-2 has no Azure Policy, and that is not the same as being uncovered.

The sovereignty policy search skips procedural objectives, correctly - they have
no policies to return. The consequence was that a control about Microsoft
support personnel accessing customer data got no sovereignty linkage at all,
because SO-2 was filtered out before matching and no policy could stand in.

For a sovereign customer that is close to the whole question. The analyst
workbook records it precisely: "SO.2 Operator access: no policy - addressed by
enabling Customer Lockbox." Reporting "no policy" without naming the feature
turns a solved requirement into an apparent gap.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pytest  # noqa: E402

from app.services.sovereignty_service import get_sovereignty_service  # noqa: E402


@pytest.fixture(scope="module")
def service():
    svc = get_sovereignty_service()
    return svc


def test_so2_is_marked_procedural_and_names_its_feature(service):
    objectives = service.get_all_objectives()
    so2 = objectives["SO-2"]
    assert so2.procedural_only is True
    assert "Customer Lockbox" in so2.named_feature


def test_only_so2_is_procedural(service):
    """A regression lock. If another objective becomes procedural the product
    must name its feature too, not inherit SO-2's."""
    procedural = [
        o.id for o in service.get_all_objectives().values() if o.procedural_only
    ]
    assert procedural == ["SO-2"]


def test_every_procedural_objective_names_a_feature(service):
    """The rule, not the instance: a procedural objective with no named feature
    is exactly the unexplained gap this exists to prevent."""
    for obj in service.get_all_objectives().values():
        if obj.procedural_only:
            assert obj.named_feature.strip(), obj.id


def test_an_operator_access_control_matches_so2(service):
    matched = service.procedural_objectives_for_control(
        control_description=(
            "Microsoft support personnel must not access customer data without "
            "documented customer approval."
        ),
        control_domain="Access Control",
    )
    assert [o.id for o in matched] == ["SO-2"]


def test_a_lockbox_control_matches_so2(service):
    matched = service.procedural_objectives_for_control(
        control_description="Customer Lockbox requests must be reviewed and approved.",
    )
    assert [o.id for o in matched] == ["SO-2"]


def test_an_unrelated_control_matches_nothing(service):
    """Attaching Customer Lockbox to an encryption control would be noise
    dressed as sovereignty analysis."""
    matched = service.procedural_objectives_for_control(
        control_description="Data at rest must be encrypted with customer-managed keys.",
        control_domain="Data Protection",
    )
    assert matched == []


def test_the_policy_search_still_returns_no_policies_for_so2(service):
    """The filter that caused the omission is correct and stays: SO-2 genuinely
    has no policies. The fix is to report the objective, not to invent one."""
    policies = service.get_relevant_policies_for_control(
        control_description="Customer Lockbox approval for support access",
    )
    for p in policies:
        assert "SO-2" not in p.sovereignty_objectives


def test_the_mapping_names_the_feature_as_the_outside_step():
    """End to end through the enrichment hook, without a model call."""
    from types import SimpleNamespace

    from app.services.ai_mapping_service import AIMappingService

    svc = AIMappingService.__new__(AIMappingService)
    svc.sovereignty_service = get_sovereignty_service()

    mapping = SimpleNamespace(
        outside_step=None,
        sovereignty=SimpleNamespace(sovereignty_objectives=[]),
    )
    control = SimpleNamespace(
        description="Microsoft support access to customer data requires approval.",
        domain="Access Control",
    )

    svc._apply_procedural_sovereignty(mapping, control)

    assert "Customer Lockbox" in mapping.outside_step
    assert "SO-2" in mapping.sovereignty.sovereignty_objectives


def test_a_step_the_classifier_already_named_is_not_overwritten():
    """The classifier read the control text; this saw only keywords. It
    supplements rather than overrides."""
    from types import SimpleNamespace

    from app.services.ai_mapping_service import AIMappingService

    svc = AIMappingService.__new__(AIMappingService)
    svc.sovereignty_service = get_sovereignty_service()

    mapping = SimpleNamespace(
        outside_step="Documented support-access approval procedure",
        sovereignty=SimpleNamespace(sovereignty_objectives=[]),
    )
    control = SimpleNamespace(
        description="Support access to customer data requires customer approval.",
        domain="Access Control",
    )

    svc._apply_procedural_sovereignty(mapping, control)

    assert mapping.outside_step == "Documented support-access approval procedure"
    # The objective is still recorded even though the step was left alone.
    assert "SO-2" in mapping.sovereignty.sovereignty_objectives


def test_an_unrelated_control_is_left_completely_alone():
    from types import SimpleNamespace

    from app.services.ai_mapping_service import AIMappingService

    svc = AIMappingService.__new__(AIMappingService)
    svc.sovereignty_service = get_sovereignty_service()

    mapping = SimpleNamespace(
        outside_step=None,
        sovereignty=SimpleNamespace(sovereignty_objectives=["SO-3"]),
    )
    control = SimpleNamespace(
        description="Storage accounts must use customer-managed keys.",
        domain="Data Protection",
    )

    svc._apply_procedural_sovereignty(mapping, control)

    assert mapping.outside_step is None
    assert mapping.sovereignty.sovereignty_objectives == ["SO-3"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
