"""
Control comparison (diff) service.

Compares an **internal** control set (extracted from an uploaded PDF) against a
chosen **external** framework catalogue and buckets every control as:

* ``matched``         — internal control fully covered by an external control
* ``partial-overlap`` — internal control partially covered
* ``gap``             — internal control with no external equivalent
* ``extra``           — external control with no internal equivalent

The LLM only emits ``matched`` / ``partial-overlap`` / ``gap`` (one row per
internal control). The ``extra`` bucket is computed deterministically afterwards
from the external controls that no match referenced.

The model is read from ``PipelineConfig.from_env()`` (``AZURE_OPENAI_DEPLOYMENT_NAME``)
— never hardcoded — so the live deployment's model (e.g. gpt-5.2) is honoured.
"""

import asyncio
import csv
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Catalogue files follow ``<KEY>_Azure_Mappings.csv``. Only these are exposed.
_CATALOGUE_SUFFIX = "_Azure_Mappings.csv"
_REQUIRED_COLUMNS = {"Domain", "Control_Name", "Requirement_Summary", "Control_Type"}

# Optional prettier display names; falls back to the key with spaces.
_DISPLAY_NAMES = {
    "SAMA_Catalog": "SAMA (Saudi Central Bank)",
    "ADHICS_Framework": "ADHICS (Abu Dhabi Healthcare)",
    "Saudi_Arabia_Government": "Saudi Arabia Government",
    "Oman_Government": "Oman Government",
    "South_African_Government": "South African Government",
}


# ── External catalogue model ──────────────────────────────────────────────────

class ExternalControl(BaseModel):
    """A single control loaded from an external-framework catalogue CSV."""
    control_id: str
    control_name: str
    description: str = ""
    domain: str = ""
    control_type: str = ""


# ── LLM structured-output models ──────────────────────────────────────────────

class ComparisonControlMatch(BaseModel):
    """One internal control's alignment to the external framework."""
    internal_control_id: str = Field(..., description="ID of the internal control being classified")
    internal_control_title: str = Field("", description="Title of the internal control")
    external_control_id: Optional[str] = Field(
        None, description="ID of the best-matching external control, if any"
    )
    external_control_name: Optional[str] = Field(
        None, description="Name of the best-matching external control, if any"
    )
    bucket: Literal["matched", "partial-overlap", "gap"] = Field(
        ..., description="matched = fully covered; partial-overlap = partially; gap = no external equivalent"
    )
    similarity: float = Field(0.0, ge=0.0, le=1.0, description="Semantic similarity 0.0-1.0")
    rationale: str = Field("", description="Short reason for the classification")


class ComparisonResult(BaseModel):
    """Structured LLM output for one batch of internal controls."""
    matches: List[ComparisonControlMatch] = Field(default_factory=list)
    summary: str = Field("", description="Brief summary of coverage for this batch")


COMPARISON_SYSTEM_PROMPT = """You are an expert compliance analyst performing a gap analysis.

You are given:
1. A batch of INTERNAL controls (an organisation's own policy/control set).
2. The full list of EXTERNAL controls from a chosen regulatory framework.

For EACH internal control, decide how well the EXTERNAL framework covers it and assign exactly one bucket:

- "matched": an external control fully covers the intent of the internal control.
- "partial-overlap": an external control covers the internal control only partially.
- "gap": NO external control covers the internal control (the internal requirement is unique).

Rules:
1. Return exactly ONE row per internal control given in this batch — never omit, duplicate, or invent internal controls.
2. For "matched" and "partial-overlap", set external_control_id and external_control_name to the BEST single matching external control, using the EXACT external control id as provided.
3. For "gap", leave external_control_id and external_control_name null.
4. similarity is your semantic confidence (1.0 = identical intent, 0.0 = unrelated).
5. Compare on intent and requirement substance, not just wording. Domains differ in naming across frameworks.
6. Do NOT report external controls that have no internal equivalent — that is computed separately."""


# ── Catalogue loading ─────────────────────────────────────────────────────────

def _catalogues_dir() -> Path:
    """Resolve the bundled catalogues directory (env override > settings)."""
    env = os.getenv("CATALOGUES_DIR")
    raw = env or settings.catalogues_dir
    p = Path(raw)
    if p.is_absolute():
        return p
    # Resolve relative to the backend ``app/`` package dir (…/app/services/ -> app/).
    return Path(__file__).resolve().parent.parent / raw


def _display_name(key: str) -> str:
    return _DISPLAY_NAMES.get(key, key.replace("_", " "))


def _read_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return fieldnames, rows


def list_external_frameworks() -> List[Dict[str, Any]]:
    """Return all valid bundled external frameworks (dynamic, dir-scanned)."""
    out: List[Dict[str, Any]] = []
    cat_dir = _catalogues_dir()
    if not cat_dir.is_dir():
        logger.warning("catalogues_dir_missing", extra={"dir": str(cat_dir)})
        return out

    for path in sorted(cat_dir.glob(f"*{_CATALOGUE_SUFFIX}")):
        try:
            fieldnames, rows = _read_rows(path)
            if not _REQUIRED_COLUMNS.issubset(set(fieldnames)):
                logger.warning("catalogue_missing_columns", extra={"file": path.name})
                continue
            valid = [r for r in rows if (fieldnames and r.get(fieldnames[0]) and r.get("Control_Name"))]
            if not valid:
                continue
            key = path.name[: -len(_CATALOGUE_SUFFIX)]
            out.append({
                "key": key,
                "display_name": _display_name(key),
                "control_count": len(valid),
            })
        except Exception as exc:  # noqa: BLE001 — a bad file must not break listing
            logger.warning("catalogue_read_failed", extra={"file": path.name, "error": str(exc)})
    return out


def load_external_controls(framework_key: str) -> Tuple[str, List[ExternalControl]]:
    """Load external controls for a framework. Raises ValueError if unavailable."""
    # Guard against path traversal — only a bare key is allowed.
    if not framework_key or "/" in framework_key or "\\" in framework_key or ".." in framework_key:
        raise ValueError(f"Invalid framework key: {framework_key!r}")

    path = _catalogues_dir() / f"{framework_key}{_CATALOGUE_SUFFIX}"
    if not path.is_file():
        raise ValueError(
            f"External framework '{framework_key}' is not available in this deployment "
            f"(no bundled catalogue). PDF-fallback frameworks are not yet supported."
        )

    fieldnames, rows = _read_rows(path)
    if not _REQUIRED_COLUMNS.issubset(set(fieldnames)):
        raise ValueError(f"Catalogue '{path.name}' is missing required columns")

    id_col = fieldnames[0]
    controls: List[ExternalControl] = []
    for row in rows:
        cid = (row.get(id_col) or "").strip()
        name = (row.get("Control_Name") or "").strip()
        if not cid or not name:
            continue
        controls.append(ExternalControl(
            control_id=cid,
            control_name=name,
            description=(row.get("Requirement_Summary") or "").strip(),
            domain=(row.get("Domain") or "").strip(),
            control_type=(row.get("Control_Type") or "").strip(),
        ))
    if not controls:
        raise ValueError(f"Catalogue '{path.name}' contains no usable controls")

    return _display_name(framework_key), controls


# ── Comparison engine ─────────────────────────────────────────────────────────

_BUCKET_RANK = {"matched": 3, "partial-overlap": 2, "gap": 1}


def _norm(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _compare_batch(config, internal_batch: List[Dict[str, str]],
                   external_controls: List[ExternalControl]) -> ComparisonResult:
    """Blocking single-batch LLM comparison (run via asyncio.to_thread)."""
    from app.pipeline.control_extractor import _parse_with_retry, get_openai_client

    client = get_openai_client(config)

    external_block = "\n".join(
        f"- [{c.control_id}] {c.control_name} ({c.domain}): {c.description}"
        for c in external_controls
    )
    internal_block = "\n".join(
        f"- [{c['id']}] {c['title']} ({c.get('domain', '')}): {c.get('description', '')}"
        for c in internal_batch
    )
    user_prompt = (
        f"## EXTERNAL framework controls\n{external_block}\n\n"
        f"## INTERNAL controls to classify ({len(internal_batch)})\n{internal_block}\n\n"
        f"Classify every internal control above. Return exactly one row per internal control."
    )

    completion = _parse_with_retry(
        client,
        config,
        messages=[
            {"role": "system", "content": COMPARISON_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format=ComparisonResult,
    )
    parsed = completion.choices[0].message.parsed
    return parsed or ComparisonResult(matches=[], summary="")


async def compare_controls(
    internal_controls: List[Dict[str, str]],
    external_controls: List[ExternalControl],
    config,
    batch_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the full bucketed comparison. Returns matches + counts + summary.

    ``internal_controls`` items: ``{"id", "title", "description", "domain"}``.
    """
    size = batch_size or max(1, getattr(config, "batch_size", 5))

    # Canonical external lookup by normalised id.
    ext_by_norm: Dict[str, ExternalControl] = {_norm(c.control_id): c for c in external_controls}

    # internal canonical id -> best match record
    best: Dict[str, Dict[str, Any]] = {}
    summaries: List[str] = []

    for start in range(0, len(internal_controls), size):
        batch = internal_controls[start:start + size]
        batch_ids = {_norm(c["id"]): c for c in batch}

        try:
            result = await asyncio.to_thread(_compare_batch, config, batch, external_controls)
        except Exception as exc:  # noqa: BLE001 — surface as gaps, keep job alive
            logger.warning("comparison_batch_failed", extra={"start": start, "error": str(exc)})
            result = ComparisonResult(matches=[], summary="")

        if result.summary:
            summaries.append(result.summary)

        for m in result.matches:
            nid = _norm(m.internal_control_id)
            src = batch_ids.get(nid)
            if src is None:
                continue  # invented / out-of-batch internal id — drop

            bucket = m.bucket if m.bucket in _BUCKET_RANK else "gap"
            ext_id: Optional[str] = None
            ext_name: Optional[str] = None

            if bucket in ("matched", "partial-overlap"):
                ext = ext_by_norm.get(_norm(m.external_control_id))
                if ext is None:
                    # LLM referenced an unknown external control — downgrade to gap.
                    bucket = "gap"
                else:
                    ext_id = ext.control_id
                    ext_name = ext.control_name

            candidate = {
                "internal_control_id": src["id"],
                "internal_control_title": src.get("title", "") or m.internal_control_title,
                "external_control_id": ext_id,
                "external_control_name": ext_name,
                "bucket": bucket,
                "similarity": float(m.similarity or 0.0) if bucket != "gap" else 0.0,
                "rationale": m.rationale or "",
            }

            prev = best.get(nid)
            if prev is None or (
                _BUCKET_RANK[bucket], candidate["similarity"]
            ) > (_BUCKET_RANK[prev["bucket"]], prev["similarity"]):
                best[nid] = candidate

        # Fill any internal controls the LLM omitted in this batch as gaps.
        for nid, src in batch_ids.items():
            if nid not in best:
                best[nid] = {
                    "internal_control_id": src["id"],
                    "internal_control_title": src.get("title", ""),
                    "external_control_id": None,
                    "external_control_name": None,
                    "bucket": "gap",
                    "similarity": 0.0,
                    "rationale": "No external equivalent identified.",
                }

    matches: List[Dict[str, Any]] = list(best.values())

    # ── extra: external controls no match referenced ──────────────────────────
    used_external = {
        _norm(m["external_control_id"])
        for m in matches
        if m["bucket"] in ("matched", "partial-overlap") and m["external_control_id"]
    }
    for ext in external_controls:
        if _norm(ext.control_id) not in used_external:
            matches.append({
                "internal_control_id": None,
                "internal_control_title": None,
                "external_control_id": ext.control_id,
                "external_control_name": ext.control_name,
                "bucket": "extra",
                "similarity": 0.0,
                "rationale": "External control with no internal equivalent.",
            })

    counts = {"matched": 0, "partial-overlap": 0, "gap": 0, "extra": 0}
    for m in matches:
        counts[m["bucket"]] = counts.get(m["bucket"], 0) + 1

    return {
        "matches": matches,
        "counts": counts,
        "summary": " ".join(summaries).strip(),
    }


# ── Full-union initiative construction (Phase 3) ──────────────────────────────

_ALLOWED_CONTROL_TYPES = {
    "Technical", "Policy", "Contractual", "Management", "Operational", "Governance",
}


def _coerce_control_type(value: Optional[str]) -> str:
    """Map free-text control types onto the ExtractedControl Literal set."""
    raw = (value or "").strip()
    for allowed in _ALLOWED_CONTROL_TYPES:
        if raw.lower() == allowed.lower():
            return allowed
    return "Technical"


def build_union_extraction(comparison_doc: Dict[str, Any]):
    """Build a ``ControlExtractionResult`` for the *effective union* of a completed
    comparison: **all** internal controls (matched + partial-overlap + gap) plus the
    **external** controls that have no internal equivalent (the ``extra`` bucket).

    Requires the comparison ``result`` to carry the full ``internal_controls`` dicts
    (persisted by the comparison job). Raises ``ValueError`` if they are absent
    (e.g. a comparison created before this field existed → caller should re-run).
    """
    from app.pipeline.models import ControlExtractionResult, ExtractedControl

    result = (comparison_doc or {}).get("result") or {}
    internal_controls = result.get("internal_controls")
    if not internal_controls:
        raise ValueError(
            "This comparison predates union-build support. Please re-run the comparison."
        )

    framework_key = comparison_doc.get("externalFramework") or ""
    internal_fw = result.get("internal_framework") or "Internal Controls"
    external_fw = result.get("external_framework") or framework_key or "External Framework"

    controls: List[ExtractedControl] = []
    seen_ids: set[str] = set()

    def _add(cid: str, title: str, desc: str, domain: str, ctype: str) -> None:
        cid = (cid or "").strip()
        if not cid:
            return
        key = _norm(cid)
        if key in seen_ids:
            return
        seen_ids.add(key)
        title = (title or "").strip() or cid
        controls.append(
            ExtractedControl(
                control_id=cid,
                control_title=title,
                control_description=(desc or "").strip() or title,
                domain=(domain or "").strip() or "General",
                control_type=_coerce_control_type(ctype),
                sub_controls=[],
            )
        )

    # 1. All internal controls (the org's own control set).
    for c in internal_controls:
        _add(
            c.get("id", ""),
            c.get("title", ""),
            c.get("description", ""),
            c.get("domain", ""),
            c.get("control_type", ""),
        )

    # 2. External controls with no internal equivalent (the ``extra`` bucket).
    extra_ids = {
        _norm(m.get("external_control_id"))
        for m in result.get("matches", [])
        if m.get("bucket") == "extra" and m.get("external_control_id")
    }
    if extra_ids and framework_key:
        try:
            _, external_controls = load_external_controls(framework_key)
        except ValueError:
            external_controls = []
        for ext in external_controls:
            if _norm(ext.control_id) in extra_ids:
                _add(
                    ext.control_id,
                    ext.control_name,
                    ext.description,
                    ext.domain,
                    ext.control_type,
                )

    counts = result.get("counts", {}) or {}
    summary = (
        f"Effective union of {internal_fw} and {external_fw}: "
        f"{len(controls)} controls "
        f"({counts.get('matched', 0)} matched, {counts.get('partial-overlap', 0)} partial, "
        f"{counts.get('gap', 0)} gaps, {counts.get('extra', 0)} external-only)."
    )

    return ControlExtractionResult(
        framework_name=f"Effective Union — {internal_fw} + {external_fw}",
        framework_version=None,
        issuing_authority=None,
        country_or_region=None,
        controls=controls,
        summary=summary,
    )
