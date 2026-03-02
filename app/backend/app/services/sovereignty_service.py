"""
Sovereign Landing Zone (SLZ) data service.
Loads, indexes, and provides search functionality for SLZ policies,
initiatives, archetypes, and sovereignty control objectives.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from functools import lru_cache

from app.models.sovereignty import (
    SLZPolicyDefinition,
    SLZInitiative,
    SLZArchetype,
    SLZPolicyAssignment,
    SovereigntyControlObjective,
    SovereigntyLevel,
)

logger = logging.getLogger(__name__)


class SovereigntyService:
    """Service for loading and searching SLZ sovereignty policies."""

    def __init__(self, data_dir: Optional[str] = None):
        """Initialize the sovereignty service.

        Args:
            data_dir: Directory containing slz_policies.json and slz_archetypes.json.
                      Defaults to app/data/ relative to this file.
        """
        if data_dir:
            self._data_dir = Path(data_dir)
        else:
            self._data_dir = Path(__file__).resolve().parent.parent / "data"

        self._policies: List[SLZPolicyDefinition] = []
        self._initiatives: List[SLZInitiative] = []
        self._assignments: List[SLZPolicyAssignment] = []
        self._archetypes: List[SLZArchetype] = []
        self._objectives: Dict[str, SovereigntyControlObjective] = {}
        self._built_in_initiatives: List[dict] = []

        # Indexes
        self._policies_by_level: Dict[str, List[SLZPolicyDefinition]] = {}
        self._policies_by_service: Dict[str, List[SLZPolicyDefinition]] = {}
        self._policies_by_objective: Dict[str, List[SLZPolicyDefinition]] = {}
        self._policies_by_name: Dict[str, SLZPolicyDefinition] = {}
        self._archetypes_by_name: Dict[str, SLZArchetype] = {}

        self._loaded = False

    # ── Loading ──────────────────────────────────────────────────────

    def load(self) -> None:
        """Load SLZ data from JSON files."""
        if self._loaded:
            return

        policies_file = self._data_dir / "slz_policies.json"
        archetypes_file = self._data_dir / "slz_archetypes.json"

        if not policies_file.exists():
            logger.warning(f"SLZ policies file not found: {policies_file}")
            self._loaded = True
            return

        try:
            with open(policies_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse sovereignty objectives
            for so_id, so_data in data.get("sovereignty_objectives", {}).items():
                self._objectives[so_id] = SovereigntyControlObjective(**so_data)

            # Parse policy definitions
            for pd in data.get("policy_definitions", []):
                self._policies.append(SLZPolicyDefinition(**pd))

            # Parse policy set definitions (initiatives)
            for psd in data.get("policy_set_definitions", []):
                self._initiatives.append(SLZInitiative(**psd))

            # Parse policy assignments
            for pa in data.get("policy_assignments", []):
                self._assignments.append(SLZPolicyAssignment(**pa))

            # Parse archetypes
            for arch in data.get("archetypes", []):
                self._archetypes.append(SLZArchetype(**arch))

            # Store built-in initiatives
            self._built_in_initiatives = data.get("built_in_initiatives", [])

            # Build indexes
            self._build_indexes()
            self._loaded = True

            logger.info(
                f"Loaded SLZ data: {len(self._policies)} policies, "
                f"{len(self._initiatives)} initiatives, "
                f"{len(self._assignments)} assignments, "
                f"{len(self._archetypes)} archetypes, "
                f"{len(self._objectives)} objectives"
            )

        except Exception as e:
            logger.error(f"Failed to load SLZ data: {e}")
            self._loaded = True  # Mark loaded to avoid retry loops

    def _build_indexes(self) -> None:
        """Build lookup indexes for fast searching."""
        self._policies_by_level = {}
        self._policies_by_service = {}
        self._policies_by_objective = {}
        self._policies_by_name = {}

        for policy in self._policies:
            # By level
            level = policy.sovereignty_level
            self._policies_by_level.setdefault(level, []).append(policy)

            # By service
            svc = policy.service_category
            self._policies_by_service.setdefault(svc, []).append(policy)

            # By objective
            for obj in policy.sovereignty_objectives:
                self._policies_by_objective.setdefault(obj, []).append(policy)

            # By name
            self._policies_by_name[policy.name] = policy

        # Archetypes by name
        self._archetypes_by_name = {a.name: a for a in self._archetypes}

    # ── Queries ──────────────────────────────────────────────────────

    def get_all_policies(self) -> List[SLZPolicyDefinition]:
        """Get all SLZ policy definitions."""
        self._ensure_loaded()
        return self._policies

    def get_policies_by_level(self, level: str) -> List[SLZPolicyDefinition]:
        """Get policies for a sovereignty level (L1, L2, L3).

        Note: Higher levels include lower level policies.
        L3 includes L2 + L1. L2 includes L1.
        """
        self._ensure_loaded()
        result = []
        level_hierarchy = {"L1": ["L1"], "L2": ["L1", "L2"], "L3": ["L1", "L2", "L3"]}
        for lvl in level_hierarchy.get(level, [level]):
            result.extend(self._policies_by_level.get(lvl, []))
        return result

    def get_policies_by_service(self, service: str) -> List[SLZPolicyDefinition]:
        """Get policies for a specific Azure service category."""
        self._ensure_loaded()
        # Try exact match first
        if service in self._policies_by_service:
            return self._policies_by_service[service]
        # Fuzzy match
        service_lower = service.lower()
        for svc, policies in self._policies_by_service.items():
            if service_lower in svc.lower() or svc.lower() in service_lower:
                return policies
        return []

    def get_policies_by_objective(self, objective_id: str) -> List[SLZPolicyDefinition]:
        """Get policies for a sovereignty control objective (SO-1 through SO-5)."""
        self._ensure_loaded()
        return self._policies_by_objective.get(objective_id, [])

    def get_policy_by_name(self, name: str) -> Optional[SLZPolicyDefinition]:
        """Look up a single policy by name."""
        self._ensure_loaded()
        return self._policies_by_name.get(name)

    def search_policies(self, query: str) -> List[SLZPolicyDefinition]:
        """Full-text search across policy names and descriptions."""
        self._ensure_loaded()
        query_lower = query.lower()
        results = []
        for policy in self._policies:
            text = f"{policy.display_name} {policy.description} {policy.service_category}".lower()
            if query_lower in text:
                results.append(policy)
        return results

    def get_relevant_policies_for_control(
        self,
        control_description: str,
        control_domain: Optional[str] = None,
    ) -> List[SLZPolicyDefinition]:
        """Find SLZ policies relevant to an external framework control.

        Uses keyword matching against the control text to surface
        sovereignty policies the AI can reference.
        """
        self._ensure_loaded()
        text = f"{control_description} {control_domain or ''}".lower()
        scored: List[tuple] = []

        for policy in self._policies:
            score = 0
            policy_text = f"{policy.display_name} {policy.description}".lower()

            # Check objective keywords
            for obj_id, obj in self._objectives.items():
                if obj.procedural_only:
                    continue
                for kw in obj.keywords:
                    if kw.lower() in text:
                        # This control is sovereignty-relevant
                        # Check if the policy relates to the same objective
                        if obj_id in policy.sovereignty_objectives:
                            score += 3

            # Domain/service matching
            if control_domain:
                domain_lower = control_domain.lower()
                if domain_lower in policy.service_category.lower():
                    score += 2
                if domain_lower in policy_text:
                    score += 1

            # Generic text overlap
            for word in text.split():
                if len(word) > 3 and word in policy_text:
                    score += 0.5

            if score > 0:
                scored.append((score, policy))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:10]]

    # ── Objectives ───────────────────────────────────────────────────

    def get_all_objectives(self) -> Dict[str, SovereigntyControlObjective]:
        """Get all sovereignty control objectives."""
        self._ensure_loaded()
        return self._objectives

    def get_objective(self, objective_id: str) -> Optional[SovereigntyControlObjective]:
        """Get a specific sovereignty control objective."""
        self._ensure_loaded()
        return self._objectives.get(objective_id)

    # ── Initiatives ──────────────────────────────────────────────────

    def get_all_initiatives(self) -> List[SLZInitiative]:
        """Get all SLZ initiatives."""
        self._ensure_loaded()
        return self._initiatives

    def get_built_in_initiatives(self) -> List[dict]:
        """Get the two built-in Sovereignty Baseline initiatives."""
        self._ensure_loaded()
        return self._built_in_initiatives

    # ── Archetypes ───────────────────────────────────────────────────

    def get_all_archetypes(self) -> List[SLZArchetype]:
        """Get all SLZ management group archetypes."""
        self._ensure_loaded()
        return self._archetypes

    def get_archetype(self, name: str) -> Optional[SLZArchetype]:
        """Get a specific archetype by name."""
        self._ensure_loaded()
        return self._archetypes_by_name.get(name)

    def get_archetype_assignments(self, archetype_name: str) -> List[SLZPolicyAssignment]:
        """Get policy assignments for a specific archetype."""
        self._ensure_loaded()
        archetype = self._archetypes_by_name.get(archetype_name)
        if not archetype:
            return []

        relevant = []
        key_names = set(archetype.key_assignments + archetype.policy_assignments)
        for assignment in self._assignments:
            if assignment.name in key_names:
                relevant.append(assignment)
        return relevant

    def recommend_archetype(self, sovereignty_level: str) -> str:
        """Recommend an archetype based on sovereignty level."""
        if sovereignty_level == "L3":
            return "confidential_corp"
        elif sovereignty_level == "L2":
            return "sovereign_root"
        else:
            return "sovereign_root"

    # ── Assignments ──────────────────────────────────────────────────

    def get_all_assignments(self) -> List[SLZPolicyAssignment]:
        """Get all SLZ policy assignments."""
        self._ensure_loaded()
        return self._assignments

    # ── Summary / Stats ──────────────────────────────────────────────

    def get_summary(self) -> Dict:
        """Get a summary of loaded SLZ data."""
        self._ensure_loaded()
        levels = {}
        for p in self._policies:
            levels[p.sovereignty_level] = levels.get(p.sovereignty_level, 0) + 1

        services = {}
        for p in self._policies:
            services[p.service_category] = services.get(p.service_category, 0) + 1

        return {
            "total_policies": len(self._policies),
            "total_initiatives": len(self._initiatives),
            "total_assignments": len(self._assignments),
            "total_archetypes": len(self._archetypes),
            "total_objectives": len(self._objectives),
            "policies_by_level": levels,
            "policies_by_service": services,
            "built_in_initiatives": len(self._built_in_initiatives),
        }

    # ── Helpers ──────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()


@lru_cache
def get_sovereignty_service() -> SovereigntyService:
    """Get cached sovereignty service instance."""
    service = SovereigntyService()
    service.load()
    return service
