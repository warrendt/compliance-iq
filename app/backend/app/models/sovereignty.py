"""
Pydantic models for Sovereign Landing Zone (SLZ) policy integration.
"""

from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class SovereigntyLevel(str, Enum):
    """Sovereignty control levels mapping to SLZ management group archetypes."""
    L1_GLOBAL = "L1"       # Data Residency + Trusted Launch
    L2_CMK = "L2"          # Customer-Managed Keys (at-rest encryption)
    L3_CONFIDENTIAL = "L3" # Confidential Computing (encryption in-use)


class SovereigntyControlObjective(BaseModel):
    """One of the five Sovereignty Control Objectives (SO-1 through SO-5)."""

    id: str = Field(..., description="Objective ID (SO-1 through SO-5)")
    name: str = Field(..., description="Short name (e.g., Data Residency)")
    description: str = Field(..., description="Full description of the objective")
    applicable_levels: List[str] = Field(
        default_factory=list,
        description="SLZ levels where this objective applies (L1, L2, L3)"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Keywords used for classification"
    )
    procedural_only: bool = Field(
        False,
        description="True if no Azure Policy exists (e.g., SO-2 Customer Lockbox)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "SO-1",
                "name": "Data Residency",
                "description": "Ensure data stays within approved geographic regions.",
                "applicable_levels": ["L1", "L2", "L3"],
                "keywords": ["location", "allowed locations"],
                "procedural_only": False,
            }
        }


class SLZPolicyDefinition(BaseModel):
    """A Sovereign Landing Zone policy definition."""

    name: str = Field(..., description="Policy name/identifier")
    display_name: str = Field(..., description="Human-readable policy name")
    description: str = Field(default="", description="Policy description")
    effect: str = Field(default="Audit", description="Policy effect (Audit, Deny, etc.)")
    sovereignty_level: str = Field(default="L1", description="SLZ level (L1, L2, L3)")
    sovereignty_objectives: List[str] = Field(
        default_factory=list,
        description="List of SO-* objective IDs this policy enforces"
    )
    service_category: str = Field(default="General", description="Azure service category")
    policy_type: str = Field(default="Custom", description="BuiltIn or Custom")
    mode: str = Field(default="All", description="Policy mode")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    parameter_names: List[str] = Field(default_factory=list)
    source_file: str = Field(default="", description="Source file in Azure-Landing-Zones-Library")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "cmk-storage-account",
                "display_name": "Storage accounts should use customer-managed key for encryption",
                "description": "Secure your blob and file storage with customer-managed keys.",
                "effect": "Audit",
                "sovereignty_level": "L2",
                "sovereignty_objectives": ["SO-3"],
                "service_category": "Storage",
            }
        }


class SLZInitiative(BaseModel):
    """A Sovereign Landing Zone policy set definition (initiative)."""

    name: str = Field(..., description="Initiative name/identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(default="")
    sovereignty_level: str = Field(default="L1")
    sovereignty_objectives: List[str] = Field(default_factory=list)
    service_category: str = Field(default="General")
    policy_definition_count: int = Field(default=0)
    policy_definitions: List[Dict[str, Any]] = Field(default_factory=list)
    is_built_in: bool = Field(default=False)
    learn_url: Optional[str] = Field(default=None, description="Microsoft Learn documentation URL")
    source_file: str = Field(default="")


class SLZArchetype(BaseModel):
    """An SLZ management group archetype."""

    name: str = Field(..., description="Archetype identifier (e.g., sovereign_root)")
    display_name: Optional[str] = Field(None, description="Human-readable name")
    description: str = Field(default="")
    parent: Optional[str] = Field(None, description="Parent archetype")
    sovereignty_level: str = Field(default="L1")
    key_assignments: List[str] = Field(default_factory=list)
    policy_assignments: List[str] = Field(default_factory=list)
    policy_definitions: List[str] = Field(default_factory=list)
    policy_set_definitions: List[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "confidential_corp",
                "display_name": "Confidential Corp",
                "description": "Connected workloads requiring confidential computing.",
                "parent": "sovereign_root",
                "sovereignty_level": "L3",
                "key_assignments": ["Enforce-Sovereign-Conf"],
            }
        }


class SovereigntyMapping(BaseModel):
    """Sovereignty dimension of a control mapping, produced by the AI alongside MCSB mapping."""

    sovereignty_level: str = Field(
        ...,
        description="Recommended SLZ level: L1 (Data Residency), L2 (CMK), L3 (Confidential Computing)"
    )
    sovereignty_objectives: List[str] = Field(
        default_factory=list,
        description="Relevant SO-* control objectives (SO-1 through SO-5)"
    )
    slz_policy_names: List[str] = Field(
        default_factory=list,
        description="SLZ policy definition names that enforce this control"
    )
    target_archetype: str = Field(
        default="sovereign_root",
        description="Recommended SLZ management group archetype"
    )
    reasoning: str = Field(
        default="",
        description="Explanation of sovereignty level recommendation"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sovereignty_level": "L2",
                "sovereignty_objectives": ["SO-3"],
                "slz_policy_names": ["cmk-storage-account", "cmk-sql-server"],
                "target_archetype": "sovereign_root",
                "reasoning": "This control requires encryption at rest with CMK, aligning with SO-3.",
            }
        }


class SLZPolicyAssignment(BaseModel):
    """An SLZ policy assignment targeting a management group archetype."""

    name: str = Field(..., description="Assignment name")
    display_name: str = Field(default="")
    description: str = Field(default="")
    policy_definition_id: str = Field(default="", description="Referenced policy/initiative")
    enforcement_mode: str = Field(default="Default")
    parameters: Dict[str, Any] = Field(default_factory=dict)
    source_file: str = Field(default="")
