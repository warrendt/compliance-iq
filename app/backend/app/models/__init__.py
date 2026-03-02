"""
Pydantic models for the AI Control Mapping Agent.
"""

from app.models.control import ExternalControl, MCSBControl, FrameworkUpload
from app.models.mapping import (
    ControlMapping,
    MappingBatch,
    MappingJob,
    MappingRequest
)
from app.models.policy import (
    PolicyDefinitionReference,
    PolicyInitiativeMetadata,
    PolicyInitiativeProperties,
    PolicyInitiative,
    PolicyGenerationRequest,
    PolicyGenerationResponse
)
from app.models.sovereignty import (
    SovereigntyLevel,
    SovereigntyControlObjective,
    SovereigntyMapping,
    SLZPolicyDefinition,
    SLZInitiative,
    SLZArchetype,
    SLZPolicyAssignment,
)

__all__ = [
    # Control models
    "ExternalControl",
    "MCSBControl",
    "FrameworkUpload",
    # Mapping models
    "ControlMapping",
    "MappingBatch",
    "MappingJob",
    "MappingRequest",
    # Policy models
    "PolicyDefinitionReference",
    "PolicyInitiativeMetadata",
    "PolicyInitiativeProperties",
    "PolicyInitiative",
    "PolicyGenerationRequest",
    "PolicyGenerationResponse",
    # Sovereignty models
    "SovereigntyLevel",
    "SovereigntyControlObjective",
    "SovereigntyMapping",
    "SLZPolicyDefinition",
    "SLZInitiative",
    "SLZArchetype",
    "SLZPolicyAssignment",
]

# Resolve forward reference "ControlMapping" inside PolicyGenerationRequest
PolicyGenerationRequest.model_rebuild()
