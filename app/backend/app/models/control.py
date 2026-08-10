"""
Pydantic models for compliance controls.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict
from datetime import datetime, timezone


class ExternalControl(BaseModel):
    """Model for external framework control uploaded by user."""

    control_id: str = Field(..., description="Control ID from external framework")
    control_name: str = Field(..., description="Short control name/title")
    description: str = Field(..., description="Detailed control description")
    domain: Optional[str] = Field(None, description="Control domain (e.g., Identity, Network)")
    control_type: Optional[str] = Field(None, description="Nature of the control: Technical, Policy, Contractual, Management, Operational, or Governance")
    requirements: Optional[str] = Field(None, description="Specific requirements")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "control_id": "SAMA-AC-01",
            "control_name": "Strong Authentication",
            "description": "Enforce MFA for privileged and user access; disable legacy protocols",
            "domain": "Identity & Access Control",
            "control_type": "Technical"
        }
    })


class FrameworkUpload(BaseModel):
    """Model for uploaded framework control data."""

    framework_name: str = Field(..., description="Name of the compliance framework")
    framework_version: Optional[str] = Field(None, description="Framework version")
    controls: List[ExternalControl] = Field(..., description="List of framework controls")
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(json_schema_extra={
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
    })
