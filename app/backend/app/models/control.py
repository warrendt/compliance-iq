"""
Pydantic models for compliance controls.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class ExternalControl(BaseModel):
    """Model for external framework control uploaded by user."""

    control_id: str = Field(..., description="Control ID from external framework")
    control_name: str = Field(..., description="Short control name/title")
    description: str = Field(..., description="Detailed control description")
    domain: Optional[str] = Field(None, description="Control domain (e.g., Identity, Network)")
    control_type: Optional[str] = Field(None, description="Management, Operational, or Technical")
    requirements: Optional[str] = Field(None, description="Specific requirements")

    class Config:
        json_schema_extra = {
            "example": {
                "control_id": "SAMA-AC-01",
                "control_name": "Strong Authentication",
                "description": "Enforce MFA for privileged and user access; disable legacy protocols",
                "domain": "Identity & Access Control",
                "control_type": "Technical"
            }
        }


class MCSBControl(BaseModel):
    """Model for Microsoft Cloud Security Benchmark control."""

    control_id: str = Field(..., description="MCSB control ID (e.g., IM-1)")
    domain: str = Field(..., description="Security domain")
    control_name: str = Field(..., description="Control title")
    description: str = Field(..., description="Full control description")
    azure_policy_ids: List[str] = Field(
        default_factory=list,
        description="Associated Azure Policy definition GUIDs"
    )
    defender_recommendations: List[str] = Field(
        default_factory=list,
        description="Microsoft Defender for Cloud recommendations"
    )
    related_frameworks: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Mappings to other frameworks (CIS, NIST, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "control_id": "IM-1",
                "domain": "Identity Management",
                "control_name": "Use centralized identity and authentication system",
                "description": "Use a centralized identity and authentication system...",
                "azure_policy_ids": ["4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"],
                "defender_recommendations": ["Enable MFA for all users"],
                "related_frameworks": {
                    "CIS": ["CIS-5.1"],
                    "NIST": ["IA-2"]
                }
            }
        }


class FrameworkUpload(BaseModel):
    """Model for uploaded framework control data."""

    framework_name: str = Field(..., description="Name of the compliance framework")
    framework_version: Optional[str] = Field(None, description="Framework version")
    controls: List[ExternalControl] = Field(..., description="List of framework controls")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "framework_name": "SAMA Cybersecurity Framework",
                "framework_version": "v1.0",
                "controls": [
                    {
                        "control_id": "SAMA-AC-01",
                        "control_name": "Strong Authentication",
                        "description": "Enforce MFA for all access",
                        "domain": "Identity & Access Control"
                    }
                ]
            }
        }
