#!/usr/bin/env python3
"""Generate the Microsoft attestation catalog snapshot.

Category D controls ("Microsoft attested") are the ones the customer cannot
enforce and cannot implement: Microsoft operates them, and the customer's only
route to satisfying an auditor is to *cite Microsoft's attestation*. Today the
product asserts "Microsoft-operated" and stops, which leaves the customer to
prove it themselves.

An invented clause reference fails in front of a regulator exactly the way an
invented policy GUID does. So D citations are grounded the same way policy IDs
are: against a catalog, with an ``exists()`` check, and anything that cannot be
grounded is reported as a gap rather than printed.

Where the clause facts come from
--------------------------------
Not from the standards themselves -- their text is copyrighted, and paraphrasing
a clause is how you end up citing something that does not exist. They come from
``Microsoft.PolicyInsights/policyMetadata``, the same source the analyst
workbook's Legend names:

    "ISO/IEC 27002:2022 clause numbers used in this workbook were taken from the
     Azure built-in initiative 'ISO/IEC 27002 2022' group identifiers. The 2013
     Annex A numbering differs and should not be substituted."

Each metadata entry carries the clause id, its ``title``, the control
``category``, and Microsoft's own ``owner`` assignment (Shared / Microsoft /
Customer). We keep those and the scheme's evidence location; we deliberately do
*not* keep the ``requirements`` field, which is the closest thing to standard
body text.

Scheme-level evidence facts -- which document to ask for, where it lives, and
whether an NDA is required -- have no ARM representation, so they are curated
here and marked ``source: "curated"``. Clause facts are marked
``source: "azure-policy-metadata"``. The distinction is preserved into the
snapshot so the product never presents a curated fact as a live one.

Usage::

    python scripts/generate_attestation_catalog.py               # from live ARM
    python scripts/generate_attestation_catalog.py --raw dump.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

METADATA_API_VERSION = "2019-10-01"

DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "app" / "backend" / "app" / "data" / "policy_catalog"
    / "attestation_catalog.json"
)

# Attestation basis kinds. A D control resolves to exactly one of these, and
# ``BASIS_NONE`` is a first-class outcome -- the sovereign gap case in the
# analyst workbook (UAE national security clearance, which no Microsoft
# certification attests) must be sayable.
BASIS_CERTIFICATION = "certification_clause"
BASIS_AUDIT_REPORT = "audit_report_criterion"
BASIS_DOCUMENTATION = "published_documentation"
BASIS_NONE = "none"

STP = "https://servicetrust.microsoft.com"
LEARN = "https://learn.microsoft.com/azure/compliance/offerings"

# Scheme registry.
#
# ``prefix`` is the policyMetadata name prefix that carries this scheme's
# clauses. Schemes with no prefix have no Azure metadata representation at all
# (SOC 1, SOC 3, ISO 27018, CSA STAR certification) -- they are still real
# attestations a customer can cite, so they are carried at scheme level with no
# clause list rather than being silently unavailable.
#
# ``access`` follows the workbook Legend: "SOC 1 and SOC 2 reports require
# sign-in with a work account and acceptance of the Microsoft NDA. ISO
# certificates are downloadable without an NDA."
SCHEMES: List[Dict[str, Any]] = [
    {
        "key": "iso_27001_2022",
        "aliases": ["iso iec 27001 2022", "iso 27001 2022", "iso27001 2022", "iso/iec 27001:2022"],
        "name": "ISO/IEC 27001:2022",
        "basis_kind": BASIS_CERTIFICATION,
        "prefix": "ISO_IEC_27001_2022_",
        "clause_label": "clause",
        "evidence_document": "ISO/IEC 27001:2022 certificate and Statement of Applicability",
        "evidence_location": f"{STP}/viewpage/ISO",
        "access_condition": "Downloadable without an NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal, open ISO/IEC reports, and download "
            "the current ISO/IEC 27001 certificate and Statement of Applicability."
        ),
    },
    {
        "key": "iso_27001_2013",
        "aliases": ["iso 27001 2013", "iso iec 27001 2013", "iso 27001:2013", "annex a"],
        "name": "ISO 27001:2013",
        "basis_kind": BASIS_CERTIFICATION,
        "prefix": "ISO27001-2013_",
        "clause_label": "Annex A control",
        "evidence_document": "ISO 27001:2013 certificate and Statement of Applicability",
        "evidence_location": f"{STP}/viewpage/ISO",
        "access_condition": "Downloadable without an NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal, open ISO/IEC reports, and download the "
            "ISO 27001:2013 certificate. Note the 2013 Annex A numbering differs from "
            "ISO/IEC 27002:2022 and must not be substituted for it."
        ),
    },
    {
        "key": "iso_27002_2022",
        "aliases": ["iso iec 27002 2022", "iso 27002 2022", "iso/iec 27002:2022"],
        "name": "ISO/IEC 27002:2022",
        "basis_kind": BASIS_CERTIFICATION,
        "prefix": "ISO_IEC_27002_2022_",
        "clause_label": "clause",
        "evidence_document": "ISO/IEC 27001:2022 certificate (27002 provides the control guidance)",
        "evidence_location": f"{STP}/viewpage/ISO",
        "access_condition": "Downloadable without an NDA",
        "retrieval": (
            "ISO/IEC 27002 is guidance rather than a certifiable standard; cite it alongside "
            "the ISO/IEC 27001:2022 certificate obtained from the Service Trust Portal."
        ),
    },
    {
        "key": "iso_27017_2015",
        "aliases": ["iso iec 27017", "iso 27017", "cloud services controls"],
        "name": "ISO/IEC 27017:2015",
        "basis_kind": BASIS_CERTIFICATION,
        "prefix": "ISO_IEC_27017_2015_",
        "clause_label": "control",
        "evidence_document": "ISO/IEC 27017:2015 certificate",
        "evidence_location": f"{STP}/viewpage/ISO",
        "access_condition": "Downloadable without an NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal, open ISO/IEC reports, and download the "
            "current ISO/IEC 27017 cloud services certificate."
        ),
    },
    {
        "key": "iso_27018_2019",
        "aliases": ["iso iec 27018", "iso 27018", "pii in public cloud"],
        "name": "ISO/IEC 27018:2019",
        "basis_kind": BASIS_CERTIFICATION,
        "prefix": "",  # no Azure policyMetadata representation
        "clause_label": "control",
        "evidence_document": "ISO/IEC 27018:2019 certificate",
        "evidence_location": f"{STP}/viewpage/ISO",
        "access_condition": "Downloadable without an NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal, open ISO/IEC reports, and download the "
            "current ISO/IEC 27018 PII-in-public-cloud certificate."
        ),
        "note": (
            "Azure publishes no clause-level policy metadata for this scheme, so citations "
            "are scheme-level only."
        ),
    },
    {
        "key": "soc_2",
        "aliases": ["soc 2 type ii", "soc 2 type 2", "soc2", "soc 2", "trust services criteria"],
        "name": "SOC 2 Type II",
        "basis_kind": BASIS_AUDIT_REPORT,
        # Must be ``SOC_2_`` and not ``SOC_2``: the shorter form also swallows
        # every ``SOC_2023_*`` entry, which produced citations reading
        # "SOC 2 Type II criterion 023_CC6.4" -- a criterion that does not exist.
        "prefix": "SOC_2_",
        "clause_label": "criterion",
        "evidence_document": "Azure SOC 2 Type II report",
        "evidence_location": f"{STP}/viewpage/SOC",
        "access_condition": "Requires sign-in with a work account and acceptance of the Microsoft NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal with a work account, accept the Microsoft NDA, "
            "and download the current Azure SOC 2 Type II report."
        ),
    },
    {
        "key": "soc_2_2023",
        "aliases": ["soc 2 2023", "soc 2023"],
        "name": "SOC 2 (2023 Trust Services Criteria)",
        "basis_kind": BASIS_AUDIT_REPORT,
        "prefix": "SOC_2023_",
        "clause_label": "criterion",
        "evidence_document": "Azure SOC 2 Type II report (2023 Trust Services Criteria)",
        "evidence_location": f"{STP}/viewpage/SOC",
        "access_condition": "Requires sign-in with a work account and acceptance of the Microsoft NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal with a work account, accept the Microsoft NDA, "
            "and download the current Azure SOC 2 Type II report."
        ),
    },
    {
        "key": "soc_1",
        "aliases": ["soc 1 type ii", "soc 1 type 2", "soc1", "soc 1"],
        "name": "SOC 1 Type II",
        "basis_kind": BASIS_AUDIT_REPORT,
        "prefix": "",
        "clause_label": "criterion",
        "evidence_document": "Azure SOC 1 Type II report",
        "evidence_location": f"{STP}/viewpage/SOC",
        "access_condition": "Requires sign-in with a work account and acceptance of the Microsoft NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal with a work account, accept the Microsoft NDA, "
            "and download the current Azure SOC 1 Type II report."
        ),
        "note": "Azure publishes no clause-level policy metadata for this scheme.",
    },
    {
        "key": "soc_3",
        "aliases": ["soc 3", "soc3"],
        "name": "SOC 3",
        "basis_kind": BASIS_AUDIT_REPORT,
        "prefix": "",
        "clause_label": "criterion",
        "evidence_document": "Azure SOC 3 public report",
        "evidence_location": f"{STP}/viewpage/SOC",
        "access_condition": "Publicly downloadable; no NDA required",
        "retrieval": "Download the Azure SOC 3 report from the Service Trust Portal.",
        "note": "Azure publishes no clause-level policy metadata for this scheme.",
    },
    {
        "key": "csa_ccm_v4",
        "aliases": ["csa star", "cloud controls matrix", "csa ccm", "caiq", "star attestation"],
        "name": "CSA Cloud Controls Matrix v4.0.12",
        "basis_kind": BASIS_CERTIFICATION,
        "prefix": "CSA_v4.0.12_",
        "clause_label": "control",
        "evidence_document": "CSA STAR Attestation and CAIQ (Cloud Controls Matrix v4)",
        "evidence_location": f"{STP}/viewpage/CSASTAR",
        "access_condition": "CSA STAR registry entries are public; the STAR Attestation report requires NDA acceptance",
        "retrieval": (
            "Retrieve the Microsoft CAIQ from the CSA STAR registry, and the STAR Attestation "
            "report from the Service Trust Portal."
        ),
    },
    {
        "key": "pci_dss_v4_0_1",
        "aliases": ["pci dss v4 0 1", "pci dss 4.0.1"],
        "name": "PCI DSS v4.0.1",
        "basis_kind": BASIS_AUDIT_REPORT,
        # Longest-prefix-first matching matters here: ``PCI_DSS_v4.0_`` would
        # otherwise never see v4.0.1, and ``PCI_DSS_v4`` would merge three
        # mutually incompatible requirement numberings into one scheme.
        "prefix": "PCI_DSS_v4.0.1_",
        "clause_label": "requirement",
        "evidence_document": "Azure PCI DSS Attestation of Compliance (AoC)",
        "evidence_location": f"{STP}/viewpage/PCI",
        "access_condition": "Requires sign-in with a work account and acceptance of the Microsoft NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal with a work account, accept the Microsoft NDA, "
            "and download the current Azure PCI DSS Attestation of Compliance."
        ),
    },
    {
        "key": "pci_dss_v4_0",
        "aliases": ["pci dss v4", "pci dss 4.0", "pci dss"],
        "name": "PCI DSS v4.0",
        "basis_kind": BASIS_AUDIT_REPORT,
        "prefix": "PCI_DSS_v4.0_",
        "clause_label": "requirement",
        "evidence_document": "Azure PCI DSS Attestation of Compliance (AoC)",
        "evidence_location": f"{STP}/viewpage/PCI",
        "access_condition": "Requires sign-in with a work account and acceptance of the Microsoft NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal with a work account, accept the Microsoft NDA, "
            "and download the current Azure PCI DSS Attestation of Compliance."
        ),
    },
    {
        "key": "pci_dss_v3_2_1",
        "aliases": ["pci dss v3 2 1", "pci dss 3.2.1"],
        "name": "PCI DSS v3.2.1",
        "basis_kind": BASIS_AUDIT_REPORT,
        "prefix": "PCI_DSS_v3.2.1_",
        "clause_label": "requirement",
        "evidence_document": "Azure PCI DSS Attestation of Compliance (AoC)",
        "evidence_location": f"{STP}/viewpage/PCI",
        "access_condition": "Requires sign-in with a work account and acceptance of the Microsoft NDA",
        "retrieval": (
            "Sign in to the Service Trust Portal with a work account, accept the Microsoft NDA, "
            "and download the Azure PCI DSS Attestation of Compliance."
        ),
        "note": "Superseded by PCI DSS v4.0; cite only where a regulator still references v3.2.1.",
    },
    {
        "key": "microsoft_documentation",
        "aliases": ["published microsoft documentation", "published product documentation", "product documentation", "microsoft learn", "not a certification item", "product behaviour", "platform documentation"],
        "name": "Published Microsoft documentation",
        "basis_kind": BASIS_DOCUMENTATION,
        "prefix": "",
        "clause_label": "article",
        "evidence_document": "Microsoft Learn product documentation",
        "evidence_location": LEARN,
        "access_condition": "Public; no sign-in required",
        "retrieval": "Cite the specific Microsoft Learn article describing the platform behaviour.",
        "note": (
            "Not a certification item. Used where a requirement is satisfied by documented "
            "product behaviour rather than by an audited control."
        ),
    },
]


def _fetch_metadata_az() -> List[Dict[str, Any]]:
    """Page through ``Microsoft.PolicyInsights/policyMetadata`` via the Azure CLI."""
    entries: List[Dict[str, Any]] = []
    url = (
        "https://management.azure.com/providers/Microsoft.PolicyInsights/"
        f"policyMetadata?api-version={METADATA_API_VERSION}&$top=1000"
    )
    while url:
        raw = subprocess.run(
            ["az", "rest", "--method", "get", "--url", url, "-o", "json"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
        page = json.loads(raw)
        entries.extend(page.get("value") or [])
        url = page.get("nextLink")
    return entries


def _clause_id(name: str, prefix: str) -> str:
    """Strip the scheme prefix, leaving the clause number the analyst would cite.

    CSA names its controls ``DOMAIN-NN`` (``IAM-01``) but Azure spells them
    ``CSA_v4.0.12_IAM_01``, so the trailing segment is re-hyphenated. Without
    this the catalog would answer "IAM_01 does not exist" for the identifier
    printed in every CSA CAIQ.
    """
    tail = name[len(prefix):] if prefix and name.startswith(prefix) else name
    tail = tail.lstrip("_").strip()
    if prefix.startswith("CSA_") and "_" in tail:
        domain, _, number = tail.partition("_")
        tail = f"{domain}-{number}"
    return tail


def build_catalog(entries: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    # Longest prefix first. ``PCI_DSS_v4.0_`` is a prefix of ``PCI_DSS_v4.0.1_``
    # only in the other direction, but ``PCI_DSS_v4.0.1_x`` does start with
    # ``PCI_DSS_v4.0``; matching shortest-first would file every v4.0.1
    # requirement under v4.0 and silently produce citations against the wrong
    # revision of the standard.
    by_prefix = sorted(
        ((s, s["prefix"]) for s in SCHEMES if s["prefix"]),
        key=lambda pair: len(pair[1]),
        reverse=True,
    )
    clauses: Dict[str, List[Dict[str, Any]]] = {s["key"]: [] for s in SCHEMES}

    for entry in entries:
        name = (entry.get("name") or "").strip()
        props = entry.get("properties") or {}
        title = (props.get("title") or "").strip()
        if not name or not title:
            continue
        for scheme, prefix in by_prefix:
            if not name.startswith(prefix):
                continue
            clause = _clause_id(name, prefix)
            if not clause:
                break
            clauses[scheme["key"]].append(
                {
                    "clause": clause,
                    "title": title,
                    # Microsoft's own responsibility assignment for the clause.
                    # Kept because it is evidence about who operates the control,
                    # which is exactly the question a D control asks.
                    "owner": (props.get("owner") or "").strip(),
                    "category": " ".join((props.get("category") or "").split()),
                    "metadata_id": (props.get("metadataId") or name).strip(),
                    # Deliberately excludes ``requirements`` -- the field closest
                    # to copyrighted standard text.
                    "source": "azure-policy-metadata",
                }
            )
            break

    schemes: List[Dict[str, Any]] = []
    for scheme in SCHEMES:
        rows = sorted(clauses[scheme["key"]], key=lambda c: c["clause"])
        schemes.append(
            {
                **{k: v for k, v in scheme.items() if k != "prefix"},
                "clause_count": len(rows),
                "clauses": rows,
                "evidence_source": "curated",
                "clause_source": (
                    "azure-policy-metadata" if rows else "unavailable"
                ),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata_api_version": METADATA_API_VERSION,
        "scheme_count": len(schemes),
        "clause_count": sum(s["clause_count"] for s in schemes),
        "basis_kinds": [
            BASIS_CERTIFICATION, BASIS_AUDIT_REPORT, BASIS_DOCUMENTATION, BASIS_NONE,
        ],
        "schemes": schemes,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", help="Path to a captured policyMetadata JSON dump")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    if args.raw:
        raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
        entries = raw.get("value") if isinstance(raw, dict) else raw
    else:
        entries = _fetch_metadata_az()

    catalog = build_catalog(entries or [])

    # Fail loudly rather than shipping an empty catalog. A silently empty
    # attestation catalog would make every D control look like an unattested
    # gap, which is the opposite failure to the one this file exists to prevent.
    if catalog["clause_count"] == 0:
        print(
            "ERROR: no attestation clauses resolved from the input; refusing to "
            "write an empty catalog.",
            file=sys.stderr,
        )
        return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {catalog['clause_count']} clauses across "
        f"{catalog['scheme_count']} schemes to {out}"
    )
    for scheme in catalog["schemes"]:
        print(f"  {scheme['name']:32} {scheme['clause_count']:4} ({scheme['clause_source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
