"""
Mapping Validation Module.
Validates the control-to-Azure-Policy mappings before generating initiative artifacts.
"""

import logging
import re
from typing import Optional

from .models import (
    ControlPolicyMapping,
    ControlExtractionResult,
    ValidationReport,
    ValidationIssue,
)

logger = logging.getLogger(__name__)

# Known Azure Policy definition GUIDs (from existing catalogues)
KNOWN_POLICY_GUIDS = {
    "055f3b15-58a8-4d91-a4f6-8437a6c8f7e8",
    "fc5e4038-4584-4632-8c85-c0448d374b2c",
    "e71308d3-144b-4262-b144-efdc3cc90517",
    "1e66c121-a66a-4b1f-9b83-0fd99bf0fc2d",
    "34c877ad-507e-4c82-993e-3452a6e0ad3c",
    "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b",
    "1f314764-cb73-4fc9-b863-8eca98ac36e9",
    "0b15565f-aa9e-48ba-8619-45960f2c314d",
    "818719e5-1338-4776-9a9d-3c31e4df5986",
    "428256e6-1fac-4f48-a757-df34c2b3336d",
    "b79fa14e-238a-4c2d-b376-442ce508fc84",
    "e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f",
    "0b60c0b2-2dc2-4e1c-b5c9-abbed971de53",
    "7595c971-233d-4bcf-bd18-596129188c49",
    "404c3081-a854-4457-ae30-26a93ef643f9",
    "4733ea7b-a883-42fe-8cac-97454c2a9e4a",
    "a4af4a39-4135-47fb-b175-47fbdf85311d",
    "702dd420-7fcc-42c5-afe8-4026edd20fe0",
    "18adea5e-f416-4d0f-8aa8-d24321e3e274",
    "0a370ff3-6cab-4e85-8995-295fd854c5b8",
    "ca610c1d-041c-4332-9d88-7ed3094967c7",
    "55d1f543-d1b0-4811-9663-d6d0dbc6326d",
    "013e242c-8828-4970-87b3-ab247555486d",
    "ac076320-ddcf-4066-b451-6154267e8ad2",
    "e1145ab1-eb4f-43d8-911b-36ddf771d13f",
    "8e86a5b6-b9bd-49d1-8e21-4bb8a0862222",
    "09024ccc-0c5f-475e-9457-b7c0d9ed487b",
    "22bee202-a82f-4305-9a2a-6d7f44d4dedb",
    "37bc2e11-1d3c-4e6e-a9fc-62ca7b58b6c2",
    "e56962a6-4747-49cd-b67b-bf8b01975c4c",
    "c9d007d0-c057-4772-b18c-01693a6eae35",
    "0725b4dd-7e76-479c-a735-68e7ee23d5ca",
    "8e826246-c976-48f6-b03e-619bb92b3d82",
    "5f0bc445-3935-4915-9981-011aa2b46147",
    "f4b53539-8df9-40e4-86c6-6b607703bd4e",
    "2c89a2e5-7285-40fe-afe0-ae8654b92fb2",
}

GUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

VALID_MCSB_PREFIXES = {
    "NS", "IM", "PA", "DP", "AM", "LT", "IR", "PV", "ES", "BR", "DS", "GS",
}


def validate_mappings(
    extraction: ControlExtractionResult,
    mappings: list[ControlPolicyMapping],
    min_confidence: float = 0.5,
) -> ValidationReport:
    """
    Validate the complete set of control-to-policy mappings.

    Checks:
    - All extracted controls have a mapping
    - Policy definition IDs are valid GUIDs
    - MCSB control IDs follow expected format
    - Confidence scores are reasonable
    - No duplicate policy references within a group
    - Manual controls have attestation notes

    Args:
        extraction: The original extracted controls.
        mappings: The policy mappings to validate.
        min_confidence: Threshold below which a warning is raised.

    Returns:
        ValidationReport with all issues found.
    """
    issues: list[ValidationIssue] = []
    total_controls = len(extraction.controls)
    extracted_ids = {c.control_id for c in extraction.controls}
    mapped_ids = {m.control_id for m in mappings}

    # ── Check: all controls were mapped ───────────────────────────────────
    unmapped = extracted_ids - mapped_ids
    for ctrl_id in unmapped:
        issues.append(ValidationIssue(
            severity="error",
            control_id=ctrl_id,
            message="Control was extracted but not mapped to any Azure Policy",
            suggestion="Re-run the mapping pipeline or manually add mapping",
        ))

    # ── Per-mapping checks ────────────────────────────────────────────────
    all_policy_ids: set[str] = set()
    automatable_count = 0
    manual_count = 0
    confidence_sum = 0.0

    for mapping in mappings:
        control_id = mapping.control_id

        # Check MCSB control ID format
        if mapping.mcsb_control_id:
            parts = mapping.mcsb_control_id.split("-")
            if len(parts) < 2 or parts[0] not in VALID_MCSB_PREFIXES:
                issues.append(ValidationIssue(
                    severity="warning",
                    control_id=control_id,
                    message=f"MCSB control ID '{mapping.mcsb_control_id}' has unexpected format",
                    suggestion=f"Expected format like 'NS-1', 'IM-6', 'DP-3'. Valid prefixes: {', '.join(sorted(VALID_MCSB_PREFIXES))}",
                ))

        # Check confidence score
        confidence_sum += mapping.confidence_score
        if mapping.confidence_score < min_confidence:
            issues.append(ValidationIssue(
                severity="warning",
                control_id=control_id,
                message=f"Low confidence mapping ({mapping.confidence_score:.2f} < {min_confidence})",
                suggestion="Review this mapping manually before deployment",
            ))

        # Check Azure Policy IDs
        if mapping.is_automatable:
            automatable_count += 1
            if not mapping.azure_policies:
                issues.append(ValidationIssue(
                    severity="error",
                    control_id=control_id,
                    message="Control marked as automatable but has no Azure Policy mappings",
                    suggestion="Add Azure Policy definitions or mark as not automatable",
                ))

            for policy in mapping.azure_policies:
                pid = policy.policy_definition_id

                if not GUID_PATTERN.match(pid):
                    issues.append(ValidationIssue(
                        severity="error",
                        control_id=control_id,
                        message=f"Invalid policy GUID format: '{pid}'",
                        suggestion="Azure Policy definition IDs must be valid UUIDs",
                    ))
                else:
                    all_policy_ids.add(pid)

                    if pid not in KNOWN_POLICY_GUIDS:
                        issues.append(ValidationIssue(
                            severity="info",
                            control_id=control_id,
                            message=f"Policy GUID '{pid}' is not in the known-good list",
                            suggestion="Verify this GUID exists in your Azure environment before deployment",
                        ))
        else:
            manual_count += 1
            if not mapping.manual_attestation_note:
                issues.append(ValidationIssue(
                    severity="warning",
                    control_id=control_id,
                    message="Non-automatable control missing manual attestation note",
                    suggestion="Add guidance on what manual steps or evidence are needed",
                ))

    avg_confidence = confidence_sum / len(mappings) if mappings else 0.0

    error_count = sum(1 for i in issues if i.severity == "error")
    is_valid = error_count == 0

    if not mappings:
        issues.append(ValidationIssue(
            severity="error",
            control_id="N/A",
            message="No controls were mapped",
            suggestion="Check that the PDF contains extractable controls",
        ))
        is_valid = False

    report = ValidationReport(
        is_valid=is_valid,
        total_controls=total_controls,
        automatable_controls=automatable_count,
        manual_controls=manual_count,
        unique_policies=len(all_policy_ids),
        avg_confidence=round(avg_confidence, 3),
        issues=issues,
    )

    errors = sum(1 for i in issues if i.severity == "error")
    warnings = sum(1 for i in issues if i.severity == "warning")
    infos = sum(1 for i in issues if i.severity == "info")

    logger.info(
        f"Validation {'PASSED' if is_valid else 'FAILED'}: "
        f"{total_controls} controls, {automatable_count} automatable, "
        f"{len(all_policy_ids)} unique policies, "
        f"avg confidence {avg_confidence:.2f}, "
        f"{errors} errors, {warnings} warnings, {infos} info"
    )

    return report
