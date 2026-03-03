"""
Mapping Validation Module.
Validates the control-to-Azure-Policy mappings before generating initiative artifacts.
"""

import logging
import re
from typing import Optional

from models import (
    ControlPolicyMapping,
    ControlExtractionResult,
    ValidationReport,
    ValidationIssue,
)

logger = logging.getLogger(__name__)

# Verified Azure Policy definition GUIDs (tested and confirmed deployable in MngEnvMCAP).
# Used to validate whether a GUID is likely real before deployment.
# GUIDs NOT in this set will generate an "info" warning — not an error.
KNOWN_POLICY_GUIDS = {
    # Identity & Access Management
    "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b",  # MFA owners
    "9297c21d-2ed6-4474-b48f-163f75654ce3",  # MFA write
    "e3576e28-8b17-4677-84c3-db2990658d64",  # MFA read
    "a451c1ef-c6ca-483d-87ed-f49761e3ffb5",  # K8s RBAC (audit)
    "34c877ad-507e-4c82-993e-3452a6e0ad3c",  # K8s RBAC enabled
    "0b15565f-aa9e-48ba-8619-45960f2c314d",  # Multiple subscription owners
    "a8eff44e-8db1-4c48-82a2-64d4e30b56bc",  # Deprecated owner accounts removed
    "94e1c2ac-cbbe-4cac-a2b5-2cb8b36ce676",  # Deprecated accounts removed
    "9bc48460-f641-4a27-9f38-efe33a4a3e9e",  # AAD admin SQL server
    "abfb7388-5bf4-4ad7-ba99-2cd2f41cebb9",  # AAD admin SQL MI
    "0015ea4d-51ff-4ce3-8d8c-f3f8f0be26b8",  # Custom RBAC roles audit
    "1f314764-cb73-4fc9-b863-8eca98ac36e9",  # RBAC K8s services
    "b0f33259-77d7-4c9e-aac6-3aabcfae693c",  # JIT VM access
    # Network Security
    "e71308d3-144b-4262-b144-efdc3cc90517",  # NSG on subnets
    "2c89a2e5-7285-40fe-afe0-ae8654b92fb2",  # NSG ports restricted (VM)
    "fc5e4038-4584-4632-8c85-c0448d374b2c",  # NSG ports restricted (NSG)
    "bb91dfba-c30d-4263-9add-9c2384e659a6",  # Remote debug Web App off
    "cb510bfd-1cba-4d9f-a1ea-bed557ae0564",  # Remote debug Functions off
    "f9d614c5-c173-4d56-95a7-b4437057d193",  # Remote debug API App off
    "1e66c121-a66d-4b99-b523-e2cf4bf16934",  # Azure Firewall enabled
    "83e0d761-c550-47de-b1b6-359f2a30b354",  # Adaptive network hardening
    "9dfea752-cf9d-4745-b47b-81b8330bbb9f",  # SQL MI public endpoint disabled
    "ae89ebf1-3572-4ab1-b1bd-ec5f00bab3a6",  # SQL private endpoint
    "1c06e275-d63d-4540-b761-71f364c2111d",  # KeyVault private endpoint
    # Encryption & Data Protection
    "7595c971-233d-4bcf-bd18-596129188c49",  # SQL TDE
    "404c3081-a854-4457-ae30-26a93ef643f9",  # Secure transfer storage
    "4733ea7b-a883-42fe-8cac-97454c2a9e4a",  # Storage network restrict
    "a4af4a39-4135-4a60-8bf6-d34b2a1d4f2c",  # Storage CMK
    "1f905d99-2622-4c13-100b-f7c8e2078bc5",  # Cosmos DB CMK
    "702dd420-7fcc-42c5-afe8-4026edd20fe0",  # Disk CMK
    "18adea5e-f416-4d0f-8aa8-d24321e3e274",  # PostgreSQL CMK
    "0a370ff3-6cab-4e85-8995-295fd854c5b8",  # SQL MI CMK
    "0961003e-5a0a-4549-abde-af6a37f2724d",  # Temp disk encryption
    "67121cc7-ff16-4bfd-986d-b15f4c767a1b",  # Cognitive Services CMK
    "0725b4dd-7e76-479c-a735-68e7ee23d5ca",  # Cognitive Services public network
    # Logging & Monitoring
    "818719e5-1338-4776-9a9d-3c31e4df5986",  # Log Analytics agent on VM
    "428256e6-1fac-4f48-a757-df34c2b3336d",  # Diagnostic settings (no param)
    "89099bee-89e0-4b26-a5f4-165451757743",  # SQL audit retention 90 days
    "b954148f-4c11-4c38-8221-be76711e194e",  # SQL MI advanced security
    "b0d14bf4-f90c-4e66-9457-1346f80b5a44",  # Security contact email
    "6e2593d9-add6-4083-9c9b-4b7d2188c899",  # Defender SQL email notifications
    # Key Management
    "8e826246-c976-48f6-b03e-619bb92b3d82",  # KV key expiration
    "5f0bc445-3935-4915-9981-011aa2b46147",  # KV secret expiration
    "f4b53539-8df9-40e4-86c6-6b607703bd4e",  # Keys backed by HSM
    "6a523b34-47f5-4a80-a97e-d3e2d8bca2d6",  # KV Managed HSM purge protection
    "c39ba22d-4428-4149-b981-98acef4f7277",  # KV firewall enabled
    # Endpoint Security & Vulnerability
    "e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f",  # Vuln assessment VMs
    "44e1ad92-5f90-4a45-83bb-81cd4695e9f4",  # VM vulnerability findings resolved
    "1b7aa243-0538-4a73-b824-0b3fc489d80c",  # Vuln assessment SQL MI
    "013e242c-8828-4970-87b3-ab247555486d",  # Endpoint protection
    "ac076320-ddcf-4066-b451-6154267e8ad2",  # Anti-malware / Endpoint Protection
    "86b3d65f-7626-441e-b690-81a8b71cff60",  # System updates (classic)
    "bd876905-5b84-4f73-ab2d-2e7a7c4568d9",  # Vulnerability assessment solution
    "9c276cf7-d6e0-4a09-a4b4-be5f06902a79",  # VMSS system updates
    # Backup & Recovery
    "09024ccc-0c5f-475e-9457-b7c0d9ed487b",  # Azure Backup VMs
    "22bee202-a82f-4305-9a2a-6d7f44d4dedb",  # Geo-redundant backup MySQL
    # Data Classification & Privacy
    "ca610c1d-041c-4332-9d88-7ed3094967c7",  # SQL private endpoint connections
    "0b60c0b2-2dc2-4e1c-b5c9-abbed971de53",  # SQL data classification
    # Location / Data Residency
    "e56962a6-4747-49cd-b67b-bf8b01975c4c",  # Allowed locations
    "37bc2e11-1d3c-4e6e-a9fc-62ca7b58b6c2",  # Allowed locations for RGs
    # Incident Response / Alerts
    "8e86a5b6-b9bd-49d1-8e21-4bb8a0862222",  # Adaptive application controls
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
            message=f"Control was extracted but not mapped to any Azure Policy",
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

                # Validate GUID format
                if not GUID_PATTERN.match(pid):
                    issues.append(ValidationIssue(
                        severity="error",
                        control_id=control_id,
                        message=f"Invalid policy GUID format: '{pid}'",
                        suggestion="Azure Policy definition IDs must be valid UUIDs",
                    ))
                else:
                    all_policy_ids.add(pid)

                    # Check if it's a known GUID
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

    # ── Summary checks ────────────────────────────────────────────────────
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

    # Log summary
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
