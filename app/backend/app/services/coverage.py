"""
Coverage taxonomy for control-to-Azure-Policy mapping.

The AI mapping engine over-attaches Azure Policy IDs: process, legal, HR and
governance controls that Azure cannot technically enforce get handed a catch-all
policy (typically an MCSB "Governance & Strategy" entry). The control extractor
already classifies every control's *nature* (``control_type``), but that signal
was dropped before mapping.

This module is the deterministic guarantee. It carries the extractor's
classification through to the mapping and decides, with pure functions, which
controls are genuinely Azure-Policy-enforceable. Only enforceable controls keep
their ``azure_policy_ids``; everything else is routed to a manual register.

Coverage categories
-------------------
The names below are the identifiers; the display names are the analyst's own,
taken from the source workbook's Legend sheet:

- ``A_AzurePolicy``          "Azure Policy enforced"
- ``B_AzureConfig``          "Azure/Entra config - partial"
- ``C_Process``              "Process / organisational"
- ``D_MicrosoftAttestation`` "Microsoft attested"

The word *partial* in category B is load-bearing and was previously lost. The
Legend defines B as: Azure Policy or Entra configuration covers a substantial
part of the control, but full coverage needs configuration outside Azure Policy
(for example Entra Conditional Access, which has no Azure Policy equivalent).
B is therefore **partial coverage plus a named outside step**, not "no policy".

Invariant enforced everywhere: ``azure_policy_ids`` is non-empty **only** when
coverage is ``A_AzurePolicy`` or ``B_AzureConfig``. A and B are treated
identically for policy emission; the nuance is carried by ``policy_effects`` and
``enforcement_plane``, which are resolved from the catalog rather than asserted.
``C_Process`` and ``D_MicrosoftAttestation`` never carry policy IDs.

Coverage category is independent of responsibility. The source workbook states
this explicitly: the category describes *how* a control is met, not *who* owns
it. A process control can be Microsoft-owned, and this module must not infer one
axis from the other.

Nothing is dropped silently. Every candidate policy ID that fails validation is
recorded on the mapping with the reason it was rejected, because a control that
lost its enforcement to a typo must not look identical to one that never needed
enforcement.

Compliance is a wider notion than Azure-Policy enforcement: A and B are covered
because Azure enforces or configures them, and ``D_MicrosoftAttestation`` is
compliant because Microsoft operates and certifies it on the customer's behalf.
``C_Process`` remains an open customer action. See
``INHERITED_COMPLIANT_CATEGORIES``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

CoverageCategory = str  # one of the COVERAGE_* constants below

COVERAGE_A = "A_AzurePolicy"
COVERAGE_B = "B_AzureConfig"
COVERAGE_C = "C_Process"
COVERAGE_D = "D_MicrosoftAttestation"

VALID_COVERAGE_CATEGORIES = frozenset(
    {COVERAGE_A, COVERAGE_B, COVERAGE_C, COVERAGE_D}
)

# Categories that emit Azure Policy IDs into the initiative. A and B are
# identical here by design: B is *partial* Azure coverage, not absent coverage,
# so stripping its policies deletes real enforcement the customer is entitled to.
POLICY_BEARING_CATEGORIES = frozenset({COVERAGE_A, COVERAGE_B})

# Categories for which confidence_score is never a graded match-quality signal.
# C_Process and D_MicrosoftAttestation controls never attempt an Azure Policy
# match - confidence_score is forced to 0.0 as a placeholder (see
# ai_mapping_service.py's ControlMapping construction), not a real assessment
# of how well anything matched. Averaging that fixed 0.0 in with A/B controls'
# genuine confidence judgements drags a legitimate "every enforceable control
# matched well" result down to a misleading low headline number - exactly the
# defect this constant exists to prevent. ``None`` (legacy/unclassified
# mappings) is deliberately NOT included here, for the same backward-
# compatibility reason coverage_summary buckets it as "unclassified" rather
# than excluding it.
CONFIDENCE_EXCLUDED_CATEGORIES = frozenset({COVERAGE_C, COVERAGE_D})


def confidence_eligible(category: Optional[str]) -> bool:
    """True when a mapping's confidence_score is a meaningful match-quality signal.

    Use this to scope any "average confidence" / "high confidence" statistic
    to the controls where confidence was actually judged - A_AzurePolicy and
    B_AzureConfig (plus legacy ``None`` mappings, for backward compatibility).
    C_Process and D_MicrosoftAttestation controls are excluded: Azure was
    never attempted for them, so their fixed 0.0 confidence_score is a
    placeholder, not a low score.
    """
    return category not in CONFIDENCE_EXCLUDED_CATEGORIES


# The analyst's display names, from the source workbook's Legend sheet. The
# A_/B_/C_/D_ codes are internal identifiers; these are what a reader sees.
COVERAGE_DISPLAY_NAMES = {
    COVERAGE_A: "Azure Policy enforced",
    COVERAGE_B: "Azure/Entra config - partial",
    COVERAGE_C: "Process / organisational",
    COVERAGE_D: "Microsoft attested",
}

# The policy_type for a control that is in scope for Azure but for which no
# built-in definition exists. Distinct from "N/A", which means Azure Policy was
# never the right instrument: this control *should* have a policy and does not,
# so the answer is to author one. The analyst workbook records the same state as
# "Built-in + Custom (... SLZ definition)".
CUSTOM_POLICY_REQUIRED = "Custom definition required"


def coverage_display_name(category: Optional[str]) -> str:
    """The analyst-facing name for a coverage category identifier."""
    return COVERAGE_DISPLAY_NAMES.get(category or "", "Unclassified")


# Categories that count as compliant without any customer action. Microsoft
# operates the underlying control and evidences it through its own audited
# certifications (Service Trust Portal), so the control is inherited-compliant:
# it must stay out of the initiative, but it is not a coverage gap either.
INHERITED_COMPLIANT_CATEGORIES = frozenset({COVERAGE_D})

# control_type values (from pipeline/control_extractor.py) that describe a
# control's nature as process/organisational rather than a technical control an
# Azure Policy could audit or enforce. Compared case-folded.
PROCESS_CONTROL_TYPES = frozenset(
    {"policy", "contractual", "management", "operational", "governance"}
)

# Keywords indicating the control concerns Microsoft-operated infrastructure the
# customer attests to via the Service Trust Portal / certifications rather than
# configures — routed to D_MicrosoftAttestation. Compared case-insensitively.
ATTESTATION_KEYWORDS = (
    "data centre",
    "data center",
    "datacentre",
    "datacenter",
    "physical security",
    "physical access",
    "hypervisor",
    "host operating system",
    "microsoft personnel",
    "service trust",
    "iso 27001",
    "soc 2",
    "csp certification",
    "cloud service provider certification",
)

# Keywords indicating a genuinely technical control, used to override a
# process-typed classification when the text is clearly about enforceable Azure
# configuration (defence against extractor mis-classification).
TECHNICAL_KEYWORDS = (
    "encrypt",
    "tls",
    "mfa",
    "multi-factor",
    "firewall",
    "network security group",
    "private endpoint",
    "key vault",
    "backup",
    "logging",
    "diagnostic",
    "retention",
    "rbac",
    "role assignment",
    "vulnerability",
    "patch",
    "azure policy",
)


def _casefold(value: Optional[str]) -> str:
    return (value or "").strip().casefold()


def is_process_control(control_type: Optional[str]) -> bool:
    """True if ``control_type`` names a process/organisational control nature."""
    return _casefold(control_type) in PROCESS_CONTROL_TYPES


def _has_keyword(text: str, keywords: Iterable[str]) -> bool:
    low = text.casefold()
    return any(kw in low for kw in keywords)


def resolve_coverage(
    control_type: Optional[str],
    enforceable_policy_ids: List[str],
    text: str = "",
    model_category: Optional[str] = None,
    classification: Optional[str] = None,
    requires_outside_step: bool = False,
) -> Tuple[CoverageCategory, bool]:
    """Decide a control's coverage category and Azure-enforceability.

    Deterministic and side-effect free.

    ``classification`` is the blind classification stage's verdict
    (``control_classification_service``), reached without seeing any policy
    candidates. It is the *primary* signal, because it is the only one that
    judged the control on its own terms; the keyword heuristics below are the
    fallback for when that stage is disabled or failed.

    Precedence:
    1. A blind classification of C or D is authoritative and **demotes** even a
       control that retrieved policies. This is the whole point of the stage:
       a governance control that happens to lexically resemble a policy must not
       become "enforced" just because retrieval found something.
    2. A blind classification of A or B is treated as one decision — "this
       control is in scope for Azure enforcement" — because the stage cannot
       tell A from B. Measured against the gold mapping it placed **19 of 24**
       gold-``A_AzurePolicy`` controls in ``B_AzureConfig``: whether a built-in
       definition exists is a fact about the catalog that no amount of reading
       the control text reveals, so the stage hedges. Its own eval scores only
       the A∪B in-scope decision for exactly this reason.

       The split is therefore settled here, from two signals the stage *can*
       supply reliably:

       * **Did anything survive retrieval and validation?** If not, the control
         is an explicit gap — reported as such by ``apply_coverage`` rather than
         absorbed into a category label, which is what the previous behaviour
         did (a recall miss became a silent "B" and lost its policies).
       * **Does full coverage need a step outside Azure Policy?**
         (``requires_outside_step`` — the classification names the step). That,
         not the A/B label, is what *partial* means: in the gold mapping 18 of
         21 ``B_AzureConfig`` controls carry policy IDs, several with ``Deny``.
         B is Azure coverage plus a named remaining step, not absent coverage.

       So: policies + an outside step → B; policies + nothing outstanding → A.
       When the classification supplies no ``outside_step``, this degrades
       exactly to the previously measured behaviour (A whenever policies
       survive), so the change cannot regress it.
    3. Without a classification, fall back to the original heuristics: a
       genuinely technical control (not process-typed, or process-typed but with
       clearly technical text) holding enforceable IDs is ``A_AzurePolicy``.
    4. Otherwise a valid explicit ``model_category`` (B/C/D) is respected.
    5. Otherwise attestation keywords → ``D_MicrosoftAttestation``.
    6. Otherwise → ``C_Process`` as the conservative default.

    Returns ``(coverage_category, azure_enforceable)``. ``azure_enforceable``
    means "covered by Azure" and is ``True`` for A and B alike.
    """
    has_policies = bool(enforceable_policy_ids)
    process = is_process_control(control_type)
    technical_text = _has_keyword(text, TECHNICAL_KEYWORDS)

    # 1-2. The blind classification wins; the A/B split is settled by evidence
    # plus the named outside step.
    if classification in VALID_COVERAGE_CATEGORIES:
        if classification in (COVERAGE_C, COVERAGE_D):
            return classification, False
        if has_policies and not requires_outside_step:
            return COVERAGE_A, True
        return COVERAGE_B, True

    # 3. Enforceable technical control.
    if has_policies and (not process or technical_text):
        return (COVERAGE_B, True) if requires_outside_step else (COVERAGE_A, True)

    # 4. Respect an explicit, valid non-A model classification.
    if model_category in {COVERAGE_B, COVERAGE_C, COVERAGE_D}:
        return model_category, model_category == COVERAGE_B

    # 5. Microsoft-operated / attestation.
    if _has_keyword(text, ATTESTATION_KEYWORDS):
        return COVERAGE_D, False

    # 6. Conservative default: process controls (and anything non-enforceable).
    return COVERAGE_C, False


def apply_coverage(
    mapping,
    control_type: Optional[str],
    catalog=None,
    classification=None,
    attestations=None,
):
    """Enrich a ``ControlMapping`` in place with coverage classification.

    - Propagates ``control_type`` onto the mapping.
    - Computes the enforceable subset of ``azure_policy_ids``, **recording every
      rejected candidate and why** on ``dropped_policy_ids``.
    - Resolves the coverage category and sets ``azure_enforceable``.
    - Keeps ``azure_policy_ids`` for A and B alike; clears them for C and D —
      the invariant that keeps non-Azure controls out of the initiative.
    - Flags ``coverage_gap`` when a control is in scope for Azure but nothing
      survived retrieval and validation, so a recall failure is visible instead
      of hiding inside a category label.
    - **Grounds Category D against the attestation catalog**, so "Microsoft
      attested" resolves to a citation the customer can hand an auditor, or to
      an admitted gap — never to a bare assertion.
    - Records the blind classification's reason, responsibility and evidence
      source, and derives the enforcement plane and effects from the catalog.

    Responsibility is recorded as the classification reported it and is **not**
    inferred from the coverage category: the two are independent axes, and a
    process control may well be Microsoft-owned.

    Pure with respect to inputs other than the passed ``mapping`` (which it
    returns for convenience). ``catalog`` is optional; when ``None`` the
    Regulatory-Compliance strip is skipped and all well-formed IDs count as
    candidates. ``classification`` is the blind classification stage's result.
    ``attestations`` is the attestation catalog; when ``None`` the shipped
    singleton is used, and when it cannot be loaded every D control degrades to
    a declared gap rather than to an unchecked pass.
    """
    mapping.control_type = control_type

    raw_ids = list(mapping.azure_policy_ids or [])
    enforceable_ids, rejected = partition_policy_ids(raw_ids, catalog)

    text = " ".join(
        part
        for part in (
            getattr(mapping, "external_control_name", ""),
            getattr(mapping, "reasoning", ""),
        )
        if part
    )

    classified = getattr(classification, "coverage_category", None)
    outside_step = (getattr(classification, "outside_step", "") or "").strip()
    category, enforceable = resolve_coverage(
        control_type=control_type,
        enforceable_policy_ids=enforceable_ids,
        text=text,
        model_category=mapping.coverage_category,
        classification=classified,
        requires_outside_step=bool(outside_step),
    )

    mapping.coverage_category = category
    mapping.coverage_display = coverage_display_name(category)
    mapping.azure_enforceable = enforceable
    # The named step only means something where Azure covers the control at all;
    # on C/D it would imply a partial Azure story that does not exist.
    mapping.outside_step = (
        outside_step if (category == COVERAGE_B and outside_step) else None
    )
    if category in POLICY_BEARING_CATEGORIES:
        mapping.azure_policy_ids = enforceable_ids
    else:
        mapping.azure_policy_ids = []

    # Rejections are only meaningful where policies were wanted. For C and D the
    # candidates were never going to be emitted, so reporting them would be
    # noise rather than a finding.
    mapping.dropped_policy_ids = (
        rejected if category in POLICY_BEARING_CATEGORIES else []
    )
    mapping.coverage_gap = bool(
        category in POLICY_BEARING_CATEGORIES and not mapping.azure_policy_ids
    )

    if classification is not None:
        mapping.coverage_reason = (
            getattr(classification, "reason", "") or None
        )
        mapping.responsibility = (
            getattr(classification, "responsibility", "") or None
        )
        mapping.evidence_source = (
            getattr(classification, "evidence_source", "") or None
        )

    # Responsibility and coverage category are independent axes: the source
    # workbook is explicit that the category "describes HOW a control is met,
    # not WHO owns it", and 30 of its process/organisational controls are
    # Microsoft-owned. So responsibility is never derived from the category --
    # with one exception that is a definition rather than an inference.
    #
    # D_MicrosoftAttestation *means* "Microsoft operates this and the customer
    # cannot configure it". Filling Microsoft in when the classifier said
    # nothing restates that definition. The reverse inferences -- C implies
    # Customer, A/B implies Customer -- are the ones that misattribute
    # ownership, so they are deliberately absent.
    if category == COVERAGE_D and not getattr(mapping, "responsibility", None):
        mapping.responsibility = "Microsoft"

    # Category D is the only category whose entire deliverable is a citation, so
    # it is the only one where an ungrounded claim is indistinguishable from a
    # lie. Resolve it now, before the reason is composed from it.
    if category == COVERAGE_D:
        apply_attestation(mapping, attestations)

    # A control demoted out of A/B carries no policies, so its plane is manual
    # regardless of what the classification said.
    enrich_policy_details(mapping, catalog)
    apply_provenance(mapping, catalog)
    return mapping


def clear_moot_sovereignty(mapping) -> None:
    """Clear a C/D control's sovereignty card when it carries no real objective.

    The mapping prompt asks the model to assign a sovereignty dimension to
    EVERY control, defaulting to L1/sovereign_root with an empty objectives
    list when none applies. For a process or Microsoft-attestation control
    that will never carry an Azure Policy or SLZ policy, that default renders
    as a real assignment ("Level: L1 - Global", "Target Archetype:
    sovereign_root") when the model's own sovereignty reasoning says the
    opposite - no sovereignty requirement applies here at all. Shown next to
    a mapping that constructs no initiative entry, it reads as a second,
    contradictory verdict rather than a placeholder.

    The one legitimate exception is a real procedural sovereignty objective
    (e.g. SO-2 Customer Lockbox), which has no Azure Policy but genuine
    sovereignty relevance - callers apply that (see
    ``AIMappingService._apply_procedural_sovereignty``) before this runs, so
    it is preserved by checking for a non-empty ``sovereignty_objectives``
    rather than category alone.

    Must run after ``apply_coverage`` (needs the resolved ``coverage_category``)
    and after any procedural sovereignty enrichment.
    """
    category = getattr(mapping, "coverage_category", None)
    if category not in (COVERAGE_C, COVERAGE_D):
        return
    sovereignty = getattr(mapping, "sovereignty", None)
    if sovereignty is None:
        return
    if getattr(sovereignty, "sovereignty_objectives", None):
        return  # a real procedural objective is attached - keep it
    mapping.sovereignty = None


def apply_provenance(mapping, catalog=None):
    """Record what verified this mapping and when.

    The analyst workbook's Legend documents a ``Verification Date & Source``
    column - "when and how the mapping was verified" - and warns that region
    and service availability "changes without customer notice" and must be
    re-verified before each release. Neither existed anywhere in the product.

    Provenance is the difference between an answer and a defensible one. A
    regulator asking "how do you know this policy exists" needs the catalog
    snapshot the identifier was checked against; without it the answer is
    "the system said so".

    Deliberately deterministic: the timestamp and catalog date are facts the
    code holds, never model output.
    """
    verified_at = datetime.now(timezone.utc).isoformat()
    snapshot = ""
    source = "unavailable"
    if catalog is not None:
        snapshot = str(getattr(catalog, "snapshot_date", "") or "")
        source = str(getattr(catalog, "source", "") or "unknown")

    mapping.verified_at = verified_at
    mapping.catalog_snapshot_date = snapshot
    mapping.verification_source = (
        f"Azure Policy catalog {source}"
        + (f", captured {snapshot}" if snapshot else ", capture date unknown")
    )
    # An undated catalog is not a detail. It means nobody can say whether the
    # definitions cited still exist, so it is carried as a blocker rather than
    # left for a reader to notice.
    if catalog is None or not snapshot:
        mapping.provenance_blocker = (
            "The policy catalog snapshot carries no capture date, so this "
            "mapping cannot be dated. Re-verify against a live catalog before "
            "presenting it as current."
        )
    return mapping


def apply_attestation(mapping, attestations=None):
    """Ground a Category D control's attestation claim, or declare it a gap.

    The claim the model produces is free text on ``evidence_source`` — today
    anything from a real clause reference to "Microsoft operates this control".
    It is resolved against the attestation catalog exactly as policy GUIDs are
    resolved against the policy catalog, and the outcome replaces the claim:

    * grounded — a clause that exists, with the title **read** from Azure's
      published metadata, plus the evidence document, where to get it and
      whether an NDA is required.
    * scheme-level — the scheme is a real Microsoft attestation but Azure
      publishes no metadata for the cited clause. The scheme is still citable;
      the clause is carried as explicitly unverified.
    * gap — nothing grounds it. ``attestation_gap`` is set and the reason is
      stated. This is the sovereign case: a requirement such as UAE national
      security clearance that Microsoft's certifications do not cover must be
      escalated, not absorbed into a generic Microsoft-attested pass.

    ``evidence_source`` is overwritten with the resolved text so that no
    downstream consumer can print the unvalidated claim by accident.
    """
    if attestations is None:
        try:  # local import: avoids a cycle and keeps the catalog optional
            from app.services.attestation_catalog_service import (
                get_attestation_catalog_service,
            )

            attestations = get_attestation_catalog_service()
        except Exception:  # pragma: no cover - defensive
            attestations = None

    claim = (getattr(mapping, "evidence_source", None) or "").strip()

    if attestations is None:
        mapping.attestation = None
        mapping.attestation_gap = True
        mapping.evidence_source = (
            "No Microsoft attestation could be verified: the attestation catalog "
            "is unavailable. Treat this control as unevidenced until checked."
        )
        return mapping

    citation = attestations.resolve(claim)
    mapping.attestation = citation.to_dict()
    mapping.attestation_gap = citation.is_gap

    if citation.is_gap:
        # Say plainly that Microsoft does not attest this, and why. A regulator
        # discovering the gap is far worse than the customer being told now.
        mapping.evidence_source = (
            "No Microsoft attestation grounds this requirement — "
            f"{citation.reason}. Escalate as a gap rather than claiming coverage."
        )
    else:
        parts = [citation.citation_text()]
        if citation.evidence_document:
            parts.append(f"Evidence: {citation.evidence_document}")
        if citation.evidence_location:
            parts.append(citation.evidence_location)
        if citation.access_condition:
            parts.append(citation.access_condition)
        mapping.evidence_source = " · ".join(p for p in parts if p)

    return mapping


def _is_enforceable_id(policy_id: str, catalog) -> bool:
    """True if ``policy_id`` looks like a usable, enforceable policy GUID.

    Thin wrapper over :func:`classify_policy_id`, kept because callers outside
    this module use it as a predicate.
    """
    return classify_policy_id(policy_id, catalog) == ID_OK


# Rejection reasons for a candidate policy ID. These are reported, never
# swallowed: a control that lost its enforcement to a mistyped GUID must not be
# indistinguishable from one that never had any.
ID_OK = "ok"
ID_EMPTY = "empty"
ID_MALFORMED = "malformed"
ID_UNKNOWN = "not-in-catalog"
ID_NON_ENFORCEABLE = "non-enforceable-placeholder"
ID_DEPRECATED = "deprecated"
ID_MANAGED_CONTROL = "microsoft-managed-control"

ID_REJECTION_MESSAGES = {
    ID_EMPTY: "empty policy identifier",
    ID_MALFORMED: "not a well-formed policy definition GUID",
    ID_UNKNOWN: "no such definition in the Azure Policy catalog",
    ID_NON_ENFORCEABLE: (
        "Regulatory Compliance placeholder — carries no enforcement effect"
    ),
    ID_DEPRECATED: (
        "withdrawn by Microsoft — a replacement built-in must be selected"
    ),
    ID_MANAGED_CONTROL: (
        "Microsoft Managed Control — operated and attested by Microsoft, "
        "not deployable as tenant enforcement"
    ),
}

_GUID_CHARS = set("0123456789abcdef-")


def _looks_like_guid(guid: str) -> bool:
    """Structural GUID check: 8-4-4-4-12 hexadecimal.

    **This is a fallback, not the authority.** It was previously documented as
    "deliberately strict", on the belief that the workbook's
    ``17k78e20-9358-41c9-923c-fb736d382a12`` was a mistyped identifier - the
    letter ``k`` is not hexadecimal - and that catching it was the point.

    That was wrong, and measurably so: ``az policy definition show`` returns it
    as ``policyType: BuiltIn``, "Transparent Data Encryption on SQL databases
    should be enabled". It is a real, live, deployable policy. The analyst was
    right; the structural check would have thrown away a correct answer and
    reported a genuine control as unenforceable.

    So the catalog decides first, and this only answers the question the
    catalog cannot: is an identifier the catalog has never heard of at least
    shaped like one, or is it a hallucinated document title? It is the only
    non-GUID-shaped name among 2,269 initiative members, which is precisely
    what made a format-first rule dangerous - it is right almost every time,
    and wrong exactly where it costs a customer a control.
    """
    low = guid.casefold()
    if len(low) != 36 or set(low) - _GUID_CHARS:
        return False
    return [len(part) for part in low.split("-")] == [8, 4, 4, 4, 12]


def normalise_policy_id(policy_id: str) -> str:
    """The bare GUID from a full ARM policy definition path or a raw GUID."""
    return (policy_id or "").strip().rstrip("/").rsplit("/", 1)[-1]


def classify_policy_id(policy_id: str, catalog) -> str:
    """Why a candidate policy ID is or is not usable.

    Returns :data:`ID_OK` or one of the rejection reasons. Splitting this out of
    the old boolean predicate is what makes silent drops impossible: the caller
    can now say *which* check failed, on which control.

    Drops catalog "Regulatory Compliance" (Microsoft Managed Control /
    manual-attestation) placeholders when a catalog is supplied; these carry no
    audit/deny effect so they must not count as enforcement.

    Also drops GUIDs the catalog has never heard of. The selecting model can
    hallucinate an ID, and treating one as enforceable produced a mapping that
    contradicted itself — ``azure_enforceable=True`` with no effects and a
    manual enforcement plane, because enrichment could not find the definition.

    **Order matters: the catalog is asked before the format check.** Azure ships
    at least one real built-in whose name is not GUID-shaped
    (``17k78e20-…``, verified live as BuiltIn). Checking format first rejected
    it as malformed and reported a genuine, deployable policy as a lost
    identifier. Format now only answers for identifiers the catalog cannot
    recognise, where it still does useful work: it separates "an ID this
    snapshot does not have" from "not an identifier at all".

    A definition Azure has *retired* is reported as :data:`ID_DEPRECATED`
    rather than as unknown. It is still excluded - a withdrawn built-in must
    never be proposed for new governance - but the customer's next action
    differs: find the replacement, rather than distrust the citation.
    """
    if not policy_id or not policy_id.strip():
        return ID_EMPTY
    guid = normalise_policy_id(policy_id)

    known = False
    if catalog is not None:
        checker = getattr(catalog, "identifier_exists", None) or getattr(
            catalog, "exists", None
        )
        if callable(checker):
            known = bool(checker(guid))

    if not known:
        is_managed = getattr(catalog, "is_managed_control", None) if catalog else None
        if callable(is_managed) and is_managed(guid):
            # Microsoft attestation, not a missing policy. It is still excluded
            # from the initiative - it enforces nothing - but calling it
            # "unknown" would report the Microsoft-attested half of the answer
            # as broken data.
            return ID_MANAGED_CONTROL
        is_deprecated = getattr(catalog, "is_deprecated", None) if catalog else None
        if callable(is_deprecated) and is_deprecated(guid):
            # Retired, not imaginary. The customer needs a migration, not a
            # correction, and saying "no such policy" about something Azure
            # shipped for years is its own kind of wrong answer.
            return ID_DEPRECATED
        if not _looks_like_guid(guid):
            return ID_MALFORMED
        if catalog is None:
            return ID_OK
        exists = getattr(catalog, "exists", None)
        if callable(exists):
            return ID_UNKNOWN
        return ID_OK

    is_non_enforceable = getattr(catalog, "is_non_enforceable", None)
    if callable(is_non_enforceable) and is_non_enforceable(guid):
        return ID_NON_ENFORCEABLE
    return ID_OK


def partition_policy_ids(policy_ids, catalog) -> Tuple[List[str], List[dict]]:
    """Split candidate IDs into the usable ones and reported rejections.

    The second element is never discarded by callers — it is surfaced on the
    mapping so a reviewer can see that enforcement was lost and why.
    """
    kept: List[str] = []
    rejected: List[dict] = []
    for pid in policy_ids or []:
        reason = classify_policy_id(pid, catalog)
        if reason == ID_OK:
            kept.append(pid)
        else:
            rejected.append(
                {
                    "policy_id": (pid or "").strip(),
                    "reason": reason,
                    "detail": ID_REJECTION_MESSAGES.get(reason, reason),
                }
            )
    return kept, rejected



def _reason_for(mapping) -> str:
    """Human-readable reason a control is not Azure-Policy enforceable.

    Prefers the classification stage's substantive, control-specific reason and
    falls back to a generic sentence only when that is unavailable. The generic
    strings are a safety net, not the intended output: a manual register whose
    every row says the same thing tells the reader nothing.

    Category D is the exception, and takes its grounding first. Its deliverable
    *is* the citation, and an ungrounded D row is the one place where the
    model's fluent prose is actively dangerous — "Microsoft operates this
    control" reads exactly like evidence while grounding nothing.
    """
    reason = (getattr(mapping, "coverage_reason", None) or "").strip()

    if mapping.coverage_category == COVERAGE_D:
        attestation = getattr(mapping, "attestation", None) or {}
        if getattr(mapping, "attestation_gap", False):
            why = attestation.get("reason") or "no Microsoft attestation was identified"
            # Keep the control-specific reason. "No attestation covers this"
            # is only actionable if the reader knows *what* is uncovered --
            # "UAE security clearance for operations personnel" is the sentence
            # that gets escalated, not the generic rejection.
            lead = (
                f"{reason} No Microsoft attestation covers it"
                if reason
                else "Microsoft-operated control, but no Microsoft attestation covers this requirement"
            )
            return (
                f"{lead}: {why}. Escalate as a gap rather than claiming coverage."
            )
        citation = attestation.get("citation")
        if citation:
            retrieval = (attestation.get("retrieval") or "").strip()
            lead = (
                f"{reason} Attested by {citation}."
                if reason
                else f"Microsoft-operated control, attested by {citation}."
            )
            return f"{lead} {retrieval}".strip()

    if reason:
        return reason
    step = (getattr(mapping, "outside_step", None) or "").strip()
    if mapping.coverage_category == COVERAGE_B:
        # Naming the remaining step is the difference between an instruction and
        # an unexplained shortfall.
        return (
            f"Azure covers this control substantially; full coverage also needs: {step}"
            if step
            else (
                "Azure/Entra configuration covers part of this control; full "
                "coverage needs a configuration step outside Azure Policy"
            )
        )

    return {
        COVERAGE_C: "Process / legal / organisational control — not Azure-enforceable",
        COVERAGE_D: (
            "Microsoft-operated control — no attestation citation was resolved, "
            "so this control is unevidenced until one is confirmed"
        ),
    }.get(mapping.coverage_category, "Not Azure-Policy enforceable")


# Azure Policy effects that act at deployment time: they block or mutate the
# request itself, so the control is enforced by the landing zone before a
# non-conformant resource ever exists.
DEPLOY_TIME_EFFECTS = frozenset({"deny", "modify", "deployifnotexists", "append"})# Effects that only observe. They surface non-conformance as a Defender for Cloud
# recommendation after the fact; they do not block anything.
RUN_TIME_EFFECTS = frozenset({"audit", "auditifnotexists"})

PLANE_DEPLOY = "SLZ (deploy-time)"
PLANE_RUNTIME = "Defender (run-time)"
PLANE_BOTH = "SLZ (deploy-time) + Defender (run-time)"
PLANE_MANUAL = "None (manual control)"

# Used when a policy id resolves to no definition in the catalog snapshot. The
# effect slot still has to be filled so effects stay aligned with the ids.
EFFECT_UNKNOWN = "Unknown"



def enforcement_plane_for(effects: Iterable[str]) -> str:
    """Where a set of policy effects takes effect.

    Deploy-time and run-time enforcement are materially different promises, and
    the gold mapping records them separately: ``Deny`` blocks a non-conformant
    deployment, while ``Audit``/``AuditIfNotExists`` only report it. Conflating
    them overstates coverage.
    """
    normalised = {(e or "").strip().casefold() for e in effects if e}
    deploy = bool(normalised & DEPLOY_TIME_EFFECTS)
    runtime = bool(normalised & RUN_TIME_EFFECTS)
    if deploy and runtime:
        return PLANE_BOTH
    if deploy:
        return PLANE_DEPLOY
    if runtime:
        return PLANE_RUNTIME
    return PLANE_MANUAL


def enrich_policy_details(mapping, catalog=None):
    """Populate ``policy_effects``, ``policy_type`` and ``enforcement_plane``.

    Resolved from the catalog snapshot, never model-generated: the effect a
    policy actually carries is a fact about the definition, and asking a model to
    recall it invites confident errors that would misreport whether a control is
    blocked or merely observed.

    Returns the mapping for convenience.
    """
    policy_ids = list(getattr(mapping, "azure_policy_ids", None) or [])
    if not policy_ids or catalog is None:
        mapping.policy_effects = []
        mapping.available_effects = []
        # "N/A" is correct for a control Azure was never going to enforce. It is
        # wrong for one that is in scope and came back empty: that control needs
        # a policy definition that does not exist yet, and saying so is the
        # difference between an actionable instruction and an unexplained blank.
        # The analyst workbook records this state explicitly as
        # "Built-in + Custom (... SLZ definition)".
        if not policy_ids and getattr(mapping, "coverage_gap", False):
            mapping.policy_type = CUSTOM_POLICY_REQUIRED
        else:
            mapping.policy_type = "N/A" if not policy_ids else "Built-in"
        mapping.enforcement_plane = (
            PLANE_MANUAL if not policy_ids else mapping.enforcement_plane
        )
        return mapping

    effects: List[str] = []
    available: List[str] = []
    for policy_id in policy_ids:
        guid = policy_id.strip().rstrip("/").rsplit("/", 1)[-1]
        definition = catalog.get(guid) if hasattr(catalog, "get") else None
        definition = definition or {}
        # One entry per policy id, in the same order - deliberately NOT
        # deduplicated. The analyst workbook aligns effects positionally with
        # the identifiers on the row (";"-separated, same length), so a reader
        # can tell which policy denies and which only audits. Collapsing to a
        # distinct set destroys that correspondence: three ids that all audit
        # became one effect, and the row no longer said anything about the
        # second and third policies. An unresolvable definition is named as
        # unknown rather than left blank, because a blank reads as "no effect".
        effect = definition.get("effect", "")
        effects.append(effect or EFFECT_UNKNOWN)
        for allowed in definition.get("allowed_effects") or ():
            if allowed not in available:
                available.append(allowed)

    mapping.policy_effects = effects
    mapping.available_effects = available
    mapping.policy_type = "Built-in"
    # The plane reflects the *default* effect, because that is what applies if
    # nobody intervenes. available_effects records that a stricter choice exists.
    mapping.enforcement_plane = enforcement_plane_for(effects)
    return mapping


def manual_register_rows(mappings) -> List[dict]:
    """Build manual-register rows for controls Azure does not cover.

    Only ``C_Process`` and ``D_MicrosoftAttestation`` belong here. B controls
    were previously included because the code stripped their policies, but B is
    *partial Azure coverage* — it emits policies and enters the initiative, so
    listing it as a manual control misrepresents what the customer must do.

    Controls with ``coverage_category is None`` (legacy mappings) are treated as
    enforceable and skipped, preserving backward-compatible behaviour.
    """
    rows: List[dict] = []
    for m in mappings:
        category = getattr(m, "coverage_category", None)
        if category not in (COVERAGE_C, COVERAGE_D):
            continue
        attestation = getattr(m, "attestation", None) or {}
        rows.append(
            {
                "control_id": m.external_control_id,
                "control_name": m.external_control_name,
                "control_type": getattr(m, "control_type", None) or "",
                "coverage_category": category,
                "coverage_display": coverage_display_name(category),
                "policy_category": getattr(m, "policy_category", None) or "",
                "responsibility": getattr(m, "responsibility", None) or "",
                "evidence_source": getattr(m, "evidence_source", None) or "",
                "enforcement_plane": (
                    getattr(m, "enforcement_plane", None) or PLANE_MANUAL
                ),
                # The attestation columns are what turn a D row from an
                # assertion into something an auditor can check: the basis, the
                # document, where to get it, and whether it needs an NDA.
                "attestation_status": attestation.get("status", ""),
                "attestation_basis": attestation.get("basis_kind", ""),
                "attestation_citation": attestation.get("citation", ""),
                "attestation_document": attestation.get("evidence_document", ""),
                "attestation_location": attestation.get("evidence_location", ""),
                "attestation_access": attestation.get("access_condition", ""),
                "attestation_gap": bool(getattr(m, "attestation_gap", False)),
                "verified_at": getattr(m, "verified_at", None) or "",
                "catalog_snapshot_date": getattr(m, "catalog_snapshot_date", None) or "",
                "verification_source": getattr(m, "verification_source", None) or "",
                "provenance_blocker": getattr(m, "provenance_blocker", None) or "",
                "reason": _reason_for(m),
            }
        )
    return rows


def coverage_gap_rows(mappings) -> List[dict]:
    """Controls in scope for Azure that came back with no usable policy.

    These are the honest failures: the classification put the control in scope
    for Azure enforcement, but retrieval found nothing, or everything it found
    failed validation. Reporting them separately is what stops a recall miss
    from being silently absorbed into a category label — the exact behaviour the
    old A/B derivation produced.
    """
    rows: List[dict] = []
    for m in mappings:
        if not getattr(m, "coverage_gap", False):
            continue
        dropped = list(getattr(m, "dropped_policy_ids", None) or [])
        step = (getattr(m, "outside_step", None) or "").strip()
        rows.append(
            {
                "control_id": m.external_control_id,
                "control_name": m.external_control_name,
                "coverage_category": getattr(m, "coverage_category", None) or "",
                "coverage_display": coverage_display_name(
                    getattr(m, "coverage_category", None)
                ),
                "outside_step": step,
                "rejected_policy_ids": dropped,
                "reason": (
                    "candidate policies were rejected during validation"
                    if dropped
                    else "no candidate policy was retrieved for this control"
                ),
                # A gap without a next step is a complaint. Naming the remedy
                # turns it into work someone can pick up: author a definition,
                # or do the thing Azure Policy cannot assert.
                "policy_type": getattr(m, "policy_type", None) or CUSTOM_POLICY_REQUIRED,
                "remediation": (
                    f"No built-in definition covers this control. Author a custom "
                    f"Azure Policy definition, or complete it outside Azure Policy: {step}"
                    if step
                    else (
                        "No built-in definition covers this control. Author a custom "
                        "Azure Policy definition, or record a compensating control."
                    )
                ),
            }
        )
    return rows


def dropped_entry_field(dropped, field: str) -> str:
    """Read one field off a dropped-policy entry, dict or model alike.

    ``dropped_policy_ids`` is genuinely heterogeneous and cannot be assumed to
    hold either shape. The API models type it as ``DroppedPolicyIdentifier``
    (``app.models.mapping``), so anything arriving through request validation is
    coerced to that model; the pipeline models type the same field as ``dict``
    (``app.pipeline.models``) and ``initiative_builder._record_drop`` appends
    plain dicts, which list mutation performs no validation on. Both shapes
    therefore reach these shared readers, and assuming ``dict`` here returned
    500s from every generate endpoint.
    """
    if dropped is None:
        return ""
    getter = getattr(dropped, "get", None)
    value = getter(field, "") if callable(getter) else getattr(dropped, field, "")
    return "" if value is None else str(value)


def dropped_policy_rows(mappings) -> List[dict]:
    """Every candidate policy ID that was discarded, and why, per control.

    Silent drops are the failure mode this product exists to prevent: a control
    that lost its enforcement to a malformed or non-existent GUID must not look
    identical to one that never needed enforcement.
    """
    rows: List[dict] = []
    for m in mappings:
        for dropped in getattr(m, "dropped_policy_ids", None) or []:
            rows.append(
                {
                    "control_id": m.external_control_id,
                    "control_name": m.external_control_name,
                    "policy_id": dropped_entry_field(dropped, "policy_id"),
                    "reason": dropped_entry_field(dropped, "reason"),
                    "detail": dropped_entry_field(dropped, "detail"),
                }
            )
    return rows


def coverage_summary(mappings) -> dict:
    """Count controls per coverage category, the Azure-covered and compliant shares.

    Two distinct measures are returned and must not be conflated:

    - ``azure_enforceable``/``azure_enforceable_pct`` — controls Azure covers,
      i.e. ``A_AzurePolicy`` **and** ``B_AzureConfig``. Both emit policies into
      the initiative; B additionally needs a configuration step outside Azure
      Policy, which is why it is reported separately as ``azure_partial``.
    - ``compliant``/``compliant_pct`` — controls that need no customer
      remediation: the Azure-covered ones plus the
      ``INHERITED_COMPLIANT_CATEGORIES`` (``D_MicrosoftAttestation``, satisfied
      by Microsoft's own attestation). ``C_Process`` stays outside this count as
      an open customer action.

    ``coverage_gaps`` counts controls in scope for Azure that produced no usable
    policy, and ``dropped_policy_ids`` counts candidates rejected in validation.
    Neither is cosmetic: they are how a recall failure stays visible.

    ``attestation_gaps`` counts D controls whose claim could not be grounded in
    any Microsoft attestation, and **only grounded D controls count towards
    ``compliant``**. This is the headline number where honesty is decided:
    counting an unattested control as compliant because it was labelled
    ``D_MicrosoftAttestation`` is how a UAE customer would be told they pass a
    national-clearance requirement Microsoft has never attested to. The category
    is a claim; only a grounded citation is evidence. A D control that was never
    resolved against the attestation catalog at all is treated the same way —
    unevidenced is unevidenced, however it got that way.

    Legacy mappings (``coverage_category is None``) are bucketed under
    ``"unclassified"`` so totals always reconcile.
    """
    counts = {
        COVERAGE_A: 0,
        COVERAGE_B: 0,
        COVERAGE_C: 0,
        COVERAGE_D: 0,
        "unclassified": 0,
    }
    gaps = 0
    dropped = 0
    attestation_gaps = 0
    attested = 0
    for m in mappings:
        category = getattr(m, "coverage_category", None)
        if category in counts:
            counts[category] += 1
        else:
            counts["unclassified"] += 1
        if getattr(m, "coverage_gap", False):
            gaps += 1
        if category == COVERAGE_D:
            if attestation_is_grounded(m):
                attested += 1
            else:
                attestation_gaps += 1
        dropped += len(getattr(m, "dropped_policy_ids", None) or [])

    total = sum(counts.values())
    enforceable = sum(counts[c] for c in POLICY_BEARING_CATEGORIES)
    inherited = attested
    compliant = enforceable + inherited
    counts["total"] = total
    counts["azure_enforced"] = counts[COVERAGE_A]
    counts["azure_partial"] = counts[COVERAGE_B]
    counts["azure_enforceable"] = enforceable
    counts["azure_enforceable_pct"] = (
        round(100.0 * enforceable / total, 1) if total else 0.0
    )
    counts["inherited_compliant"] = inherited
    counts["compliant"] = compliant
    counts["compliant_pct"] = round(100.0 * compliant / total, 1) if total else 0.0
    counts["coverage_gaps"] = gaps
    counts["attestation_gaps"] = attestation_gaps
    counts["dropped_policy_ids"] = dropped
    return counts


def attestation_is_grounded(mapping) -> bool:
    """Did this control's attestation claim actually resolve to something real?

    Deliberately strict, and deliberately not the inverse of ``attestation_gap``:
    a control that was never resolved at all has ``attestation_gap`` unset, and
    treating that as grounded would let an unevidenced control through on a
    default value. Evidence has to be positively present.
    """
    if getattr(mapping, "attestation_gap", False):
        return False
    attestation = getattr(mapping, "attestation", None)
    if not attestation:
        return False
    return attestation.get("status") not in (None, "", "unattested")


def attestation_gap_rows(mappings) -> List[dict]:
    """Category D controls that no Microsoft attestation grounds.

    The most valuable output in the system, and the reason this product can be
    shown to a regulator. The analyst workbook's control 3.1.3.4 asks for UAE
    national security clearance for operations personnel; ISO/IEC 27001 and
    SOC 2 attest *screening*, not UAE clearance. It has to be escalated
    commercially, and it can only be escalated if it is said out loud.
    """
    rows: List[dict] = []
    for m in mappings:
        if getattr(m, "coverage_category", None) != COVERAGE_D:
            continue
        if attestation_is_grounded(m):
            continue
        attestation = getattr(m, "attestation", None) or {}
        rows.append(
            {
                "control_id": m.external_control_id,
                "control_name": m.external_control_name,
                "claim": attestation.get("raw_claim", ""),
                "reason": attestation.get("reason", "")
                or "no Microsoft attestation was identified for this requirement",
                "action": "Escalate commercially; do not report as covered.",
            }
        )
    return rows


def manual_controls_csv(mappings) -> str:
    """Render the manual register as CSV text (header + one row per C/D control)."""
    import csv
    import io

    fieldnames = [
        "control_id",
        "control_name",
        "control_type",
        "coverage_category",
        "coverage_display",
        "policy_category",
        "responsibility",
        "evidence_source",
        "enforcement_plane",
        "attestation_status",
        "attestation_basis",
        "attestation_citation",
        "attestation_document",
        "attestation_location",
        "attestation_access",
        "attestation_gap",
        "verified_at",
        "catalog_snapshot_date",
        "verification_source",
        "provenance_blocker",
        "reason",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in manual_register_rows(mappings):
        writer.writerow(row)
    return buffer.getvalue()
