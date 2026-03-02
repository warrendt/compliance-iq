"""
Sync SLZ (Sovereign Landing Zone) policy definitions from Azure-Landing-Zones-Library.

This script clones/pulls the Azure-Landing-Zones-Library repo and extracts all SLZ 
policy definitions, initiatives, and assignments into local JSON files used by the
SovereigntyService at runtime.

Usage:
    python -m scripts.sync_slz_policies [--output-dir PATH] [--repo-dir PATH]
"""

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Canonical source
REPO_URL = "https://github.com/Azure/Azure-Landing-Zones-Library.git"
SLZ_PATH = "platform/slz"

# Sovereignty Control Objectives
SOVEREIGNTY_OBJECTIVES = {
    "SO-1": {
        "id": "SO-1",
        "name": "Data Residency",
        "description": "Ensure data stays within approved geographic regions. Enforces allowed locations for resources and resource groups.",
        "applicable_levels": ["L1", "L2", "L3"],
        "keywords": ["location", "allowed locations", "data residency", "geographic", "region"],
    },
    "SO-2": {
        "id": "SO-2",
        "name": "Customer Lockbox",
        "description": "Require customer approval before Microsoft support can access customer data. No Azure Policy available — procedural control only.",
        "applicable_levels": ["L1", "L2", "L3"],
        "keywords": ["lockbox", "customer approval", "support access"],
        "procedural_only": True,
    },
    "SO-3": {
        "id": "SO-3",
        "name": "Customer-Managed Keys",
        "description": "Encrypt data at rest using customer-managed keys (CMK) instead of Microsoft-managed keys.",
        "applicable_levels": ["L2", "L3"],
        "keywords": ["customer-managed key", "CMK", "encryption", "encrypt", "byok", "bring your own key"],
    },
    "SO-4": {
        "id": "SO-4",
        "name": "Confidential Computing",
        "description": "Restrict deployments to confidential computing-capable resource types and VM SKUs for encryption in-use.",
        "applicable_levels": ["L3"],
        "keywords": ["confidential", "trusted execution", "TEE", "SGX", "SEV-SNP", "allowed resource types", "allowed virtual machine"],
    },
    "SO-5": {
        "id": "SO-5",
        "name": "Trusted Launch",
        "description": "Require Trusted Launch for virtual machines to protect against boot-level attacks.",
        "applicable_levels": ["L1", "L2", "L3"],
        "keywords": ["trusted launch", "trustedlaunch", "secure boot", "vTPM"],
    },
}

# Service category detection from policy names/descriptions
SERVICE_CATEGORY_PATTERNS = {
    "Compute": ["virtual machine", "vm ", "vmss", "compute", "disk", "managed disk"],
    "Storage": ["storage account", "blob", "file share", "queue storage", "table storage"],
    "Networking": ["network", "vnet", "subnet", "nsg", "firewall", "dns", "ip ", "route"],
    "Databases": ["sql", "cosmos", "mysql", "postgresql", "mariadb", "database"],
    "Key Vault": ["key vault", "keyvault"],
    "Containers": ["container", "kubernetes", "aks", "acr"],
    "App Services": ["app service", "web app", "function app"],
    "AI/ML": ["machine learning", "cognitive", "openai", "ai service"],
    "API Management": ["api management", "apim"],
    "Identity": ["identity", "managed identity", "active directory"],
    "Monitoring": ["monitor", "log analytics", "diagnostic", "insight"],
    "Security": ["security", "defender", "sentinel"],
    "Integration": ["service bus", "event hub", "event grid", "logic app"],
    "General": [],
}

# SLZ Archetype definitions
SLZ_ARCHETYPES = {
    "sovereign_root": {
        "name": "Sovereign Root",
        "description": "Top-level management group. Inherits ALZ root and adds sovereignty global policies.",
        "parent": "alz_root",
        "sovereignty_level": "L1",
        "key_assignments": ["Enforce-Sovereign-Global"],
    },
    "confidential_corp": {
        "name": "Confidential Corp",
        "description": "Connected workloads requiring confidential computing protections.",
        "parent": "sovereign_root",
        "sovereignty_level": "L3",
        "key_assignments": ["Enforce-Sovereign-Conf"],
    },
    "confidential_online": {
        "name": "Confidential Online",
        "description": "Internet-facing workloads requiring confidential computing protections.",
        "parent": "sovereign_root",
        "sovereignty_level": "L3",
        "key_assignments": ["Enforce-Sovereign-Conf"],
    },
    "public": {
        "name": "Public",
        "description": "Standard non-sovereign workloads with basic guardrails.",
        "parent": "sovereign_root",
        "sovereignty_level": "L1",
        "key_assignments": [],
    },
}

# Built-in sovereignty baseline initiatives
BUILT_IN_INITIATIVES = [
    {
        "initiative_id": "mcfs-baseline-global",
        "display_name": "Sovereignty Baseline - Global Policies",
        "description": "Built-in Azure Policy initiative enforcing SO-1 (Data Residency) and SO-5 (Trusted Launch) for all sovereign workloads.",
        "sovereignty_objectives": ["SO-1", "SO-5"],
        "sovereignty_level": "L1",
        "learn_url": "https://learn.microsoft.com/en-us/azure/governance/policy/samples/mcfs-baseline-global",
        "is_built_in": True,
    },
    {
        "initiative_id": "mcfs-baseline-confidential",
        "display_name": "Sovereignty Baseline - Confidential Policies",
        "description": "Built-in Azure Policy initiative enforcing SO-1 (Data Residency), SO-3 (CMK), and SO-4 (Confidential Computing).",
        "sovereignty_objectives": ["SO-1", "SO-3", "SO-4"],
        "sovereignty_level": "L3",
        "learn_url": "https://learn.microsoft.com/en-us/azure/governance/policy/samples/mcfs-baseline-confidential",
        "is_built_in": True,
    },
]


def clone_or_pull_repo(repo_dir: Path) -> None:
    """Clone or pull the Azure-Landing-Zones-Library repo."""
    if (repo_dir / ".git").exists():
        logger.info(f"Pulling latest changes in {repo_dir}")
        subprocess.run(["git", "-C", str(repo_dir), "pull", "--ff-only"], check=True, capture_output=True)
    else:
        logger.info(f"Cloning {REPO_URL} → {repo_dir}")
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", REPO_URL, str(repo_dir)],
            check=True, capture_output=True,
        )
        # Sparse checkout just the SLZ platform directory
        subprocess.run(
            ["git", "-C", str(repo_dir), "sparse-checkout", "set", SLZ_PATH],
            check=True, capture_output=True,
        )


def classify_sovereignty_level(policy: Dict[str, Any]) -> str:
    """Classify a policy into sovereignty level L1, L2, or L3."""
    text = f"{policy.get('display_name', '')} {policy.get('description', '')}".lower()

    # L3: Confidential Computing
    for kw in SOVEREIGNTY_OBJECTIVES["SO-4"]["keywords"]:
        if kw.lower() in text:
            return "L3"

    # L2: Customer-Managed Keys
    for kw in SOVEREIGNTY_OBJECTIVES["SO-3"]["keywords"]:
        if kw.lower() in text:
            return "L2"

    # L1: Data Residency, Trusted Launch, or general
    return "L1"


def classify_sovereignty_objective(policy: Dict[str, Any]) -> List[str]:
    """Map a policy to its sovereignty control objectives."""
    text = f"{policy.get('display_name', '')} {policy.get('description', '')}".lower()
    objectives = []

    for so_id, so_def in SOVEREIGNTY_OBJECTIVES.items():
        if so_def.get("procedural_only"):
            continue
        for kw in so_def["keywords"]:
            if kw.lower() in text:
                objectives.append(so_id)
                break

    return objectives if objectives else ["SO-1"]  # Default to data residency


def classify_service_category(policy: Dict[str, Any]) -> str:
    """Classify a policy into a service category."""
    text = f"{policy.get('display_name', '')} {policy.get('description', '')}".lower()

    for category, keywords in SERVICE_CATEGORY_PATTERNS.items():
        for kw in keywords:
            if kw in text:
                return category

    return "General"


def parse_alz_policy_definition(filepath: Path) -> Optional[Dict[str, Any]]:
    """Parse an ALZ policy definition JSON file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("name", filepath.stem.replace(".alz_policy_definition", ""))
        props = data.get("properties", {})

        policy = {
            "name": name,
            "display_name": props.get("displayName", name),
            "description": props.get("description", ""),
            "policy_type": props.get("policyType", "Custom"),
            "mode": props.get("mode", "All"),
            "metadata": props.get("metadata", {}),
            "parameters": {k: {kk: vv for kk, vv in v.items() if kk != "defaultValue"} for k, v in props.get("parameters", {}).items()},
            "parameter_names": list(props.get("parameters", {}).keys()),
            "policy_rule": props.get("policyRule", {}),
            "source_file": str(filepath.name),
        }

        # Extract effect from policy rule
        effect = ""
        rule = props.get("policyRule", {})
        then_block = rule.get("then", {})
        effect_val = then_block.get("effect", "")
        if isinstance(effect_val, str):
            effect = effect_val
        elif isinstance(effect_val, dict):
            # Parameterized effect like "[parameters('effect')]"
            effect = "Parameterized"
        policy["effect"] = effect

        # Classify
        policy["sovereignty_level"] = classify_sovereignty_level(policy)
        policy["sovereignty_objectives"] = classify_sovereignty_objective(policy)
        policy["service_category"] = classify_service_category(policy)

        return policy

    except Exception as e:
        logger.warning(f"Failed to parse {filepath}: {e}")
        return None


def parse_alz_policy_set_definition(filepath: Path) -> Optional[Dict[str, Any]]:
    """Parse an ALZ policy set (initiative) definition JSON file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("name", filepath.stem.replace(".alz_policy_set_definition", ""))
        props = data.get("properties", {})

        initiative = {
            "name": name,
            "display_name": props.get("displayName", name),
            "description": props.get("description", ""),
            "policy_type": props.get("policyType", "Custom"),
            "metadata": props.get("metadata", {}),
            "parameters": list(props.get("parameters", {}).keys()),
            "policy_definition_count": len(props.get("policyDefinitions", [])),
            "policy_definitions": [],
            "source_file": str(filepath.name),
        }

        # Extract policy definition references
        for pd in props.get("policyDefinitions", []):
            ref = {
                "policy_definition_id": pd.get("policyDefinitionId", ""),
                "policy_definition_reference_id": pd.get("policyDefinitionReferenceId", ""),
                "parameters": {k: str(v) for k, v in pd.get("parameters", {}).items()},
            }
            # Extract built-in policy GUID from reference ID
            pid = pd.get("policyDefinitionId", "")
            guid_match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", pid, re.I)
            if guid_match:
                ref["policy_guid"] = guid_match.group(0)
            initiative["policy_definitions"].append(ref)

        # Classify
        initiative["sovereignty_level"] = classify_sovereignty_level(initiative)
        initiative["sovereignty_objectives"] = classify_sovereignty_objective(initiative)
        initiative["service_category"] = classify_service_category(initiative)

        return initiative

    except Exception as e:
        logger.warning(f"Failed to parse {filepath}: {e}")
        return None


def parse_alz_policy_assignment(filepath: Path) -> Optional[Dict[str, Any]]:
    """Parse an ALZ policy assignment JSON file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        name = data.get("name", filepath.stem.replace(".alz_policy_assignment", ""))
        props = data.get("properties", {})

        assignment = {
            "name": name,
            "display_name": props.get("displayName", name),
            "description": props.get("description", ""),
            "policy_definition_id": props.get("policyDefinitionId", ""),
            "enforcement_mode": data.get("enforcementMode", props.get("enforcementMode", "Default")),
            "parameters": {k: str(v) for k, v in props.get("parameters", {}).items()},
            "non_compliance_messages": props.get("nonComplianceMessages", []),
            "identity": data.get("identity", {}),
            "source_file": str(filepath.name),
        }

        return assignment

    except Exception as e:
        logger.warning(f"Failed to parse {filepath}: {e}")
        return None


def parse_archetype_definition(filepath: Path) -> Optional[Dict[str, Any]]:
    """Parse an SLZ archetype definition JSON file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        archetype = {
            "name": data.get("name", filepath.stem),
            "display_name": data.get("display_name", filepath.stem),
            "policy_assignments": data.get("policy_assignments", []),
            "policy_definitions": data.get("policy_definitions", []),
            "policy_set_definitions": data.get("policy_set_definitions", []),
            "role_assignments": data.get("role_assignments", []),
            "source_file": str(filepath.name),
        }

        return archetype

    except Exception as e:
        logger.warning(f"Failed to parse {filepath}: {e}")
        return None


def walk_slz_directory(slz_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Walk the SLZ directory and parse all policy files."""
    results = {
        "policy_definitions": [],
        "policy_set_definitions": [],
        "policy_assignments": [],
        "archetype_definitions": [],
    }

    if not slz_dir.exists():
        logger.error(f"SLZ directory not found: {slz_dir}")
        return results

    for root, dirs, files in os.walk(slz_dir):
        for fname in sorted(files):
            fpath = Path(root) / fname

            if fname.endswith(".alz_policy_definition.json"):
                parsed = parse_alz_policy_definition(fpath)
                if parsed:
                    results["policy_definitions"].append(parsed)

            elif fname.endswith(".alz_policy_set_definition.json"):
                parsed = parse_alz_policy_set_definition(fpath)
                if parsed:
                    results["policy_set_definitions"].append(parsed)

            elif fname.endswith(".alz_policy_assignment.json"):
                parsed = parse_alz_policy_assignment(fpath)
                if parsed:
                    results["policy_assignments"].append(parsed)

            elif fname.endswith(".alz_archetype_definition.json") or (
                "archetype_definitions" in str(root) and fname.endswith(".json")
            ):
                parsed = parse_archetype_definition(fpath)
                if parsed:
                    results["archetype_definitions"].append(parsed)

    return results


def build_slz_data(raw: Dict[str, List[Dict]]) -> Dict[str, Any]:
    """Build the final SLZ data structure for the SovereigntyService."""

    # Enrich archetypes with static metadata
    archetypes = []
    for arch_raw in raw["archetype_definitions"]:
        arch_name = arch_raw["name"]
        static_meta = SLZ_ARCHETYPES.get(arch_name, {})
        merged = {**arch_raw, **static_meta} if static_meta else arch_raw
        archetypes.append(merged)

    # If no archetypes were parsed from files, use our static definitions
    if not archetypes:
        archetypes = [{"name": k, **v} for k, v in SLZ_ARCHETYPES.items()]

    return {
        "metadata": {
            "source": "Azure/Azure-Landing-Zones-Library",
            "slz_path": SLZ_PATH,
            "policy_definition_count": len(raw["policy_definitions"]),
            "policy_set_definition_count": len(raw["policy_set_definitions"]),
            "policy_assignment_count": len(raw["policy_assignments"]),
            "archetype_count": len(archetypes),
        },
        "sovereignty_objectives": SOVEREIGNTY_OBJECTIVES,
        "built_in_initiatives": BUILT_IN_INITIATIVES,
        "policy_definitions": raw["policy_definitions"],
        "policy_set_definitions": raw["policy_set_definitions"],
        "policy_assignments": raw["policy_assignments"],
        "archetypes": archetypes,
    }


def write_output(data: Dict[str, Any], output_dir: Path) -> None:
    """Write the SLZ data to output JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Main policies file
    policies_file = output_dir / "slz_policies.json"
    with open(policies_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Wrote {policies_file} ({policies_file.stat().st_size / 1024:.1f} KB)")

    # Archetypes file (smaller, for quick access)
    archetypes_file = output_dir / "slz_archetypes.json"
    archetypes_data = {
        "archetypes": data["archetypes"],
        "sovereignty_objectives": data["sovereignty_objectives"],
        "built_in_initiatives": data["built_in_initiatives"],
    }
    with open(archetypes_file, "w", encoding="utf-8") as f:
        json.dump(archetypes_data, f, indent=2, default=str)
    logger.info(f"Wrote {archetypes_file} ({archetypes_file.stat().st_size / 1024:.1f} KB)")

    # Summary
    logger.info("=" * 60)
    logger.info("SLZ Data Sync Summary")
    logger.info("=" * 60)
    logger.info(f"  Policy definitions:     {data['metadata']['policy_definition_count']}")
    logger.info(f"  Policy set definitions:  {data['metadata']['policy_set_definition_count']}")
    logger.info(f"  Policy assignments:      {data['metadata']['policy_assignment_count']}")
    logger.info(f"  Archetypes:              {data['metadata']['archetype_count']}")

    # Level breakdown
    levels = {"L1": 0, "L2": 0, "L3": 0}
    for pd in data["policy_definitions"]:
        lvl = pd.get("sovereignty_level", "L1")
        levels[lvl] = levels.get(lvl, 0) + 1
    logger.info(f"  Level breakdown:         L1={levels['L1']}, L2={levels['L2']}, L3={levels['L3']}")


def generate_fallback_data(output_dir: Path) -> None:
    """
    Generate SLZ data from known built-in policies when the repo cannot be cloned.
    This provides a usable starting point without network access.
    """
    logger.info("Generating fallback SLZ data from known sovereignty policies...")

    # Well-known SLZ policies from Microsoft documentation
    known_policies = [
        # SO-1: Data Residency
        {
            "name": "allowed-locations",
            "display_name": "Allowed locations",
            "description": "This policy enables you to restrict the locations your organization can specify when deploying resources.",
            "effect": "Deny",
            "sovereignty_level": "L1",
            "sovereignty_objectives": ["SO-1"],
            "service_category": "General",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "General"},
            "parameters": {},
            "parameter_names": ["listOfAllowedLocations"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "allowed-locations-for-resource-groups",
            "display_name": "Allowed locations for resource groups",
            "description": "This policy enables you to restrict the locations your organization can create resource groups in.",
            "effect": "Deny",
            "sovereignty_level": "L1",
            "sovereignty_objectives": ["SO-1"],
            "service_category": "General",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "General"},
            "parameters": {},
            "parameter_names": ["listOfAllowedLocations"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        # SO-3: Customer-Managed Keys
        {
            "name": "cmk-recovery-services",
            "display_name": "Azure Recovery Services vaults should use customer-managed keys for encrypting backup data",
            "description": "Use customer-managed keys to manage the encryption at rest of your backup data.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Security",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Backup"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-container-instances",
            "display_name": "Azure container instance container group should use customer-managed key for encryption",
            "description": "Secure your containers with greater flexibility using customer-managed keys.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Containers",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Container Instance"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-aks",
            "display_name": "Azure Kubernetes Service clusters should use customer-managed keys for disk encryption",
            "description": "Encrypt at rest OS and data disks of AKS cluster nodes with customer-managed keys.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Containers",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Kubernetes"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-managed-disks",
            "display_name": "Managed disks should be double encrypted with both platform-managed and customer-managed keys",
            "description": "Customers can select double encryption with both platform- and customer-managed keys.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Compute",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Compute"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-mysql",
            "display_name": "MySQL servers should use customer-managed keys to encrypt data at rest",
            "description": "Use customer-managed keys to manage the encryption at rest of your MySQL servers.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Databases",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "SQL"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-os-data-disks",
            "display_name": "OS and data disks should be encrypted with a customer-managed key",
            "description": "Use customer-managed keys to manage the encryption at rest of the contents of your managed disks.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Compute",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Compute"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-postgresql",
            "display_name": "PostgreSQL servers should use customer-managed keys to encrypt data at rest",
            "description": "Use customer-managed keys to manage the encryption at rest of your PostgreSQL servers.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Databases",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "SQL"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-queue-storage",
            "display_name": "Queue Storage should use customer-managed key for encryption",
            "description": "Secure your queue storage with greater flexibility using customer-managed keys.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Storage",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Storage"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-sql-mi",
            "display_name": "SQL managed instances should use customer-managed keys to encrypt data at rest",
            "description": "Use customer-managed keys for TDE on your SQL managed instances.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Databases",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "SQL"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-sql-server",
            "display_name": "SQL servers should use customer-managed keys to encrypt data at rest",
            "description": "Use customer-managed keys for TDE on your SQL servers.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Databases",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "SQL"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-storage-scope",
            "display_name": "Storage account encryption scopes should use customer-managed keys to encrypt data at rest",
            "description": "Use customer-managed keys for encryption scopes on storage accounts.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Storage",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Storage"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-storage-account",
            "display_name": "Storage accounts should use customer-managed key for encryption",
            "description": "Secure your blob and file storage with customer-managed keys.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Storage",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Storage"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-table-storage",
            "display_name": "Table Storage should use customer-managed key for encryption",
            "description": "Secure your table storage with greater flexibility using customer-managed keys.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Storage",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Storage"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-hpc-cache",
            "display_name": "HPC Cache accounts should use customer-managed key for encryption",
            "description": "Manage encryption at rest of Azure HPC Cache with customer-managed keys.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Compute",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Storage"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "cmk-cosmos-db",
            "display_name": "Azure Cosmos DB accounts should use customer-managed keys to encrypt data at rest",
            "description": "Use customer-managed keys to manage the encryption at rest of your Azure Cosmos DB.",
            "effect": "Audit",
            "sovereignty_level": "L2",
            "sovereignty_objectives": ["SO-3"],
            "service_category": "Databases",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Cosmos DB"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        # SO-4: Confidential Computing
        {
            "name": "allowed-resource-types-cc",
            "display_name": "Allowed resource types",
            "description": "Restrict resource types to only those supporting confidential computing.",
            "effect": "Deny",
            "sovereignty_level": "L3",
            "sovereignty_objectives": ["SO-4"],
            "service_category": "Compute",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "General"},
            "parameters": {},
            "parameter_names": ["listOfResourceTypesAllowed"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "allowed-vm-skus-cc",
            "display_name": "Allowed virtual machine size SKUs",
            "description": "Restrict VM SKU sizes to only confidential computing-capable series.",
            "effect": "Deny",
            "sovereignty_level": "L3",
            "sovereignty_objectives": ["SO-4"],
            "service_category": "Compute",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Compute"},
            "parameters": {},
            "parameter_names": ["listOfAllowedSKUs"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        # SO-5: Trusted Launch
        {
            "name": "disk-os-trustedlaunch",
            "display_name": "Disks and OS image should support TrustedLaunch",
            "description": "Ensure managed disks and OS images support Trusted Launch.",
            "effect": "Audit",
            "sovereignty_level": "L1",
            "sovereignty_objectives": ["SO-5"],
            "service_category": "Compute",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Compute"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
        {
            "name": "vm-trustedlaunch",
            "display_name": "Virtual Machine should have TrustedLaunch enabled",
            "description": "Enable TrustedLaunch on virtual machine to protect from boot-level attacks.",
            "effect": "Audit",
            "sovereignty_level": "L1",
            "sovereignty_objectives": ["SO-5"],
            "service_category": "Compute",
            "policy_type": "BuiltIn",
            "mode": "All",
            "metadata": {"category": "Compute"},
            "parameters": {},
            "parameter_names": ["effect"],
            "policy_rule": {},
            "source_file": "builtin",
        },
    ]

    # Build the same structure as the full sync
    data = {
        "metadata": {
            "source": "fallback-known-policies",
            "slz_path": "N/A",
            "policy_definition_count": len(known_policies),
            "policy_set_definition_count": 2,
            "policy_assignment_count": 4,
            "archetype_count": len(SLZ_ARCHETYPES),
        },
        "sovereignty_objectives": SOVEREIGNTY_OBJECTIVES,
        "built_in_initiatives": BUILT_IN_INITIATIVES,
        "policy_definitions": known_policies,
        "policy_set_definitions": [
            {
                "name": "Sovereignty-Baseline-Global",
                "display_name": "Sovereignty Baseline - Global Policies",
                "description": "Enforces SO-1 (Data Residency) and SO-5 (Trusted Launch) across all sovereign workloads.",
                "sovereignty_level": "L1",
                "sovereignty_objectives": ["SO-1", "SO-5"],
                "service_category": "General",
                "policy_type": "BuiltIn",
                "metadata": {},
                "parameters": ["listOfAllowedLocations"],
                "policy_definition_count": 4,
                "policy_definitions": [],
                "source_file": "builtin",
            },
            {
                "name": "Sovereignty-Baseline-Confidential",
                "display_name": "Sovereignty Baseline - Confidential Policies",
                "description": "Enforces SO-1, SO-3 (CMK), and SO-4 (Confidential Computing) for confidential workloads.",
                "sovereignty_level": "L3",
                "sovereignty_objectives": ["SO-1", "SO-3", "SO-4"],
                "service_category": "General",
                "policy_type": "BuiltIn",
                "metadata": {},
                "parameters": ["listOfAllowedLocations", "listOfResourceTypesAllowed", "listOfAllowedSKUs"],
                "policy_definition_count": 18,
                "policy_definitions": [],
                "source_file": "builtin",
            },
        ],
        "policy_assignments": [
            {
                "name": "Enforce-Sovereign-Global",
                "display_name": "Enforce Sovereignty Baseline - Global",
                "description": "Assigns the Sovereignty Baseline Global initiative at sovereignty root.",
                "policy_definition_id": "Sovereignty-Baseline-Global",
                "enforcement_mode": "Default",
                "parameters": {},
                "non_compliance_messages": [],
                "identity": {},
                "source_file": "builtin",
            },
            {
                "name": "Enforce-Sovereign-Conf",
                "display_name": "Enforce Sovereignty Baseline - Confidential",
                "description": "Assigns the Sovereignty Baseline Confidential initiative at confidential MGs.",
                "policy_definition_id": "Sovereignty-Baseline-Confidential",
                "enforcement_mode": "Default",
                "parameters": {},
                "non_compliance_messages": [],
                "identity": {},
                "source_file": "builtin",
            },
        ],
        "archetypes": [{"name": k, **v} for k, v in SLZ_ARCHETYPES.items()],
    }

    write_output(data, output_dir)


def main():
    parser = argparse.ArgumentParser(description="Sync SLZ policies from Azure-Landing-Zones-Library")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "app" / "data"),
        help="Directory to write output JSON files",
    )
    parser.add_argument(
        "--repo-dir",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / ".cache" / "Azure-Landing-Zones-Library"),
        help="Directory to clone/cache the repo",
    )
    parser.add_argument(
        "--fallback",
        action="store_true",
        help="Skip repo clone and generate from known built-in policies",
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    repo_dir = Path(args.repo_dir)

    if args.fallback:
        generate_fallback_data(output_dir)
        return

    try:
        clone_or_pull_repo(repo_dir)
        slz_dir = repo_dir / SLZ_PATH

        logger.info(f"Parsing SLZ policies from {slz_dir}")
        raw = walk_slz_directory(slz_dir)

        if not any(raw.values()):
            logger.warning("No SLZ files found in repo. Generating fallback data.")
            generate_fallback_data(output_dir)
            return

        data = build_slz_data(raw)
        write_output(data, output_dir)

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        logger.warning(f"Git operations failed: {e}. Generating fallback data.")
        generate_fallback_data(output_dir)


if __name__ == "__main__":
    main()
