"""
Pydantic models for compliance platform selection.
Allows users to choose their target platform (Azure, Microsoft 365, or Microsoft Purview)
at the start of the compliance mapping workflow.
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional


class CompliancePlatform(str, Enum):
    """Target compliance platform for policy generation."""
    AZURE_DEFENDER = "azure_defender"       # Microsoft Defender for Cloud (existing)
    MICROSOFT_365 = "microsoft_365"         # Microsoft 365 compliance policies
    MICROSOFT_PURVIEW = "microsoft_purview" # Microsoft Purview data governance


class PlatformCapability(BaseModel):
    """Describes a capability within a compliance platform."""

    id: str = Field(..., description="Capability identifier")
    name: str = Field(..., description="Human-readable capability name")
    description: str = Field(..., description="What this capability covers")
    api_endpoint: str = Field(default="", description="Microsoft Graph API endpoint")
    requires_license: Optional[str] = Field(None, description="Required Microsoft license tier")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "dlp",
                "name": "Data Loss Prevention",
                "description": "Create and manage DLP policies across M365 services",
                "api_endpoint": "/security/dataLossPreventionPolicies",
                "requires_license": "Microsoft 365 E5 Compliance"
            }
        }


class PlatformInfo(BaseModel):
    """Information about a compliance platform and its capabilities."""

    platform: CompliancePlatform = Field(..., description="Platform identifier")
    display_name: str = Field(..., description="Human-readable platform name")
    description: str = Field(..., description="Platform description")
    icon: str = Field(default="🛡️", description="Display icon")
    capabilities: List[PlatformCapability] = Field(
        default_factory=list,
        description="Available capabilities in this platform"
    )
    api_base: str = Field(default="", description="Base API URL")
    documentation_url: str = Field(default="", description="Microsoft Learn documentation URL")

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "microsoft_365",
                "display_name": "Microsoft 365",
                "description": "Compliance policies for Microsoft 365 workloads",
                "icon": "📧",
                "capabilities": [],
                "api_base": "https://graph.microsoft.com/v1.0",
                "documentation_url": "https://learn.microsoft.com/en-us/microsoft-365/compliance/"
            }
        }


class PlatformSelectionRequest(BaseModel):
    """Request model for selecting a compliance platform."""

    platform: CompliancePlatform = Field(
        ...,
        description="Target compliance platform"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="Selected capability IDs (empty = all capabilities)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "microsoft_365",
                "capabilities": ["dlp", "conditional_access"]
            }
        }


class PlatformSelectionResponse(BaseModel):
    """Response model after platform selection."""

    platform: CompliancePlatform = Field(..., description="Selected platform")
    platform_info: PlatformInfo = Field(..., description="Platform details")
    selected_capabilities: List[PlatformCapability] = Field(
        default_factory=list,
        description="Capabilities that will be used"
    )
    next_steps: List[str] = Field(
        default_factory=list,
        description="Recommended next steps for the user"
    )
