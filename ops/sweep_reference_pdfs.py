"""Run real regulation PDFs through extract -> map and check the invariants.

Why this exists as a container job rather than a local script: Azure OpenAI and
Cosmos both have public network access disabled, so the mapping engine can only
execute inside the VNet. ``az containerapp exec`` is rate limited (429 with a
600s retry-after after a handful of calls) and caps the command length, so it
cannot carry a 14-PDF sweep either. This runs where the dependencies are.

What it checks is the *rule*, never a count. The gold workbook is one worked
example of the method; every assertion here has to hold for a 30-control
circular and a 400-control standard alike, in English or Arabic.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

# The menu that policy_mapper.py used to be limited to. Kept only to prove the
# engine now reaches past it - if every emitted identifier still fell inside
# these 34, the catalog rewiring would have silently regressed.
OLD_MENU = {
    "013e242c-8828-4970-87b3-ab247555486d",
    "055f3b15-58a8-4d91-a4f6-8437a6c8f7e8",
    "0725b4dd-7e76-479c-a735-68e7ee23d5ca",
    "0961003e-5a0a-4549-abde-af6a37f2724d",
    "0a075868-4c26-42ef-914c-5bc007359560",
    "0e60b895-3786-45da-8377-9c6b4b6ac5f9",
    "1a4e592a-6a6e-44a5-9814-e36264ca96e7",
    "1b7aa243-30e4-4c9e-bca8-d0d3022b7829",
    "1f314764-cb73-4fc9-b863-8eca98ac36e9",
    "22bee202-a82f-4305-9a2a-6d7f44d4dedb",
    "2913021d-f2fd-4f3d-b958-22354e2bdbcb",
    "2c89a2e5-7285-40fe-afe0-ae8654b92fb2",
    "34c877ad-507e-4c82-993e-3452a6e0ad3c",
    "361c2074-3595-4e5d-8cab-4f21dffc835c",
    "404c3081-a854-4457-ae30-26a93ef643f9",
    "41425d9f-d1a5-499a-9932-f8ed8453932c",
    "47a6b606-51aa-4496-8bb7-64b11cf66adc",
    "4d24b6d4-5e53-4a4f-a7f4-618fa573ee4b",
    "51522a96-0869-4a82-8a4b-8eddf3feb677",
    "5752e6d6-1206-46d8-8ab1-ecc2f71a8112",
    "617c02be-7f02-4efd-8836-3180d47b6c68",
    "6fac406b-40ca-413b-bf8e-0bf964659c25",
    "7796937f-307b-4598-941c-67d3a05ebfe7",
    "7c1b1214-f927-48bf-8882-84f0af6588b1",
    "86b3d65f-7626-441e-b690-81a8b71cff60",
    "89099bee-89e0-4b26-a5f4-165451757743",
    "8c122334-9d20-4eb8-89ea-ac9a705b74ae",
    "951af2fa-529b-416e-ab6e-066fd85ac459",
    "9daedab3-fb2d-461e-b861-71790eead4f6",
    "a451c1ef-c6ca-483d-87ed-f49761e3ffb5",
    "a6fb4358-5bf4-4ad7-ba82-2cd2f41ce5e9",
    "b0f33259-77d7-4c9e-aac6-3aabcfae693c",
    "cb510bfd-1cba-4d9f-a230-cb0976f4bb71",
    "e71308d3-144b-4262-b144-efdc3cc90517",
}

CAT_A, CAT_B, CAT_C, CAT_D = (
    "A_AzurePolicy",
    "B_AzureConfig",
    "C_Process",
    "D_MicrosoftAttestation",
)
GENERIC_D = "microsoft-operated"


def _violation(out: List[dict], rule: str, control: str, detail: str) -> None:
    out.append({"rule": rule, "control": control, "detail": detail})


def check_invariants(mappings: List[Any], catalog) -> Dict[str, Any]:
    """Assert the plan's acceptance rules. Returns violations, never raises."""
    v: List[dict] = []
    emitted: set = set()

    for m in mappings:
        cid = getattr(m, "external_control_id", "?")
        cat = getattr(m, "coverage_category", None)
        ids = list(getattr(m, "azure_policy_ids", []) or [])
        emitted.update(ids)

        # C and D never carry policy, and must say something control-specific.
        if cat in (CAT_C, CAT_D) and ids:
            _violation(v, "c_d_emit_no_policy", cid, f"{cat} carries {ids}")
        if cat in (CAT_C, CAT_D):
            reason = (getattr(m, "coverage_reason", None) or "").strip()
            if len(reason) < 20:
                _violation(v, "c_d_substantive_reason", cid, f"reason={reason!r}")

        # Every identifier that survives must be one the catalog knows.
        for pid in ids:
            if not catalog.identifier_exists(pid):
                _violation(v, "emitted_guid_exists", cid, pid)

        # Effects line up one-to-one with the identifiers on the row.
        effects = list(getattr(m, "policy_effects", []) or [])
        if ids and effects and len(ids) != len(effects):
            _violation(
                v, "effects_align", cid, f"{len(ids)} ids vs {len(effects)} effects"
            )

        # A D control must reach one of four honest states, never a generic line.
        if cat == CAT_D:
            att = getattr(m, "attestation", None) or {}
            gap = bool(getattr(m, "attestation_gap", False))
            basis = att.get("basis_kind") if isinstance(att, dict) else None
            if not gap and not basis:
                _violation(v, "d_has_basis_or_gap", cid, f"attestation={att!r}")
            if basis and not gap:
                if not att.get("evidence_location"):
                    _violation(v, "d_grounded_has_location", cid, str(att)[:120])
            reason = (getattr(m, "coverage_reason", None) or "").lower()
            if GENERIC_D in reason and not (basis or gap):
                _violation(v, "d_not_generic_only", cid, reason[:120])

        # A B control that retrieved policy keeps it.
        if cat == CAT_B and getattr(m, "azure_enforceable", False) and not ids:
            if not getattr(m, "coverage_gap", False):
                _violation(v, "b_not_stripped_or_gap_declared", cid, "B, no ids, no gap")

        # In scope but nothing retrieved has to be stated, not relabelled.
        if cat in (CAT_A, CAT_B) and not ids and not getattr(m, "coverage_gap", False):
            _violation(v, "no_silent_gap", cid, f"{cat} with no ids and coverage_gap=False")

        # Nothing is discarded quietly.
        for d in getattr(m, "dropped_policy_ids", []) or []:
            if not isinstance(d, dict) or not d.get("reason"):
                _violation(v, "drops_are_reported", cid, repr(d)[:120])

        # Provenance: an answer without a source is not defensible.
        if not getattr(m, "verified_at", None) or not getattr(m, "catalog_snapshot_date", None):
            _violation(v, "provenance_present", cid, "missing verified_at/snapshot")

    cats = {}
    resp = {}
    pairs = set()
    engine_failures = 0
    failure_reasons: Dict[str, int] = {}
    for m in mappings:
        c = getattr(m, "coverage_category", None)
        r = getattr(m, "responsibility", None)
        cats[c] = cats.get(c, 0) + 1
        resp[r] = resp.get(r, 0) + 1
        pairs.add((c, r))
        if getattr(m, "mcsb_control_id", None) == "N/A":
            engine_failures += 1
            # Counting failures says something is wrong; naming them says what.
            # The reason is on the mapping because the fallback now carries it.
            reason = str(getattr(m, "coverage_reason", "") or "")[-160:]
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

    # The defect this check exists for: settings.ai_max_tokens did not exist, so
    # every mapping call raised AttributeError, was swallowed by a broad except,
    # and came back as a fallback. The result looked like a framework of process
    # controls rather than a broken engine. A failure rate is a finding.
    if mappings and engine_failures == len(mappings):
        _violation(v, "engine_not_failing_wholesale", "*", f"all {len(mappings)} mappings are fallbacks")
    elif engine_failures:
        _violation(
            v, "engine_failures_reported", "*", f"{engine_failures}/{len(mappings)} fell back"
        )

    beyond = sorted(emitted - OLD_MENU)
    if emitted and not beyond:
        _violation(v, "whole_catalog_reach", "*", "every id fell inside the old 34-GUID menu")

    return {
        "violations": v,
        "engine_failures": engine_failures,
        "failure_reasons": failure_reasons,
        "distribution": {"category": cats, "responsibility": resp},
        "distinct_policy_ids": len(emitted),
        "ids_beyond_old_menu": len(beyond),
        # Observation, not a target: does the data show the two axes are independent?
        "category_responsibility_pairs": sorted(
            f"{c}/{r}" for c, r in pairs if c and r
        ),
    }


def _violation_counts(res: Dict[str, Any]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for v in res.get("violations") or []:
        rule = str(v.get("rule", "?"))
        counts[rule] = counts.get(rule, 0) + 1
    return counts


def _summary(res: Dict[str, Any]) -> Dict[str, Any]:
    """A one-line verdict that survives the log agent's line splitting."""
    if res.get("error"):
        return {"pdf": res.get("pdf"), "error": res["error"][:200]}
    return {
        "pdf": res.get("pdf"),
        "controls": res.get("controls_mapped"),
        "engine_failures": res.get("engine_failures"),
        "cats": res.get("distribution", {}).get("category"),
        "ids": res.get("distinct_policy_ids"),
        "beyond": res.get("ids_beyond_old_menu"),
        "violations": res.get("violation_count"),
        "rules": sorted(_violation_counts(res)),
        "seconds": res.get("total_seconds"),
    }


def run_one(pdf_path: str, max_controls: int) -> Dict[str, Any]:
    from app.pipeline.config import PipelineConfig
    from app.pipeline.pdf_extractor import extract_text_from_pdf
    from app.pipeline.control_extractor import extract_controls_from_text
    from app.models.control import ExternalControl
    from app.services.ai_mapping_service import AIMappingService
    from app.services import get_policy_catalog_service

    started = time.time()
    result: Dict[str, Any] = {"pdf": os.path.basename(pdf_path)}

    text = extract_text_from_pdf(pdf_path)
    result["chars"] = len(text)
    # Arabic is the core market, not an edge case - record whether the text
    # survived extraction at all, since a silent empty read looks like a
    # framework with no controls.
    result["arabic_chars"] = sum(1 for ch in text if "\u0600" <= ch <= "\u06ff")

    t0 = time.time()
    extraction = extract_controls_from_text(text, PipelineConfig())
    controls = list(extraction.controls)
    result["extract_seconds"] = round(time.time() - t0, 1)
    result["controls_extracted"] = len(controls)
    result["framework"] = getattr(extraction, "framework_name", None)

    if max_controls and len(controls) > max_controls:
        controls = controls[:max_controls]
    result["controls_mapped"] = len(controls)

    externals = [
        ExternalControl(
            control_id=c.control_id,
            control_name=c.control_title,
            description=c.control_description,
            domain=c.domain,
            control_type=c.control_type,
            requirements="; ".join(c.sub_controls) if c.sub_controls else None,
        )
        for c in controls
    ]

    svc = AIMappingService()
    t0 = time.time()
    batch = asyncio.run(svc.map_controls_batch(externals, concurrency=4))
    result["map_seconds"] = round(time.time() - t0, 1)

    result.update(check_invariants(batch.mappings, get_policy_catalog_service()))
    result["violation_count"] = len(result["violations"])
    result["total_seconds"] = round(time.time() - started, 1)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.environ.get("SWEEP_DIR", "/sweep/reference_documents"))
    ap.add_argument(
        "--max-controls",
        type=int,
        default=int(os.environ.get("SWEEP_MAX_CONTROLS", "0")),
        help="0 = no cap",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=int(os.environ.get("SWEEP_LIMIT", "0")),
        help="0 = every PDF",
    )
    ap.add_argument(
        "--skip",
        type=int,
        default=int(os.environ.get("SWEEP_SKIP", "0")),
        help="skip the N smallest, so a sweep can be resumed",
    )
    args = ap.parse_args()

    pdfs = sorted(Path(args.dir).glob("**/*.pdf"), key=lambda p: p.stat().st_size)
    pdfs = pdfs[args.skip :]
    if args.limit:
        pdfs = pdfs[: args.limit]

    print(f"SWEEP_START {len(pdfs)} pdfs", flush=True)
    failures = 0
    for pdf in pdfs:
        try:
            res = run_one(str(pdf), args.max_controls)
        except Exception as exc:  # a crash is a finding, not a reason to stop
            res = {
                "pdf": pdf.name,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc()[-1200:],
            }
        if res.get("error") or res.get("violation_count"):
            failures += 1
        print("SWEEP_RESULT " + json.dumps(res, ensure_ascii=False), flush=True)
        # The full result runs to several KB and the log agent splits long lines,
        # which makes it unparseable downstream. Emit the verdict on one short
        # line as well, and the violations as one line per rule with a count.
        print("SWEEP_SUMMARY " + json.dumps(_summary(res), ensure_ascii=False), flush=True)
        for rule, count in sorted(_violation_counts(res).items()):
            print(f"SWEEP_VIOLATION {res.get('pdf', '?')[:40]} {rule} n={count}", flush=True)
        for reason, count in sorted((res.get("failure_reasons") or {}).items()):
            print(f"SWEEP_FAILREASON n={count} {reason[:220]}", flush=True)

    print(f"SWEEP_DONE pdfs={len(pdfs)} with_findings={failures}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
