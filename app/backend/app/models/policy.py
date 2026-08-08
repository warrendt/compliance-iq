"""
Pydantic models for Azure Policy initiatives.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from app.models.mapping import ControlMapping


class PolicyParameterSpec(BaseModel):
    """Schema for a single required (no-default) built-in policy parameter.

    Surfaced to the UI so it can prompt the operator for a concrete value,
    letting a parameterized built-in be included with user-supplied literals
    instead of being excluded from the initiative.
    """

    type: str = Field("String", description="ARM parameter type (String, Array, Integer, Boolean, ...)")
    description: Optional[str] = Field(None, description="Human-readable help text from the built-in's metadata")
    allowed_values: Optional[List[Any]] = Field(
        None, description="Permitted values, when the built-in constrains them (render as a dropdown)"
    )


class ParameterizedPolicyRequirement(BaseModel):
    """A built-in that needs operator-supplied parameter values to be included.

    Built-ins with a required parameter that has no ``defaultValue`` cannot live
    in a custom policy set unless a value is supplied (ARM rejects the set
    definition with ``MissingPolicyParameter``). Rather than silently drop them,
    the generator returns this so the UI can collect the values and re-generate
    with them baked in as literal reference parameters.
    """

    policy_id: str = Field(..., description="Built-in policy definition GUID")
    display_name: str = Field(..., description="Built-in display name")
    control_ids: List[str] = Field(
        default_factory=list,
        description="External framework control IDs that mapped to this built-in",
    )
    parameters: Dict[str, PolicyParameterSpec] = Field(
        default_factory=dict,
        description="Required parameters (name -> schema) the operator must supply",
    )


class PolicyDefinitionReference(BaseModel):
    """Reference to an Azure Policy definition within an initiative."""

    policy_definition_id: str = Field(
        ...,
        description="Full resource ID of the policy definition"
    )
    policy_definition_reference_id: str = Field(
        ...,
        description="Unique reference ID (typically the control ID)"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameter values for this policy"
    )
    group_names: List[str] = Field(
        default_factory=list,
        description="Names of the policyDefinitionGroups (controls) this policy belongs to"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "policyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b",
            "policyDefinitionReferenceId": "SAMA-AC-01",
            "parameters": {},
            "groupNames": ["SAMA_AC_01"]
        }
    })


class PolicyDefinitionGroup(BaseModel):
    """A control grouping inside a Regulatory Compliance initiative.

    Grouping is what turns a flat policy set definition into a
    Regulatory-Compliance-style initiative: each group represents one control of
    the source framework and the member policies reference it via ``groupNames``.
    """

    name: str = Field(..., description="Unique group name (sanitized control ID)")
    display_name: Optional[str] = Field(
        None, description="Human-readable group name (control ID + title)"
    )
    category: Optional[str] = Field(
        None, description="Compliance domain / category for this control"
    )
    description: Optional[str] = Field(None, description="Group description")

    def to_azure_json(self) -> Dict[str, Any]:
        """Emit the Azure ``policyDefinitionGroups`` entry (omitting empty fields)."""
        group: Dict[str, Any] = {"name": self.name}
        if self.display_name:
            group["displayName"] = self.display_name
        if self.category:
            group["category"] = self.category
        if self.description:
            group["description"] = self.description
        return group


class PolicyInitiativeMetadata(BaseModel):
    """Metadata for Azure Policy initiative."""

    category: str = Field(default="Regulatory Compliance")
    source: str = Field(default="ComplianceIQ AI Mapping Agent")
    version: str = Field(default="1.0.0")
    generated_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    framework_name: Optional[str] = None
    framework_version: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "category": "Regulatory Compliance",
            "source": "ComplianceIQ AI Mapping Agent",
            "version": "1.0.0",
            "generatedDate": "2026-01-20T10:00:00Z",
            "frameworkName": "SAMA Cybersecurity Framework",
            "frameworkVersion": "v1.0"
        }
    })


class PolicyInitiativeProperties(BaseModel):
    """Properties of an Azure Policy initiative."""

    display_name: str = Field(..., description="Initiative display name")
    description: str = Field(..., description="Initiative description")
    metadata: PolicyInitiativeMetadata = Field(..., description="Initiative metadata")
    policy_definitions: List[PolicyDefinitionReference] = Field(
        ...,
        description="List of policy definitions in this initiative"
    )
    policy_definition_groups: List[PolicyDefinitionGroup] = Field(
        default_factory=list,
        description="Control groupings that make this a Regulatory Compliance initiative"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "displayName": "SAMA Cybersecurity Framework Compliance",
            "description": "AI-generated policy initiative for SAMA framework compliance",
            "metadata": {},
            "policyDefinitions": []
        }
    })


class PolicyInitiative(BaseModel):
    """Complete Azure Policy initiative definition."""

    properties: PolicyInitiativeProperties = Field(..., description="Initiative properties")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "properties": {
                "displayName": "SAMA Compliance Initiative",
                "description": "AI-generated initiative",
                "metadata": {
                    "category": "Regulatory Compliance"
                },
                "policyDefinitions": []
            }
        }
    })

    def to_azure_json(self) -> Dict[str, Any]:
        """
        Convert to Azure Policy JSON format.

        Returns:
            Dict: Azure Policy initiative JSON
        """
        policy_definitions: List[Dict[str, Any]] = []
        for pd in self.properties.policy_definitions:
            entry: Dict[str, Any] = {
                "policyDefinitionId": pd.policy_definition_id,
                "policyDefinitionReferenceId": pd.policy_definition_reference_id,
                "parameters": pd.parameters,
            }
            if pd.group_names:
                entry["groupNames"] = pd.group_names
            policy_definitions.append(entry)

        properties: Dict[str, Any] = {
            "displayName": self.properties.display_name,
            "description": self.properties.description,
            "metadata": {
                "category": self.properties.metadata.category,
                # Onboards the initiative to Microsoft Defender for Cloud so it
                # surfaces under Regulatory compliance (evaluated 24-48h after
                # assignment). Documented flag; see
                # learn.microsoft.com/azure/defender-for-cloud/create-custom-recommendations.
                "ASC": "true",
                "source": self.properties.metadata.source,
                "version": self.properties.metadata.version,
                "generatedDate": self.properties.metadata.generated_date.isoformat(),
                "frameworkName": self.properties.metadata.framework_name,
                "frameworkVersion": self.properties.metadata.framework_version
            },
            "policyDefinitions": policy_definitions,
        }

        if self.properties.policy_definition_groups:
            properties["policyDefinitionGroups"] = [
                group.to_azure_json()
                for group in self.properties.policy_definition_groups
            ]

        return {"properties": properties}


class PolicyGenerationRequest(BaseModel):
    """Request model for generating policy initiative."""

    framework_name: str = Field(..., description="Framework name")
    framework_version: Optional[str] = Field(None, description="Framework version")
    mappings: List["ControlMapping"] = Field(..., description="List of control mappings")
    include_all_policies: bool = Field(
        True,
        description="Include all mapped policies or only high-confidence ones"
    )
    min_confidence_threshold: float = Field(
        0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score to include a mapping"
    )
    enforce_mode: bool = Field(
        False,
        description="When False (default), assignments use DoNotEnforce (audit-only). "
                    "When True, assignments use Default (enforcement enabled)."
    )
    policy_parameter_values: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Operator-supplied values for parameterized built-ins, keyed by "
                    "policy definition GUID then parameter name "
                    "(e.g. {\"<guid>\": {\"vaultName\": \"rsv-prod\"}}). When all of a "
                    "built-in's required parameters are supplied, it is included with "
                    "those values baked in as literal reference parameters instead of "
                    "being excluded."
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "framework_name": "SAMA Cybersecurity",
            "framework_version": "v1.0",
            "mappings": [],
            "include_all_policies": True,
            "min_confidence_threshold": 0.7,
            "enforce_mode": False
        }
    })


class ManualControlEntry(BaseModel):
    """A control Azure cannot address, routed to the manual register.

    Only ``C_Process`` and ``D_MicrosoftAttestation`` appear here.
    ``B_AzureConfig`` is *partial* Azure coverage — it emits policies and enters
    the initiative — so listing it as a manual control would tell the customer
    to do work Azure is already doing.

    These controls are deliberately excluded from the generated initiative
    (their ``azure_policy_ids`` are empty) and surfaced here as a completely
    separate section so operators can track them for manual attestation.
    """

    control_id: str = Field(..., description="External framework control ID")
    control_name: str = Field("", description="External framework control name")
    control_type: str = Field(
        "", description="Nature of the control (Policy/Contractual/Operational/…)"
    )
    coverage_category: str = Field(
        ...,
        description="Coverage taxonomy: C_Process or D_MicrosoftAttestation",
    )
    coverage_display: str = Field(
        "",
        description=(
            "Analyst-facing category name: 'Process / organisational' or "
            "'Microsoft attested'"
        ),
    )
    mcsb_control_id: str = Field("", description="Associated MCSB control ID, if any")
    responsibility: str = Field(
        "",
        description=(
            "Who owns the control — Customer, Microsoft or Shared. Independent "
            "of coverage_category: a process control may be Microsoft-owned."
        ),
    )
    evidence_source: str = Field(
        "",
        description=(
            "Where the evidence lives — a Microsoft attestation clause for "
            "D_MicrosoftAttestation, or the customer's GRC artefact for C_Process"
        ),
    )
    enforcement_plane: str = Field(
        "", description="Where the control is enforced; 'None (manual control)' here"
    )
    attestation_status: str = Field(
        "",
        description=(
            "For D controls: 'grounded' (the clause exists and its title was "
            "read from Azure's published metadata), 'scheme_only' (the scheme is "
            "real but the cited clause could not be verified) or 'unattested' "
            "(nothing grounds the claim). Empty for C controls."
        ),
    )
    attestation_basis: str = Field(
        "",
        description=(
            "certification_clause, audit_report_criterion, published_documentation "
            "or none. 'Certified against ISO 27001' and 'tested in a SOC 2 report' "
            "are different claims and an auditor treats them differently."
        ),
    )
    attestation_citation: str = Field(
        "", description="The validated citation, or empty when nothing was grounded"
    )
    attestation_document: str = Field(
        "", description="The evidence document to obtain (certificate, audit report)"
    )
    attestation_location: str = Field(
        "", description="Where the document lives (Service Trust Portal, Microsoft Learn)"
    )
    attestation_access: str = Field(
        "",
        description=(
            "Access condition — SOC reports need a work account and the Microsoft "
            "NDA; ISO certificates do not. Sending an auditor to a document they "
            "cannot open is a failed answer."
        ),
    )
    attestation_gap: bool = Field(
        False,
        description=(
            "True when no Microsoft attestation covers this requirement. Must be "
            "escalated rather than reported as covered."
        ),
    )
    reason: str = Field(
        ..., description="Why the control is not addressable by Azure"
    )


class AttestationGapEntry(BaseModel):
    """A Microsoft-operated control that no Microsoft attestation grounds.

    The sovereign case, and the most consequential row this product emits. The
    analyst workbook's control 3.1.3.4 requires UAE national security clearance
    for operations personnel; ISO/IEC 27001 and SOC 2 attest *screening*, not
    UAE clearance, so it is a gap to escalate commercially. Silently rolling it
    into a "Microsoft attested" pass would hand the customer a false answer on
    exactly the requirement their regulator scrutinises hardest.
    """

    control_id: str = Field(..., description="External framework control ID")
    control_name: str = Field("", description="External framework control name")
    claim: str = Field("", description="The unvalidated attestation claim that was rejected")
    reason: str = Field("", description="Why it could not be grounded")
    action: str = Field("", description="What the customer must do instead")


class CoverageGapEntry(BaseModel):
    """A control in scope for Azure for which no usable policy was found.

    Distinct from a manual control: Azure *should* be able to address this, but
    retrieval returned nothing, or everything it returned failed validation.
    Reported explicitly so a recall failure cannot be mistaken for a considered
    category judgement — the exact confusion the previous A/B derivation caused.
    """

    control_id: str = Field(..., description="External framework control ID")
    control_name: str = Field("", description="External framework control name")
    coverage_category: str = Field("", description="A_AzurePolicy or B_AzureConfig")
    coverage_display: str = Field("", description="Analyst-facing category name")
    outside_step: str = Field(
        "",
        description="Named configuration step outside Azure Policy, if one was identified",
    )
    rejected_policy_ids: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Candidate identifiers discarded in validation, with reasons",
    )
    reason: str = Field("", description="Why this control has no usable policy")
    policy_type: str = Field(
        "",
        description=(
            "'Custom definition required' when no built-in covers the control. "
            "Distinct from 'N/A', which means Azure Policy was never the right "
            "instrument for it."
        ),
    )
    remediation: str = Field(
        "",
        description=(
            "The named next step. A gap without one is a complaint; with one it "
            "is work someone can pick up."
        ),
    )


class PolicyGenerationResponse(BaseModel):
    """Response model for policy generation."""

    initiative: PolicyInitiative = Field(..., description="Generated policy initiative")
    total_controls: int = Field(..., description="Total controls processed")
    included_policies: int = Field(..., description="Number of policies included")
    excluded_policies: int = Field(..., description="Number of policies excluded (low confidence)")
    invalid_policies: int = Field(
        0,
        description="Number of policy definition IDs dropped because they were not valid Azure Policy GUIDs"
    )
    excluded_builtin_policies: int = Field(
        0,
        description="Number of built-in policies dropped because they cannot be part of a custom policy set (e.g. System Policy)"
    )
    excluded_parameterized_policies: int = Field(
        0,
        description="Number of built-in policies dropped because they require a parameter value with no default (e.g. vault name/region), which ARM would reject in a custom policy set"
    )
    parameterized_requirements: List[ParameterizedPolicyRequirement] = Field(
        default_factory=list,
        description="Excluded parameterized built-ins and their required-parameter schemas, so the UI can collect values and re-generate with them included"
    )
    warnings: List[str] = Field(default_factory=list, description="Warning messages")

    manual_controls: List[ManualControlEntry] = Field(
        default_factory=list,
        description="Controls Azure cannot address (C_Process, "
        "D_MicrosoftAttestation) — excluded from the initiative and listed here "
        "as a separate manual-attestation register",
    )
    coverage_gaps: List[CoverageGapEntry] = Field(
        default_factory=list,
        description="Controls in scope for Azure for which no usable policy was "
        "found. Reported separately from manual controls so a retrieval failure "
        "is never presented as a category judgement",
    )
    dropped_policy_ids: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Every candidate policy identifier discarded during "
        "validation, with the control it came from and the reason (malformed "
        "GUID, absent from the catalog, non-enforceable placeholder). Nothing is "
        "dropped silently: a control that lost enforcement to a typo must not "
        "look identical to one that never needed any",
    )
    attestation_gaps: List[AttestationGapEntry] = Field(
        default_factory=list,
        description="Microsoft-operated controls that no Microsoft attestation "
        "grounds. Excluded from the compliant count and surfaced for commercial "
        "escalation, because a sovereign requirement Microsoft does not attest "
        "must never be absorbed into a generic attested pass",
    )
    coverage_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-coverage-category counts, the Azure-covered share "
        "(A + B) and the compliant share (A + B + grounded D), plus "
        "coverage_gaps, attestation_gaps and dropped_policy_ids counts. "
        "Ungrounded D controls are deliberately excluded from 'compliant': the "
        "category is a claim, only a validated citation is evidence",
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "initiative": {},
            "total_controls": 36,
            "included_policies": 34,
            "excluded_policies": 2,
            "invalid_policies": 0,
            "warnings": ["2 controls excluded due to confidence < 0.7"]
        }
    })
