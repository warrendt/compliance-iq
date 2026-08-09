"""Grounding for Category D ("Microsoft attested") controls.

A D control is one the customer can neither enforce with policy nor implement
themselves: Microsoft operates it. Their only route to satisfying an auditor is
to *cite Microsoft's attestation* -- and a citation is only worth anything if it
is real. An invented ``ISO/IEC 27001:2022 clause 9.2`` fails in front of a
regulator exactly the way an invented policy GUID does, so citations are
validated here the same way GUIDs are validated against the policy catalog.

Three honest outcomes, and no fourth
------------------------------------
``resolve()`` never returns a guess. It returns one of:

``GROUNDED``
    The scheme and the clause both exist in the catalog. The clause title is
    *read* from Azure's published metadata, never authored by the model.

``SCHEME_ONLY``
    The scheme is a real Microsoft attestation, but this clause is not in
    Azure's published metadata. This is common and is **not** the model's fault:
    Azure only publishes metadata for clauses it ships policies against, so a
    genuine clause of a genuine standard can be absent. The scheme and its
    evidence document are cited; the clause number is carried as *unverified*
    and must be presented as such. Asserting a title we cannot read would be the
    invented-GUID failure in a different costume.

``UNATTESTED``
    Nothing grounds the claim. This is the sovereign gap case and the most
    valuable output in the system: the analyst workbook's control 3.1.3.4 asks
    for UAE national security clearance for operations personnel, which ISO/IEC
    27001 and SOC 2 do not attest -- they attest *screening*. A system that
    quietly called that "Microsoft-attested" would hand a UAE customer a false
    pass on precisely the sovereign requirement their regulator cares most
    about.

Where the facts come from
-------------------------
Clause ids, titles and Microsoft's own ``owner`` assignment come from
``Microsoft.PolicyInsights/policyMetadata`` -- the source the analyst workbook's
Legend names for its ISO/IEC 27002:2022 numbering. Evidence documents,
locations and NDA conditions have no ARM representation and are curated in
``scripts/generate_attestation_catalog.py``; the snapshot keeps the two apart so
a curated fact is never presented as a live one.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Resolution outcomes.
GROUNDED = "grounded"
SCHEME_ONLY = "scheme_only"
UNATTESTED = "unattested"

# Attestation basis kinds, mirroring the generator.
BASIS_CERTIFICATION = "certification_clause"
BASIS_AUDIT_REPORT = "audit_report_criterion"
BASIS_DOCUMENTATION = "published_documentation"
BASIS_NONE = "none"

DEFAULT_CATALOG_PATH = "data/policy_catalog/attestation_catalog.json"

# Free-text the classifier produces looks like:
#   "ATTESTED BY: ISO/IEC 27001:2022 clause 9.2 (internal audit)"
#   "SOC 2 CC6.4"
#   "ISO/IEC 27002:2022 clause 7.1-7.4 (physical controls)"
# A clause is a dotted/hyphenated identifier, optionally prefixed by a letter
# code (CC6.4, A.12.1.1, IAM-01, 8.2).
_CLAUSE_RE = re.compile(
    r"\b(?:clause|control|criterion|requirement|section|annex)?\s*"
    r"((?:[A-Z]{1,4}[-.]?)?\d+(?:\.\d+)*(?:[-.]\d+)*)\b",
    re.IGNORECASE,
)
_LEAD_LABEL_RE = re.compile(r"^\s*attested\s+by\s*:\s*", re.IGNORECASE)


def _norm(text: str) -> str:
    """Fold a scheme name to a comparable key: ``ISO/IEC 27001:2022`` -> ``iso27001 2022``."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


@dataclass
class AttestationCitation:
    """A resolved (or explicitly unresolved) attestation claim."""

    status: str = UNATTESTED
    basis_kind: str = BASIS_NONE
    scheme_key: str = ""
    scheme_name: str = ""
    clause: str = ""
    clause_title: str = ""
    clause_label: str = ""
    clause_verified: bool = False
    owner: str = ""
    evidence_document: str = ""
    evidence_location: str = ""
    access_condition: str = ""
    retrieval: str = ""
    reason: str = ""
    raw_claim: str = ""
    source: str = ""

    @property
    def is_gap(self) -> bool:
        return self.status == UNATTESTED

    def citation_text(self) -> str:
        """Render the citation, never asserting more than was verified."""
        if self.status == UNATTESTED:
            return ""
        if self.status == GROUNDED:
            label = self.clause_label or "clause"
            return f"{self.scheme_name} {label} {self.clause} ({self.clause_title})"
        # SCHEME_ONLY: the scheme is real, the clause number is the model's and
        # could not be checked. Say so rather than dressing it as verified.
        if self.clause:
            label = self.clause_label or "clause"
            return (
                f"{self.scheme_name} (cited {label} {self.clause} could not be "
                f"verified against Azure's published metadata)"
            )
        return self.scheme_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "basis_kind": self.basis_kind,
            "scheme": self.scheme_name,
            "scheme_key": self.scheme_key,
            "clause": self.clause,
            "clause_title": self.clause_title,
            "clause_verified": self.clause_verified,
            "owner": self.owner,
            "citation": self.citation_text(),
            "evidence_document": self.evidence_document,
            "evidence_location": self.evidence_location,
            "access_condition": self.access_condition,
            "retrieval": self.retrieval,
            "reason": self.reason,
            "raw_claim": self.raw_claim,
            "source": self.source,
        }


class AttestationCatalogService:
    """Loads the attestation snapshot and validates citations against it."""

    def __init__(self, data_path: Optional[str] = None) -> None:
        raw = Path(data_path or DEFAULT_CATALOG_PATH)
        if not raw.is_absolute():
            raw = Path(__file__).resolve().parent.parent / raw
        self.data_path = str(raw)

        self._schemes: Dict[str, Dict[str, Any]] = {}
        self._clauses: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._alias: Dict[str, str] = {}
        self._generated_at = ""
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        path = Path(self.data_path)
        if not path.exists():
            logger.warning(
                "Attestation catalog not found at %s; every Category D citation "
                "will be reported as an unattested gap.", self.data_path,
            )
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to load attestation catalog: %s", exc)
            return

        self._generated_at = data.get("generated_at", "")
        for scheme in data.get("schemes") or []:
            key = scheme.get("key")
            if not key:
                continue
            self._schemes[key] = scheme
            for clause in scheme.get("clauses") or []:
                cid = (clause.get("clause") or "").strip()
                if cid:
                    self._clauses[(key, cid.lower())] = clause
            self._register_aliases(key, scheme.get("name") or "", scheme.get("aliases") or [])

        logger.info(
            "Loaded %d attestation clauses across %d schemes from %s",
            len(self._clauses), len(self._schemes), self.data_path,
        )

    def _register_aliases(self, key: str, name: str, extra: List[str]) -> None:
        """Register the spellings a model or a regulator actually writes.

        Curated aliases live in the catalog snapshot rather than here, because
        they are data about how each scheme is referred to in the wild. The
        documentation basis is the case that proves the need: the analyst
        workbook records it as "Not a certification item - satisfied by
        published product documentation", which shares no words with the scheme
        name "Published Microsoft documentation" and so would otherwise be
        reported as an unattested gap.
        """
        for alias in {_norm(name), _norm(key.replace("_", " ")), *(_norm(a) for a in extra)}:
            if alias:
                self._alias.setdefault(alias, key)
        # ``ISO/IEC 27001:2022`` is written a dozen ways; index the bare
        # standard number plus year so "ISO 27001 2022" and "ISO/IEC 27001:2022"
        # both land. Year-less forms are handled by the longest-match scan.
        digits = re.findall(r"\d{4,5}", name)
        if digits:
            self._alias.setdefault(_norm(" ".join(digits)), key)

    @property
    def available(self) -> bool:
        self.load()
        return bool(self._clauses) or bool(self._schemes)

    @property
    def generated_at(self) -> str:
        self.load()
        return self._generated_at

    def schemes(self) -> List[Dict[str, Any]]:
        self.load()
        return [
            {k: v for k, v in s.items() if k != "clauses"}
            for s in self._schemes.values()
        ]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def exists(self, scheme_key: str, clause: str) -> bool:
        """Does this exact clause exist? The ``catalog.exists()`` analogue for GUIDs."""
        self.load()
        return (scheme_key, (clause or "").strip().lower()) in self._clauses

    def find_scheme(self, text: str) -> Optional[Dict[str, Any]]:
        """Longest-match a scheme name inside free text."""
        self.load()
        haystack = _norm(text)
        if not haystack:
            return None
        best_key, best_len = "", 0
        for alias, key in self._alias.items():
            if alias and alias in haystack and len(alias) > best_len:
                best_key, best_len = key, len(alias)
        return self._schemes.get(best_key) if best_key else None

    def _match_clause(
        self, scheme_key: str, clause: str
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """Exact match, else a unique hierarchical descendant.

        A regulator cites "ISO/IEC 27001 clause 9.2"; Azure publishes ``9.2.2``.
        Treating that as ungrounded would report a false gap, so a citation is
        accepted when it resolves to exactly one descendant. Ambiguity is *not*
        resolved by picking one -- ``9`` matching eight clauses stays unverified.
        """
        needle = (clause or "").strip().lower()
        if not needle:
            return None, "no clause was cited"
        exact = self._clauses.get((scheme_key, needle))
        if exact:
            return exact, ""
        children = [
            row
            for (key, cid), row in self._clauses.items()
            if key == scheme_key and cid.startswith(needle + ".")
        ]
        if len(children) == 1:
            return children[0], ""
        if len(children) > 1:
            return None, (
                f"clause {clause} covers {len(children)} published sub-clauses; "
                "cite a specific one"
            )
        return None, f"clause {clause} is not in Azure's published metadata for this scheme"

    def resolve(
        self,
        claim: str,
        scheme_key: str = "",
        clause: str = "",
    ) -> AttestationCitation:
        """Validate an attestation claim, returning one of the three outcomes."""
        self.load()
        raw = _LEAD_LABEL_RE.sub("", (claim or "").strip())

        if not self._schemes:
            return AttestationCitation(
                status=UNATTESTED,
                reason="the attestation catalog is unavailable, so no citation could be checked",
                raw_claim=raw,
            )

        scheme = self._schemes.get(scheme_key) if scheme_key else None
        if scheme is None:
            scheme = self.find_scheme(raw)
        if scheme is None:
            return AttestationCitation(
                status=UNATTESTED,
                reason=(
                    "no Microsoft attestation scheme was named, so there is nothing to cite"
                    if not raw
                    else "the named attestation scheme is not one Microsoft publishes for Azure"
                ),
                raw_claim=raw,
            )

        key = scheme["key"]
        if not clause:
            clause = self._extract_clause(raw, scheme)

        base = AttestationCitation(
            basis_kind=scheme.get("basis_kind", BASIS_NONE),
            scheme_key=key,
            scheme_name=scheme.get("name", ""),
            clause_label=scheme.get("clause_label", "clause"),
            evidence_document=scheme.get("evidence_document", ""),
            evidence_location=scheme.get("evidence_location", ""),
            access_condition=scheme.get("access_condition", ""),
            retrieval=scheme.get("retrieval", ""),
            raw_claim=raw,
            source=scheme.get("clause_source", "unavailable"),
        )

        # Published documentation is scheme-level by nature -- there is no
        # clause to check, and demanding one would reject the workbook's own
        # "not a certification item, satisfied by published product
        # documentation" basis.
        if scheme.get("basis_kind") == BASIS_DOCUMENTATION:
            base.status = SCHEME_ONLY
            base.reason = "satisfied by published Microsoft documentation rather than an audited control"
            return base

        row, why = self._match_clause(key, clause)
        if row is not None:
            base.status = GROUNDED
            base.clause = row["clause"]
            base.clause_title = row.get("title", "")
            base.clause_verified = True
            base.owner = row.get("owner", "")
            base.source = row.get("source", base.source)
            base.reason = ""
            return base

        base.status = SCHEME_ONLY
        base.clause = clause
        base.clause_verified = False
        base.reason = why
        return base

    def _extract_clause(self, text: str, scheme: Dict[str, Any]) -> str:
        """Pull the clause identifier out of free text, preferring one we hold."""
        candidates = [m.group(1) for m in _CLAUSE_RE.finditer(text or "")]
        key = scheme["key"]
        # Drop fragments of the scheme's own name ("27001", "2022", "4.0.1").
        name_numbers = set(re.findall(r"[\d.]+", scheme.get("name", "")))
        filtered = [c for c in candidates if c not in name_numbers]
        for cand in filtered:
            if (key, cand.lower()) in self._clauses:
                return cand
        return filtered[0] if filtered else ""


_service: Optional[AttestationCatalogService] = None


def get_attestation_catalog_service() -> AttestationCatalogService:
    global _service
    if _service is None:
        _service = AttestationCatalogService()
        _service.load()
    return _service
