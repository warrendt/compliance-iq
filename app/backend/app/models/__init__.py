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
from app.models.platform import (
    CompliancePlatform,
    PlatformCapability,
    PlatformInfo,
    PlatformSelectionRequest,
    PlatformSelectionResponse,
)
from app.models.m365_policy import (
    M365PolicyType,
    M365ServiceScope,
    M365PolicyRule,
    M365PolicyDefinition,
    M365ControlMapping,
    M365PolicyPackage,
    M365GenerationRequest,
)
from app.models.purview import (
    PurviewConfigType,
    SensitivityLabelScope,
    SensitivityLabel,
    SensitivityLabelAction,
    RetentionLabel,
    PurviewDLPPolicy,
    PurviewControlMapping,
    PurviewConfigPackage,
    PurviewGenerationRequest,
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
    # Platform selection models
    "CompliancePlatform",
    "PlatformCapability",
    "PlatformInfo",
    "PlatformSelectionRequest",
    "PlatformSelectionResponse",
    # Microsoft 365 policy models
    "M365PolicyType",
    "M365ServiceScope",
    "M365PolicyRule",
    "M365PolicyDefinition",
    "M365ControlMapping",
    "M365PolicyPackage",
    "M365GenerationRequest",
    # Microsoft Purview models
    "PurviewConfigType",
    "SensitivityLabelScope",
    "SensitivityLabel",
    "SensitivityLabelAction",
    "RetentionLabel",
    "PurviewDLPPolicy",
    "PurviewControlMapping",
    "PurviewConfigPackage",
    "PurviewGenerationRequest",
]

# Resolve forward reference "ControlMapping" inside PolicyGenerationRequest
PolicyGenerationRequest.model_rebuild()
