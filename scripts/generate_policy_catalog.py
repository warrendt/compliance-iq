#!/usr/bin/env python3
"""Generate the Azure built-in Policy definition catalog snapshot.

The snapshot is the retrieval corpus used by ``PolicyCatalogService`` to map
external framework controls to *real* Azure Policy definition GUIDs (instead of
being limited to the small MCSB control set).

Two data sources are supported:

* ``--source az`` (default): shell out to the Azure CLI. Requires an
  authenticated ``az`` session (``az login`` / OIDC in CI). Used by the
  scheduled refresh workflow and for local regeneration.
* ``--raw <file>``: transform a previously captured ``az policy definition
  list`` JSON dump. Handy for offline regeneration and unit tests.

Deprecated definitions (``[Deprecated]`` display names / ``*-deprecated``
versions) are dropped: they must not be recommended for new governance.

Usage::

    python scripts/generate_policy_catalog.py                 # from live az
    python scripts/generate_policy_catalog.py --raw dump.json # from a dump
    python scripts/generate_policy_catalog.py --subscription <sub-id>
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

# ARM api-version kept in sync with app/backend/app/services/policy_deploy_service.py
API_VERSION = "2023-04-01"

# Default output location: shipped inside the backend package so it is copied
# into the container image and resolved relative to the package at runtime.
DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent
    / "app" / "backend" / "app" / "data" / "policy_catalog"
    / "azure_policy_catalog.json"
)

# Server-side projection keeps the CLI payload small and stable.
_AZ_QUERY = (
    "[?policyType=='BuiltIn'].{name:name, display_name:displayName, "
    "description:description, category:metadata.category, mode:mode, "
    "version:metadata.version}"
)


def _is_deprecated(item: Dict[str, Any]) -> bool:
    display = (item.get("display_name") or item.get("displayName") or "")
    version = (item.get("version") or "")
    return display.startswith("[Deprecated]") or "deprecated" in version.lower()


def normalize(raw: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Project raw definitions to the lean, deduplicated catalog schema.

    Pure function: no I/O, so it is unit-testable. Drops deprecated entries and
    anything without a name (GUID) or display name.
    """
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for item in raw:
        name = (item.get("name") or "").strip()
        display = (item.get("display_name") or item.get("displayName") or "").strip()
        if not name or not display:
            continue
        if _is_deprecated({"display_name": display, "version": item.get("version")}):
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append(
            {
                "name": name,
                "display_name": display,
                "description": (item.get("description") or "").strip(),
                "category": (item.get("category") or "Uncategorized").strip(),
                "mode": (item.get("mode") or "All").strip(),
            }
        )
    out.sort(key=lambda d: d["name"])
    return out


def _fetch_via_az(subscription: Optional[str]) -> List[Dict[str, Any]]:
    cmd = ["az", "policy", "definition", "list", "--query", _AZ_QUERY, "-o", "json"]
    if subscription:
        cmd += ["--subscription", subscription]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"az failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
    return json.loads(proc.stdout or "[]")


def build_catalog(raw: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
    definitions = normalize(raw)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "api_version": API_VERSION,
        "count": len(definitions),
        "definitions": definitions,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw", type=Path, help="Transform a captured az JSON dump instead of calling az.")
    parser.add_argument("--subscription", help="Subscription to query (defaults to az context).")
    args = parser.parse_args(argv)

    if args.raw:
        raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
        source = f"file:{args.raw.name}"
    else:
        raw = _fetch_via_az(args.subscription)
        source = "az"

    catalog = build_catalog(raw, source)
    if catalog["count"] == 0:
        print("Refusing to write an empty catalog.", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote {catalog['count']} policy definitions to {args.output} (source={source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
