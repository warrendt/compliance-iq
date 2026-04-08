"""
Pydantic models for Microsoft 365 compliance policies.
Covers DLP policies, Conditional Access, Device Compliance,
and Information Protection policies managed via Microsoft Graph API.
"""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class M365PolicyType(str, Enum):
    """Types of Microsoft 365 compliance policies."""
    DLP = "dlp"                             # Data Loss Prevention
    CONDITIONAL_ACCESS = "conditional_access" # Conditional Access policies
    DEVICE_COMPLIANCE = "device_compliance"  # Intune device compliance
    INFORMATION_PROTECTION = "information_protection"  # Information barriers
    COMMUNICATION_COMPLIANCE = "communication_compliance"  # Communication policies
    INSIDER_RISK = "insider_risk"            # Insider risk management


class M365ServiceScope(str, Enum):
    """Microsoft 365 services where policies can be applied."""
    EXCHANGE = "exchange"
    SHAREPOINT = "sharepoint"
    ONEDRIVE = "onedrive"
    TEAMS = "teams"
    ENDPOINTS = "endpoints"
    POWER_BI = "power_bi"
    ALL = "all"


class M365PolicyRule(BaseModel):
    """A rule within a Microsoft 365 compliance policy."""

    name: str = Field(..., description="Rule name")
    description: str = Field(default="", description="Rule description")
    conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions that trigger the rule"
    )
    actions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Actions to take when conditions are met"
    )
    priority: int = Field(default=0, description="Rule priority (lower = higher priority)")
    enabled: bool = Field(default=True, description="Whether the rule is active")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Block external sharing of PII",
            "description": "Prevent sharing of personal data outside the organization",
            "conditions": {
                "sensitiveInformationTypes": [
                    {"id": "a44669fe-0d48-453d-a9b1-2cc83f2cba77", "name": "Credit Card Number"}
                ]
            },
            "actions": {
                "blockAccess": True,
                "notifyUser": True,
                "notifyAdmin": True
            },
            "priority": 0,
            "enabled": True
        }
    })


class M365PolicyDefinition(BaseModel):
    """A Microsoft 365 compliance policy definition."""

    name: str = Field(..., description="Policy name")
    display_name: str = Field(..., description="Human-readable policy name")
    description: str = Field(default="", description="Policy description")
    policy_type: M365PolicyType = Field(..., description="Type of M365 policy")
    service_scopes: List[M365ServiceScope] = Field(
        default_factory=lambda: [M365ServiceScope.ALL],
        description="Services where this policy applies"
    )
    rules: List[M365PolicyRule] = Field(
        default_factory=list,
        description="Rules within this policy"
    )
    mode: str = Field(
        default="TestWithNotifications",
        description="Enforcement mode (TestWithNotifications, TestWithoutNotifications, Enable)"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "dlp-pii-protection",
            "display_name": "PII Data Loss Prevention",
            "description": "Prevents sharing of personally identifiable information",
            "policy_type": "dlp",
            "service_scopes": ["exchange", "sharepoint", "teams"],
            "rules": [],
            "mode": "TestWithNotifications"
        }
    })


class M365ControlMapping(BaseModel):
    """Mapping between a compliance control and Microsoft 365 policies."""

    external_control_id: str = Field(..., description="External framework control ID")
    external_control_name: str = Field(..., description="External control name")
    m365_policy_type: M365PolicyType = Field(..., description="Type of M365 policy")
    m365_policies: List[str] = Field(
        default_factory=list,
        description="Recommended M365 policy names"
    )
    graph_api_endpoint: str = Field(
        default="",
        description="Microsoft Graph API endpoint for this policy type"
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
            "external_control_id": "SAMA-DP-01",
            "external_control_name": "Data Classification",
            "m365_policy_type": "dlp",
            "m365_policies": ["PII Protection", "Financial Data Protection"],
            "graph_api_endpoint": "/security/dataLossPreventionPolicies",
            "confidence_score": 0.88,
            "reasoning": "Data classification control maps to DLP policy enforcement"
        }
    })


class M365PolicyPackage(BaseModel):
    """A complete package of Microsoft 365 policies for a compliance framework."""

    framework_name: str = Field(..., description="Compliance framework name")
    framework_version: Optional[str] = Field(None, description="Framework version")
    policies: List[M365PolicyDefinition] = Field(
        default_factory=list,
        description="Generated M365 policies"
    )
    mappings: List[M365ControlMapping] = Field(
        default_factory=list,
        description="Control-to-policy mappings"
    )
    total_controls: int = Field(default=0, description="Total controls processed")
    mapped_controls: int = Field(default=0, description="Controls with M365 mappings")
    deployment_script: str = Field(
        default="",
        description="PowerShell script for deploying policies via Microsoft Graph"
    )
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "framework_name": "SAMA Cybersecurity Framework",
            "policies": [],
            "mappings": [],
            "total_controls": 36,
            "mapped_controls": 28
        }
    })


class M365GenerationRequest(BaseModel):
    """Request model for generating Microsoft 365 compliance policies."""

    framework_name: str = Field(..., description="Framework name")
    framework_version: Optional[str] = Field(None, description="Framework version")
    policy_types: List[M365PolicyType] = Field(
        default_factory=lambda: [M365PolicyType.DLP, M365PolicyType.CONDITIONAL_ACCESS],
        description="Types of M365 policies to generate"
    )
    service_scopes: List[M365ServiceScope] = Field(
        default_factory=lambda: [M365ServiceScope.ALL],
        description="Target M365 services"
    )
    enforcement_mode: str = Field(
        default="TestWithNotifications",
        description="Default enforcement mode for generated policies"
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "framework_name": "SAMA Cybersecurity",
            "policy_types": ["dlp", "conditional_access"],
            "service_scopes": ["exchange", "sharepoint", "teams"],
            "enforcement_mode": "TestWithNotifications"
        }
    })
