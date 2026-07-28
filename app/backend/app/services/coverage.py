"""
Coverage taxonomy for control-to-Azure-Policy mapping.

The AI mapping engine over-attaches Azure Policy IDs: process, legal, HR and
governance controls that Azure cannot technically enforce get handed a catch-all
policy (typically an MCSB "Governance & Strategy" entry). The control extractor
already classifies every control's *nature* (``control_type``), but that signal
was dropped before mapping.

This module is the deterministic guarantee. It carries the extractor's
classification through to the mapping and decides, with pure functions, which
controls are genuinely Azure-Policy-enforceable. Only enforceable controls keep
their ``azure_policy_ids``; everything else is routed to a manual register.

Coverage categories
-------------------
- ``A_AzurePolicy``       enforceable/auditable via Azure Policy (emit policy IDs)
- ``B_AzureConfig``       Azure-configurable but not via Azure Policy (no IDs)
- ``C_Process``           process / legal / HR / contractual (manual register)
- ``D_MicrosoftAttestation`` Microsoft-operated (datacentre/physical) attestation

Invariant enforced everywhere: ``azure_policy_ids`` is non-empty **only** when
coverage is ``A_AzurePolicy``. This aligns with the PDF pipeline's existing
``is_automatable`` flag (A ⇔ automatable).

Compliance is a wider notion than Azure-Policy enforcement: ``A_AzurePolicy``
is compliant because Azure enforces it, and ``D_MicrosoftAttestation`` is
compliant because Microsoft operates and certifies it on the customer's behalf.
``B_AzureConfig`` and ``C_Process`` remain open customer actions. See
``INHERITED_COMPLIANT_CATEGORIES``.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

CoverageCategory = str  # one of the COVERAGE_* constants below

COVERAGE_A = "A_AzurePolicy"
COVERAGE_B = "B_AzureConfig"
COVERAGE_C = "C_Process"
COVERAGE_D = "D_MicrosoftAttestation"

VALID_COVERAGE_CATEGORIES = frozenset(
    {COVERAGE_A, COVERAGE_B, COVERAGE_C, COVERAGE_D}
)

# Categories that count as compliant without any customer action. Microsoft
# operates the underlying control and evidences it through its own audited
# certifications (Service Trust Portal), so the control is inherited-compliant:
# it must stay out of the initiative, but it is not a coverage gap either.
INHERITED_COMPLIANT_CATEGORIES = frozenset({COVERAGE_D})

# control_type values (from pipeline/control_extractor.py) that describe a
# control's nature as process/organisational rather than a technical control an
# Azure Policy could audit or enforce. Compared case-folded.
PROCESS_CONTROL_TYPES = frozenset(
    {"policy", "contractual", "management", "operational", "governance"}
)

# Keywords indicating the control concerns Microsoft-operated infrastructure the
# customer attests to via the Service Trust Portal / certifications rather than
# configures — routed to D_MicrosoftAttestation. Compared case-insensitively.
ATTESTATION_KEYWORDS = (
    "data centre",
    "data center",
    "datacentre",
    "datacenter",
    "physical security",
    "physical access",
    "hypervisor",
    "host operating system",
    "microsoft personnel",
    "service trust",
    "iso 27001",
    "soc 2",
    "csp certification",
    "cloud service provider certification",
)

# Keywords indicating a genuinely technical control, used to override a
# process-typed classification when the text is clearly about enforceable Azure
# configuration (defence against extractor mis-classification).
TECHNICAL_KEYWORDS = (
    "encrypt",
    "tls",
    "mfa",
    "multi-factor",
    "firewall",
    "network security group",
    "private endpoint",
    "key vault",
    "backup",
    "logging",
    "diagnostic",
    "retention",
    "rbac",
    "role assignment",
    "vulnerability",
    "patch",
    "azure policy",
)


def _casefold(value: Optional[str]) -> str:
    return (value or "").strip().casefold()


def is_process_control(control_type: Optional[str]) -> bool:
    """True if ``control_type`` names a process/organisational control nature."""
    return _casefold(control_type) in PROCESS_CONTROL_TYPES


def _has_keyword(text: str, keywords: Iterable[str]) -> bool:
    low = text.casefold()
    return any(kw in low for kw in keywords)


def resolve_coverage(
    control_type: Optional[str],
    enforceable_policy_ids: List[str],
    text: str = "",
    model_category: Optional[str] = None,
) -> Tuple[CoverageCategory, bool]:
    """Decide a control's coverage category and Azure-enforceability.

    Deterministic and side-effect free.

    Precedence:
    1. A genuinely technical control (not process-typed, OR process-typed but the
       text is clearly technical) that has at least one enforceable policy ID is
       ``A_AzurePolicy``.
    2. Otherwise, a valid explicit ``model_category`` (B/C/D) is respected.
    3. Otherwise, attestation keywords → ``D_MicrosoftAttestation``.
    4. Otherwise, process controls → ``C_Process``; anything left with no
       enforceable policy → ``C_Process`` as the conservative default.

    Returns ``(coverage_category, azure_enforceable)``. ``azure_enforceable`` is
    ``True`` iff the category is ``A_AzurePolicy``.
    """
    has_policies = bool(enforceable_policy_ids)
    process = is_process_control(control_type)
    technical_text = _has_keyword(text, TECHNICAL_KEYWORDS)

    # 1. Enforceable technical control.
    if has_policies and (not process or technical_text):
        return COVERAGE_A, True

    # 2. Respect an explicit, valid non-A model classification.
    if model_category in {COVERAGE_B, COVERAGE_C, COVERAGE_D}:
        return model_category, False

    # 3. Microsoft-operated / attestation.
    if _has_keyword(text, ATTESTATION_KEYWORDS):
        return COVERAGE_D, False

    # 4. Conservative default: process controls (and anything non-enforceable).
    return COVERAGE_C, False


def apply_coverage(mapping, control_type: Optional[str], catalog=None):
    """Enrich a ``ControlMapping`` in place with coverage classification.

    - Propagates ``control_type`` onto the mapping.
    - Computes the enforceable subset of ``azure_policy_ids`` (dropping catalog
      "Regulatory Compliance" placeholders when a catalog is supplied).
    - Resolves the coverage category and sets ``azure_enforceable``.
    - Clears ``azure_policy_ids`` whenever coverage is not ``A_AzurePolicy`` —
      the invariant that keeps non-enforceable controls out of the initiative.

    Pure with respect to inputs other than the passed ``mapping`` (which it
    returns for convenience). ``catalog`` is optional; when ``None`` the
    Regulatory-Compliance strip is skipped and all well-formed IDs count as
    candidates.
    """
    mapping.control_type = control_type

    raw_ids = list(mapping.azure_policy_ids or [])
    enforceable_ids = [
        pid for pid in raw_ids if _is_enforceable_id(pid, catalog)
    ]

    text = " ".join(
        part
        for part in (
            getattr(mapping, "external_control_name", ""),
            getattr(mapping, "reasoning", ""),
        )
        if part
    )

    category, enforceable = resolve_coverage(
        control_type=control_type,
        enforceable_policy_ids=enforceable_ids,
        text=text,
        model_category=mapping.coverage_category,
    )

    mapping.coverage_category = category
    mapping.azure_enforceable = enforceable
    if category == COVERAGE_A:
        mapping.azure_policy_ids = enforceable_ids
    else:
        mapping.azure_policy_ids = []
    return mapping


def _is_enforceable_id(policy_id: str, catalog) -> bool:
    """True if ``policy_id`` looks like a usable, enforceable policy GUID.

    Drops catalog "Regulatory Compliance" (Microsoft Managed Control /
    manual-attestation) placeholders when a catalog is supplied; these carry no
    audit/deny effect so they must not count as enforcement.
    """
    if not policy_id or not policy_id.strip():
        return False
    if catalog is None:
        return True
    guid = policy_id.strip().rstrip("/").rsplit("/", 1)[-1]
    is_non_enforceable = getattr(catalog, "is_non_enforceable", None)
    if callable(is_non_enforceable) and is_non_enforceable(guid):
        return False
    return True


def _reason_for(mapping) -> str:
    """Human-readable reason a control is not Azure-Policy enforceable."""
    return {
        COVERAGE_B: "Azure-configurable but not enforceable via Azure Policy",
        COVERAGE_C: "Process / legal / organisational control — not Azure-enforceable",
        COVERAGE_D: (
            "Microsoft-operated control — compliant via Microsoft attestation "
            "(Service Trust Portal); no customer action required"
        ),
    }.get(mapping.coverage_category, "Not Azure-Policy enforceable")


def manual_register_rows(mappings) -> List[dict]:
    """Build manual-register rows for every non-``A_AzurePolicy`` mapping.

    Controls with ``coverage_category is None`` (legacy mappings) are treated as
    enforceable and skipped, preserving backward-compatible behaviour.
    """
    rows: List[dict] = []
    for m in mappings:
        category = getattr(m, "coverage_category", None)
        if category is None or category == COVERAGE_A:
            continue
        rows.append(
            {
                "control_id": m.external_control_id,
                "control_name": m.external_control_name,
                "control_type": getattr(m, "control_type", None) or "",
                "coverage_category": category,
                "mcsb_control_id": m.mcsb_control_id,
                "reason": _reason_for(m),
            }
        )
    return rows


def coverage_summary(mappings) -> dict:
    """Count controls per coverage category, the Azure-enforceable and compliant shares.

    Two distinct measures are returned and must not be conflated:

    - ``azure_enforceable``/``azure_enforceable_pct`` — controls Azure Policy
      enforces (``A_AzurePolicy`` only). Drives what lands in the initiative.
    - ``compliant``/``compliant_pct`` — controls that need no customer remediation:
      ``A_AzurePolicy`` plus the ``INHERITED_COMPLIANT_CATEGORIES``
      (``D_MicrosoftAttestation``, satisfied by Microsoft's own attestation).
      ``B_AzureConfig`` and ``C_Process`` stay outside this count as open actions.

    Legacy mappings (``coverage_category is None``) are bucketed under
    ``"unclassified"`` so totals always reconcile.
    """
    counts = {
        COVERAGE_A: 0,
        COVERAGE_B: 0,
        COVERAGE_C: 0,
        COVERAGE_D: 0,
        "unclassified": 0,
    }
    for m in mappings:
        category = getattr(m, "coverage_category", None)
        if category in counts:
            counts[category] += 1
        elif category is None:
            counts["unclassified"] += 1
        else:
            counts["unclassified"] += 1

    total = sum(counts.values())
    enforceable = counts[COVERAGE_A]
    inherited = sum(counts[c] for c in INHERITED_COMPLIANT_CATEGORIES)
    compliant = enforceable + inherited
    counts["total"] = total
    counts["azure_enforceable"] = enforceable
    counts["azure_enforceable_pct"] = (
        round(100.0 * enforceable / total, 1) if total else 0.0
    )
    counts["inherited_compliant"] = inherited
    counts["compliant"] = compliant
    counts["compliant_pct"] = round(100.0 * compliant / total, 1) if total else 0.0
    return counts


def manual_controls_csv(mappings) -> str:
    """Render the manual register as CSV text (header + one row per non-A control)."""
    import csv
    import io

    fieldnames = [
        "control_id",
        "control_name",
        "control_type",
        "coverage_category",
        "mcsb_control_id",
        "reason",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in manual_register_rows(mappings):
        writer.writerow(row)
    return buffer.getvalue()
