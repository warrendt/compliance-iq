"""The acceptance invariants, asserted on both call sites from one input.

The product has two entry points that produce deployable artifacts: the
services path (Pages 1-4, ``AIMappingService`` -> ``coverage.apply_coverage``)
and the pipeline path (Page 8 Diff Compare and the skill CLI,
``pipeline.policy_mapper`` -> ``pipeline.initiative_builder``). The pipeline
path lost the coverage taxonomy once already by reimplementing it rather than
delegating, and the whole class of defect is invisible to any test that
exercises only one side.

So every rule here is driven through **both** paths from the same synthetic
control set, and asserts the same outcome of each. These are rules, never
counts: the analyst workbook is one worked example on one framework, and its
distribution is a property of that document. What must generalise is that no
process or attestation control emits a policy, that nothing is silently
dropped, and that every identifier the product prints can actually be deployed.
"""

import os
import sys
import types
from pathlib import Path

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import pytest  # noqa: E402

from app.services import coverage  # noqa: E402
from app.pipeline import policy_mapper  # noqa: E402
from app.services.policy_catalog_service import get_policy_catalog_service  # noqa: E402

# Real, live built-ins - resolved against the shipped catalog, not invented.
REAL_GUID = "404c3081-a854-4457-ae30-26a93ef643f9"
NON_GUID_BUILTIN = "17k78e20-9358-41c9-923c-fb736d382a12"
INVENTED_GUID = "00000000-0000-0000-0000-000000000000"

POLICY_BEARING = {coverage.COVERAGE_A, coverage.COVERAGE_B}
NON_POLICY_BEARING = {coverage.COVERAGE_C, coverage.COVERAGE_D}


class _Mapping:
    """Duck-typed services ``ControlMapping``, the input to both paths."""

    def __init__(self, control_id, policy_ids=None):
        self.external_control_id = control_id
        self.external_control_name = f"Control {control_id}"
        self.mcsb_control_id = "DP-3"
        self.mcsb_control_name = "Encrypt data in transit"
        self.mcsb_domain = "Data Protection"
        self.confidence_score = 0.9
        self.reasoning = "Relevant."
        self.azure_policy_ids = list(policy_ids or [])
        self.defender_recommendations = []
        self.coverage_category = None
        self.coverage_display = None
        self.coverage_reason = None
        self.azure_enforceable = False
        self.coverage_gap = False
        self.outside_step = None
        self.responsibility = None
        self.enforcement_plane = None
        self.policy_effects = []
        self.available_effects = []
        self.policy_type = None
        self.evidence_source = None
        self.attestation = None
        self.attestation_gap = False
        self.dropped_policy_ids = []
        self.verified_at = None
        self.catalog_snapshot_date = None
        self.verification_source = None
        self.provenance_blocker = None


class _Classification:
    def __init__(self, category, **kw):
        self.coverage_category = category
        self.reason = kw.get("reason", "A control-specific reason.")
        self.responsibility = kw.get("responsibility")
        self.outside_step = kw.get("outside_step", "")
        self.evidence = kw.get("evidence", "")
        self.evidence_source = kw.get("evidence_source", "")


@pytest.fixture(scope="module")
def catalog():
    return get_policy_catalog_service()


def _through_services(category, policy_ids, catalog, **kw):
    m = _Mapping("CTRL-1", policy_ids)
    coverage.apply_coverage(m, "Technical", catalog, _Classification(category, **kw))
    return m


def _through_pipeline(services_mapping):
    """The same mapping, converted for the pipeline artifacts."""
    return policy_mapper._to_pipeline_mapping(
        services_mapping,
        types.SimpleNamespace(
            control_id=services_mapping.external_control_id,
            control_title=services_mapping.external_control_name,
            domain="Data Protection",
            control_description="A requirement.",
            control_type="Technical",
        ),
        get_policy_catalog_service(),
    )


def _pipeline_policy_ids(pm):
    return [p.policy_definition_id for p in (pm.azure_policies or [])]


def _dropped_ids(m):
    """Rejections are reported as records, not bare strings - a drop that does
    not say why is only half a report."""
    return [
        d["policy_id"] if isinstance(d, dict) else d
        for d in (m.dropped_policy_ids or [])
    ]


# ── No process or attestation control emits a policy ─────────────────


@pytest.mark.parametrize("category", sorted(NON_POLICY_BEARING))
def test_a_non_azure_control_emits_no_policy_on_either_path(category, catalog):
    """The workbook's structural rule, and the one the pipeline path lost. A
    policy attached to a process control is a false claim of enforcement."""
    svc = _through_services(category, [REAL_GUID], catalog)
    assert svc.azure_policy_ids == []
    assert _pipeline_policy_ids(_through_pipeline(svc)) == []


@pytest.mark.parametrize("category", sorted(NON_POLICY_BEARING))
def test_a_non_azure_control_still_explains_itself_on_either_path(category, catalog):
    """Stripping the policy without saying why leaves the customer with a blank
    where their obligation was."""
    svc = _through_services(category, [REAL_GUID], catalog)
    assert (svc.coverage_reason or "").strip()
    pipe = _through_pipeline(svc)
    assert (pipe.manual_attestation_note or pipe.coverage_reason or "").strip()


# ── A and B keep their policies ──────────────────────────────────────


@pytest.mark.parametrize("category", sorted(POLICY_BEARING))
def test_an_azure_control_keeps_its_policies_on_either_path(category, catalog):
    """B used to be stripped here. B is defined as Azure-addressable, so
    clearing its policies deleted a whole class of the deliverable."""
    svc = _through_services(category, [REAL_GUID], catalog, outside_step="Conditional Access")
    assert REAL_GUID in svc.azure_policy_ids
    assert REAL_GUID in _pipeline_policy_ids(_through_pipeline(svc))


@pytest.mark.parametrize("category", sorted(POLICY_BEARING))
def test_an_azure_control_is_marked_enforceable_on_either_path(category, catalog):
    svc = _through_services(category, [REAL_GUID], catalog, outside_step="Conditional Access")
    assert svc.azure_enforceable is True
    assert _through_pipeline(svc).is_automatable is True


# ── Identifiers ──────────────────────────────────────────────────────


def test_an_invented_identifier_never_reaches_the_output(catalog):
    svc = _through_services(coverage.COVERAGE_A, [INVENTED_GUID], catalog)
    assert INVENTED_GUID not in svc.azure_policy_ids
    assert INVENTED_GUID not in _pipeline_policy_ids(_through_pipeline(svc))


def test_an_invented_identifier_is_reported_not_silently_dropped(catalog):
    """The defect the analyst workbook demonstrates. A control that loses its
    enforcement must not look identical to one that never needed any."""
    svc = _through_services(coverage.COVERAGE_A, [INVENTED_GUID], catalog)
    assert _dropped_ids(svc) == [INVENTED_GUID]
    assert _dropped_ids(_through_pipeline(svc)) == [INVENTED_GUID]


def test_a_dropped_identifier_says_why_it_was_dropped(catalog):
    """"Dropped" alone is not actionable: a hallucinated ID and one missing
    from this snapshot need different responses."""
    svc = _through_services(coverage.COVERAGE_A, [INVENTED_GUID], catalog)
    entry = svc.dropped_policy_ids[0]
    assert entry["reason"] == coverage.ID_UNKNOWN
    assert entry["detail"].strip()


def test_a_real_but_non_guid_shaped_identifier_survives_both_paths(catalog):
    """17k78e20-... is a live BuiltIn whose name contains a 'k'. Format-first
    validation called it malformed and threw away a correct, deployable answer.
    The catalog is asked first now; format only answers where it cannot."""
    svc = _through_services(coverage.COVERAGE_A, [NON_GUID_BUILTIN], catalog)
    assert NON_GUID_BUILTIN in svc.azure_policy_ids
    assert _dropped_ids(svc) == []
    assert NON_GUID_BUILTIN in _pipeline_policy_ids(_through_pipeline(svc))


def test_something_that_is_not_an_identifier_at_all_is_still_rejected(catalog):
    """The format check keeps the job it was actually good at."""
    svc = _through_services(coverage.COVERAGE_A, ["Ensure encryption is on"], catalog)
    assert svc.azure_policy_ids == []
    assert svc.dropped_policy_ids[0]["reason"] == coverage.ID_MALFORMED


def test_a_good_identifier_survives_alongside_a_bad_one(catalog):
    """One bad identifier must not cost the control its working policies."""
    svc = _through_services(coverage.COVERAGE_A, [REAL_GUID, INVENTED_GUID], catalog)
    assert svc.azure_policy_ids == [REAL_GUID]
    assert _dropped_ids(svc) == [INVENTED_GUID]


def test_policy_names_come_from_the_catalog_not_the_model(catalog):
    """A display name the model authored is a plausible-looking fabrication;
    the catalog is the only thing that knows what a GUID is actually called."""
    svc = _through_services(coverage.COVERAGE_A, [REAL_GUID], catalog)
    pipe = _through_pipeline(svc)
    assert pipe.azure_policies[0].policy_name == catalog.get(REAL_GUID)["display_name"]


# ── Provenance ───────────────────────────────────────────────────────


def test_every_mapping_carries_provenance_on_either_path(catalog):
    """An answer without provenance is not defensible to a regulator, whatever
    else is right about it."""
    for category in (coverage.COVERAGE_A, coverage.COVERAGE_C, coverage.COVERAGE_D):
        svc = _through_services(category, [REAL_GUID], catalog)
        assert svc.verification_source, category
        assert svc.verified_at, category
        pipe = _through_pipeline(svc)
        assert pipe.verification_source, category
        assert pipe.verified_at, category


def test_provenance_records_the_catalog_snapshot_or_says_it_cannot(catalog):
    """An empty field would leave the reader to notice an omission - the same
    failure as a silent drop, one level up."""
    svc = _through_services(coverage.COVERAGE_A, [REAL_GUID], catalog)
    assert (svc.catalog_snapshot_date or "").strip() or (
        svc.provenance_blocker or ""
    ).strip()


# ── The join key ─────────────────────────────────────────────────────


def test_control_id_survives_as_the_join_key(catalog):
    """Names are not stable across a re-extraction; ids are. Anything keyed on
    the name silently mis-joins when wording changes."""
    svc = _through_services(coverage.COVERAGE_A, [REAL_GUID], catalog)
    assert _through_pipeline(svc).control_id == svc.external_control_id


# ── The category axes stay independent ───────────────────────────────


def test_a_process_control_can_be_microsoft_owned(catalog):
    """Category describes HOW a control is met, responsibility WHO owns it.
    Deriving one from the other misattributes work to the wrong party."""
    svc = _through_services(
        coverage.COVERAGE_C, [], catalog, responsibility="Microsoft"
    )
    assert svc.coverage_category == coverage.COVERAGE_C
    assert svc.responsibility == "Microsoft"


def test_an_unanswered_responsibility_stays_empty_rather_than_guessed(catalog):
    """A confidently wrong owner sends the work to the wrong party and looks
    authoritative doing it."""
    svc = _through_services(coverage.COVERAGE_C, [], catalog, responsibility=None)
    assert not svc.responsibility


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
