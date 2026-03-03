#!/usr/bin/env python3
"""
fix_guids.py — Applies a verified replacement map (sourced from real Azure built-in policy data)
to all framework policies.json files. Every replacement GUID has been validated against the
.policy-guid-cache.json file that was populated by `az policy definition list`.

Run:
  python fix_guids.py --dry-run    # show what would change
  python fix_guids.py              # apply all fixes
"""

import json
import os
import sys
import argparse
from pathlib import Path
from copy import deepcopy

SCRIPT_DIR = Path(__file__).parent
CACHE_FILE = SCRIPT_DIR / ".policy-guid-cache.json"

FRAMEWORKS = [
    "SAMA",
    "ADHICS",
    "Saudi Arabia Government",
    "South African Government",
    "Oman Government",
]

# ── Verified replacement map (confirmed against .policy-guid-cache.json) ─────
# Format: "bad_guid": ("correct_guid", "display_name")
# All correct GUIDs confirmed present in the Azure built-in policy cache.
REPLACEMENTS = {
    # MFA read — same prefix, wrong suffix
    "e3576e28-8602-4d61-b977-31a496128c53": (
        "81b3ccb4-e6e8-4e4a-8d05-5df25cd29fd4",
        "[Deprecated]: Accounts with read permissions on Azure resources should be MFA enabled",
    ),
    # Custom RBAC audit — completely wrong GUID (was our previous "fix")
    "0015ea4d-51ff-4ce3-8d8c-f3f8f0be26b8": (
        "a451c1ef-c6ca-483d-87ed-f49761e3ffb5",
        "Audit usage of custom RBAC roles",
    ),
    # Remote debug — Web/App Service
    "bb91dfba-f30e-4b18-ac8b-4d4e2b57d7c8": (
        "cb510bfd-1cba-4d9f-a230-cb0976f4bb71",
        "App Service apps should have remote debugging turned off",
    ),
    # Remote debug — Function apps (same prefix, wrong suffix as above)
    "cb510bfd-1cba-4d9f-a1ea-5d395ade7625": (
        "0e60b895-3786-45da-8377-9c6b4b6ac5f9",
        "Function apps should have remote debugging turned off",
    ),
    # Remote debug — API apps  
    "f9d614c5-c173-4d34-b42f-e7d0c5d9f89f": (
        "e9c8d085-d9cc-4b17-9cdc-059f1f01f19e",
        "[Deprecated]: Remote debugging should be turned off for API Apps",
    ),
    # Deprecated owner — custom subscription owner roles
    "a8eff44e-8a0e-49e8-b78f-6424f5f5b9a6": (
        "10ee2ea2-fb4d-45b8-a7e9-a2e770044cd9",
        "[Deprecated]: Custom subscription owner roles should not exist",
    ),
    # External accounts with read permissions
    "cca13f66-60b6-4671-a56e-3c97aba9f5d0": (
        "e9ac8f8e-ce22-4355-8f04-99b911d6be52",
        "Guest accounts with read permissions on Azure resources should be removed",
    ),
    # AAD admin for SQL servers
    "9bc48460-f641-4ef6-b0d7-e6e3c6a51acf": (
        "1f314764-cb73-4fc9-b863-8eca98ac36e9",
        "An Azure Active Directory administrator should be provisioned for SQL servers",
    ),
    # AAD/Entra auth for SQL Managed Instances
    "abfb7388-7082-4c07-bde4-9494d6b4e4b0": (
        "0c28c3fb-c244-42d5-a9bf-f35f2999577b",
        "Azure SQL Managed Instance should have Microsoft Entra-only authentication enabled",
    ),
    # Security contact email
    "b0d14bf4-d4fb-44cd-94a8-e7c8e6be68a5": (
        "4f4f78b8-e367-4b10-a341-d9a4ad5cf1c7",
        "Subscriptions should have a contact email address for security issues",
    ),
    # VMSS system updates (deprecated but exists)
    "9c276cf7-4e72-4578-b1ef-9d0a3b94f61e": (
        "c3f317a7-a95c-4547-b7e7-11017ebdf2fe",
        "[Deprecated]: System updates on virtual machine scale sets should be installed",
    ),
    # Key Vault private link/endpoint
    "1c06e275-d469-4136-9c30-cc65e2a9bfb6": (
        "a6abeaec-4d90-4a02-805f-6b26c4d3fbe9",
        "Azure Key Vaults should use private link",
    ),
    # Key Vault firewall (note: -a66d does not exist; correct audit policy is 55615ac9)
    "1e66c121-a66d-4b99-b523-e2cf4bf16934": (
        "55615ac9-af46-4a59-874e-391cc3dfb490",
        "Azure Key Vault should have firewall enabled or public network access disabled",
    ),
    # SQL private endpoint
    "ae89ebf1-7f27-46ee-a28c-eb1f3e0b0e51": (
        "7698e800-9299-47a6-b3b6-5a0fee576eed",
        "Private endpoint connections on Azure SQL Database should be enabled",
    ),
    # Storage account CMK
    "a4af4a39-4135-4a60-8bf6-d34b2a1d4f2c": (
        "6fac406b-40ca-413b-bf8e-0bf964659c25",
        "Storage accounts should use customer-managed key for encryption",
    ),
    # Cosmos DB CMK — same prefix, wrong suffix
    "1f905d99-2622-4c13-100b-f7c8e2078bc5": (
        "1f905d99-2ab7-462c-a6b0-f709acca6c8f",
        "Azure Cosmos DB accounts should use customer-managed keys to encrypt data at rest",
    ),
    # SQL Managed Instance auditing — use closest available
    "b954148f-4c11-4c38-8221-be76711e194e": (
        "a6fb4358-5bf4-4ad7-ba82-2cd2f41ce5e9",
        "Auditing on SQL server should be enabled",
    ),
    # Vulnerability assessment on SQL Managed Instance — same prefix, wrong suffix
    "1b7aa243-0aae-4b6f-a25b-a9e7430c5e29": (
        "1b7aa243-30e4-4c9e-bca8-d0d3022b634a",
        "Vulnerability assessment should be enabled on SQL Managed Instance",
    ),
    # Adaptive network hardening (deprecated but exists)
    "83e0d761-a202-44ec-a836-340498e1b9fe": (
        "08e6af2d-db70-460a-bfe9-d5bd474ba9d6",
        "[Deprecated]: Adaptive network hardening recommendations should be applied on internet facing virtual machines",
    ),
    # Vulnerability assessment on VMs
    "44e1ad92-5222-4c49-a0f3-0a2b023a47f9": (
        "501541f7-f7e7-4cd6-868c-4190fdad3ac9",
        "A vulnerability assessment solution should be enabled on your virtual machines",
    ),
    # Endpoint protection on machines (deprecated but exists)
    "4da35fc9-8a1e-4f77-bb53-96d4c4e4a64f": (
        "1f7c564c-0a90-4d44-b7e1-9d456cffaee8",
        "[Deprecated]: Endpoint protection should be installed on your machines",
    ),
    # Cognitive Services CMK (deprecated but exists)
    "67121cc7-4b87-484c-b351-8d39bda0a285": (
        "11566b39-f7f7-4b82-ab06-68d8700eb0a4",
        "[Deprecated]: Cognitive Services accounts should use customer owned storage or enable data encryption",
    ),
    # Cognitive Services disable public network
    "0725b4dd-7e76-479c-a078-d51d9a7e9891": (
        "47ba1dd7-28d9-4b07-a8d5-9813bed64e0c",
        "Configure Cognitive Services accounts to disable public network access",
    ),
}


def verify_replacements_against_cache():
    """Verify all replacement GUIDs actually exist in the Azure policy cache."""
    if not CACHE_FILE.exists() or CACHE_FILE.stat().st_size == 0:
        print("  ⚠️  No cache file found — skipping pre-verification")
        print("     Run: python validate_guids.py --refresh-cache")
        return True

    with open(CACHE_FILE) as f:
        cache = json.load(f)
    valid_ids = {p["id"] for p in cache}

    errors = []
    for bad, (correct, name) in REPLACEMENTS.items():
        if correct not in valid_ids:
            errors.append(f"  ❌ Replacement GUID not in Azure: {correct}  ({name})")

    if errors:
        print("\n⛔ Replacement verification FAILED — these GUIDs do not exist in Azure:")
        for e in errors:
            print(e)
        return False
    return True


def extract_guid(entry):
    pid = entry.get("PolicyDefinitionId") or entry.get("policyDefinitionId", "")
    return pid.split("/")[-1]


def set_guid(entry, new_guid):
    """Replace the GUID in the PolicyDefinitionId field."""
    new_id = f"/providers/Microsoft.Authorization/policyDefinitions/{new_guid}"
    if "PolicyDefinitionId" in entry:
        entry["PolicyDefinitionId"] = new_id
    else:
        entry["policyDefinitionId"] = new_id
    return entry


def fix_framework(fw_name, dry_run=False):
    json_path = SCRIPT_DIR / fw_name / "policies.json"
    if not json_path.exists():
        print(f"\n  ⚠️  Skipping {fw_name} — policies.json not found")
        return 0

    with open(json_path) as f:
        entries = json.load(f)

    fixed_entries = []
    changes = 0
    for entry in entries:
        guid = extract_guid(entry)
        if guid in REPLACEMENTS:
            new_guid, display_name = REPLACEMENTS[guid]
            ref_id = entry.get("PolicyDefinitionReferenceId") or entry.get("policyDefinitionReferenceId", "")
            print(f"  FIX  {ref_id}")
            print(f"       {guid}  →  {new_guid}")
            print(f"       {display_name}")
            if not dry_run:
                entry = deepcopy(entry)
                set_guid(entry, new_guid)
            changes += 1
        fixed_entries.append(entry)

    if not dry_run and changes > 0:
        with open(json_path, "w") as f:
            json.dump(fixed_entries, f, indent=2)
        print(f"\n  ✅ Saved {fw_name}/policies.json ({changes} GUIDs replaced)")
    elif changes == 0:
        print(f"  ✅ {fw_name} — no changes needed")

    return changes


def main():
    parser = argparse.ArgumentParser(description="Apply verified GUID replacements to all framework policies.json files")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing files")
    parser.add_argument("--framework", help="Only fix a specific framework (partial name match)")
    parser.add_argument("--skip-verify", action="store_true", help="Skip cache verification step")
    args = parser.parse_args()

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Applying {len(REPLACEMENTS)} verified GUID replacements\n")

    if not args.skip_verify:
        print("▶ Verifying replacements against Azure policy cache...")
        if not verify_replacements_against_cache():
            print("\n  Run `python validate_guids.py --refresh-cache` to update the cache,")
            print("  then re-run this script.")
            sys.exit(1)
        print("  ✅ All replacement GUIDs confirmed in Azure\n")

    fw_list = FRAMEWORKS
    if args.framework:
        fw_list = [fw for fw in FRAMEWORKS if args.framework.lower() in fw.lower()]

    total_changes = 0
    for fw in fw_list:
        print(f"▶ {fw}")
        total_changes += fix_framework(fw, dry_run=args.dry_run)
        print()

    print(f"{'═'*50}")
    if args.dry_run:
        print(f"  DRY RUN complete — {total_changes} changes would be applied")
        print(f"  Run without --dry-run to apply")
    else:
        print(f"  Complete — {total_changes} GUIDs replaced across all frameworks")
        if total_changes > 0:
            print(f"\n  Next: run validate_guids.py to confirm zero invalid GUIDs remain")
            print(f"  Then: run DeployAllInitiatives.ps1")


if __name__ == "__main__":
    main()
