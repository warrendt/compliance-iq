"""
Azure Policy Initiative Generation Service.
Generates valid Azure Policy initiative definitions from control mappings.
"""

import logging
import json
import re
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.models import (
    ControlMapping,
    PolicyInitiative,
    PolicyInitiativeProperties,
    PolicyInitiativeMetadata,
    PolicyDefinitionReference,
    PolicyDefinitionGroup,
    PolicyGenerationRequest,
    PolicyGenerationResponse
)
from app.services.sovereignty_service import get_sovereignty_service
from app.services.policy_catalog_service import get_policy_catalog_service

logger = logging.getLogger(__name__)

# Azure Policy definition IDs (built-in and custom) are referenced by a UUID.
# Anything that is not a well-formed GUID (e.g. an LLM-hallucinated document
# title) is not a real policy definition and would be rejected by ARM, so it is
# stripped at generation time rather than emitted into the initiative.
_POLICY_GUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _is_valid_policy_guid(policy_id: str) -> bool:
    """Return True if ``policy_id`` is a well-formed Azure Policy definition GUID.

    Accepts either a bare GUID or a full
    ``/providers/Microsoft.Authorization/policyDefinitions/<guid>`` resource ID,
    validating only the trailing definition segment.
    """
    if not policy_id:
        return False
    segment = policy_id.strip().rstrip("/").rsplit("/", 1)[-1]
    return bool(_POLICY_GUID_PATTERN.match(segment))


def _sanitize_ref_id(value: str) -> str:
    """Sanitize a string into a safe ``policyDefinitionReferenceId`` fragment."""
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", (value or "").strip()).strip("_")
    return cleaned or "control"


def _sanitize_group_name(value: str) -> str:
    """Sanitize a control ID into a valid ``policyDefinitionGroups`` name.

    Azure group names allow alphanumerics and underscores; anything else is
    collapsed to an underscore so member policies can reference the group via
    ``groupNames``.
    """
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", (value or "").strip()).strip("_")
    return cleaned or "control"


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

        # Generate policy definitions (invalid/hallucinated GUIDs are stripped)
        # and the control groupings that make this a Regulatory Compliance
        # initiative.
        (
            policy_definitions,
            groups,
            invalid_policy_ids,
            non_includable_ids,
            parameterized_ids,
        ) = self._create_policy_definitions(filtered_mappings)

        unique_invalid = sorted(set(invalid_policy_ids))
        if unique_invalid:
            preview = ", ".join(unique_invalid[:5])
            if len(unique_invalid) > 5:
                preview += ", …"
            warnings.append(
                f"{len(unique_invalid)} invalid policy definition ID(s) dropped "
                f"(not valid Azure Policy GUIDs): {preview}"
            )

        unique_non_includable = sorted(set(non_includable_ids))
        if unique_non_includable:
            preview = ", ".join(unique_non_includable[:5])
            if len(unique_non_includable) > 5:
                preview += ", …"
            warnings.append(
                f"{len(unique_non_includable)} non-includable built-in policy(ies) "
                f"dropped (cannot be part of a custom policy set, e.g. System "
                f"Policy): {preview}"
            )

        unique_parameterized = sorted(set(parameterized_ids))
        if unique_parameterized:
            preview = ", ".join(unique_parameterized[:5])
            if len(unique_parameterized) > 5:
                preview += ", …"
            warnings.append(
                f"{len(unique_parameterized)} parameterized built-in policy(ies) "
                f"dropped (require a parameter value with no default, e.g. vault "
                f"name/region, so ARM would reject the set definition): {preview}"
            )

        # Create metadata
        metadata = PolicyInitiativeMetadata(
            framework_name=request.framework_name,
            framework_version=request.framework_version,
            generated_date=datetime.now(timezone.utc)
        )

        # Create properties
        properties = PolicyInitiativeProperties(
            display_name=f"{request.framework_name} Compliance Initiative",
            description=f"AI-generated policy initiative for {request.framework_name} compliance framework",
            metadata=metadata,
            policy_definitions=policy_definitions,
            policy_definition_groups=groups
        )

        # Create initiative
        initiative = PolicyInitiative(properties=properties)

        # Create response
        response = PolicyGenerationResponse(
            initiative=initiative,
            total_controls=len(request.mappings),
            included_policies=len(policy_definitions),
            excluded_policies=len(request.mappings) - len(filtered_mappings),
            invalid_policies=len(unique_invalid),
            excluded_builtin_policies=len(unique_non_includable),
            excluded_parameterized_policies=len(unique_parameterized),
            warnings=warnings
        )

        logger.info(
            f"Generated initiative with {response.included_policies} policies, "
            f"excluded {response.excluded_policies}, "
            f"dropped {response.invalid_policies} invalid policy ID(s)"
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
    ) -> tuple[
        List[PolicyDefinitionReference],
        List[PolicyDefinitionGroup],
        List[str],
        List[str],
        List[str],
    ]:
        """
        Create policy definition references and control groups from mappings.

        Each external control becomes one ``policyDefinitionGroups`` entry and its
        mapped policies reference it via ``groupNames`` — this is what turns a flat
        policy set definition into a Regulatory-Compliance-style initiative. A
        policy GUID shared by several controls is emitted once but accumulates the
        group names of every control it maps to (mirrors the pipeline builder).

        Any ``azure_policy_ids`` entry that is not a well-formed Azure Policy
        definition GUID is dropped (it would be rejected by ARM as
        ``PolicyDefinitionNotFound``) and returned separately for honest
        reporting.

        Built-ins the catalog positively classifies as non-includable (e.g.
        "System Policy") are also dropped — ARM rejects them with "can not be part
        of a custom policy set", which would break the generated deployment
        scripts. They are returned separately so callers can report them.

        Built-ins that have a required (no-default) parameter are dropped too:
        ARM rejects the set definition with ``MissingPolicyParameter`` unless a
        value is supplied, and the generator cannot invent resource-specific
        values (vault names, regions, workspace IDs). They are returned separately
        for honest reporting.

        Args:
            mappings: List of control mappings

        Returns:
            Tuple of (policy definition references, control groups, dropped
            invalid IDs, dropped non-includable built-in IDs, dropped
            parameterized built-in IDs)
        """
        catalog = get_policy_catalog_service()
        policy_by_full_id: Dict[str, PolicyDefinitionReference] = {}
        ordered_definitions: List[PolicyDefinitionReference] = []
        groups_by_name: Dict[str, PolicyDefinitionGroup] = {}
        ordered_groups: List[PolicyDefinitionGroup] = []
        used_ref_ids: set[str] = set()
        invalid_ids: List[str] = []
        non_includable_ids: List[str] = []
        parameterized_ids: List[str] = []

        for mapping in mappings:
            # Skip if no Azure Policy IDs
            if not mapping.azure_policy_ids:
                logger.warning(
                    f"Control {mapping.external_control_id} has no Azure Policy IDs"
                )
                continue

            # One group per external control (created lazily; pruned later if it
            # ends up with no valid policies).
            group_name = _sanitize_group_name(mapping.external_control_id)
            if group_name not in groups_by_name:
                display_name = mapping.external_control_id
                if mapping.external_control_name:
                    display_name = (
                        f"{mapping.external_control_id}: {mapping.external_control_name}"
                    )
                group = PolicyDefinitionGroup(
                    name=group_name,
                    display_name=display_name,
                    category=mapping.mcsb_domain or None,
                    description=mapping.reasoning or None,
                )
                groups_by_name[group_name] = group
                ordered_groups.append(group)

            # Create a policy definition reference for each Azure Policy
            for policy_id in mapping.azure_policy_ids:
                # Strip hallucinated / malformed policy definition IDs that ARM
                # would reject (e.g. document titles instead of GUIDs).
                if not _is_valid_policy_guid(policy_id):
                    invalid_ids.append(policy_id)
                    logger.warning(
                        f"Control {mapping.external_control_id}: dropping invalid "
                        f"Azure Policy definition ID '{policy_id}' (not a valid GUID)"
                    )
                    continue

                # Bare GUID for catalog lookup (policy_id may be a full resource ID).
                policy_guid = policy_id.strip().rstrip("/").rsplit("/", 1)[-1]

                # Strip built-ins that cannot be part of a custom policy set (e.g.
                # "System Policy"). ARM rejects them with "can not be part of a
                # custom policy set", which would break the generated deployment
                # scripts. Only dropped when the catalog positively classifies them.
                if catalog.is_non_includable(policy_guid):
                    non_includable_ids.append(policy_guid)
                    logger.warning(
                        f"Control {mapping.external_control_id}: dropping "
                        f"non-includable built-in '{policy_guid}' "
                        f"(cannot be part of a custom policy set)"
                    )
                    continue

                # Strip built-ins that have a required (no-default) parameter.
                # ARM rejects the set definition with "MissingPolicyParameter"
                # unless a value is supplied, and the generator cannot invent
                # resource-specific values. Only dropped when the catalog
                # positively flags them.
                if catalog.requires_parameters(policy_guid):
                    parameterized_ids.append(policy_guid)
                    logger.warning(
                        f"Control {mapping.external_control_id}: dropping "
                        f"parameterized built-in '{policy_guid}' "
                        f"(has a required parameter with no default value)"
                    )
                    continue

                # Create full policy definition ID
                full_policy_id = (
                    f"/providers/Microsoft.Authorization/policyDefinitions/{policy_guid}"
                )

                # A policy shared across controls is emitted once but joins each
                # control's group.
                existing = policy_by_full_id.get(full_policy_id)
                if existing is not None:
                    if group_name not in existing.group_names:
                        existing.group_names.append(group_name)
                    continue

                # Azure requires a UNIQUE policyDefinitionReferenceId per set.
                # Multiple controls (or one control with several policies) would
                # otherwise collide on the bare control ID and ARM would reject
                # the initiative. Derive a stable, unique reference id.
                base_ref = _sanitize_ref_id(mapping.external_control_id)
                ref_id = base_ref
                suffix = 2
                while ref_id in used_ref_ids:
                    ref_id = f"{base_ref}_{suffix}"
                    suffix += 1
                used_ref_ids.add(ref_id)

                # Create reference
                policy_def = PolicyDefinitionReference(
                    policy_definition_id=full_policy_id,
                    policy_definition_reference_id=ref_id,
                    parameters={},  # Can be extended to support parameterization
                    group_names=[group_name],
                )

                policy_by_full_id[full_policy_id] = policy_def
                ordered_definitions.append(policy_def)

        # Only keep groups that ended up with at least one valid policy so the
        # initiative never references an empty control group.
        used_group_names = {
            name for pd in ordered_definitions for name in pd.group_names
        }
        groups = [g for g in ordered_groups if g.name in used_group_names]

        logger.info(
            f"Created {len(ordered_definitions)} policy definition references "
            f"across {len(groups)} control group(s)"
            + (f", dropped {len(invalid_ids)} invalid" if invalid_ids else "")
            + (
                f", dropped {len(non_includable_ids)} non-includable"
                if non_includable_ids else ""
            )
            + (
                f", dropped {len(parameterized_ids)} parameterized"
                if parameterized_ids else ""
            )
        )
        return (
            ordered_definitions,
            groups,
            invalid_ids,
            non_includable_ids,
            parameterized_ids,
        )

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

        # Add policy definitions (with control group membership)
        for policy_def in props.policy_definitions:
            group_names_bicep = ", ".join(
                f"'{name}'" for name in policy_def.group_names
            )
            bicep_template += f"""      {{
        policyDefinitionId: '{policy_def.policy_definition_id}'
        policyDefinitionReferenceId: '{policy_def.policy_definition_reference_id}'
        parameters: {{}}
        groupNames: [{group_names_bicep}]
      }}
"""

        bicep_template += "    ]\n"

        # Add control groups (Regulatory Compliance grouping)
        if props.policy_definition_groups:
            bicep_template += "    policyDefinitionGroups: [\n"
            for group in props.policy_definition_groups:
                bicep_template += f"      {{\n        name: '{group.name}'\n"
                if group.display_name:
                    safe_display = group.display_name.replace("'", "\\'")
                    bicep_template += f"        displayName: '{safe_display}'\n"
                if group.category:
                    safe_category = group.category.replace("'", "\\'")
                    bicep_template += f"        category: '{safe_category}'\n"
                bicep_template += "      }\n"
            bicep_template += "    ]\n"

        bicep_template += """  }
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
        location: str = "eastus",
    ) -> Dict[str, str]:
        """
        Generate deployment scripts for Azure CLI and PowerShell.

        Args:
            initiative: Policy initiative
            initiative_name: Name for the initiative
            scope_type: Deployment scope (subscription, management_group)
            enforce_mode: When False (default), assignments use DoNotEnforce (audit-only).
                          When True, assignments use Default (enforcement enabled).
            location: Region for the assignment's managed identity. An identity is
                      mandatory even in DoNotEnforce mode because Regulatory
                      Compliance initiatives typically contain DeployIfNotExists /
                      Modify policies, which Azure refuses to assign without one.

        Returns:
            Dictionary with 'cli' and 'powershell' script strings
        """
        enforcement_mode_ps = "Default" if enforce_mode else "DoNotEnforce"

        # New-AzPolicySetDefinition / `az policy set-definition create` take the
        # policy references and the control groups as SEPARATE arrays — not the
        # `{"properties": {...}}` wrapper. Passing the wrapper (or omitting the
        # groups) is why an earlier build produced an ungrouped "Custom (legacy)"
        # initiative. Split them here.
        props = initiative.to_azure_json()["properties"]
        policy_definitions = props.get("policyDefinitions", [])
        policy_groups = props.get("policyDefinitionGroups", [])
        policy_definitions_json = json.dumps(policy_definitions, indent=2)
        policy_groups_json = json.dumps(policy_groups, indent=2)
        category = initiative.properties.metadata.category
        has_groups = bool(policy_groups)

        # ── Azure CLI script ──────────────────────────────────────────────
        cli_groups_file = (
            f"""
cat > policy-groups.json <<'EOF'
{policy_groups_json}
EOF
"""
            if has_groups
            else ""
        )
        cli_groups_arg = "  --definition-groups policy-groups.json \\\n" if has_groups else ""

        # A stable GUID for the optional Defender for Cloud custom standard.
        cli_standard_guid = str(uuid.uuid4())
        safe_display = initiative.properties.display_name.replace('"', '\\"')
        safe_desc = (initiative.properties.description or "").replace('"', '\\"')

        cli_script = f"""#!/bin/bash
# Deploy {initiative.properties.display_name}
#
# Creates three resources (all audit-only by default):
#   1. the policy set definition (initiative)
#   2. an assignment (DoNotEnforce + system-assigned identity)
#   3. a Defender for Cloud custom compliance standard linking the initiative
#
# A managed identity is attached to the assignment even in DoNotEnforce mode
# because Regulatory Compliance initiatives typically contain DeployIfNotExists /
# Modify policies, which Azure refuses to assign without an identity + location.
set -euo pipefail

SUBSCRIPTION_ID="${{SUBSCRIPTION_ID:-$(az account show --query id -o tsv)}}"
SCOPE="/subscriptions/$SUBSCRIPTION_ID"
LOCATION="${{LOCATION:-{location}}}"
INITIATIVE_NAME="{initiative_name}"
ASSIGNMENT_NAME="{initiative_name}-audit"

# Regulatory Compliance initiative: policy references and control groups are
# supplied as separate arrays.
cat > policy-definitions.json <<'EOF'
{policy_definitions_json}
EOF
{cli_groups_file}
# 1. Create policy initiative (metadata is JSON — a "key=value" shorthand breaks
#    on values containing spaces such as "Regulatory Compliance").
az policy set-definition create \\
  --name "$INITIATIVE_NAME" \\
  --display-name "{safe_display}" \\
  --description "{safe_desc}" \\
  --definitions policy-definitions.json \\
{cli_groups_arg}  --subscription "$SUBSCRIPTION_ID" \\
  --metadata '{{"category":"{category}"}}'
echo "Initiative created."

# 2. Assign it audit-only, with a system-assigned identity (mandatory for
#    DeployIfNotExists / Modify policies even under DoNotEnforce).
SETDEF_ID="$SCOPE/providers/Microsoft.Authorization/policySetDefinitions/$INITIATIVE_NAME"
az policy assignment create \\
  --name "$ASSIGNMENT_NAME" \\
  --display-name "{safe_display} - Assessment (audit-only)" \\
  --policy-set-definition "$SETDEF_ID" \\
  --scope "$SCOPE" \\
  --enforcement-mode DoNotEnforce \\
  --mi-system-assigned \\
  --location "$LOCATION"
echo "Initiative assigned (audit-only)."

# 3. (Optional) Register a Defender for Cloud custom compliance standard so the
#    initiative appears under Defender for Cloud > Regulatory compliance.
#    Requires the Microsoft Defender CSPM plan on the scope. The assessments
#    field must be present ([] is accepted; a null value returns HTTP 400).
STANDARD_GUID="{cli_standard_guid}"
cat > defender-standard.json <<EOF
{{
  "properties": {{
    "displayName": "{safe_display}",
    "description": "{safe_desc}",
    "cloudProviders": ["Azure"],
    "assessments": [],
    "policySetDefinitionId": "$SETDEF_ID"
  }}
}}
EOF
az rest --method put \\
  --url "https://management.azure.com$SCOPE/providers/Microsoft.Security/securityStandards/$STANDARD_GUID?api-version=2024-08-01" \\
  --headers "Content-Type=application/json" \\
  --body @defender-standard.json
echo "Defender for Cloud custom standard registered: $STANDARD_GUID"
"""

        # ── PowerShell script ─────────────────────────────────────────────
        ps_groups_block = (
            f"""
$groupDefinitions = @'
{policy_groups_json}
'@
"""
            if has_groups
            else ""
        )
        ps_groups_arg = "  -GroupDefinition $groupDefinitions `\n" if has_groups else ""

        ps_script = f"""# Deploy {initiative.properties.display_name}
# Enforcement Mode: {enforcement_mode_ps}

param(
    [Parameter(Mandatory=$false)]
    [string]$Scope = "",

    [Parameter(Mandatory=$false)]
    [string]$Location = "{location}",

    [Parameter(Mandatory=$false)]
    [switch]$AuditOnly,

    [Parameter(Mandatory=$false)]
    [switch]$AssignAfterCreation
)

# Enforcement mode: generated from mapping agent setting, overridable via -AuditOnly switch
$EnforcementMode = if ($AuditOnly) {{ 'DoNotEnforce' }} else {{ '{enforcement_mode_ps}' }}

# Regulatory Compliance initiative: policy references and control groups are
# supplied to New-AzPolicySetDefinition as SEPARATE arrays.
$policyDefinitions = @'
{policy_definitions_json}
'@
{ps_groups_block}
# Create policy initiative
# -Metadata takes a JSON string (Az.Resources 10.x); a raw hashtable is rejected.
$metadata = @{{category="{category}"}} | ConvertTo-Json -Compress
New-AzPolicySetDefinition `
  -Name "{initiative_name}" `
  -DisplayName "{initiative.properties.display_name}" `
  -Description "{initiative.properties.description}" `
  -PolicyDefinition $policyDefinitions `
{ps_groups_arg}  -Metadata $metadata

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
                -EnforcementMode $EnforcementMode `
                -IdentityType SystemAssigned `
                -Location $Location
            Write-Host "Initiative assigned (enforcement: $EnforcementMode, identity: SystemAssigned @ $Location)" -ForegroundColor Green
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

    def generate_security_standard(
        self,
        initiative: PolicyInitiative,
        initiative_name: str,
        standard_name: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Generate a Microsoft Defender for Cloud custom compliance standard.

        A plain policy set definition (initiative) surfaces in Defender for Cloud
        as a *Custom (legacy)* item. To appear as a first-class **Compliance**
        standard in the Regulatory Compliance dashboard, the initiative must be
        wrapped in a ``Microsoft.Security/securityStandards`` resource whose
        ``policySetDefinitionId`` links it. This mechanism requires the
        **Microsoft Defender CSPM** plan on the target scope.

        Args:
            initiative: The generated policy initiative.
            initiative_name: Name the initiative (policy set definition) is
                deployed under; used to resolve its resource ID.
            standard_name: Optional GUID for the standard (one is generated when
                omitted — Azure requires the standard name to be a GUID).

        Returns:
            Dict with ``standard_name``, ``arm_template`` (JSON string) and
            ``powershell`` (deploy script) keys.
        """
        standard_name = standard_name or str(uuid.uuid4())
        display_name = f"{initiative.properties.display_name}"
        description = (
            initiative.properties.description
            or f"Custom compliance standard for {initiative.properties.metadata.framework_name}."
        )

        arm_template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "metadata": {
                "_generator": "ComplianceIQ",
                "comments": "Requires the Microsoft Defender CSPM plan on the target scope.",
            },
            "parameters": {
                "standardName": {
                    "type": "string",
                    "defaultValue": standard_name,
                    "metadata": {"description": "GUID name of the custom security standard."},
                },
                "policySetDefinitionId": {
                    "type": "string",
                    "metadata": {
                        "description": "Resource ID of the policy set definition (initiative) to link."
                    },
                },
            },
            "resources": [
                {
                    "type": "Microsoft.Security/securityStandards",
                    "apiVersion": "2024-08-01",
                    "name": "[parameters('standardName')]",
                    "properties": {
                        "displayName": display_name,
                        "description": description,
                        "cloudProviders": ["Azure"],
                        # The 2024-08-01 API rejects a null/omitted assessments
                        # field (HTTP 400 "Assessments value cannot be null!").
                        # An empty array is accepted; Defender derives the
                        # assessments from the linked policy set definition.
                        "assessments": [],
                        "policySetDefinitionId": "[parameters('policySetDefinitionId')]",
                    },
                }
            ],
        }
        arm_template_json = json.dumps(arm_template, indent=2)

        ps_script = f"""# Deploy Defender for Cloud custom compliance standard
# {display_name}
#
# Wraps the policy initiative '{initiative_name}' in a
# Microsoft.Security/securityStandards resource so it appears as a first-class
# *Compliance* standard in the Defender for Cloud Regulatory Compliance
# dashboard (instead of "Custom (legacy)").
#
# PREREQUISITE: the Microsoft Defender CSPM plan must be enabled on the target
# scope. Deploy and (optionally) assign the initiative first.

param(
    [Parameter(Mandatory=$false)]
    [string]$Scope = "",

    [Parameter(Mandatory=$false)]
    [string]$InitiativeName = "{initiative_name}"
)

$ErrorActionPreference = "Stop"

if (-not $Scope) {{
    $context = Get-AzContext
    if (-not $context) {{ Write-Error "Not authenticated. Run Connect-AzAccount first."; exit 1 }}
    $Scope = "/subscriptions/$($context.Subscription.Id)"
}}
Write-Host "[Scope] $Scope" -ForegroundColor Yellow

# Resolve the initiative (policy set definition) resource ID at this scope.
$psd = Get-AzPolicySetDefinition -Name $InitiativeName -ErrorAction SilentlyContinue
if ($psd -and $psd.PolicySetDefinitionId) {{
    $policySetId = $psd.PolicySetDefinitionId
}} elseif ($psd -and $psd.Id) {{
    $policySetId = $psd.Id
}} else {{
    $policySetId = "$Scope/providers/Microsoft.Authorization/policySetDefinitions/$InitiativeName"
    Write-Warning "Initiative not found via Get-AzPolicySetDefinition; using derived ID: $policySetId"
}}

$standardName = "{standard_name}"
$body = @{{
    properties = @{{
        displayName           = "{display_name}"
        description           = "{description}"
        cloudProviders        = @("Azure")
        assessments           = @()
        policySetDefinitionId = $policySetId
    }}
}} | ConvertTo-Json -Depth 10

# Windows PowerShell 5.1 can serialise an empty @() as null; the securityStandards
# API rejects a null assessments field (HTTP 400). Normalise to an empty array.
$body = $body -replace '"assessments":\\s*(null|"")', '"assessments": []'

$path = "$Scope/providers/Microsoft.Security/securityStandards/$standardName`?api-version=2024-08-01"

Write-Host "Creating custom compliance standard: $standardName" -ForegroundColor Green
$response = Invoke-AzRestMethod -Method PUT -Path $path -Payload $body
if ($response.StatusCode -ge 400) {{
    Write-Error "Failed to create standard ($($response.StatusCode)): $($response.Content)"
    exit 1
}}

Write-Host "SUCCESS: Custom compliance standard created." -ForegroundColor Green
Write-Host "  Standard: $standardName" -ForegroundColor White
Write-Host "  Linked initiative: $policySetId" -ForegroundColor White
Write-Host ""
Write-Host "It appears under Defender for Cloud > Regulatory compliance once the" -ForegroundColor Cyan
Write-Host "Defender CSPM plan is enabled and assessments have been evaluated." -ForegroundColor Cyan
"""

        return {
            "standard_name": standard_name,
            "arm_template": arm_template_json,
            "powershell": ps_script,
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
            allowed_locations: Optional list of allowed Azure regions (e.g.,
                ["southafricanorth", "southafricawest"])

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
# -Metadata takes a JSON string (Az.Resources 10.x); a raw hashtable is rejected.
$metadata = @{{category="Regulatory Compliance"}} | ConvertTo-Json -Compress
New-AzPolicySetDefinition `
    -Name $InitiativeName `
    -DisplayName "{display_name}" `
    -Description "{description}" `
    -PolicyDefinition $TempFile `
    -ManagementGroupName $ManagementGroupId `
    -Metadata $metadata

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
