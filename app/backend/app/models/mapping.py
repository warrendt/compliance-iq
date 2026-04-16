"""
Pydantic models for control mappings.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal, Optional
from datetime import datetime, timezone
from app.models.sovereignty import SovereigntyMapping
from app.models.control import ExternalControl


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
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    result: Optional[MappingBatch] = None

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


class MappingRequest(BaseModel):
    """Request model for initiating control mapping."""

    framework_name: str = Field(..., description="Name of framework")
    controls: List[ExternalControl] = Field(..., description="Controls to map")
    batch_mode: bool = Field(True, description="Process in batch mode")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "framework_name": "SAMA Cybersecurity",
            "controls": [],
            "batch_mode": True
        }
    })
