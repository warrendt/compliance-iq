"""
Database models for Cosmos DB documents
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from uuid import uuid4


class BaseDocument(BaseModel):
    """Base model for all Cosmos DB documents"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    _etag: Optional[str] = None
    _ts: Optional[int] = None
    ttl: Optional[int] = None  # Time to live in seconds


class MappingResultDocument(BaseDocument):
    """Document for storing AI mapping results"""
    userId: str
    date: str  # Format: YYYY-MM-DD for partition key
    controlId: str
    controlName: str
    framework: str
    domain: Optional[str] = None
    mcsbMappings: List[Dict[str, Any]]
    confidence: float
    reasoning: str
    policyRecommendations: List[str]
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "userId": "user@example.com",
            "date": "2026-02-10",
            "controlId": "SAMA-CC-001",
            "controlName": "Access Control",
            "framework": "SAMA",
            "mcsbMappings": [],
            "confidence": 0.95,
            "reasoning": "Strong alignment with MCSB controls",
            "policyRecommendations": ["CIS-1", "CIS-2"]
        }
    })


class AuditLogDocument(BaseDocument):
    """Document for audit trail"""
    userId: str
    action: str
    resourceType: str
    resourceId: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    ipAddress: Optional[str] = None
    userAgent: Optional[str] = None
    success: bool = True
    errorMessage: Optional[str] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "userId": "user@example.com",
            "action": "mapping.created",
            "resourceType": "mapping_result",
            "resourceId": "abc-123",
            "metadata": {"controlCount": 5},
            "success": True
        }
    })


class UserUploadDocument(BaseDocument):
    """Document for cached user uploads"""
    userId: str
    fileName: str
    fileSize: int
    fileType: str
    fileHash: str  # SHA256 hash for deduplication
    content: Optional[str] = None  # Base64 encoded or reference to blob
    rowCount: int
    columnNames: List[str]
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "userId": "user@example.com",
            "fileName": "sama_controls.csv",
            "fileSize": 1024,
            "fileType": "text/csv",
            "fileHash": "abc123...",
            "rowCount": 36,
            "columnNames": ["Control ID", "Control Name", "Description"]
        }
    })


class GeneratedArtifactDocument(BaseDocument):
    """Document for generated policy artifacts"""
    userId: str
    artifactType: str  # 'bicep', 'json', 'powershell'
    framework: str
    controlCount: int
    content: str  # Generated file content
    fileName: str
    fileSize: int
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "userId": "user@example.com",
            "artifactType": "bicep",
            "framework": "SAMA",
            "controlCount": 36,
            "content": "// Bicep template content...",
            "fileName": "sama_policy_initiative.bicep",
            "fileSize": 2048
        }
    })


class UserProfileDocument(BaseDocument):
    """Document for user profiles — one document per user (partitioned by userId)."""
    userId: str
    displayName: str = ""
    email: str = ""
    preferredPlatform: str = "azure_defender"
    uploadCount: int = 0
    mappingCount: int = 0
    exportCount: int = 0
    lastActive: Optional[datetime] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "userId": "user@example.com",
            "displayName": "Jane Smith",
            "email": "user@example.com",
            "preferredPlatform": "azure_defender",
            "uploadCount": 5,
            "mappingCount": 12,
            "exportCount": 3,
            "lastActive": "2026-01-01T12:00:00Z"
        }
    })


class ComparisonDocument(BaseDocument):
    """Document for an internal-vs-external control diff/comparison run.

    Partitioned by ``userId``. Phase 1 defines the shape; the comparison
    service (Phase 2) populates ``result`` and ``counts``.
    """
    userId: str
    status: str = "pending"  # pending | running | completed | failed
    internalFileName: str = ""
    externalFramework: str = ""
    direction: str = "internal_vs_external"
    result: Dict[str, Any] = Field(default_factory=dict)
    counts: Dict[str, int] = Field(default_factory=dict)
    errorMessage: Optional[str] = None

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "userId": "user@example.com",
            "status": "completed",
            "internalFileName": "popia.pdf",
            "externalFramework": "SAMA",
            "direction": "internal_vs_external",
            "counts": {"matched": 12, "partial-overlap": 5, "gap": 8, "extra": 3},
        }
    })


class PolicyVersionDocument(BaseDocument):
    """Immutable per-user policy initiative version (partitioned by ``userId``).

    Versions are never mutated. A revert creates a *new* version that copies the
    target's ``artifact_payload`` and records lineage in ``parent_version`` /
    ``metadata``.
    """
    userId: str
    version_number: int
    semantic_version: str = "1.0.0"
    version_stream: str = "initiative:default"
    parent_version: Optional[int] = None
    artifact_payload: Dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    sourceComparisonId: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "userId": "user@example.com",
            "version_number": 2,
            "parent_version": 1,
            "status": "active",
            "sourceComparisonId": "cmp-123",
            "artifact_payload": {"initiative": {}, "artifacts": []},
            "metadata": {"reverted_from_version": 1},
        }
    })
