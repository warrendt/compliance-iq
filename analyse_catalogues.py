#!/usr/bin/env python3
"""Analyse catalogue CSVs to understand Azure Policy ID coverage, then generate
expanded policies.json for each framework from the catalogue data."""
import csv, json, re, os, uuid
from collections import defaultdict

BASE = "/Users/wdt/Desktop/Cloud Compliance Toolkit/cctoolkit_v1"
CAT  = BASE + "/catalogues"
FW   = BASE + "/framework"

files = {
    "ADHICS": (CAT + "/ADHICS_Framework_Azure_Mappings.csv",
               FW  + "/ADHICS"),
    "KSA":    (CAT + "/Saudi_Arabia_Government_Azure_Mappings.csv",
               FW  + "/Saudi Arabia Government"),
    "SAG":    (CAT + "/South_African_Government_Azure_Mappings.csv",
               FW  + "/South African Government"),
    "SAMA":   (CAT + "/SAMA_Catalog_Azure_Mappings.csv",
               FW  + "/SAMA"),
    "OMN":    (CAT + "/Oman_Government_Azure_Mappings.csv",
               FW  + "/Oman Government"),
}

GUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

for fw_name, (csv_path, fw_dir) in files.items():
    rows = list(csv.DictReader(open(csv_path)))
    # Identify key columns
    cols = list(rows[0].keys())
    id_col   = next((c for c in cols if "policy_id"   in c.lower()), None)
    ctrl_col = cols[0]  # first col is always the control ID
    dom_col  = next((c for c in cols if "domain" in c.lower()), None)

    # Count coverage
    mapped = [r for r in rows if id_col and GUID_RE.search(r.get(id_col, ""))]
    print(fw_name + ": " + str(len(rows)) + " controls, " + str(len(mapped)) + " with valid Azure Policy GUID")

    if not mapped:
        print("  -> no GUIDs in catalogue, skipping\n")
        continue

    # Load existing groups to build group name map
    groups_path = fw_dir + "/groups.json"
    with open(groups_path) as gf:
        groups = json.load(gf)
    # Build domain keyword -> group name map
    group_names = [g["name"] for g in groups]

    # Load existing policies.json to understand current policy keys format
    policies_path = fw_dir + "/policies.json"
    with open(policies_path) as pf:
        existing = json.load(pf)
    # Detect key casing from existing entries
    sample = existing[0] if existing else {}
    use_pascal = "PolicyDefinitionId" in sample  # SAMA uses PascalCase

    # Build new policy entries from catalogue
    seen_guids = set()
    new_entries = []

    for row in rows:
        raw_id = row.get(id_col, "").strip()
        m = GUID_RE.search(raw_id)
        if not m:
            continue
        guid = m.group(0).lower()
        if guid in seen_guids:
            continue
        seen_guids.add(guid)

        ctrl_id = row.get(ctrl_col, "").strip()
        # Map control domain to a group
        domain_hint = row.get(dom_col, "").lower() if dom_col else ""
        # Find best matching group by checking group name tokens against domain
        best_group = group_names[0]
        for gn in group_names:
            tokens = gn.replace("_", " ").lower().split()
            if any(t in domain_hint for t in tokens if len(t) > 2):
                best_group = gn
                break

        ref_id = ctrl_id.replace("-", "_").replace(" ", "_") + "_" + guid[:8]
        policy_path = "/providers/Microsoft.Authorization/policyDefinitions/" + guid

        if use_pascal:
            entry = {
                "PolicyDefinitionReferenceId": ref_id,
                "PolicyDefinitionId": policy_path,
                "Parameters": {},
                "GroupNames": [best_group]
            }
        else:
            entry = {
                "policyDefinitionReferenceId": ref_id,
                "policyDefinitionId": policy_path,
                "parameters": {},
                "groupNames": [best_group]
            }
        new_entries.append(entry)

    print("  -> " + str(len(new_entries)) + " unique GUIDs to write to policies.json")
    print("  -> sample: " + str(new_entries[0]) if new_entries else "")
    print()

print("\nDone — run again with write=True to apply")
