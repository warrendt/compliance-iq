#!/usr/bin/env python3
"""
validate_guids.py — Validates Azure Policy GUIDs in framework policies.json files
against real Azure built-in policy data, and suggests correct alternatives.

Usage:
  python validate_guids.py                     # validate only
  python validate_guids.py --fix               # remove invalid entries from JSON files
  python validate_guids.py --refresh-cache     # force refresh the Azure policy cache
  python validate_guids.py --search "MFA read" # find a policy by display name keyword
"""

import json
import os
import sys
import subprocess
import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher

SCRIPT_DIR = Path(__file__).parent
CACHE_FILE = SCRIPT_DIR / ".policy-guid-cache.json"
CACHE_MAX_AGE_HOURS = 24

FRAMEWORKS = [
    "SAMA",
    "ADHICS",
    "Saudi Arabia Government",
    "South African Government",
    "Oman Government",
]


# ── Cache management ──────────────────────────────────────────────────────────

def load_cache(force_refresh=False):
    """Load the Azure built-in policy cache, refreshing if stale or missing."""
    if not force_refresh and CACHE_FILE.exists() and CACHE_FILE.stat().st_size > 0:
        mtime = datetime.fromtimestamp(CACHE_FILE.stat().st_mtime, tz=timezone.utc)
        age_hours = (datetime.now(tz=timezone.utc) - mtime).total_seconds() / 3600
        if age_hours < CACHE_MAX_AGE_HOURS:
            try:
                with open(CACHE_FILE) as f:
                    cached = json.load(f)
                print(f"  Using cached policy list ({len(cached)} policies, age: {int(age_hours * 60)} min)", flush=True)
                return cached
            except json.JSONDecodeError:
                print("  Cache file is corrupt — re-fetching...", flush=True)

    print("  Fetching all Azure built-in policy definitions (this takes ~30s)...", flush=True)
    result = subprocess.run(
        [
            "az", "policy", "definition", "list",
            "--query", "[?policyType=='BuiltIn'].{id:name, displayName:displayName, description:description, category:metadata.category}",
            "--output", "json",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"  ERROR: az CLI failed — {result.stderr.strip()}", file=sys.stderr)
        print("  Are you logged in? Run: az login", file=sys.stderr)
        sys.exit(1)

    policies = json.loads(result.stdout)
    with open(CACHE_FILE, "w") as f:
        json.dump(policies, f)
    print(f"  Cached {len(policies)} built-in policies → {CACHE_FILE.name}", flush=True)
    return policies


def build_lookup(policies):
    """Build an O(1) lookup dict from GUID → policy info."""
    return {p["id"]: p for p in policies}


# ── GUID extraction ───────────────────────────────────────────────────────────

def extract_guid(policy_entry):
    """Extract GUID from a policy entry (handles both camelCase and PascalCase keys)."""
    pid = (
        policy_entry.get("PolicyDefinitionId")
        or policy_entry.get("policyDefinitionId", "")
    )
    return pid.split("/")[-1]


def extract_ref_id(policy_entry):
    return (
        policy_entry.get("PolicyDefinitionReferenceId")
        or policy_entry.get("policyDefinitionReferenceId", "")
    )


# ── Suggestion engine ─────────────────────────────────────────────────────────

def keywords_from_ref_id(ref_id):
    """
    Extract human-readable keywords from a reference ID.
    e.g. 'SAMA_AC01_MFA_Read' → ['MFA', 'Read']
         'ADHICS_IAM_MFA_Read' → ['MFA', 'Read']
         'SAG_NET_RemoteDbgWeb' → ['Remote', 'Debug', 'Web']
    """
    # Strip framework prefix and control code (e.g. SAMA_AC01_, ADHICS_IAM_)
    stripped = re.sub(r'^[A-Z]+_[A-Z0-9]+_', '', ref_id)
    # Split CamelCase and underscores
    words = re.sub(r'([a-z])([A-Z])', r'\1 \2', stripped).replace('_', ' ').split()
    return [w for w in words if len(w) > 2]


def find_suggestions(ref_id, policies, n=3):
    """Find the top-n most likely matching built-in policies by keyword similarity."""
    keywords = keywords_from_ref_id(ref_id)
    if not keywords:
        return []

    scored = []
    kw_lower = [k.lower() for k in keywords]
    for p in policies:
        dn = (p.get("displayName") or "").lower()
        desc = (p.get("description") or "").lower()
        # Count keyword matches in display name
        hits = sum(1 for k in kw_lower if k in dn)
        # Bonus score from description
        desc_hits = sum(0.3 for k in kw_lower if k in desc)
        # Similarity ratio as tiebreaker
        ratio = SequenceMatcher(None, " ".join(kw_lower), dn).ratio()
        score = hits + desc_hits + ratio * 0.1
        if score > 0.5:
            scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:n]]


# ── Validation ────────────────────────────────────────────────────────────────

def validate_framework(fw_name, lookup, policies, fix=False):
    json_path = SCRIPT_DIR / fw_name / "policies.json"
    if not json_path.exists():
        print(f"\n  ⚠️  Skipping {fw_name} — policies.json not found")
        return 0, 0, []

    with open(json_path) as f:
        entries = json.load(f)

    print(f"\n▶ {fw_name} ({len(entries)} policies)")

    valid_count = 0
    invalid_entries = []

    for entry in entries:
        guid = extract_guid(entry)
        ref_id = extract_ref_id(entry)

        if guid in lookup:
            valid_count += 1
        else:
            suggestions = find_suggestions(ref_id, policies)
            invalid_entries.append({
                "ref_id": ref_id,
                "bad_guid": guid,
                "suggestions": suggestions,
            })
            print(f"  ❌ {ref_id}")
            print(f"     GUID: {guid}  ← NOT FOUND in Azure")
            if suggestions:
                print(f"     Suggestions (from real Azure data):")
                for s in suggestions:
                    deprecated = "[Deprecated] " if "[Deprecated]" in (s.get("displayName") or "") else ""
                    print(f"       ✦ {s['id']}  →  {deprecated}{s['displayName']}")
            else:
                kw = " ".join(keywords_from_ref_id(ref_id))
                print(f"     No auto-suggestion — search Azure: az policy definition list --query \"[?contains(displayName,'{kw}')]\" -o table")

    status = "✅" if not invalid_entries else "⚠️ "
    print(f"  {status} Valid: {valid_count}  |  ❌ Invalid: {len(invalid_entries)}")

    if fix and invalid_entries:
        bad_guids = {e["bad_guid"] for e in invalid_entries}
        fixed = [e for e in entries if extract_guid(e) not in bad_guids]
        with open(json_path, "w") as f:
            json.dump(fixed, f, indent=2)
        print(f"  🔧 Removed {len(invalid_entries)} invalid entries → {fw_name}/policies.json updated ({len(fixed)} remain)")

    return valid_count, len(invalid_entries), invalid_entries


# ── Search command ────────────────────────────────────────────────────────────

def search_policies(query, policies):
    """Search built-in policies by keyword."""
    q_lower = query.lower()
    results = [
        p for p in policies
        if q_lower in (p.get("displayName") or "").lower()
        or q_lower in (p.get("description") or "").lower()
    ]
    if not results:
        print(f"No built-in policies found matching '{query}'")
        return
    print(f"\n{len(results)} policies matching '{query}':\n")
    for p in results:
        deprecated = "  [DEPRECATED]" if "[Deprecated]" in (p.get("displayName") or "") else ""
        print(f"  {p['id']}{deprecated}")
        print(f"  → {p['displayName']}")
        if p.get("category"):
            print(f"     Category: {p['category']}")
        print()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Validate Azure Policy GUIDs in framework files")
    parser.add_argument("--fix", action="store_true",
                        help="Remove invalid policy entries from policies.json files")
    parser.add_argument("--refresh-cache", action="store_true",
                        help="Force refresh the Azure policy cache (ignore cache age)")
    parser.add_argument("--search", metavar="KEYWORD",
                        help="Search Azure built-in policies by display name keyword")
    parser.add_argument("--framework", metavar="NAME",
                        help="Only validate a specific framework (partial name match)")
    args = parser.parse_args()

    print("\n▶ Loading Azure built-in policy definitions...")
    policies = load_cache(force_refresh=args.refresh_cache)
    lookup = build_lookup(policies)
    print(f"  Total built-in policies available: {len(lookup)}")

    # Search mode
    if args.search:
        search_policies(args.search, policies)
        return

    # Validation mode
    fw_list = FRAMEWORKS
    if args.framework:
        fw_list = [fw for fw in FRAMEWORKS if args.framework.lower() in fw.lower()]
        if not fw_list:
            print(f"No framework found matching '{args.framework}'")
            sys.exit(1)

    total_valid = 0
    total_invalid = 0
    all_invalid = []

    for fw in fw_list:
        v, i, inv = validate_framework(fw, lookup, policies, fix=args.fix)
        total_valid += v
        total_invalid += i
        all_invalid.extend([{**e, "framework": fw} for e in inv])

    # Summary
    print(f"\n{'═'*50}")
    print(f"  Total valid GUIDs   : {total_valid}")
    print(f"  Total invalid GUIDs : {total_invalid}")

    if total_invalid > 0:
        print(f"\n  Invalid GUIDs (summary):")
        for e in all_invalid:
            print(f"    [{e['framework']}] {e['ref_id']}  →  {e['bad_guid']}")
            for s in e["suggestions"][:1]:
                print(f"      Best match: {s['id']}  ({s['displayName']})")
        if not args.fix:
            print(f"\n  Run with --fix to automatically remove invalid entries.")
            print(f"  Then search for replacements: python validate_guids.py --search '<keyword>'")
        print()
        sys.exit(1)
    else:
        print(f"\n  ✅ All GUIDs are valid! Safe to deploy.\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
