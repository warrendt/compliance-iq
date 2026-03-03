"""
Azure Policy Initiative Generation Service.
Generates valid Azure Policy initiative definitions from control mappings.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.models import (
    ControlMapping,
    PolicyInitiative,
    PolicyInitiativeProperties,
    PolicyInitiativeMetadata,
    PolicyDefinitionReference,
    PolicyGenerationRequest,
    PolicyGenerationResponse
)
from app.services.sovereignty_service import get_sovereignty_service

logger = logging.getLogger(__name__)


class PolicyGenerationService:
    """Service for generating Azure Policy initiatives."""

    def generate_initiative(
        self,
        request: PolicyGenerationRequest
    ) -> PolicyGenerationResponse:
        """
        Generate Azure Policy initiative from control mappings.

        Args:
            request: Policy generation request with mappings

        Returns:
            PolicyGenerationResponse with generated initiative

        Example:
            ```python
            service = PolicyGenerationService()
            response = service.generate_initiative(request)
            json_output = response.initiative.to_azure_json()
            ```
        """
        logger.info(f"Generating policy initiative for {request.framework_name}")

        # Filter mappings by confidence threshold
        filtered_mappings, warnings = self._filter_mappings(
            request.mappings,
            request.min_confidence_threshold,
            request.include_all_policies
        )

        # Generate policy definitions
        policy_definitions = self._create_policy_definitions(filtered_mappings)

        # Create metadata
        metadata = PolicyInitiativeMetadata(
            framework_name=request.framework_name,
            framework_version=request.framework_version,
            generated_date=datetime.utcnow()
        )

        # Create properties
        properties = PolicyInitiativeProperties(
            display_name=f"{request.framework_name} Compliance Initiative",
            description=f"AI-generated policy initiative for {request.framework_name} compliance framework",
            metadata=metadata,
            policy_definitions=policy_definitions
        )

        # Create initiative
        initiative = PolicyInitiative(properties=properties)

        # Create response
        response = PolicyGenerationResponse(
            initiative=initiative,
            total_controls=len(request.mappings),
            included_policies=len(policy_definitions),
            excluded_policies=len(request.mappings) - len(filtered_mappings),
            warnings=warnings
        )

        logger.info(
            f"Generated initiative with {response.included_policies} policies, "
            f"excluded {response.excluded_policies}"
        )

        return response

    def _filter_mappings(
        self,
        mappings: List[ControlMapping],
        min_confidence: float,
        include_all: bool
    ) -> tuple[List[ControlMapping], List[str]]:
        """
        Filter mappings based on confidence threshold.

        Args:
            mappings: List of control mappings
            min_confidence: Minimum confidence threshold
            include_all: Whether to include all policies regardless of confidence

        Returns:
            Tuple of (filtered mappings, warning messages)
        """
        warnings = []

        if include_all:
            logger.debug("Including all policies (include_all=True)")
            return mappings, warnings

        # Filter by confidence
        filtered = []
        excluded_count = 0

        for mapping in mappings:
            if mapping.confidence_score >= min_confidence:
                filtered.append(mapping)
            else:
                excluded_count += 1
                logger.debug(
                    f"Excluded {mapping.external_control_id} "
                    f"(confidence {mapping.confidence_score:.2f} < {min_confidence})"
                )

        if excluded_count > 0:
            warnings.append(
                f"{excluded_count} control(s) excluded due to confidence < {min_confidence}"
            )

        # Check for controls with no Azure Policy IDs
        no_policy_count = sum(1 for m in filtered if not m.azure_policy_ids)
        if no_policy_count > 0:
            warnings.append(
                f"{no_policy_count} control(s) have no associated Azure Policy definitions"
            )

        return filtered, warnings

    def _create_policy_definitions(
        self,
        mappings: List[ControlMapping]
    ) -> List[PolicyDefinitionReference]:
        """
        Create policy definition references from mappings.

        Args:
            mappings: List of control mappings

        Returns:
            List of policy definition references
        """
        policy_definitions = []
        seen_policy_ids = set()

        for mapping in mappings:
            # Skip if no Azure Policy IDs
            if not mapping.azure_policy_ids:
                logger.warning(
                    f"Control {mapping.external_control_id} has no Azure Policy IDs"
                )
                continue

            # Create a policy definition reference for each Azure Policy
            for policy_id in mapping.azure_policy_ids:
                # Avoid duplicates
                if policy_id in seen_policy_ids:
                    logger.debug(f"Skipping duplicate policy: {policy_id}")
                    continue

                seen_policy_ids.add(policy_id)

                # Create full policy definition ID
                full_policy_id = (
                    f"/providers/Microsoft.Authorization/policyDefinitions/{policy_id}"
                )

                # Create reference
                policy_def = PolicyDefinitionReference(
                    policy_definition_id=full_policy_id,
                    policy_definition_reference_id=mapping.external_control_id,
                    parameters={}  # Can be extended to support parameterization
                )

                policy_definitions.append(policy_def)

        logger.info(f"Created {len(policy_definitions)} policy definition references")
        return policy_definitions

    def validate_initiative(self, initiative: PolicyInitiative) -> tuple[bool, List[str]]:
        """
        Validate Azure Policy initiative structure.

        Args:
            initiative: Policy initiative to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check display name
        if not initiative.properties.display_name:
            errors.append("Display name is required")

        # Check description
        if not initiative.properties.description:
            errors.append("Description is required")

        # Check policy definitions
        if not initiative.properties.policy_definitions:
            errors.append("At least one policy definition is required")

        # Validate policy definition structure
        for idx, policy_def in enumerate(initiative.properties.policy_definitions):
            if not policy_def.policy_definition_id:
                errors.append(f"Policy definition {idx}: policy_definition_id is required")

            if not policy_def.policy_definition_reference_id:
                errors.append(
                    f"Policy definition {idx}: policy_definition_reference_id is required"
                )

            # Validate policy definition ID format
            if not policy_def.policy_definition_id.startswith(
                "/providers/Microsoft.Authorization/policyDefinitions/"
            ):
                errors.append(
                    f"Policy definition {idx}: Invalid policy_definition_id format"
                )

        is_valid = len(errors) == 0

        if is_valid:
            logger.info("Initiative validation passed")
        else:
            logger.error(f"Initiative validation failed: {errors}")

        return is_valid, errors

    def export_as_json(
        self,
        initiative: PolicyInitiative,
        pretty: bool = True
    ) -> str:
        """
        Export initiative as JSON string.

        Args:
            initiative: Policy initiative to export
            pretty: Whether to pretty-print JSON

        Returns:
            JSON string
        """
        azure_json = initiative.to_azure_json()

        if pretty:
            return json.dumps(azure_json, indent=2)
        else:
            return json.dumps(azure_json)

    def export_as_bicep(
        self,
        initiative: PolicyInitiative,
        initiative_name: str = "customComplianceInitiative"
    ) -> str:
        """
        Export initiative as Bicep template.

        Args:
            initiative: Policy initiative to export
            initiative_name: Name for the Bicep resource

        Returns:
            Bicep template string
        """
        props = initiative.properties

        bicep_template = f"""// Azure Policy Initiative - {props.display_name}
// Generated by ComplianceIQ AI Mapping Agent

@description('Location for the policy initiative')
param location string = resourceGroup().location

@description('Policy initiative display name')
param displayName string = '{props.display_name}'

@description('Policy initiative description')
param description string = '{props.description}'

resource policyInitiative 'Microsoft.Authorization/policySetDefinitions@2021-06-01' = {{
  name: '{initiative_name}'
  properties: {{
    displayName: displayName
    description: description
    policyType: 'Custom'
    metadata: {{
      category: '{props.metadata.category}'
      source: '{props.metadata.source}'
      version: '{props.metadata.version}'
      frameworkName: '{props.metadata.framework_name}'
    }}
    policyDefinitions: [
"""

        # Add policy definitions
        for policy_def in props.policy_definitions:
            bicep_template += f"""      {{
        policyDefinitionId: '{policy_def.policy_definition_id}'
        policyDefinitionReferenceId: '{policy_def.policy_definition_reference_id}'
        parameters: {{}}
      }}
"""

        bicep_template += """    ]
  }
}

output initiativeId string = policyInitiative.id
output initiativeName string = policyInitiative.name
"""

        return bicep_template

    def generate_deployment_script(
        self,
        initiative: PolicyInitiative,
        initiative_name: str,
        scope_type: str = "subscription",
        enforce_mode: bool = False,
    ) -> Dict[str, str]:
        """
        Generate deployment scripts for Azure CLI and PowerShell.

        Args:
            initiative: Policy initiative
            initiative_name: Name for the initiative
            scope_type: Deployment scope (subscription, management_group)
            enforce_mode: When False (default), assignments use DoNotEnforce (audit-only).
                          When True, assignments use Default (enforcement enabled).

        Returns:
            Dictionary with 'cli' and 'powershell' script strings
        """
        enforcement_mode_ps = "Default" if enforce_mode else "DoNotEnforce"
        # Export as JSON
        json_content = self.export_as_json(initiative, pretty=False)

        # Azure CLI script
        cli_script = f"""#!/bin/bash
# Deploy {initiative.properties.display_name}

# Save initiative definition to file
cat > initiative.json <<'EOF'
{json_content}
EOF

# Create policy initiative
az policy set-definition create \\
  --name "{initiative_name}" \\
  --display-name "{initiative.properties.display_name}" \\
  --description "{initiative.properties.description}" \\
  --definitions initiative.json \\
  --metadata category="{initiative.properties.metadata.category}"

echo "Initiative created successfully"
"""

        # PowerShell script
        ps_script = f"""# Deploy {initiative.properties.display_name}
# Enforcement Mode: {enforcement_mode_ps}

param(
    [Parameter(Mandatory=$false)]
    [string]$Scope = "",

    [Parameter(Mandatory=$false)]
    [switch]$AuditOnly,

    [Parameter(Mandatory=$false)]
    [switch]$AssignAfterCreation
)

# Enforcement mode: generated from mapping agent setting, overridable via -AuditOnly switch
$EnforcementMode = if ($AuditOnly) {{ 'DoNotEnforce' }} else {{ '{enforcement_mode_ps}' }}

# Save initiative definition to file
$initiativeJson = @'
{json_content}
'@

Set-Content -Path "initiative.json" -Value $initiativeJson

# Create policy initiative
New-AzPolicySetDefinition `
  -Name "{initiative_name}" `
  -DisplayName "{initiative.properties.display_name}" `
  -Description "{initiative.properties.description}" `
  -PolicyDefinition "initiative.json" `
  -Metadata @{{category="{initiative.properties.metadata.category}"}}

Write-Host "Initiative created successfully"

if ($AssignAfterCreation) {{
    Write-Host "Assigning initiative (enforcement mode: $EnforcementMode)..." -ForegroundColor Yellow
    $context = Get-AzContext
    if (-not $context) {{ Write-Error "Not authenticated. Run Connect-AzAccount first."; exit 1 }}
    $TargetScope = if ($Scope) {{ $Scope }} else {{ "/subscriptions/$($context.Subscription.Id)" }}
    $assignmentName = "{initiative_name}-$(Get-Date -Format 'yyyyMMdd')"
    $policySetDef = Get-AzPolicySetDefinition -Name "{initiative_name}" -ErrorAction SilentlyContinue
    if ($policySetDef) {{
        $existingAssignment = Get-AzPolicyAssignment -Scope $TargetScope |
            Where-Object {{ $_.Name -eq $assignmentName }}
        if ($existingAssignment) {{
            if ($existingAssignment.Properties.EnforcementMode -ne $EnforcementMode) {{
                Set-AzPolicyAssignment -Name $assignmentName -Scope $TargetScope -EnforcementMode $EnforcementMode
                Write-Host "Updated assignment enforcement mode to: $EnforcementMode" -ForegroundColor Green
            }} else {{
                Write-Host "Assignment already up to date (enforcement: $EnforcementMode)" -ForegroundColor Green
            }}
        }} else {{
            New-AzPolicyAssignment `
                -Name $assignmentName `
                -DisplayName "{initiative.properties.display_name} - Assessment" `
                -Scope $TargetScope `
                -PolicySetDefinition $policySetDef `
                -EnforcementMode $EnforcementMode
            Write-Host "Initiative assigned (enforcement: $EnforcementMode)" -ForegroundColor Green
        }}
    }} else {{
        Write-Warning "Could not find initiative '{initiative_name}'. Assignment skipped."
    }}
}}
"""

        return {
            "cli": cli_script,
            "powershell": ps_script
        }

    # ── SLZ-Specific Initiative Generation ────────────────────────────

    def generate_slz_initiatives(
        self,
        mappings: List[ControlMapping],
        framework_name: str,
        allowed_locations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate SLZ-specific policy initiatives targeting management group archetypes.

        Produces separate initiative artifacts for each SLZ archetype:
        - sovereign_root: Global baseline (L1) policies
        - confidential_corp / confidential_online: Confidential baseline (L2+L3) policies

        Args:
            mappings: List of control mappings (must include sovereignty field)
            framework_name: Name of the compliance framework
            allowed_locations: Optional list of allowed Azure regions (e.g., ["uaecentral", "uaenorth"])

        Returns:
            Dictionary with per-archetype initiative JSON, Bicep, and deployment scripts
        """
        logger.info(f"Generating SLZ initiatives for {framework_name}")

        sovereignty_service = get_sovereignty_service()

        # Separate mappings by sovereignty level
        level_mappings: Dict[str, List[ControlMapping]] = {"L1": [], "L2": [], "L3": []}
        for m in mappings:
            if m.sovereignty and m.sovereignty.sovereignty_level:
                level = m.sovereignty.sovereignty_level
                level_mappings.setdefault(level, []).append(m)
            else:
                level_mappings["L1"].append(m)

        # Collect SLZ policy names referenced across all mappings
        all_slz_policy_names = set()
        for m in mappings:
            if m.sovereignty and m.sovereignty.slz_policy_names:
                all_slz_policy_names.update(m.sovereignty.slz_policy_names)

        # Build per-archetype artifacts
        archetypes = sovereignty_service.get_all_archetypes()
        archetype_artifacts: Dict[str, Dict[str, Any]] = {}

        for archetype in archetypes:
            arch_name = archetype.name
            arch_level = archetype.sovereignty_level

            # Determine which mappings apply to this archetype
            applicable = []
            level_hierarchy = {"L1": ["L1"], "L2": ["L1", "L2"], "L3": ["L1", "L2", "L3"]}
            for lvl in level_hierarchy.get(arch_level, ["L1"]):
                applicable.extend(level_mappings.get(lvl, []))

            if not applicable:
                continue

            # Collect policy IDs (Azure Policy + SLZ)
            policy_ids = set()
            slz_names = set()
            for m in applicable:
                for pid in m.azure_policy_ids:
                    policy_ids.add(pid)
                if m.sovereignty and m.sovereignty.slz_policy_names:
                    slz_names.update(m.sovereignty.slz_policy_names)

            # Build initiative JSON
            display_name = f"{framework_name} - SLZ {archetype.display_name or arch_name} Initiative"
            description = (
                f"Sovereign Landing Zone policy initiative for {framework_name} "
                f"targeting the {archetype.display_name or arch_name} management group archetype. "
                f"Sovereignty level: {arch_level}."
            )

            policy_defs = []
            for pid in sorted(policy_ids):
                policy_defs.append({
                    "policyDefinitionId": f"/providers/Microsoft.Authorization/policyDefinitions/{pid}",
                    "policyDefinitionReferenceId": pid[:50],
                    "parameters": {}
                })

            initiative_json = {
                "properties": {
                    "displayName": display_name,
                    "description": description,
                    "metadata": {
                        "category": "Regulatory Compliance",
                        "source": "ComplianceIQ AI Mapping Agent - SLZ",
                        "frameworkName": framework_name,
                        "sovereigntyLevel": arch_level,
                        "targetArchetype": arch_name,
                        "slzPolicies": sorted(slz_names),
                    },
                    "parameters": {},
                    "policyDefinitions": policy_defs,
                }
            }

            # Add allowed locations parameter if provided
            if allowed_locations:
                initiative_json["properties"]["parameters"]["listOfAllowedLocations"] = {
                    "type": "Array",
                    "metadata": {
                        "displayName": "Allowed locations",
                        "description": "The list of locations that can be specified when deploying resources.",
                    },
                    "defaultValue": allowed_locations,
                }

            # Generate Bicep
            bicep = self._generate_slz_bicep(
                initiative_name=f"slz_{arch_name}_{framework_name.lower().replace(' ', '_')}",
                display_name=display_name,
                description=description,
                policy_defs=policy_defs,
                sovereignty_level=arch_level,
                archetype_name=arch_name,
                allowed_locations=allowed_locations,
            )

            # Generate deployment scripts targeting management groups
            scripts = self._generate_slz_deployment_scripts(
                initiative_name=f"slz-{arch_name}-{framework_name.lower().replace(' ', '-')}",
                display_name=display_name,
                description=description,
                archetype_name=arch_name,
                initiative_json=initiative_json,
            )

            archetype_artifacts[arch_name] = {
                "archetype": archetype.model_dump(),
                "sovereignty_level": arch_level,
                "control_count": len(applicable),
                "policy_count": len(policy_defs),
                "slz_policy_names": sorted(slz_names),
                "initiative_json": initiative_json,
                "bicep_template": bicep,
                "deployment_scripts": scripts,
            }

        # Summary
        summary = {
            "framework_name": framework_name,
            "total_mappings": len(mappings),
            "sovereignty_mappings": sum(1 for m in mappings if m.sovereignty),
            "level_distribution": {k: len(v) for k, v in level_mappings.items()},
            "archetypes_generated": list(archetype_artifacts.keys()),
            "allowed_locations": allowed_locations,
        }

        logger.info(
            f"Generated SLZ initiatives for {len(archetype_artifacts)} archetypes: "
            f"{', '.join(archetype_artifacts.keys())}"
        )

        return {
            "summary": summary,
            "archetype_artifacts": archetype_artifacts,
            "built_in_initiatives": sovereignty_service.get_built_in_initiatives(),
        }

    def _generate_slz_bicep(
        self,
        initiative_name: str,
        display_name: str,
        description: str,
        policy_defs: List[Dict],
        sovereignty_level: str,
        archetype_name: str,
        allowed_locations: Optional[List[str]] = None,
    ) -> str:
        """Generate Bicep template for an SLZ initiative."""

        locations_param = ""
        if allowed_locations:
            locations_str = ", ".join(f"'{loc}'" for loc in allowed_locations)
            locations_param = f"""
@description('Allowed Azure regions for data residency (SO-1)')
param allowedLocations array = [{locations_str}]
"""

        bicep = f"""// Sovereign Landing Zone Policy Initiative
// Framework: {display_name}
// Archetype: {archetype_name} | Level: {sovereignty_level}
// Generated by ComplianceIQ AI Mapping Agent

targetScope = 'managementGroup'

@description('Management Group ID to assign this initiative')
param managementGroupId string

@description('Policy initiative display name')
param displayName string = '{display_name}'

@description('Policy initiative description')
param initiativeDescription string = '{description}'
{locations_param}
resource policyInitiative 'Microsoft.Authorization/policySetDefinitions@2021-06-01' = {{
  name: '{initiative_name}'
  properties: {{
    displayName: displayName
    description: initiativeDescription
    policyType: 'Custom'
    metadata: {{
      category: 'Regulatory Compliance'
      source: 'ComplianceIQ AI Mapping Agent - SLZ'
      sovereigntyLevel: '{sovereignty_level}'
      targetArchetype: '{archetype_name}'
    }}
    policyDefinitions: [
"""
        for pd in policy_defs:
            bicep += f"""      {{
        policyDefinitionId: '{pd["policyDefinitionId"]}'
        policyDefinitionReferenceId: '{pd["policyDefinitionReferenceId"]}'
        parameters: {{}}
      }}
"""

        bicep += f"""    ]
  }}
}}

// Assign the initiative to the target management group
resource policyAssignment 'Microsoft.Authorization/policyAssignments@2022-06-01' = {{
  name: 'assign-{initiative_name}'
  properties: {{
    displayName: '${{displayName}} - Assignment'
    description: 'Auto-assigned by ComplianceIQ for archetype {archetype_name}'
    policyDefinitionId: policyInitiative.id
    enforcementMode: 'DoNotEnforce'
  }}
}}

output initiativeId string = policyInitiative.id
output assignmentId string = policyAssignment.id
"""
        return bicep

    def _generate_slz_deployment_scripts(
        self,
        initiative_name: str,
        display_name: str,
        description: str,
        archetype_name: str,
        initiative_json: Dict,
        enforce_mode: bool = False,
    ) -> Dict[str, str]:
        """Generate deployment scripts targeting management group archetypes."""

        json_str = json.dumps(initiative_json, indent=2)

        cli_script = f"""#!/bin/bash
# =============================================================================
# SLZ Policy Initiative Deployment - {display_name}
# Target Archetype: {archetype_name}
# =============================================================================

set -euo pipefail

# Configuration
INITIATIVE_NAME="{initiative_name}"
MANAGEMENT_GROUP_ID="${{1:?Usage: $0 <management-group-id>}}"

echo "=== Deploying SLZ Initiative ==="
echo "Initiative: {display_name}"
echo "Archetype: {archetype_name}"
echo "Management Group: $MANAGEMENT_GROUP_ID"
echo ""

# Save initiative definition
cat > /tmp/${{INITIATIVE_NAME}}.json <<'EOF'
{json_str}
EOF

# Create the policy set definition at management group scope
az policy set-definition create \\
  --name "$INITIATIVE_NAME" \\
  --display-name "{display_name}" \\
  --description "{description}" \\
  --definitions /tmp/${{INITIATIVE_NAME}}.json \\
  --management-group "$MANAGEMENT_GROUP_ID" \\
  --metadata category="Regulatory Compliance"

echo ""
echo "=== Assigning Initiative ==="

# Assign to the management group
az policy assignment create \\
  --name "assign-$INITIATIVE_NAME" \\
  --display-name "{display_name} - Assignment" \\
  --policy-set-definition "$INITIATIVE_NAME" \\
  --scope "/providers/Microsoft.Management/managementGroups/$MANAGEMENT_GROUP_ID" \\
  --enforcement-mode DoNotEnforce

echo ""
echo "✅ SLZ initiative deployed and assigned to management group: $MANAGEMENT_GROUP_ID"
"""

        ps_script = f"""# =============================================================================
# SLZ Policy Initiative Deployment - {display_name}
# Target Archetype: {archetype_name}
# =============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$ManagementGroupId
)

$ErrorActionPreference = 'Stop'

$InitiativeName = "{initiative_name}"

Write-Host "=== Deploying SLZ Initiative ===" -ForegroundColor Cyan
Write-Host "Initiative: {display_name}"
Write-Host "Archetype: {archetype_name}"
Write-Host "Management Group: $ManagementGroupId"
Write-Host ""

# Initiative definition
$InitiativeJson = @'
{json_str}
'@

$TempFile = [System.IO.Path]::GetTempFileName()
Set-Content -Path $TempFile -Value $InitiativeJson

# Create policy set definition at management group scope
New-AzPolicySetDefinition `
    -Name $InitiativeName `
    -DisplayName "{display_name}" `
    -Description "{description}" `
    -PolicyDefinition $TempFile `
    -ManagementGroupName $ManagementGroupId `
    -Metadata @{{category="Regulatory Compliance"}}

Write-Host ""
Write-Host "=== Assigning Initiative ===" -ForegroundColor Cyan

# Get the policy set definition
$PolicySetDef = Get-AzPolicySetDefinition -Name $InitiativeName -ManagementGroupName $ManagementGroupId

# Assign to management group
New-AzPolicyAssignment `
    -Name "assign-$InitiativeName" `
    -DisplayName "{display_name} - Assignment" `
    -PolicySetDefinition $PolicySetDef `
    -Scope "/providers/Microsoft.Management/managementGroups/$ManagementGroupId" `
    -EnforcementMode DoNotEnforce

Write-Host ""
Write-Host "✅ SLZ initiative deployed and assigned to management group: $ManagementGroupId" -ForegroundColor Green

# Cleanup
Remove-Item $TempFile -Force
"""

        return {
            "cli": cli_script,
            "powershell": ps_script,
        }


def get_policy_service() -> PolicyGenerationService:
    """Get policy generation service instance."""
    return PolicyGenerationService()
