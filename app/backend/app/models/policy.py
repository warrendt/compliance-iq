"""
Pydantic models for Azure Policy initiatives.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.models.mapping import ControlMapping


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

    class Config:
        json_schema_extra = {
            "example": {
                "policyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b",
                "policyDefinitionReferenceId": "SAMA-AC-01",
                "parameters": {}
            }
        }


class PolicyInitiativeMetadata(BaseModel):
    """Metadata for Azure Policy initiative."""

    category: str = Field(default="Regulatory Compliance")
    source: str = Field(default="ComplianceIQ AI Mapping Agent")
    version: str = Field(default="1.0.0")
    generated_date: datetime = Field(default_factory=datetime.utcnow)
    framework_name: Optional[str] = None
    framework_version: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "category": "Regulatory Compliance",
                "source": "ComplianceIQ AI Mapping Agent",
                "version": "1.0.0",
                "generatedDate": "2026-01-20T10:00:00Z",
                "frameworkName": "SAMA Cybersecurity Framework",
                "frameworkVersion": "v1.0"
            }
        }


class PolicyInitiativeProperties(BaseModel):
    """Properties of an Azure Policy initiative."""

    display_name: str = Field(..., description="Initiative display name")
    description: str = Field(..., description="Initiative description")
    metadata: PolicyInitiativeMetadata = Field(..., description="Initiative metadata")
    policy_definitions: List[PolicyDefinitionReference] = Field(
        ...,
        description="List of policy definitions in this initiative"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "displayName": "SAMA Cybersecurity Framework Compliance",
                "description": "AI-generated policy initiative for SAMA framework compliance",
                "metadata": {},
                "policyDefinitions": []
            }
        }


class PolicyInitiative(BaseModel):
    """Complete Azure Policy initiative definition."""

    properties: PolicyInitiativeProperties = Field(..., description="Initiative properties")

    class Config:
        json_schema_extra = {
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
        }

    def to_azure_json(self) -> Dict[str, Any]:
        """
        Convert to Azure Policy JSON format.

        Returns:
            Dict: Azure Policy initiative JSON
        """
        return {
            "properties": {
                "displayName": self.properties.display_name,
                "description": self.properties.description,
                "metadata": {
                    "category": self.properties.metadata.category,
                    "source": self.properties.metadata.source,
                    "version": self.properties.metadata.version,
                    "generatedDate": self.properties.metadata.generated_date.isoformat(),
                    "frameworkName": self.properties.metadata.framework_name,
                    "frameworkVersion": self.properties.metadata.framework_version
                },
                "policyDefinitions": [
                    {
                        "policyDefinitionId": pd.policy_definition_id,
                        "policyDefinitionReferenceId": pd.policy_definition_reference_id,
                        "parameters": pd.parameters
                    }
                    for pd in self.properties.policy_definitions
                ]
            }
        }


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

    class Config:
        json_schema_extra = {
            "example": {
                "framework_name": "SAMA Cybersecurity",
                "framework_version": "v1.0",
                "mappings": [],
                "include_all_policies": True,
                "min_confidence_threshold": 0.7,
                "enforce_mode": False
            }
        }


class PolicyGenerationResponse(BaseModel):
    """Response model for policy generation."""

    initiative: PolicyInitiative = Field(..., description="Generated policy initiative")
    total_controls: int = Field(..., description="Total controls processed")
    included_policies: int = Field(..., description="Number of policies included")
    excluded_policies: int = Field(..., description="Number of policies excluded (low confidence)")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")

    class Config:
        json_schema_extra = {
            "example": {
                "initiative": {},
                "total_controls": 36,
                "included_policies": 34,
                "excluded_policies": 2,
                "warnings": ["2 controls excluded due to confidence < 0.7"]
            }
        }
