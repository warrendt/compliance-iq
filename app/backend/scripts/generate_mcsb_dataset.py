"""
Generate the Microsoft Cloud Security Benchmark (MCSB) control dataset.

This produces the runtime dataset the backend loads at start-up (92 controls, 13
domains) plus a known-good built-in policy GUID index used for offline GUID
validation. Every field is sourced from an authoritative, verifiable location -
nothing is hand-authored or paraphrased:

  * Control structure + built-in policy GUIDs (all 92 controls):
    Azure/azure-policy -> built-in-policies/policySetDefinitions/Security Center/
    MCSBv2.json. Its ``policyDefinitionGroups`` are the controls (IDs such as
    ``Azure_Security_Benchmark_v3.0_DP-5``); its ``policyDefinitions`` each carry a
    built-in policy GUID and the ``groupNames`` (controls) they belong to.

  * Titles / descriptions / framework mappings (the 85 non-AI controls):
    MicrosoftDocs/SecurityBenchmarks -> Azure Security Benchmark/3.0/
    azure-security-benchmark-v3.0.xlsx (sheet "Azure Security Benchmark v3").

  * AI-1..AI-7 titles / descriptions: a committed ``ai_domain_metadata.json``
    overlay transcribed verbatim from MS Learn
    (mcsb-v2-artificial-intelligence-security). The ASB v3 spreadsheet predates the
    AI domain, so this overlay is the offline source for those seven controls.

  * ``--source arm`` (used by the scheduled refresh) instead refreshes every
    control's title/description/domain from ARM ``policyMetadata`` (properties
    ``title`` / ``description`` / ``category``), which covers all 92 controls
    including AI. Requires a delegated Azure Resource Manager access token.

Outputs (written to ``app/data/mcsb`` and committed so they ship in the image):

  * ``mcsb_v1_controls.json``          - ``{generated_at, source, count, controls}``
                                         where each control matches ``MCSBControl``.
  * ``azure_builtin_policy_index.json`` - ``{generated_at, count, guids}`` sorted
                                         unique built-in policy GUID set.

Usage::

    # Offline (default): initiative + ASB xlsx + committed AI overlay.
    python -m scripts.generate_mcsb_dataset

    # Refresh titles/descriptions/domains from ARM policyMetadata.
    ARM_ACCESS_TOKEN=$(az account get-access-token --query accessToken -o tsv) \
        python -m scripts.generate_mcsb_dataset --source arm
"""

import argparse
import json
import logging
import os
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# --- Canonical sources -------------------------------------------------------

INITIATIVE_URL = (
    "https://raw.githubusercontent.com/Azure/azure-policy/master/"
    "built-in-policies/policySetDefinitions/Security%20Center/MCSBv2.json"
)
ASB_XLSX_URL = (
    "https://raw.githubusercontent.com/MicrosoftDocs/SecurityBenchmarks/master/"
    "Azure%20Security%20Benchmark/3.0/azure-security-benchmark-v3.0.xlsx"
)
ASB_SHEET = "Azure Security Benchmark v3"

# ARM policyMetadata read model (REST 2024-10-01): properties.title / description /
# category. Verified against learn.microsoft.com policy-metadata get-resource.
ARM_METADATA_URL = (
    "https://management.azure.com/providers/Microsoft.PolicyInsights/"
    "policyMetadata/{name}?api-version=2024-10-01"
)

# Control ID embedded in a policyDefinitionGroup name, e.g.
# "Azure_Security_Benchmark_v3.0_DP-5" -> "DP-5".
CONTROL_ID_RE = re.compile(r"_([A-Z]{2}-\d+)$")

# Framework columns in the ASB spreadsheet -> related_frameworks keys.
FRAMEWORK_COLUMNS = {
    "CIS Controls v7.1 ID(s)": "CIS v7.1",
    "CIS Controls v8 ID(s)": "CIS v8",
    "NIST SP800-53 r4 ID(s)": "NIST SP800-53 r4",
    "PCI-DSS v3.2.1 ID(s)": "PCI-DSS v3.2.1",
}

# The AI domain postdates ASB v3, so its long name is not in the spreadsheet.
AI_DOMAIN_NAME = "AI Security"


# --- IO helpers --------------------------------------------------------------


def _is_url(src: str) -> bool:
    return src.startswith("http://") or src.startswith("https://")


def read_bytes(src: str) -> bytes:
    """Read raw bytes from an ``http(s)`` URL or a local filesystem path."""
    if _is_url(src):
        logger.info("Downloading %s", src)
        with urllib.request.urlopen(src, timeout=60) as resp:  # noqa: S310 (trusted hosts)
            return resp.read()
    logger.info("Reading %s", src)
    return Path(src).read_bytes()


def read_json(src: str) -> Any:
    return json.loads(read_bytes(src).decode("utf-8"))


def control_id_from_group(name: str) -> Optional[str]:
    match = CONTROL_ID_RE.search(name or "")
    return match.group(1) if match else None


def domain_prefix(control_id: str) -> str:
    return control_id.split("-", 1)[0]


def split_lines(cell: Any) -> List[str]:
    """Split a spreadsheet cell into stripped, non-empty lines."""
    if cell is None:
        return []
    return [part.strip() for part in str(cell).splitlines() if part.strip()]


# --- Source parsers ----------------------------------------------------------


def parse_initiative(initiative: Dict[str, Any]) -> Tuple[List[str], Dict[str, List[str]]]:
    """Return (ordered control IDs, GUIDs-per-control) from the MCSB initiative."""
    props = initiative["properties"]

    control_ids: List[str] = []
    for group in props["policyDefinitionGroups"]:
        cid = control_id_from_group(group.get("name", ""))
        if cid:
            control_ids.append(cid)

    guids: Dict[str, set] = defaultdict(set)
    for definition in props["policyDefinitions"]:
        guid = definition["policyDefinitionId"].split("/")[-1]
        for group_name in definition.get("groupNames", []):
            cid = control_id_from_group(group_name)
            if cid:
                guids[cid].add(guid)

    return control_ids, {cid: sorted(values) for cid, values in guids.items()}


def parse_asb_xlsx(data: bytes) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Return (per-control text/framework map, domain-prefix -> long name) from ASB."""
    import io

    import openpyxl

    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sheet = workbook[ASB_SHEET]
    rows = list(sheet.iter_rows(values_only=True))
    header = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    index = {name: pos for pos, name in enumerate(header)}

    def cell(row: Tuple[Any, ...], column: str) -> Any:
        pos = index.get(column)
        return row[pos] if pos is not None and pos < len(row) else None

    def text_cell(row: Tuple[Any, ...], column: str) -> str:
        value = cell(row, column)
        return str(value).strip() if value is not None else ""

    text: Dict[str, Dict[str, Any]] = {}
    domains: Dict[str, str] = {}
    for row in rows[1:]:
        control_id = cell(row, "ASB ID")
        if not control_id:
            continue
        control_id = str(control_id).strip()

        frameworks = {
            key: split_lines(cell(row, column))
            for column, key in FRAMEWORK_COLUMNS.items()
            if split_lines(cell(row, column))
        }
        # The Governance & Strategy (GS) controls carry "N/A" as their Security
        # Principle in the official spreadsheet; their substance lives in Azure
        # Guidance, so fall back to it rather than emit an "N/A" description.
        description = text_cell(row, "Security Principle")
        if not description or description.upper() == "N/A":
            description = text_cell(row, "Azure Guidance")
        text[control_id] = {
            "control_name": text_cell(row, "Recommendation"),
            "description": description,
            "defender_recommendations": split_lines(cell(row, "Azure Policy Mapping")),
            "related_frameworks": frameworks,
        }
        domain = cell(row, "Control Domain")
        if domain:
            domains.setdefault(domain_prefix(control_id), str(domain).strip())

    return text, domains


def parse_ai_overlay(overlay: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Normalise the committed AI overlay into the common text-map shape."""
    return {
        cid: {
            "control_name": entry.get("control_name", ""),
            "description": entry.get("description", ""),
            "defender_recommendations": entry.get("defender_recommendations", []),
            "related_frameworks": entry.get("related_frameworks", {}),
        }
        for cid, entry in overlay.items()
    }


def fetch_arm_metadata(control_ids: Iterable[str], token: str) -> Dict[str, Dict[str, str]]:
    """Fetch title/description/category per control from ARM ``policyMetadata``."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    result: Dict[str, Dict[str, str]] = {}
    for control_id in control_ids:
        name = f"Azure_Security_Benchmark_v3.0_{control_id}"
        url = ARM_METADATA_URL.format(name=name)
        request = urllib.request.Request(url, headers=headers)  # noqa: S310 (ARM host)
        try:
            with urllib.request.urlopen(request, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # network / auth / shape - refresh is best-effort
            logger.warning("ARM policyMetadata fetch failed for %s: %s", control_id, exc)
            continue
        props = body.get("properties", {})
        result[control_id] = {
            "control_name": (props.get("title") or "").strip(),
            "description": (props.get("description") or "").strip(),
            "domain": (props.get("category") or "").strip(),
        }
    return result


# --- Assembly ----------------------------------------------------------------


def build_controls(
    control_ids: List[str],
    guids_by_control: Dict[str, List[str]],
    text_by_control: Dict[str, Dict[str, Any]],
    domain_names: Dict[str, str],
    arm_by_control: Dict[str, Dict[str, str]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Merge sources into MCSBControl dicts. Returns (controls, controls_missing_text)."""
    controls: List[Dict[str, Any]] = []
    missing: List[str] = []

    for control_id in control_ids:
        prefix = domain_prefix(control_id)
        text = dict(text_by_control.get(control_id, {}))
        arm = arm_by_control.get(control_id, {})

        # ARM refresh (when present) is authoritative for title/description/domain.
        control_name = arm.get("control_name") or text.get("control_name", "")
        description = arm.get("description") or text.get("description", "")
        domain = arm.get("domain") or domain_names.get(prefix, prefix)

        if not control_name:
            missing.append(control_id)
            control_name = f"Microsoft cloud security benchmark {control_id}"

        controls.append({
            "control_id": control_id,
            "domain": domain,
            "control_name": control_name,
            "description": description,
            "azure_policy_ids": guids_by_control.get(control_id, []),
            "defender_recommendations": text.get("defender_recommendations", []),
            "related_frameworks": text.get("related_frameworks", {}),
        })

    return controls, missing


def write_outputs(controls: List[Dict[str, Any]], source: str, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    controls_file = output_dir / "mcsb_v1_controls.json"
    with open(controls_file, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_at": generated_at,
                "source": source,
                "count": len(controls),
                "controls": controls,
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )
    logger.info("Wrote %s controls to %s", len(controls), controls_file)

    guids = sorted({guid for control in controls for guid in control["azure_policy_ids"]})
    index_file = output_dir / "azure_builtin_policy_index.json"
    with open(index_file, "w", encoding="utf-8") as handle:
        json.dump(
            {"generated_at": generated_at, "count": len(guids), "guids": guids},
            handle,
            indent=2,
            ensure_ascii=False,
        )
    logger.info("Wrote %s built-in policy GUIDs to %s", len(guids), index_file)


# --- CLI ---------------------------------------------------------------------


def main() -> int:
    default_output = Path(__file__).resolve().parent.parent / "app" / "data" / "mcsb"

    parser = argparse.ArgumentParser(description="Generate the MCSB control dataset")
    parser.add_argument("--output-dir", default=str(default_output),
                        help="Directory for the generated JSON files")
    parser.add_argument("--initiative", default=INITIATIVE_URL,
                        help="Path or URL of the MCSBv2 initiative JSON")
    parser.add_argument("--asb-xlsx", default=ASB_XLSX_URL,
                        help="Path or URL of the Azure Security Benchmark v3 xlsx")
    parser.add_argument("--ai-overlay", default=None,
                        help="Path to the committed AI domain overlay JSON "
                             "(default: <output-dir>/ai_domain_metadata.json)")
    parser.add_argument("--source", choices=["offline", "arm"], default="offline",
                        help="offline: xlsx + AI overlay; arm: refresh text from "
                             "ARM policyMetadata (requires --access-token)")
    parser.add_argument("--access-token", default=os.environ.get("ARM_ACCESS_TOKEN"),
                        help="Delegated ARM access token (or env ARM_ACCESS_TOKEN)")
    parser.add_argument("--min-controls", type=int, default=90,
                        help="Fail if fewer than this many controls are produced")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    ai_overlay_path = Path(args.ai_overlay) if args.ai_overlay else output_dir / "ai_domain_metadata.json"

    control_ids, guids_by_control = parse_initiative(read_json(args.initiative))
    logger.info("Initiative: %s controls, %s with >=1 policy GUID",
                len(control_ids), sum(1 for cid in control_ids if guids_by_control.get(cid)))

    text_by_control, domain_names = parse_asb_xlsx(read_bytes(args.asb_xlsx))
    domain_names.setdefault("AI", AI_DOMAIN_NAME)

    if ai_overlay_path.exists():
        overlay = parse_ai_overlay(read_json(str(ai_overlay_path)))
        for cid, entry in overlay.items():
            text_by_control.setdefault(cid, entry)
        logger.info("Applied AI overlay for %s controls from %s", len(overlay), ai_overlay_path)
    else:
        logger.warning("AI overlay not found at %s - AI controls may lack text", ai_overlay_path)

    arm_by_control: Dict[str, Dict[str, str]] = {}
    if args.source == "arm":
        if not args.access_token:
            logger.error("--source arm requires --access-token or ARM_ACCESS_TOKEN")
            return 2
        arm_by_control = fetch_arm_metadata(control_ids, args.access_token)
        logger.info("Refreshed %s controls from ARM policyMetadata", len(arm_by_control))

    controls, missing = build_controls(
        control_ids, guids_by_control, text_by_control, domain_names, arm_by_control,
    )

    if missing:
        logger.warning("%s controls have no authoritative title (placeholder used): %s",
                       len(missing), ", ".join(missing))
    if len(controls) < args.min_controls:
        logger.error("Only %s controls produced (expected >=%s) - aborting",
                     len(controls), args.min_controls)
        return 1

    write_outputs(controls, args.source, output_dir)
    logger.info("Done: %s controls across %s domains",
                len(controls), len({c["domain"] for c in controls}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
