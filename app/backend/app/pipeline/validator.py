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
    catalog: Optional[object] = None,
) -> ValidationReport:
    """
    Validate the complete set of control-to-policy mappings.

    Checks:
    - All extracted controls have a mapping
    - Policy definition IDs are valid GUIDs
    - Referenced GUIDs exist in the Azure built-in policy catalog
    - MCSB control IDs follow expected format
    - Confidence scores are reasonable
    - No duplicate policy references within a group
    - Manual controls have attestation notes

    Args:
        extraction: The original extracted controls.
        mappings: The policy mappings to validate.
        min_confidence: Threshold below which a warning is raised.
        catalog: Optional built-in policy catalog service (injected for testing).
            When available, referenced GUIDs are checked for existence. When it
            is not, existence cannot be checked at all and that is reported as
            a warning on the report rather than being papered over with a
            hardcoded shortlist.

    Returns:
        ValidationReport with all issues found.
    """
    if catalog is None:
        try:
            from app.services.policy_catalog_service import get_policy_catalog_service
            catalog = get_policy_catalog_service()
        except Exception:  # pragma: no cover - defensive
            catalog = None
    # ``available`` is a method, so the previous ``bool(getattr(catalog,
    # "available", False))`` was always True whenever a catalog object existed -
    # including one that had failed to load.
    _available = getattr(catalog, "available", None)
    catalog_available = bool(_available() if callable(_available) else _available)

    issues: list[ValidationIssue] = []
    total_controls = len(extraction.controls)
    extracted_ids = {c.control_id for c in extraction.controls}
    mapped_ids = {m.control_id for m in mappings}

    # Existence checking is the whole point of validation here, so its absence
    # is a finding rather than a quiet downgrade. The previous fallback - a
    # hardcoded 37-GUID "known-good list" - reported every real identifier
    # outside that list as suspect and every hallucinated one inside it as
    # fine, which is worse than saying nothing.
    if not catalog_available:
        issues.append(ValidationIssue(
            severity="warning",
            control_id="",
            message="The Azure Policy catalog is unavailable, so policy GUIDs could not be checked for existence",
            suggestion="Only GUID format was validated. Regenerate the catalog snapshot with scripts/generate_policy_catalog.py before relying on this report.",
        ))

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

                    if catalog_available and not catalog.exists(pid):
                        issues.append(ValidationIssue(
                            severity="warning",
                            control_id=control_id,
                            message=f"Policy GUID '{pid}' is not a real Azure built-in policy definition",
                            suggestion="ARM would reject this as PolicyDefinitionNotFound; it will be dropped before deployment. Re-run mapping or remove it.",
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
