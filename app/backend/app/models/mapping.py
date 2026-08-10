"""
Pydantic models for control mappings.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal, Optional
from datetime import datetime, timezone
from app.models.sovereignty import SovereigntyMapping
from app.models.control import ExternalControl

_MAX_ACTIVITY_ENTRIES = 50


class AttestationCitation(BaseModel):
    """A grounded Microsoft attestation citation.

    Modelled explicitly rather than as a bare ``dict`` for two reasons. The
    practical one: ``ControlMapping`` is used as an Azure OpenAI structured
    output schema, and a bare dict serialises to an open object, which strict
    schema validation rejects with "additionalProperties is required to be
    supplied and to be false" - that error failed *every* mapping call, so the
    engine returned a fallback for every control while appearing healthy.

    The design one: a citation with arbitrary keys cannot be validated, and an
    attestation the customer cannot retrieve is not an answer. These are the
    fields an auditor needs - what attests it, where the evidence lives, and
    what it takes to get hold of it.
    """

    model_config = ConfigDict(extra="forbid")

    basis_kind: Optional[str] = Field(
        default=None,
        description=(
            "certification_clause | audit_report_criterion | "
            "published_documentation | none"
        ),
    )
    scheme: Optional[str] = Field(
        default=None, description="e.g. ISO/IEC 27001:2022, SOC 2 Type II"
    )
    citation: Optional[str] = Field(
        default=None, description="Clause or criterion reference, e.g. clause 9.2"
    )
    evidence_document: Optional[str] = Field(
        default=None, description="The certificate or report that carries the evidence"
    )
    evidence_location: Optional[str] = Field(
        default=None,
        description="Where to retrieve it (Service Trust Portal, Microsoft Learn)",
    )
    access_condition: Optional[str] = Field(
        default=None,
        description="What retrieval requires, e.g. work account sign-in and NDA",
    )
    source: Optional[str] = Field(
        default=None, description="Which catalog entry grounded this citation"
    )


class DroppedPolicyIdentifier(BaseModel):
    """An identifier that did not survive validation, and why.

    Typed for the same two reasons as the citation above: an open object breaks
    the strict response schema, and "nothing is silently dropped" is only true
    if the reason is a field rather than whatever key happened to be written.
    """

    model_config = ConfigDict(extra="forbid")

    policy_id: Optional[str] = Field(default=None, description="The rejected identifier")
    reason: Optional[str] = Field(default=None, description="Machine-readable rejection code")
    detail: Optional[str] = Field(default=None, description="What to tell the customer")


class ControlMapping(BaseModel):
    """AI-generated mapping between external control and MCSB control."""

    # NOTE: model_config for this class lives with the schema example further
    # down; a second assignment here would be silently overridden by it, which
    # is exactly how the open-schema defect survived a first fix attempt.

    external_control_id: str = Field(..., description="External framework control ID")
    external_control_name: str = Field(..., description="External control name")

    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence that the selected azure_policy_ids (or, for non-"
            "enforceable controls, the coverage classification) genuinely "
            "match this control's literal text - scored against the actual "
            "Azure Policy definitions retrieved for it, not against any "
            "intermediate control taxonomy. See SYSTEM_PROMPT for the "
            "worked calibration examples this rubric is grounded in."
        ),
    )

    reasoning: str = Field(..., description="Explanation for why this mapping was chosen")

    azure_policy_ids: List[str] = Field(
        default_factory=list,
        description="Azure Policy definition GUIDs for this control"
    )

    mapping_type: Literal["exact", "partial", "conceptual", "none"] = Field(
        ...,
        description="Type of mapping relationship"
    )

    policy_category: Optional[str] = Field(
        default=None,
        description=(
            "Grouping label derived from the catalog `category` of the "
            "selected azure_policy_ids (e.g. 'Key Vault', 'Storage', "
            "'Network'), or the external control's own domain when no policy "
            "was selected. Always server-computed after the model responds - "
            "never model-authored - because it is a resolvable fact about the "
            "real catalog entries chosen, not a judgement call. Replaces the "
            "old mcsb_domain fallback."
        ),
    )

    control_type: Optional[str] = Field(
        default=None,
        description=(
            "Nature of the control carried from the extractor: Technical, Policy, "
            "Contractual, Management, Operational, or Governance"
        ),
    )

    coverage_category: Optional[
        Literal["A_AzurePolicy", "B_AzureConfig", "C_Process", "D_MicrosoftAttestation"]
    ] = Field(
        default=None,
        description=(
            "How this control is met — independent of who owns it (see "
            "responsibility). A_AzurePolicy: enforced by Azure Policy. "
            "B_AzureConfig: Azure/Entra configuration covers this partially; it "
            "still emits policies, and full coverage needs a step outside Azure "
            "Policy. C_Process: process/legal/HR/contractual. "
            "D_MicrosoftAttestation: Microsoft-operated and attested. A and B "
            "keep azure_policy_ids; C and D never do. None for legacy mappings "
            "(confidence-only gating)."
        ),
    )

    coverage_display: Optional[str] = Field(
        default=None,
        description=(
            "Analyst-facing name for coverage_category: 'Azure Policy enforced', "
            "'Azure/Entra config - partial', 'Process / organisational', "
            "'Microsoft attested'. The A_/B_/C_/D_ codes are identifiers only."
        ),
    )

    azure_enforceable: bool = Field(
        default=False,
        description=(
            "True when Azure covers this control — coverage_category is "
            "A_AzurePolicy or B_AzureConfig. B is partial coverage, not absent "
            "coverage, so it counts here and emits policies too."
        ),
    )

    coverage_gap: bool = Field(
        default=False,
        description=(
            "True when the control is in scope for Azure but no usable policy "
            "survived retrieval and validation. Reported explicitly so a recall "
            "failure cannot hide inside a category label."
        ),
    )

    attestation: Optional["AttestationCitation"] = Field(
        default=None,
        description=(
            "For D_MicrosoftAttestation: the resolved attestation citation, "
            "validated against the attestation catalog exactly as policy GUIDs "
            "are validated against the policy catalog. Carries the scheme, the "
            "basis kind (certification clause / audit-report criterion / "
            "published documentation), the clause and whether it was verified, "
            "the evidence document, where to get it and whether an NDA is "
            "required. A citation the customer cannot retrieve is not an answer."
        ),
    )

    attestation_gap: bool = Field(
        default=False,
        description=(
            "True when a D control's claim could not be grounded in any "
            "Microsoft attestation. The sovereign case: a requirement such as "
            "UAE national security clearance, which ISO 27001 and SOC 2 do not "
            "attest, must be escalated rather than absorbed into a generic "
            "Microsoft-attested pass a regulator would later disprove."
        ),
    )

    outside_step: Optional[str] = Field(
        default=None,
        description=(
            "For B_AzureConfig: the configuration step outside Azure Policy that "
            "full coverage still needs — an Entra Conditional Access policy, a "
            "Purview labelling scheme, Customer Lockbox. This is what makes B "
            "'partial' rather than 'uncovered': the customer is told what to go "
            "and configure, not merely that a shortfall exists."
        ),
    )

    dropped_policy_ids: List[DroppedPolicyIdentifier] = Field(
        default_factory=list,
        description=(
            "Candidate policy IDs discarded during validation, each with the "
            "reason (malformed GUID, absent from catalog, non-enforceable "
            "placeholder). Never silently dropped: a control that lost its "
            "enforcement to a typo must not look like one that never needed any."
        ),
    )

    coverage_reason: Optional[str] = Field(
        default=None,
        description=(
            "Substantive justification for the coverage classification: why the "
            "mapped policies satisfy the control, or why no Azure Policy can "
            "assert it and what evidence satisfies it instead."
        ),
    )

    responsibility: Optional[Literal["Customer", "Microsoft", "Shared"]] = Field(
        default=None,
        description=(
            "Who operates the thing the control governs. An axis independent of "
            "coverage_category: the category describes HOW a control is met, "
            "this describes WHO owns it. Microsoft-owned process controls are "
            "common and legitimate; None means the question was not answered, "
            "which is reported rather than guessed."
        ),
    )

    # -- Provenance ---------------------------------------------------------
    # The analyst workbook's Legend documents a "Verification Date & Source"
    # column. Provenance is the difference between an answer and a defensible
    # one: a regulator asking how the system knows a policy exists needs the
    # catalog snapshot it was checked against.
    verified_at: Optional[str] = Field(
        default=None, description="When this mapping was produced (UTC, ISO 8601)"
    )
    catalog_snapshot_date: Optional[str] = Field(
        default=None,
        description=(
            "When the Azure Policy catalog this mapping resolved against was "
            "captured. Empty when unknown, which is itself a finding."
        ),
    )
    verification_source: Optional[str] = Field(
        default=None, description="What verified this mapping's identifiers"
    )
    provenance_blocker: Optional[str] = Field(
        default=None,
        description=(
            "Why this mapping cannot yet be presented as current — e.g. an "
            "undated catalog snapshot. The Legend's 'Blocker' column."
        ),
    )

    evidence_source: Optional[str] = Field(
        default=None,
        description=(
            "Where the evidence for a non-enforceable control lives — a Microsoft "
            "attestation (e.g. 'ISO/IEC 27001:2022 clause 9.2', SOC 2 report) for "
            "D_MicrosoftAttestation, or the customer's GRC artefact for C_Process."
        ),
    )

    enforcement_plane: Optional[str] = Field(
        default=None,
        description=(
            "Where the control is enforced, derived from the mapped policies' "
            "effects: 'SLZ (deploy-time)', 'Defender (run-time)', both, or "
            "'None (manual control)' when no policy applies."
        ),
    )

    policy_effects: List[str] = Field(
        default_factory=list,
        description=(
            "Effects of the mapped policy definitions (Deny, Audit, "
            "AuditIfNotExists, DeployIfNotExists, Modify). Resolved from the "
            "catalog, never model-generated."
        ),
    )

    available_effects: List[str] = Field(
        default_factory=list,
        description=(
            "Effects the mapped definitions permit, where they are "
            "parameterised. Distinct from policy_effects, which is what applies "
            "by default: a policy defaulting to Audit but permitting Deny can be "
            "escalated from reporting to blocking, and that choice belongs to "
            "the reviewer rather than to this engine."
        ),
    )

    policy_type: Optional[str] = Field(
        default=None,
        description="'Built-in' when policies are mapped, 'N/A' otherwise.",
    )

    defender_recommendations: List[str] = Field(
        default_factory=list,
        description=(
            "Always empty today. Reserved for real Microsoft Defender for "
            "Cloud recommendations; the engine does not query a live "
            "subscription at mapping time, so nothing is populated here "
            "rather than an invented recommendation being shown as if it "
            "were live data. See docs/BACKLOG.md B4."
        ),
    )

    # Sovereignty Landing Zone mapping (populated when SLZ context is available)
    sovereignty: Optional[SovereigntyMapping] = Field(
        default=None,
        description="Sovereign Landing Zone mapping with recommended level, objectives, and policies"
    )

    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            "external_control_id": "SAMA-AC-01",
            "external_control_name": "Strong Authentication",
            "confidence_score": 0.92,
            "reasoning": "Both controls focus on enforcing MFA and strong authentication mechanisms",
            "azure_policy_ids": ["4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"],
            "mapping_type": "exact",
            "policy_category": "Identity",
            "control_type": "Technical",
            "coverage_category": "A_AzurePolicy",
            "azure_enforceable": True,
            "coverage_reason": (
                "MFA enforcement on privileged accounts is a directly evaluable "
                "Entra ID configuration, so Azure Policy can audit conformance "
                "continuously rather than by sampling."
            ),
            "responsibility": "Customer",
            "enforcement_plane": "Defender (run-time)",
            "policy_effects": ["AuditIfNotExists"],
            "policy_type": "Built-in",
            "defender_recommendations": []
        }
    })


class MappingBatch(BaseModel):
    """Batch of control mappings for multiple controls."""

    mappings: List[ControlMapping] = Field(..., description="List of control mappings")
    unmapped_controls: List[str] = Field(
        default_factory=list,
        description="Control IDs that could not be mapped"
    )
    summary: str = Field(..., description="Summary of mapping results")
    total_controls: int = Field(..., description="Total number of controls processed")
    mapped_count: int = Field(..., description="Number of successfully mapped controls")
    avg_confidence: float = Field(..., description="Average confidence score")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "mappings": [],
            "unmapped_controls": [],
            "summary": "Successfully mapped 36 out of 36 controls with average confidence 0.87",
            "total_controls": 36,
            "mapped_count": 36,
            "avg_confidence": 0.87
        }
    })


class MappingJob(BaseModel):
    """Tracking model for async mapping jobs."""

    job_id: str = Field(..., description="Unique job identifier")
    framework_name: str = Field(..., description="Framework being mapped")
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        ...,
        description="Current job status"
    )
    progress: int = Field(0, ge=0, le=100, description="Progress percentage")
    total_controls: int = Field(..., description="Total controls to map")
    mapped_controls: int = Field(0, description="Controls mapped so far")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[MappingBatch] = None
    activity: List[dict[str, str]] = Field(
        default_factory=list,
        description="Bounded, user-safe execution events for this mapping job",
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "framework_name": "SAMA Cybersecurity",
            "status": "in_progress",
            "progress": 45,
            "total_controls": 36,
            "mapped_controls": 16,
            "created_at": "2026-01-20T10:00:00Z"
        }
    })


def record_mapping_activity(
    job: MappingJob,
    message: str,
    level: str = "INFO",
) -> None:
    """Append a bounded, user-safe execution event to a mapping job."""
    job.activity.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": level,
            "message": message,
        }
    )
    job.activity = job.activity[-_MAX_ACTIVITY_ENTRIES:]


class MappingRequest(BaseModel):
    """Request model for initiating control mapping."""

    framework_name: str = Field(..., description="Name of framework")
    controls: List[ExternalControl] = Field(..., description="Controls to map")
    batch_mode: bool = Field(True, description="Process in batch mode")
    concurrency: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Requested maximum concurrent AI mapping calls",
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "framework_name": "SAMA Cybersecurity",
            "controls": [],
            "batch_mode": True
        }
    })
