"""Attestation grounding: a citation is either real or declared missing.

These tests encode the *rule*, not the shape of any one snapshot: no assertion
here depends on how many clauses Azure happens to publish this month. They lock
in the behaviour that makes a Category D answer defensible to a regulator --
that nothing is asserted which was not read from the catalog, and that a
requirement Microsoft does not attest is said out loud rather than absorbed into
a generic pass.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import attestation_catalog_service as acs
from app.services.attestation_catalog_service import (
    BASIS_AUDIT_REPORT,
    BASIS_CERTIFICATION,
    BASIS_DOCUMENTATION,
    BASIS_NONE,
    GROUNDED,
    SCHEME_ONLY,
    UNATTESTED,
    AttestationCatalogService,
)

CATALOG_PATH = (
    Path(__file__).resolve().parent.parent
    / "backend" / "app" / "data" / "policy_catalog" / "attestation_catalog.json"
)


@pytest.fixture(scope="module")
def catalog() -> AttestationCatalogService:
    service = AttestationCatalogService(str(CATALOG_PATH))
    service.load()
    return service


# ---------------------------------------------------------------------------
# The snapshot itself
# ---------------------------------------------------------------------------
def test_catalog_ships_with_the_backend(catalog):
    """The catalog must be inside the package, or every D control becomes a gap."""
    assert CATALOG_PATH.exists(), f"attestation catalog missing at {CATALOG_PATH}"
    assert catalog.available


def test_clause_facts_and_evidence_facts_are_kept_apart(catalog):
    """A curated fact must never be presentable as a live one.

    Clause ids and titles come from Azure's published metadata; evidence
    documents, locations and NDA conditions are curated because ARM has no
    representation for them. Collapsing the two would let the product imply
    Microsoft published something it did not.
    """
    for scheme in catalog.schemes():
        assert scheme["evidence_source"] == "curated"
        assert scheme["clause_source"] in {"azure-policy-metadata", "unavailable"}


def test_every_scheme_tells_the_customer_how_to_get_the_evidence(catalog):
    """A citation the customer cannot act on is not an answer."""
    for scheme in catalog.schemes():
        assert scheme["evidence_document"].strip()
        assert scheme["evidence_location"].startswith("https://")
        assert scheme["access_condition"].strip()
        assert scheme["retrieval"].strip()


def test_nda_status_is_recorded_per_scheme(catalog):
    """The Legend's rule: SOC reports need a work account and the Microsoft NDA;
    ISO certificates do not. Sending an auditor to a document they cannot open
    is a failed answer."""
    by_name = {s["name"]: s for s in catalog.schemes()}
    assert "NDA" in by_name["SOC 2 Type II"]["access_condition"]
    assert "without an NDA" in by_name["ISO/IEC 27001:2022"]["access_condition"]


def test_standard_body_text_is_not_reproduced():
    """Clause numbers and titles are references; requirement text is not ours to ship."""
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    for scheme in data["schemes"]:
        for clause in scheme["clauses"]:
            assert "requirements" not in clause


# ---------------------------------------------------------------------------
# Grounding
# ---------------------------------------------------------------------------
def test_a_clause_title_is_read_never_authored(catalog):
    """The whole point of the catalog: the title comes from Azure, not the model.

    The claim below supplies a *wrong* parenthetical. The resolved citation must
    carry Azure's title, not the model's.
    """
    result = catalog.resolve("ATTESTED BY: SOC 2 CC6.4 (something the model made up)")
    assert result.status == GROUNDED
    assert result.clause == "CC6.4"
    assert result.clause_verified is True
    assert "made up" not in result.citation_text()
    assert result.clause_title  # read from the snapshot


def test_a_cited_parent_clause_resolves_to_its_single_published_child(catalog):
    """Regulators cite ISO/IEC 27001 "clause 9.2"; Azure publishes "9.2.2".

    Reporting that as ungrounded would be a false gap -- the clause is real and
    Microsoft is certified against it. This is the exact citation the analyst
    workbook uses for internal audit.
    """
    result = catalog.resolve("ATTESTED BY: ISO/IEC 27001:2022 clause 9.2 (internal audit)")
    assert result.status == GROUNDED
    assert result.clause.startswith("9.2")
    assert result.clause_verified is True


def test_an_ambiguous_parent_clause_is_not_silently_disambiguated(catalog):
    """"Clause 9" spans monitoring, internal audit and management review.

    Picking one would be inventing a citation. It must degrade to scheme level
    and say why.
    """
    result = catalog.resolve("ATTESTED BY: ISO/IEC 27001:2022 clause 9")
    assert result.status == SCHEME_ONLY
    assert result.clause_verified is False
    assert "sub-clause" in result.reason


def test_an_unverifiable_clause_is_never_presented_as_verified(catalog):
    """Azure publishes metadata only for clauses it ships policies against, so a
    genuine clause can be absent. The scheme is still citable -- but the clause
    number must be marked unverified in the rendered text, not quietly asserted.
    """
    result = catalog.resolve("ATTESTED BY: ISO/IEC 27002:2022 clause 7.1-7.4 (physical controls)")
    assert result.status == SCHEME_ONLY
    assert result.clause_verified is False
    assert "could not be verified" in result.citation_text()
    assert result.evidence_document  # still actionable


def test_the_basis_kind_distinguishes_a_certificate_from_an_audit_report(catalog):
    """"Certified against ISO 27001" and "tested in a SOC 2 report" are different
    claims, and an auditor treats them differently."""
    assert catalog.resolve("ISO/IEC 27001:2022 clause 8.2").basis_kind == BASIS_CERTIFICATION
    assert catalog.resolve("SOC 2 CC6.4").basis_kind == BASIS_AUDIT_REPORT


def test_published_documentation_is_a_valid_basis_without_a_clause(catalog):
    """The workbook's control 3.1.4.4: "Not a certification item - satisfied by
    published product documentation". Demanding a clause here would report a
    false gap on a legitimately documented platform behaviour.
    """
    result = catalog.resolve(
        "Not a certification item - satisfied by published product documentation"
    )
    assert result.status == SCHEME_ONLY
    assert result.basis_kind == BASIS_DOCUMENTATION
    assert result.is_gap is False


# ---------------------------------------------------------------------------
# The gap case -- the sovereign requirement
# ---------------------------------------------------------------------------
def test_a_sovereign_requirement_microsoft_does_not_attest_is_declared_a_gap(catalog):
    """The most valuable row in the analyst workbook.

    Control 3.1.3.4 demands UAE national security clearance for operations
    personnel. ISO/IEC 27001 and SOC 2 attest *screening*, not UAE clearance. A
    system that labelled this "Microsoft-attested" would hand a UAE customer a
    false pass on exactly the sovereign requirement their regulator cares most
    about -- and the regulator, not the customer, would be the one to find out.
    """
    result = catalog.resolve(
        "ATTESTED BY: UAE National Security Clearance Programme for operations personnel"
    )
    assert result.status == UNATTESTED
    assert result.is_gap is True
    assert result.basis_kind == BASIS_NONE
    assert result.citation_text() == ""  # nothing printed
    assert result.reason  # and the reason is stated


def test_a_bare_assertion_of_microsoft_operation_is_not_an_attestation(catalog):
    """"Microsoft operates this control" is what the product says today. It
    names no scheme, so it grounds nothing and must not read as evidence."""
    result = catalog.resolve("Microsoft operates this control")
    assert result.status == UNATTESTED
    assert result.citation_text() == ""


def test_an_empty_claim_is_a_gap_with_a_reason(catalog):
    result = catalog.resolve("")
    assert result.status == UNATTESTED
    assert "nothing to cite" in result.reason


def test_a_missing_catalog_produces_gaps_rather_than_silence(tmp_path):
    """If the snapshot fails to ship, every D control must degrade to an
    admitted gap -- never to an unchecked pass."""
    service = AttestationCatalogService(str(tmp_path / "absent.json"))
    result = service.resolve("ATTESTED BY: SOC 2 CC6.4")
    assert result.status == UNATTESTED
    assert "unavailable" in result.reason


# ---------------------------------------------------------------------------
# exists() -- the GUID-validation analogue
# ---------------------------------------------------------------------------
def test_exists_mirrors_policy_guid_validation(catalog):
    assert catalog.exists("soc_2", "CC6.4") is True
    assert catalog.exists("soc_2", "cc6.4") is True  # case-insensitive
    assert catalog.exists("soc_2", "CC99.9") is False
    assert catalog.exists("no_such_scheme", "CC6.4") is False


def test_scheme_versions_are_not_conflated(catalog):
    """PCI DSS v3.2.1 and v4.0 number their requirements incompatibly, and SOC 2
    Type II is not the 2023 Trust Services Criteria revision. Merging them would
    produce citations against a revision the customer was never assessed under.
    """
    names = {s["name"] for s in catalog.schemes()}
    assert "PCI DSS v4.0" in names and "PCI DSS v3.2.1" in names
    assert "SOC 2 Type II" in names

    # The bug this caught: a "SOC_2" prefix also swallows every "SOC_2023_*"
    # entry, yielding criteria such as "023_CC6.4" that exist in no report.
    for scheme in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["schemes"]:
        for clause in scheme["clauses"]:
            assert not clause["clause"].startswith("023_"), (
                f"{scheme['name']} carries a mis-parsed clause {clause['clause']}"
            )


def test_csa_controls_use_the_identifier_printed_in_the_caiq(catalog):
    """Azure spells it ``CSA_v4.0.12_IAM_01``; every CSA document says ``IAM-01``."""
    assert catalog.exists("csa_ccm_v4", "IAM-01") is True


def test_the_snapshot_records_when_it_was_generated(catalog):
    """Provenance: the Legend requires availability facts to be re-verified per
    release, which is impossible without knowing the snapshot's age."""
    assert catalog.generated_at


def test_resolution_is_stable_for_the_scheme_names_regulators_actually_write(catalog):
    """Scheme aliases are data, not code -- but they must cover real spellings."""
    for claim in (
        "ISO/IEC 27001:2022 clause 8.2",
        "ISO 27001 2022 clause 8.2",
        "iso/iec 27001:2022 clause 8.2",
    ):
        assert catalog.resolve(claim).scheme_key == "iso_27001_2022", claim
