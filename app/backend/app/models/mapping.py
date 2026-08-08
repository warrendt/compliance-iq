"""
Pydantic models for control mappings.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal, Optional
from datetime import datetime, timezone
from app.models.sovereignty import SovereigntyMapping
from app.models.control import ExternalControl

_MAX_ACTIVITY_ENTRIES = 50


class ControlMapping(BaseModel):
    """AI-generated mapping between external control and MCSB control."""

    external_control_id: str = Field(..., description="External framework control ID")
    external_control_name: str = Field(..., description="External control name")

    mcsb_control_id: str = Field(..., description="Mapped MCSB control ID")
    mcsb_control_name: str = Field(..., description="Mapped MCSB control name")
    mcsb_domain: str = Field(..., description="MCSB security domain")

    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this mapping (0.0 to 1.0)"
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
            "How this control is covered. A_AzurePolicy: enforceable via Azure "
            "Policy (only category that keeps azure_policy_ids). B_AzureConfig: "
            "Azure-configurable but not via policy. C_Process: process/legal/HR/"
            "contractual. D_MicrosoftAttestation: Microsoft-operated. None for "
            "legacy mappings (confidence-only gating)."
        ),
    )

    azure_enforceable: bool = Field(
        default=False,
        description="True only when coverage_category == 'A_AzurePolicy'",
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
            "Who owns the control under the shared responsibility model. "
            "'Microsoft' controls are attested, not customer-configurable."
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
        description="Defender for Cloud recommendations"
    )

    # Sovereignty Landing Zone mapping (populated when SLZ context is available)
    sovereignty: Optional[SovereigntyMapping] = Field(
        default=None,
        description="Sovereign Landing Zone mapping with recommended level, objectives, and policies"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "external_control_id": "SAMA-AC-01",
            "external_control_name": "Strong Authentication",
            "mcsb_control_id": "IM-6",
            "mcsb_control_name": "Use strong authentication controls",
            "mcsb_domain": "Identity Management",
            "confidence_score": 0.92,
            "reasoning": "Both controls focus on enforcing MFA and strong authentication mechanisms",
            "azure_policy_ids": ["4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"],
            "mapping_type": "exact",
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
            "defender_recommendations": ["Enable MFA for all users"]
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
