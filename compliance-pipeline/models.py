"""
Pydantic models for the PDF-to-Initiative compliance automation pipeline.
These models define the structured outputs expected from Azure OpenAI.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


# ── Stage 1: Extracted Controls from PDF ──────────────────────────────────────

class ExtractedControl(BaseModel):
    """A single control extracted from a compliance PDF by the LLM."""

    control_id: str = Field(
        ..., description="Control identifier from the document (e.g., 'TR-01', 'POL-03')"
    )
    control_title: str = Field(
        ..., description="Short title of the control"
    )
    control_description: str = Field(
        ..., description="Full description of the control requirement"
    )
    domain: str = Field(
        ..., description="Security/compliance domain (e.g., Network Security, Identity & Access, Data Protection)"
    )
    control_type: Literal["Technical", "Policy", "Contractual", "Management", "Operational", "Governance"] = Field(
        ..., description="Category of the control"
    )
    sub_controls: List[str] = Field(
        default_factory=list,
        description="List of sub-requirements or sub-controls if any"
    )


class ControlExtractionResult(BaseModel):
    """Complete result of LLM-based control extraction from a PDF."""

    framework_name: str = Field(
        ..., description="Name of the compliance framework identified in the document"
    )
    framework_version: Optional[str] = Field(
        None, description="Version of the framework if identified"
    )
    issuing_authority: Optional[str] = Field(
        None, description="Organization that issued this framework"
    )
    country_or_region: Optional[str] = Field(
        None, description="Country or region the framework applies to"
    )
    controls: List[ExtractedControl] = Field(
        ..., description="List of all controls extracted from the document"
    )
    summary: str = Field(
        ..., description="Brief summary of the framework's purpose and scope"
    )


# ── Stage 2: Azure Policy Mappings ────────────────────────────────────────────

class AzurePolicyMapping(BaseModel):
    """A single Azure Policy mapping for a control."""

    policy_definition_id: str = Field(
        ..., description="Azure Policy Definition GUID (e.g., '4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b')"
    )
    policy_name: str = Field(
        ..., description="Display name of the Azure Policy"
    )
    policy_description: str = Field(
        ..., description="Brief description of what this policy enforces"
    )
    relevance: Literal["high", "medium", "low"] = Field(
        ..., description="How relevant this policy is to the control"
    )


class ControlPolicyMapping(BaseModel):
    """Complete mapping from a single control to Azure Policies."""

    control_id: str = Field(
        ..., description="The control ID being mapped"
    )
    control_title: str = Field(
        ..., description="The control title"
    )
    domain: str = Field(
        ..., description="Security domain"
    )
    mcsb_control_id: str = Field(
        ..., description="Best matching MCSB control ID (e.g., 'IM-1', 'NS-1', 'DP-3')"
    )
    mcsb_control_name: str = Field(
        ..., description="Name of the matched MCSB control"
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Confidence of this mapping (0.0-1.0)"
    )
    mapping_rationale: str = Field(
        ..., description="Explanation of why this mapping was chosen"
    )
    azure_policies: List[AzurePolicyMapping] = Field(
        default_factory=list,
        description="Azure Policy definitions that implement this control"
    )
    defender_recommendations: List[str] = Field(
        default_factory=list,
        description="Relevant Microsoft Defender for Cloud recommendations"
    )
    is_automatable: bool = Field(
        ..., description="Whether this control can be enforced/audited via Azure Policy"
    )
    manual_attestation_note: Optional[str] = Field(
        None, description="Note about manual steps required if not fully automatable"
    )


class BatchPolicyMappingResult(BaseModel):
    """Result of mapping a batch of controls to Azure Policies."""

    mappings: List[ControlPolicyMapping] = Field(
        ..., description="List of all control-to-policy mappings"
    )


# ── Stage 3: Validated Initiative ─────────────────────────────────────────────

class ValidationIssue(BaseModel):
    """A validation issue found in the mapping."""

    severity: Literal["error", "warning", "info"] = Field(
        ..., description="Severity level"
    )
    control_id: str = Field(
        ..., description="Control ID this issue relates to"
    )
    message: str = Field(
        ..., description="Description of the issue"
    )
    suggestion: Optional[str] = Field(
        None, description="Suggested fix"
    )


class ValidationReport(BaseModel):
    """Report from initiative validation."""

    is_valid: bool = Field(..., description="Whether the initiative passes validation")
    total_controls: int = Field(..., description="Total controls in the initiative")
    automatable_controls: int = Field(..., description="Controls with Azure Policy mappings")
    manual_controls: int = Field(..., description="Controls requiring manual attestation")
    unique_policies: int = Field(..., description="Number of unique Azure Policy definitions")
    avg_confidence: float = Field(..., description="Average mapping confidence score")
    issues: List[ValidationIssue] = Field(default_factory=list, description="Validation issues")


# ── Stage 4: Initiative Output Artifacts ──────────────────────────────────────

class InitiativeGroup(BaseModel):
    """A policy definition group in the initiative (maps to a control)."""

    name: str = Field(..., description="Group name (sanitized control ID)")
    displayName: str = Field(..., description="Display name with full control reference")
    description: str = Field(..., description="Control description")


class PolicyDefinitionRef(BaseModel):
    """A policy definition reference within the initiative."""

    PolicyDefinitionReferenceId: str = Field(
        ..., description="Unique reference ID for this policy in the initiative"
    )
    PolicyDefinitionId: str = Field(
        ..., description="Full Azure Policy definition resource ID"
    )
    Parameters: dict = Field(default_factory=dict, description="Parameter overrides")
    GroupNames: List[str] = Field(
        ..., description="List of group names this policy belongs to"
    )


class InitiativeDefinition(BaseModel):
    """Complete Azure Policy Initiative (Policy Set Definition) for Defender for Cloud."""

    properties: dict = Field(..., description="The full initiative properties")


class PipelineResult(BaseModel):
    """Final result from the complete pipeline execution."""

    framework_name: str
    framework_version: Optional[str] = None
    issuing_authority: Optional[str] = None
    country_or_region: Optional[str] = None
    
    total_controls_extracted: int
    total_policies_mapped: int
    automatable_controls: int
    manual_controls: int
    avg_confidence: float
    
    validation: ValidationReport
    
    output_directory: str
    files_generated: List[str]
    
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
