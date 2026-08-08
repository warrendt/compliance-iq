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
  - manual_register.csv     (C/D controls Azure does not enforce)
  - coverage_gaps.csv       (in scope for Azure, nothing usable retrieved)
  - dropped_policy_ids.csv  (every identifier discarded, and why)

Output format matches the Oman CDC / SAMA pattern used by Defender for Cloud.
"""

import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import (
    ControlExtractionResult,
    ControlPolicyMapping,
    ValidationReport,
    InitiativeGroup,
    PolicyDefinitionRef,
)
from .validator import GUID_PATTERN

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

    # ── 9-11. The other half of the answer ────────────────────────────────
    # An initiative on its own says what Azure enforces. These three say what it
    # does not: the controls the customer must satisfy by other means, the ones
    # that should have had a policy and did not, and every identifier that was
    # rejected on the way. Omitting them is how a control that lost its
    # enforcement ends up looking like one that never needed any.
    files_created.extend(_write_coverage_reports(out, fw_safe, mappings))

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


def _record_drop(mapping: ControlPolicyMapping, policy_id, reason: str) -> None:
    """Record a rejected identifier on the control it came from.

    ARM rejects malformed and non-existent policy definition IDs, so dropping
    them is unavoidable. Dropping them *silently* is the defect this product
    exists to prevent: the initiative still deploys, the control still appears,
    and nothing anywhere says it lost its enforcement.
    """
    dropped = getattr(mapping, "dropped_policy_ids", None)
    if dropped is None:
        return
    entry = {"policy_id": (policy_id or "").strip(), "reason": reason}
    if entry not in dropped:
        dropped.append(entry)


def _build_policies(
    mappings: list[ControlPolicyMapping],
    catalog: Optional[object] = None,
) -> list[dict]:
    """Build the policyDefinitions array with group assignments.

    Drops policy definition IDs that are either malformed or that do not
    correspond to a real Azure built-in definition - ARM rejects both as
    ``PolicyDefinitionNotFound`` and fails the whole initiative. Every drop is
    recorded on ``mapping.dropped_policy_ids`` so it can be reported rather
    than only logged. Existence is checked against the shipped catalog; when
    that is unavailable only GUID format is enforced.
    """
    if catalog is None:
        from app.services.policy_catalog_service import get_policy_catalog_service
        catalog = get_policy_catalog_service()
    # ``available`` is a method, so the previous ``bool(getattr(catalog,
    # "available", False))`` was always True - including when the catalog had
    # failed to load, at which point ``exists()`` returns False for everything
    # and every policy in the initiative is dropped. The documented fallback
    # ("when the catalog is unavailable only GUID format is enforced") never
    # ran. Call it.
    available = getattr(catalog, "available", None)
    enforce_existence = bool(available() if callable(available) else available)
    if not enforce_existence:
        logger.warning(
            "Policy catalog unavailable: enforcing GUID format only, so "
            "identifiers that do not exist in Azure cannot be caught here."
        )

    policy_refs: list[dict] = []
    seen_combos: set[str] = set()

    for mapping in mappings:
        if not mapping.azure_policies:
            continue

        group_name = _sanitize_group_name(mapping.control_id)

        for policy in mapping.azure_policies:
            pid = policy.policy_definition_id

            # Strip hallucinated / malformed policy definition IDs that ARM
            # would reject (must be a valid Azure Policy GUID).
            #
            # Dropping is necessary - ARM rejects the whole deployment
            # otherwise - but doing it silently is the defect. The analyst gold
            # workbook contains a mistyped GUID (`17k78e20-...`, the letter `k`
            # is not hex) that a transcription silently discarded, leaving
            # output that still looked complete. A control that lost its
            # enforcement must not read the same as one that never needed any,
            # so every drop is recorded against the control it came from.
            if not pid or not GUID_PATTERN.match(pid.strip().rstrip("/").rsplit("/", 1)[-1]):
                logger.warning(
                    f"Control {mapping.control_id}: dropping invalid Azure Policy "
                    f"definition ID '{pid}' (not a valid GUID)"
                )
                _record_drop(mapping, pid, "malformed")
                continue

            # Strip well-formed GUIDs that are not real built-in definitions.
            if enforce_existence and not catalog.exists(pid):
                logger.warning(
                    f"Control {mapping.control_id}: dropping Azure Policy "
                    f"definition ID '{pid}' — not found in the Azure built-in "
                    f"policy catalog (would fail ARM as PolicyDefinitionNotFound)"
                )
                _record_drop(mapping, pid, "not_in_catalog")
                continue

            full_id = f"/providers/Microsoft.Authorization/policyDefinitions/{pid}"

            combo_key = f"{pid}|{group_name}"

            if combo_key in seen_combos:
                continue
            seen_combos.add(combo_key)

            existing = next(
                (p for p in policy_refs if p["PolicyDefinitionId"] == full_id),
                None,
            )

            if existing:
                if group_name not in existing["GroupNames"]:
                    existing["GroupNames"].append(group_name)
            else:
                policy_refs.append({
                    "PolicyDefinitionReferenceId": pid,
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
        "generatedDate": datetime.now(timezone.utc).isoformat() + "Z",
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
    enforce_mode: bool = False,
) -> str:
    """Generate PowerShell deployment script for Defender for Cloud."""
    initiative_file = f"{fw_safe}_Initiative.json"
    name_slug = fw_safe.replace("_", "-")
    enforcement_mode = "Default" if enforce_mode else "DoNotEnforce"

    return f'''# ============================================================================
# {extraction.framework_name} — Azure Policy Initiative Deployment
# Generated by ComplianceIQ Compliance Pipeline
# Date: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$Scope = "",

    [Parameter(Mandatory=$false)]
    [string]$ManagementGroupId = "",

    [Parameter(Mandatory=$false)]
    [switch]$AuditOnly,

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
    exit 1
}}

Write-Host "[Files] All required files found" -ForegroundColor Green
Write-Host ""

$groups   = Get-Content -Raw groups.json
$policies = Get-Content -Raw policies.json
$params   = Get-Content -Raw params.json

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

$initiativeName = "{name_slug}-compliance"
$displayName    = "{extraction.framework_name} Compliance Controls"
$description    = @"
{extraction.summary[:500] if extraction.summary else f"Regulatory compliance initiative for {extraction.framework_name}."}
"@

$metadata = @{{
    category        = "Regulatory Compliance"
    version         = "1.0.0"
    source          = "ComplianceIQ Compliance Pipeline"
}} | ConvertTo-Json -Compress

Write-Host "Creating initiative: $displayName" -ForegroundColor Green
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

    if ($ManagementGroupId) {{
        $initParams["ManagementGroupName"] = $ManagementGroupId
    }}

    $initiative = New-AzPolicySetDefinition @initParams

    Write-Host ""
    Write-Host "SUCCESS: Initiative Created" -ForegroundColor Green
    Write-Host "  Name:         $($initiative.Name)" -ForegroundColor White
    Write-Host "  Display Name: $($initiative.Properties.DisplayName)" -ForegroundColor White
    Write-Host "  Resource ID:  $($initiative.ResourceId)" -ForegroundColor White
    Write-Host ""

}} catch {{
    Write-Error $_.Exception.Message
    exit 1
}}

$enforcementMode = if ($AuditOnly) {{ 'DoNotEnforce' }} else {{ '{enforcement_mode}' }}

if ($AssignAfterCreation) {{
    Write-Host "Assigning initiative to scope (enforcement: $enforcementMode)..." -ForegroundColor Green
    $assignmentName = "{name_slug}-$(Get-Date -Format 'yyyyMMdd')"
    $existingAssignment = Get-AzPolicyAssignment -Scope $TargetScope |
        Where-Object {{ $_.Name -eq $assignmentName }}
    if ($existingAssignment) {{
        if ($existingAssignment.Properties.EnforcementMode -ne $enforcementMode) {{
            Write-Host "  Updating enforcement mode to: $enforcementMode" -ForegroundColor Yellow
            Set-AzPolicyAssignment -Name $assignmentName -Scope $TargetScope -EnforcementMode $enforcementMode
            Write-Host "[OK] Assignment enforcement mode updated" -ForegroundColor Green
        }} else {{
            Write-Host "[OK] Assignment already up to date (enforcement: $enforcementMode)" -ForegroundColor Green
        }}
    }} else {{
        $assignParams = @{{
            Name                = $assignmentName
            DisplayName         = "$displayName - Assessment"
            Scope               = $TargetScope
            PolicySetDefinition = $initiative
            Description         = "Regulatory compliance assessment for {extraction.framework_name}"
            EnforcementMode     = $enforcementMode
        }}
        if ($Location) {{
            $assignParams["Location"] = $Location
        }}
        try {{
            $assignment = New-AzPolicyAssignment @assignParams
            Write-Host "  Assignment: $($assignment.Name)" -ForegroundColor White
            Write-Host "[OK] Initiative assigned successfully (enforcement: $enforcementMode)" -ForegroundColor Green
        }} catch {{
            Write-Host "WARNING: Assignment failed" -ForegroundColor Yellow
            Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Gray
        }}
    }}
}}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Azure Portal > Policy > Definitions — verify the initiative" -ForegroundColor White
Write-Host "  2. Azure Portal > Policy > Assignments — assign to desired scope" -ForegroundColor White
Write-Host "  3. Defender for Cloud > Regulatory Compliance — view compliance" -ForegroundColor White
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
# ============================================================================

set -euo pipefail

INITIATIVE_NAME="{name_slug}-compliance"
DISPLAY_NAME="{extraction.framework_name} Compliance Controls"
DESCRIPTION="{desc}"
MGMT_GROUP=""

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

for f in groups.json policies.json params.json; do
    if [[ ! -f "$f" ]]; then
        echo "ERROR: Missing required file: $f"
        exit 1
    fi
done

echo "[Files] All required files found"
echo ""

SCOPE_ARGS=""
if [[ -n "$MGMT_GROUP" ]]; then
    SCOPE_ARGS="--management-group $MGMT_GROUP"
    echo "[Scope] Management Group: $MGMT_GROUP"
else
    SUB=$(az account show --query id -o tsv 2>/dev/null)
    echo "[Scope] Subscription: $SUB"
fi
echo ""

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
echo "SUCCESS: Initiative created"
echo ""
'''


def _write_mappings_csv(
    csv_path: Path,
    extraction: ControlExtractionResult,
    mappings: list[ControlPolicyMapping],
):
    """Write a comprehensive mapping report as CSV.

    This file is what a customer hands to an auditor, so it has to answer both
    halves of the question: what Azure enforces, and what it does not. The
    taxonomy columns carry the second half - how the control is met, who owns
    it, what completes a partial mapping, what evidences an attested one, and
    every identifier that was rejected on the way.
    """
    mapping_lookup = {m.control_id: m for m in mappings}

    fieldnames = [
        "Control_ID",
        "Control_Title",
        "Domain",
        "Control_Type",
        "Coverage_Category",
        "Coverage_Display",
        "Coverage_Reason",
        "Responsibility",
        "Azure_Enforceable",
        "Coverage_Gap",
        "Outside_Step",
        "Enforcement_Plane",
        "MCSB_Control_ID",
        "MCSB_Control_Name",
        "Confidence",
        "Azure_Policy_IDs",
        "Azure_Policy_Names",
        "Policy_Effects",
        "Available_Effects",
        "Policy_Type",
        "Evidence_Source",
        "Attestation_Citation",
        "Attestation_Evidence_Location",
        "Attestation_Access_Condition",
        "Attestation_Gap",
        "Dropped_Policy_IDs",
        "Is_Automatable",
        "Manual_Note",
        "Defender_Recommendations",
        "Mapping_Rationale",
    ]

    def _joined(values) -> str:
        return "; ".join(str(v) for v in (values or []))

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

            attestation = (getattr(m, "attestation", None) or {}) if m else {}
            dropped = _joined(
                f"{d.get('policy_id', '')} ({d.get('reason', '')})"
                for d in (getattr(m, "dropped_policy_ids", None) or [])
            ) if m else ""

            writer.writerow({
                "Control_ID": ctrl.control_id,
                "Control_Title": ctrl.control_title,
                "Domain": ctrl.domain,
                "Control_Type": ctrl.control_type,
                "Coverage_Category": (getattr(m, "coverage_category", None) or "") if m else "",
                "Coverage_Display": (getattr(m, "coverage_display", None) or "") if m else "",
                "Coverage_Reason": (getattr(m, "coverage_reason", None) or "") if m else "",
                "Responsibility": (getattr(m, "responsibility", None) or "") if m else "",
                "Azure_Enforceable": str(getattr(m, "azure_enforceable", False)) if m else "",
                "Coverage_Gap": str(getattr(m, "coverage_gap", False)) if m else "",
                "Outside_Step": (getattr(m, "outside_step", None) or "") if m else "",
                "Enforcement_Plane": (getattr(m, "enforcement_plane", None) or "") if m else "",
                "MCSB_Control_ID": m.mcsb_control_id if m else "",
                "MCSB_Control_Name": m.mcsb_control_name if m else "",
                "Confidence": f"{m.confidence_score:.2f}" if m else "",
                "Azure_Policy_IDs": policy_ids,
                "Azure_Policy_Names": policy_names,
                "Policy_Effects": _joined(getattr(m, "policy_effects", None)) if m else "",
                "Available_Effects": _joined(getattr(m, "available_effects", None)) if m else "",
                "Policy_Type": (getattr(m, "policy_type", None) or "") if m else "",
                "Evidence_Source": (getattr(m, "evidence_source", None) or "") if m else "",
                "Attestation_Citation": attestation.get("citation", ""),
                "Attestation_Evidence_Location": attestation.get("evidence_location", ""),
                "Attestation_Access_Condition": attestation.get("access_condition", ""),
                "Attestation_Gap": str(getattr(m, "attestation_gap", False)) if m else "",
                "Dropped_Policy_IDs": dropped,
                "Is_Automatable": str(m.is_automatable) if m else "",
                "Manual_Note": m.manual_attestation_note or "" if m else "",
                "Defender_Recommendations": defender_recs,
                "Mapping_Rationale": m.mapping_rationale if m else "",
            })

    logger.info(f"Wrote mapping report: {csv_path}")


class _RegisterView:
    """Present a pipeline mapping under the attribute names coverage.py expects.

    ``ControlPolicyMapping`` calls them ``control_id``/``control_title``; the
    services-path ``ControlMapping`` calls them ``external_control_id``/
    ``external_control_name``. Adapting is deliberate: the rules for what belongs
    in the manual register, and the wording of each reason, are decisions that
    must not diverge between the two entry points. Re-implementing them here is
    how the pipeline path drifted from the taxonomy in the first place.
    """

    def __init__(self, mapping: ControlPolicyMapping):
        self._m = mapping

    def __getattr__(self, name):
        return getattr(self._m, name)

    @property
    def external_control_id(self):
        return self._m.control_id

    @property
    def external_control_name(self):
        return self._m.control_title


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> str:
    """Write rows to CSV, always including the header.

    An empty file would be ambiguous - it could mean "nothing to report" or
    "this step did not run". A header with no rows says the first one.
    """
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: ("; ".join(str(x) for x in v) if isinstance(v, list) else v)
                    for k, v in row.items()
                }
            )
    logger.info(f"Wrote: {path} ({len(rows)} rows)")
    return str(path)


def _write_coverage_reports(
    out: Path,
    fw_safe: str,
    mappings: list[ControlPolicyMapping],
) -> list[str]:
    """Write the manual register, coverage gaps and dropped identifiers."""
    from app.services.coverage import (
        coverage_gap_rows,
        dropped_policy_rows,
        manual_register_rows,
    )

    views = [_RegisterView(m) for m in mappings]
    created: list[str] = []

    created.append(
        _write_csv(
            out / f"{fw_safe}_Manual_Register.csv",
            [
                "control_id",
                "control_name",
                "control_type",
                "coverage_category",
                "coverage_display",
                "mcsb_control_id",
                "responsibility",
                "evidence_source",
                "enforcement_plane",
                "attestation_status",
                "attestation_basis",
                "attestation_citation",
                "attestation_document",
                "attestation_location",
                "attestation_access",
                "attestation_gap",
                "reason",
            ],
            manual_register_rows(views),
        )
    )

    created.append(
        _write_csv(
            out / f"{fw_safe}_Coverage_Gaps.csv",
            [
                "control_id",
                "control_name",
                "coverage_category",
                "coverage_display",
                "outside_step",
                "policy_type",
                "rejected_policy_ids",
                "reason",
                "remediation",
            ],
            coverage_gap_rows(views),
        )
    )

    created.append(
        _write_csv(
            out / f"{fw_safe}_Dropped_Policy_IDs.csv",
            ["control_id", "control_name", "policy_id", "reason", "detail"],
            dropped_policy_rows(views),
        )
    )

    return created


def _write_json(path: Path, data) -> None:
    """Write JSON to file with consistent formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Wrote: {path}")
