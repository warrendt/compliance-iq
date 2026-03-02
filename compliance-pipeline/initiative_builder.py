"""
Initiative Builder Module.
Generates all Defender for Cloud regulatory compliance initiative artifacts:
  - initiative.json  (main initiative definition with policyDefinitionGroups)
  - policies.json    (policy definition references with group assignments)
  - groups.json      (group definitions — one per control)
  - params.json      (parameters, if any)
  - Deploy-Initiative.ps1  (PowerShell script to import into Azure)
  - deploy-initiative.sh   (Azure CLI script)
  - mappings.csv     (complete mapping report)

Output format matches the Oman CDC / SAMA pattern used by Defender for Cloud.
"""

import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from models import (
    ControlExtractionResult,
    ControlPolicyMapping,
    ValidationReport,
    InitiativeGroup,
    PolicyDefinitionRef,
)

logger = logging.getLogger(__name__)


def _sanitize_group_name(control_id: str) -> str:
    """Convert a control ID to a valid Azure policy group name (alphanumeric + underscore)."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", control_id)


def build_initiative_artifacts(
    extraction: ControlExtractionResult,
    mappings: list[ControlPolicyMapping],
    validation: ValidationReport,
    output_dir: str,
    allowed_locations: Optional[list[str]] = None,
) -> list[str]:
    """
    Generate all initiative artifact files.

    Args:
        extraction: The extracted framework controls.
        mappings: The validated control-to-policy mappings.
        validation: Validation report.
        output_dir: Directory to write output files.
        allowed_locations: Optional Azure regions for location policies.

    Returns:
        List of file paths created.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    files_created: list[str] = []

    # Sanitized framework name for file naming
    fw_safe = re.sub(r"[^a-zA-Z0-9]+", "_", extraction.framework_name).strip("_")

    # ── 1. groups.json ────────────────────────────────────────────────────
    groups = _build_groups(extraction, mappings)
    groups_path = out / "groups.json"
    _write_json(groups_path, groups)
    files_created.append(str(groups_path))

    # ── 2. policies.json ──────────────────────────────────────────────────
    policies = _build_policies(mappings)
    policies_path = out / "policies.json"
    _write_json(policies_path, policies)
    files_created.append(str(policies_path))

    # ── 3. params.json ────────────────────────────────────────────────────
    params = _build_params(allowed_locations)
    params_path = out / "params.json"
    _write_json(params_path, params)
    files_created.append(str(params_path))

    # ── 4. initiative.json (main definition) ──────────────────────────────
    initiative = _build_initiative(extraction, mappings, groups, policies, params)
    initiative_path = out / f"{fw_safe}_Initiative.json"
    _write_json(initiative_path, initiative)
    files_created.append(str(initiative_path))

    # ── 5. Deploy-Initiative.ps1 ──────────────────────────────────────────
    ps_path = out / "Deploy-Initiative.ps1"
    ps_content = _build_powershell_script(extraction, fw_safe)
    ps_path.write_text(ps_content, encoding="utf-8")
    files_created.append(str(ps_path))

    # ── 6. deploy-initiative.sh ───────────────────────────────────────────
    sh_path = out / "deploy-initiative.sh"
    sh_content = _build_cli_script(extraction, fw_safe)
    sh_path.write_text(sh_content, encoding="utf-8")
    files_created.append(str(sh_path))

    # ── 7. mappings.csv (full mapping report) ─────────────────────────────
    csv_path = out / f"{fw_safe}_Mappings.csv"
    _write_mappings_csv(csv_path, extraction, mappings)
    files_created.append(str(csv_path))

    # ── 8. validation_report.json ─────────────────────────────────────────
    report_path = out / "validation_report.json"
    _write_json(report_path, validation.model_dump())
    files_created.append(str(report_path))

    logger.info(f"Generated {len(files_created)} files in {out}/")
    return files_created


# ── Builders ──────────────────────────────────────────────────────────────────


def _build_groups(
    extraction: ControlExtractionResult,
    mappings: list[ControlPolicyMapping],
) -> list[dict]:
    """Build policyDefinitionGroups — one group per control."""
    groups = []
    mapping_lookup = {m.control_id: m for m in mappings}

    for ctrl in extraction.controls:
        group_name = _sanitize_group_name(ctrl.control_id)
        mapping = mapping_lookup.get(ctrl.control_id)

        display_name = f"{ctrl.control_id}: {ctrl.control_title}"
        description = ctrl.control_description

        if mapping and not mapping.is_automatable:
            description += " [MANUAL ATTESTATION REQUIRED]"
            if mapping.manual_attestation_note:
                description += f" — {mapping.manual_attestation_note}"

        groups.append({
            "name": group_name,
            "displayName": display_name,
            "description": description,
        })

    return groups


def _build_policies(mappings: list[ControlPolicyMapping]) -> list[dict]:
    """Build policyDefinitions array with group assignments."""
    policy_refs: list[dict] = []
    seen_combos: set[str] = set()

    for mapping in mappings:
        if not mapping.azure_policies:
            continue

        group_name = _sanitize_group_name(mapping.control_id)

        for policy in mapping.azure_policies:
            pid = policy.policy_definition_id
            full_id = f"/providers/Microsoft.Authorization/policyDefinitions/{pid}"

            # Create a unique reference ID
            ref_id = pid
            combo_key = f"{pid}|{group_name}"

            if combo_key in seen_combos:
                continue
            seen_combos.add(combo_key)

            # Check if this policy already has an entry (might belong to multiple groups)
            existing = next(
                (p for p in policy_refs if p["PolicyDefinitionId"] == full_id),
                None,
            )

            if existing:
                # Add this group to existing policy entry
                if group_name not in existing["GroupNames"]:
                    existing["GroupNames"].append(group_name)
            else:
                policy_refs.append({
                    "PolicyDefinitionReferenceId": ref_id,
                    "PolicyDefinitionId": full_id,
                    "Parameters": {},
                    "GroupNames": [group_name],
                })

    return policy_refs


def _build_params(allowed_locations: Optional[list[str]] = None) -> dict:
    """Build parameters object."""
    params = {}

    if allowed_locations:
        params["listOfAllowedLocations"] = {
            "type": "Array",
            "metadata": {
                "displayName": "Allowed locations",
                "description": "The list of locations that can be specified when deploying resources.",
            },
            "defaultValue": allowed_locations,
        }

    return params


def _build_initiative(
    extraction: ControlExtractionResult,
    mappings: list[ControlPolicyMapping],
    groups: list[dict],
    policies: list[dict],
    params: dict,
) -> dict:
    """Build the complete initiative JSON (Azure Policy Set Definition)."""
    automatable = sum(1 for m in mappings if m.is_automatable)
    manual = len(mappings) - automatable

    metadata = {
        "category": "Regulatory Compliance",
        "version": "1.0.0",
        "source": "ComplianceIQ Compliance Pipeline (AI-Generated)",
        "generatedDate": datetime.utcnow().isoformat() + "Z",
        "frameworkName": extraction.framework_name,
    }

    if extraction.framework_version:
        metadata["frameworkVersion"] = extraction.framework_version
    if extraction.issuing_authority:
        metadata["authority"] = extraction.issuing_authority
    if extraction.country_or_region:
        metadata["country"] = extraction.country_or_region

    metadata["totalControls"] = len(extraction.controls)
    metadata["automatableControls"] = automatable
    metadata["manualControls"] = manual

    return {
        "properties": {
            "displayName": f"{extraction.framework_name} Compliance Controls",
            "policyType": "Custom",
            "description": extraction.summary,
            "metadata": metadata,
            "parameters": params,
            "policyDefinitionGroups": groups,
            "policyDefinitions": policies,
        }
    }


def _build_powershell_script(
    extraction: ControlExtractionResult,
    fw_safe: str,
) -> str:
    """Generate PowerShell deployment script for Defender for Cloud."""
    initiative_file = f"{fw_safe}_Initiative.json"
    name_slug = fw_safe.replace("_", "-")

    return f'''# ============================================================================
# {extraction.framework_name} — Azure Policy Initiative Deployment
# Generated by ComplianceIQ Compliance Pipeline
# Date: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
# ============================================================================
#
# This script creates a custom regulatory compliance initiative in Azure
# and optionally assigns it to a scope for Defender for Cloud monitoring.
#
# Prerequisites:
#   - Az PowerShell module installed (Install-Module -Name Az)
#   - Authenticated to Azure (Connect-AzAccount)
#   - Contributor or Policy Contributor role at target scope
#   - Files in current directory: groups.json, policies.json, params.json
#
# Usage:
#   .\\Deploy-Initiative.ps1                                   # Current subscription
#   .\\Deploy-Initiative.ps1 -ManagementGroupId "mg-compliance" # Management group
#   .\\Deploy-Initiative.ps1 -AssignAfterCreation               # Create + assign
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$Scope = "",

    [Parameter(Mandatory=$false)]
    [string]$ManagementGroupId = "",

    [Parameter(Mandatory=$false)]
    [switch]$AssignAfterCreation,

    [Parameter(Mandatory=$false)]
    [string]$Location = ""
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " {extraction.framework_name}" -ForegroundColor Cyan
Write-Host " Regulatory Compliance Initiative Deployment" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# ── Determine target scope ────────────────────────────────────────────────
if ($ManagementGroupId) {{
    $TargetScope = "/providers/Microsoft.Management/managementGroups/$ManagementGroupId"
    Write-Host "[Scope] Management Group: $ManagementGroupId" -ForegroundColor Yellow
}} elseif ($Scope) {{
    $TargetScope = $Scope
    Write-Host "[Scope] Custom: $Scope" -ForegroundColor Yellow
}} else {{
    $context = Get-AzContext
    if (-not $context) {{
        Write-Error "Not authenticated to Azure. Run Connect-AzAccount first."
        exit 1
    }}
    $TargetScope = "/subscriptions/$($context.Subscription.Id)"
    Write-Host "[Scope] Subscription: $($context.Subscription.Name) ($($context.Subscription.Id))" -ForegroundColor Yellow
}}
Write-Host ""

# ── Verify required files ─────────────────────────────────────────────────
$requiredFiles = @("groups.json", "policies.json", "params.json")
$missingFiles = @()
foreach ($file in $requiredFiles) {{
    if (-not (Test-Path $file)) {{
        $missingFiles += $file
    }}
}}

if ($missingFiles.Count -gt 0) {{
    Write-Host "ERROR: Missing required files:" -ForegroundColor Red
    $missingFiles | ForEach-Object {{ Write-Host "  - $_" -ForegroundColor Red }}
    Write-Host ""
    Write-Host "Ensure you are running this script from the output directory" -ForegroundColor Yellow
    Write-Host "containing groups.json, policies.json, and params.json." -ForegroundColor Yellow
    exit 1
}}

Write-Host "[Files] All required files found" -ForegroundColor Green
Write-Host ""

# ── Load definition files ─────────────────────────────────────────────────
Write-Host "Loading policy definition files..." -ForegroundColor Gray

$groups   = Get-Content -Raw groups.json
$policies = Get-Content -Raw policies.json
$params   = Get-Content -Raw params.json

# Validate JSON
try {{
    $null = $groups   | ConvertFrom-Json
    $null = $policies | ConvertFrom-Json
    $null = $params   | ConvertFrom-Json
    Write-Host "[Validate] JSON files are valid" -ForegroundColor Green
}} catch {{
    Write-Error "Invalid JSON in definition files: $_"
    exit 1
}}

Write-Host ""

# ── Create the Policy Initiative ──────────────────────────────────────────
$initiativeName = "{name_slug}-compliance"
$displayName    = "{extraction.framework_name} Compliance Controls"
$description    = @"
{extraction.summary[:500] if extraction.summary else f"Regulatory compliance initiative for {extraction.framework_name}."}
"@

$metadata = @{{
    category        = "Regulatory Compliance"
    version         = "1.0.0"
    source          = "ComplianceIQ Compliance Pipeline"
    generatedDate   = "{datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}"
}} | ConvertTo-Json -Compress

Write-Host "Creating initiative: $displayName" -ForegroundColor Green
Write-Host "  Name: $initiativeName" -ForegroundColor Gray
Write-Host ""

try {{
    $initParams = @{{
        Name             = $initiativeName
        DisplayName      = $displayName
        Description      = $description
        Metadata         = $metadata
        GroupDefinition  = $groups
        PolicyDefinition = $policies
        Parameter        = $params
    }}

    # Add management group scope if specified
    if ($ManagementGroupId) {{
        $initParams["ManagementGroupName"] = $ManagementGroupId
    }}

    $initiative = New-AzPolicySetDefinition @initParams

    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host " SUCCESS: Initiative Created" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Name:         $($initiative.Name)" -ForegroundColor White
    Write-Host "  Display Name: $($initiative.Properties.DisplayName)" -ForegroundColor White
    Write-Host "  Resource ID:  $($initiative.ResourceId)" -ForegroundColor White
    Write-Host ""

}} catch {{
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Red
    Write-Host " ERROR: Initiative Creation Failed" -ForegroundColor Red
    Write-Host "========================================================" -ForegroundColor Red
    Write-Host ""
    Write-Error $_.Exception.Message
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Verify you have Policy Contributor role" -ForegroundColor Gray
    Write-Host "  2. Check that policy definition GUIDs exist in Azure" -ForegroundColor Gray
    Write-Host "  3. Run: Connect-AzAccount to re-authenticate" -ForegroundColor Gray
    Write-Host "  4. Check Azure subscription quota for custom initiatives" -ForegroundColor Gray
    exit 1
}}

# ── Optional: Assign the Initiative ───────────────────────────────────────
if ($AssignAfterCreation) {{
    Write-Host "Assigning initiative to scope..." -ForegroundColor Green
    Write-Host ""

    $assignmentName = "{name_slug}-$(Get-Date -Format 'yyyyMMdd')"

    $assignParams = @{{
        Name                = $assignmentName
        DisplayName         = "$displayName - Assessment"
        Scope               = $TargetScope
        PolicySetDefinition = $initiative
        Description         = "Regulatory compliance assessment for {extraction.framework_name}"
        EnforcementMode     = "Default"
    }}

    if ($Location) {{
        $assignParams["Location"] = $Location
    }}

    try {{
        $assignment = New-AzPolicyAssignment @assignParams

        Write-Host "  Assignment: $($assignment.Name)" -ForegroundColor White
        Write-Host "  Scope:      $TargetScope" -ForegroundColor White
        Write-Host ""
        Write-Host "[OK] Initiative assigned successfully" -ForegroundColor Green

    }} catch {{
        Write-Host "WARNING: Assignment failed — initiative was created but not assigned" -ForegroundColor Yellow
        Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Gray
        Write-Host "  You can assign it manually from Azure Portal > Policy > Assignments" -ForegroundColor Gray
    }}
}}

# ── Next Steps ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Next Steps" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Azure Portal > Policy > Definitions — verify the initiative" -ForegroundColor White
Write-Host "  2. Azure Portal > Policy > Assignments — assign to desired scope" -ForegroundColor White
Write-Host "  3. Defender for Cloud > Regulatory Compliance — view compliance" -ForegroundColor White
Write-Host "  4. Allow ~24 hours for initial compliance evaluation" -ForegroundColor White
Write-Host "  5. Review non-compliant resources and remediate" -ForegroundColor White
Write-Host ""
Write-Host "  Tip: Controls marked [MANUAL ATTESTATION] require manual" -ForegroundColor Gray
Write-Host "  evidence in Defender for Cloud > Regulatory Compliance." -ForegroundColor Gray
Write-Host ""
'''


def _build_cli_script(
    extraction: ControlExtractionResult,
    fw_safe: str,
) -> str:
    """Generate Azure CLI deployment script."""
    name_slug = fw_safe.replace("_", "-")
    desc = (extraction.summary[:500] if extraction.summary else
            f"Regulatory compliance initiative for {extraction.framework_name}.")

    return f'''#!/bin/bash
# ============================================================================
# {extraction.framework_name} — Azure Policy Initiative Deployment (CLI)
# Generated by ComplianceIQ Compliance Pipeline
# Date: {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}
# ============================================================================
#
# Usage:
#   chmod +x deploy-initiative.sh
#   ./deploy-initiative.sh                                    # Current subscription
#   ./deploy-initiative.sh --management-group mg-compliance   # Management group
#
# Prerequisites:
#   - Azure CLI installed and authenticated (az login)
#   - Files in current directory: groups.json, policies.json, params.json
# ============================================================================

set -euo pipefail

INITIATIVE_NAME="{name_slug}-compliance"
DISPLAY_NAME="{extraction.framework_name} Compliance Controls"
DESCRIPTION="{desc}"
MGMT_GROUP=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --management-group|-m)
            MGMT_GROUP="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

echo ""
echo "========================================================"
echo " {extraction.framework_name}"
echo " Regulatory Compliance Initiative Deployment"
echo "========================================================"
echo ""

# Verify files
for f in groups.json policies.json params.json; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: Missing required file: $f"
        exit 1
    fi
done

echo "[Files] All required files found"
echo ""

# Build scope args
SCOPE_ARGS=""
if [[ -n "$MGMT_GROUP" ]]; then
    SCOPE_ARGS="--management-group $MGMT_GROUP"
    echo "[Scope] Management Group: $MGMT_GROUP"
else
    SUB=$(az account show --query id -o tsv 2>/dev/null)
    echo "[Scope] Subscription: $SUB"
fi
echo ""

# Create the initiative
echo "Creating initiative: $DISPLAY_NAME"
echo ""

az policy set-definition create \\
    --name "$INITIATIVE_NAME" \\
    --display-name "$DISPLAY_NAME" \\
    --description "$DESCRIPTION" \\
    --definitions @policies.json \\
    --definition-groups @groups.json \\
    --params @params.json \\
    --metadata category="Regulatory Compliance" \\
    $SCOPE_ARGS

echo ""
echo "========================================================"
echo " SUCCESS: Initiative created"
echo "========================================================"
echo ""
echo " Next steps:"
echo "  1. Azure Portal > Policy > Definitions — verify"
echo "  2. Azure Portal > Policy > Assignments — assign"
echo "  3. Defender for Cloud > Regulatory Compliance — review"
echo ""
'''


def _write_mappings_csv(
    csv_path: Path,
    extraction: ControlExtractionResult,
    mappings: list[ControlPolicyMapping],
):
    """Write a comprehensive mapping report as CSV."""
    mapping_lookup = {m.control_id: m for m in mappings}

    fieldnames = [
        "Control_ID",
        "Control_Title",
        "Domain",
        "Control_Type",
        "MCSB_Control_ID",
        "MCSB_Control_Name",
        "Confidence",
        "Azure_Policy_IDs",
        "Azure_Policy_Names",
        "Is_Automatable",
        "Manual_Note",
        "Defender_Recommendations",
        "Mapping_Rationale",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for ctrl in extraction.controls:
            m = mapping_lookup.get(ctrl.control_id)
            if m:
                policy_ids = "; ".join(p.policy_definition_id for p in m.azure_policies)
                policy_names = "; ".join(p.policy_name for p in m.azure_policies)
                defender_recs = "; ".join(m.defender_recommendations)
            else:
                policy_ids = ""
                policy_names = ""
                defender_recs = ""

            writer.writerow({
                "Control_ID": ctrl.control_id,
                "Control_Title": ctrl.control_title,
                "Domain": ctrl.domain,
                "Control_Type": ctrl.control_type,
                "MCSB_Control_ID": m.mcsb_control_id if m else "",
                "MCSB_Control_Name": m.mcsb_control_name if m else "",
                "Confidence": f"{m.confidence_score:.2f}" if m else "",
                "Azure_Policy_IDs": policy_ids,
                "Azure_Policy_Names": policy_names,
                "Is_Automatable": str(m.is_automatable) if m else "",
                "Manual_Note": m.manual_attestation_note or "" if m else "",
                "Defender_Recommendations": defender_recs,
                "Mapping_Rationale": m.mapping_rationale if m else "",
            })

    logger.info(f"Wrote mapping report: {csv_path}")


def _write_json(path: Path, data) -> None:
    """Write JSON to file with consistent formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Wrote: {path}")
