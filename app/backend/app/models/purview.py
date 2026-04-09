"""
Pydantic models for Microsoft Purview compliance configuration.
Covers Sensitivity Labels, DLP policies, Retention Labels, eDiscovery,
and Data Map configurations managed via Microsoft Graph and Purview APIs.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class PurviewConfigType(str, Enum):
    """Types of Microsoft Purview configurations."""
    SENSITIVITY_LABEL = "sensitivity_label"     # Sensitivity labels & policies
    DLP_POLICY = "dlp_policy"                   # Data Loss Prevention policies
    RETENTION_LABEL = "retention_label"         # Retention labels & policies
    RETENTION_POLICY = "retention_policy"       # Retention policies
    EDISCOVERY = "ediscovery"                   # eDiscovery cases & holds
    INFORMATION_BARRIER = "information_barrier" # Information barriers
    RECORDS_MANAGEMENT = "records_management"   # Records management


class SensitivityLabelScope(str, Enum):
    """Scopes where sensitivity labels can be applied."""
    FILES_EMAILS = "files_emails"
    GROUPS_SITES = "groups_sites"
    SCHEMATIZED_DATA = "schematized_data"
    MEETINGS = "meetings"


class SensitivityLabelAction(BaseModel):
    """An action enforced by a sensitivity label."""

    action_type: str = Field(..., description="Type of action (encryption, watermark, header, footer)")
    settings: Dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific settings"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "action_type": "encryption",
            "settings": {
                "encryptionEnabled": True,
                "protectionType": "template",
                "rightsDefinitions": [
                    {"userRights": "VIEW,EDIT", "users": "all-authenticated"}
                ]
            }
        }
    })


class SensitivityLabel(BaseModel):
    """A Microsoft Purview sensitivity label definition."""

    name: str = Field(..., description="Label identifier")
    display_name: str = Field(..., description="Human-readable label name")
    description: str = Field(default="", description="Label description")
    tooltip: str = Field(default="", description="Tooltip shown to users")
    color: str = Field(default="", description="Label color (hex code)")
    priority: int = Field(default=0, description="Label priority (higher = more sensitive)")
    scope: List[SensitivityLabelScope] = Field(
        default_factory=lambda: [SensitivityLabelScope.FILES_EMAILS],
        description="Where this label can be applied"
    )
    actions: List[SensitivityLabelAction] = Field(
        default_factory=list,
        description="Protection actions enforced by this label"
    )
    auto_labeling_conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions for automatic label application"
    )
    parent_label: Optional[str] = Field(
        None,
        description="Parent label name for sub-labels"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "confidential-financial",
            "display_name": "Confidential - Financial",
            "description": "Financial data requiring encryption",
            "color": "#FF0000",
            "priority": 3,
            "scope": ["files_emails"],
            "actions": [
                {"action_type": "encryption", "settings": {"encryptionEnabled": True}}
            ]
        }
    })


class RetentionLabel(BaseModel):
    """A Microsoft Purview retention label definition."""

    name: str = Field(..., description="Label identifier")
    display_name: str = Field(..., description="Human-readable label name")
    description: str = Field(default="", description="Label description")
    retention_days: int = Field(
        default=365,
        description="Number of days to retain content"
    )
    retention_action: str = Field(
        default="keep",
        description="Action after retention period (keep, delete, keepAndDelete)"
    )
    is_record: bool = Field(
        default=False,
        description="Whether content should be marked as a record"
    )
    regulatory_record: bool = Field(
        default=False,
        description="Whether content is a regulatory record (cannot be relabeled)"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "financial-records-7y",
            "display_name": "Financial Records - 7 Years",
            "description": "Retain financial records for 7 years per regulatory requirements",
            "retention_days": 2555,
            "retention_action": "keepAndDelete",
            "is_record": True
        }
    })


class PurviewDLPPolicy(BaseModel):
    """A Microsoft Purview DLP policy definition."""

    name: str = Field(..., description="Policy identifier")
    display_name: str = Field(..., description="Human-readable policy name")
    description: str = Field(default="", description="Policy description")
    locations: List[str] = Field(
        default_factory=lambda: ["Exchange", "SharePoint", "OneDrive", "Teams"],
        description="M365 locations where the policy applies"
    )
    sensitive_info_types: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Sensitive information types to detect"
    )
    rules: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Policy rules with conditions and actions"
    )
    mode: str = Field(
        default="TestWithNotifications",
        description="Enforcement mode"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "purview-dlp-pii",
            "display_name": "Purview PII Protection",
            "locations": ["Exchange", "SharePoint", "OneDrive"],
            "sensitive_info_types": [
                {"name": "Credit Card Number", "id": "50842eb7-edc8-4019-85dd-5a5c1f2bb085"}
            ],
            "mode": "TestWithNotifications"
        }
    })


class PurviewControlMapping(BaseModel):
    """Mapping between a compliance control and Purview configurations."""

    external_control_id: str = Field(..., description="External framework control ID")
    external_control_name: str = Field(..., description="External control name")
    purview_config_type: PurviewConfigType = Field(
        ...,
        description="Type of Purview configuration"
    )
    sensitivity_labels: List[str] = Field(
        default_factory=list,
        description="Recommended sensitivity labels"
    )
    retention_labels: List[str] = Field(
        default_factory=list,
        description="Recommended retention labels"
    )
    dlp_policies: List[str] = Field(
        default_factory=list,
        description="Recommended DLP policies"
    )
    graph_api_endpoint: str = Field(
        default="",
        description="Microsoft Graph API endpoint"
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Mapping confidence score"
    )
    reasoning: str = Field(default="", description="Why this mapping was chosen")
    implementation_guide: str = Field(
        default="",
        description="Step-by-step implementation guidance"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "external_control_id": "SAMA-DP-02",
            "external_control_name": "Data Retention",
            "purview_config_type": "retention_label",
            "retention_labels": ["Financial Records - 7 Years"],
            "confidence_score": 0.90,
            "reasoning": "Data retention control maps to Purview retention label policies"
        }
    })


class PurviewConfigPackage(BaseModel):
    """A complete Purview configuration package for a compliance framework."""

    framework_name: str = Field(..., description="Compliance framework name")
    framework_version: Optional[str] = Field(None, description="Framework version")
    sensitivity_labels: List[SensitivityLabel] = Field(
        default_factory=list,
        description="Generated sensitivity labels"
    )
    retention_labels: List[RetentionLabel] = Field(
        default_factory=list,
        description="Generated retention labels"
    )
    dlp_policies: List[PurviewDLPPolicy] = Field(
        default_factory=list,
        description="Generated DLP policies"
    )
    mappings: List[PurviewControlMapping] = Field(
        default_factory=list,
        description="Control-to-configuration mappings"
    )
    total_controls: int = Field(default=0, description="Total controls processed")
    mapped_controls: int = Field(default=0, description="Controls with Purview mappings")
    deployment_script: str = Field(
        default="",
        description="PowerShell script for deploying via Microsoft Graph"
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "framework_name": "SAMA Cybersecurity Framework",
            "sensitivity_labels": [],
            "retention_labels": [],
            "dlp_policies": [],
            "mappings": [],
            "total_controls": 36,
            "mapped_controls": 22
        }
    })


class PurviewGenerationRequest(BaseModel):
    """Request model for generating Microsoft Purview configurations."""

    framework_name: str = Field(..., description="Framework name")
    framework_version: Optional[str] = Field(None, description="Framework version")
    config_types: List[PurviewConfigType] = Field(
        default_factory=lambda: [
            PurviewConfigType.SENSITIVITY_LABEL,
            PurviewConfigType.DLP_POLICY,
            PurviewConfigType.RETENTION_LABEL,
        ],
        description="Types of Purview configurations to generate"
    )
    enforcement_mode: str = Field(
        default="TestWithNotifications",
        description="Default enforcement mode for generated policies"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "framework_name": "SAMA Cybersecurity",
            "config_types": ["sensitivity_label", "dlp_policy", "retention_label"],
            "enforcement_mode": "TestWithNotifications"
        }
    })
