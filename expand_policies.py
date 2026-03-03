#!/usr/bin/env python3
"""
Expand all 5 framework policies.json files with comprehensive Azure built-in policy mappings.
Removes failing DINE policies (55d1f543, b79fa14e) and adds ~30-40 policies per framework.
"""
import json, os

BASE = "/Users/wdt/Desktop/Cloud Compliance Toolkit/cctoolkit_v1/framework"

# ──────────────────────────────────────────────────────────────────
# Master catalogue of Azure Policy built-in GUIDs that are
# broadly available in Azure tenants.
# ──────────────────────────────────────────────────────────────────
P = "/providers/Microsoft.Authorization/policyDefinitions/"

def pid(guid): return P + guid

# logAnalytics param ref (used by 818719e5 only)
LOG_PARAM = {"logAnalytics": {"value": "[parameters('logAnalytics')]"}}

# ──────────────────────────────────────────────────────────────────
# SAMA  (PascalCase keys)
# ──────────────────────────────────────────────────────────────────
def sama_entry(ref_id, guid, groups, params=None):
    return {
        "PolicyDefinitionReferenceId": ref_id,
        "PolicyDefinitionId": pid(guid),
        "Parameters": params or {},
        "GroupNames": groups if isinstance(groups, list) else [groups]
    }

SAMA_POLICIES = [
    # ── SAMA-AC-01  Access Control ────────────────────────────────
    sama_entry("SAMA_AC01_MFA_Owners",        "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b", "SAMA-AC-01"),
    sama_entry("SAMA_AC01_MFA_Write",         "9297c21d-2d0a-4958-8955-00b9f6db96d0", "SAMA-AC-01"),
    sama_entry("SAMA_AC01_MFA_Read",          "e3576e28-8602-4d61-b977-31a496128c53", "SAMA-AC-01"),
    sama_entry("SAMA_AC01_JIT_VM",            "1f314764-cb73-4fc9-b863-8eca98ac36e9", "SAMA-AC-01"),
    sama_entry("SAMA_AC01_MgmtPorts",         "0b15565f-aa9e-48ba-8619-45960f2c314d", "SAMA-AC-01"),
    sama_entry("SAMA_AC01_DeprecatedOwner",   "a8eff44e-8a0e-49e8-b78f-6424f5f5b9a6", "SAMA-AC-01"),
    sama_entry("SAMA_AC01_DeprecatedAccts",   "94e1c2ac-cbbe-4cac-a2b5-389c812dee87", "SAMA-AC-01"),
    sama_entry("SAMA_AC01_ExtWrite",          "5c607a2e-c700-4744-8254-d77e7c9eb5e4", "SAMA-AC-01"),
    sama_entry("SAMA_AC01_ExtRead",           "cca13f66-60b6-4671-a56e-3c97aba9f5d0", "SAMA-AC-01"),
    # ── SAMA-AC-03  Identity & Authentication ─────────────────────
    sama_entry("SAMA_AC03_CustomRBAC",        "0015ea4d-1bef-4a42-83a4-621c6455c474", "SAMA-AC-03"),
    sama_entry("SAMA_AC03_AADAdmin_SQL",      "9bc48460-f641-4ef6-b0d7-e6e3c6a51acf", "SAMA-AC-03"),
    sama_entry("SAMA_AC03_AADAdmin_SQLMI",    "abfb7388-7082-4c07-bde4-9494d6b4e4b0", "SAMA-AC-03"),
    sama_entry("SAMA_AC03_CMKDisk",           "702dd420-7fcc-42c5-afe8-4026edd20fe0", "SAMA-AC-03"),  # kept from original
    sama_entry("SAMA_AC03_SecurityContact",   "b0d14bf4-d4fb-44cd-94a8-e7c8e6be68a5", "SAMA-AC-03"),
    # ── SAMA-NS-01  Network Security ──────────────────────────────
    sama_entry("SAMA_NS01_NSG_Subnets",       "e71308d3-144b-4262-b144-efdc3cc90517", "SAMA-NS-01"),
    sama_entry("SAMA_NS01_NSG_Subnets2",      "2c89a2e5-a4bb-42d5-8a17-af8c0bcc1e79", "SAMA-NS-01"),
    sama_entry("SAMA_NS01_VMInternet_NSG",    "09024ccc-0c5f-475e-9457-b7c0d9ed487b", "SAMA-NS-01"),
    sama_entry("SAMA_NS01_RemoteDbgWeb",      "bb91dfba-f30e-4b18-ac8b-4d4e2b57d7c8", "SAMA-NS-01"),
    sama_entry("SAMA_NS01_RemoteDbgFunc",     "cb510bfd-1cba-4d9f-a1ea-5d395ade7625", "SAMA-NS-01"),
    sama_entry("SAMA_NS01_RemoteDbgAPI",      "f9d614c5-c173-4d34-b42f-e7d0c5d9f89f", "SAMA-NS-01"),
    # ── SAMA-NS-02  Network Infrastructure ────────────────────────
    sama_entry("SAMA_NS02_PrivateLink",       "ca610c1d-041c-4332-9d88-7ed3094967c7", "SAMA-NS-02"),
    sama_entry("SAMA_NS02_PE_KeyVault",       "1c06e275-d469-4136-9c30-cc65e2a9bfb6", "SAMA-NS-02"),
    sama_entry("SAMA_NS02_KV_Firewall",       "1e66c121-a66d-4b99-b523-e2cf4bf16934", "SAMA-NS-02"),
    sama_entry("SAMA_NS02_PE_SQL",            "ae89ebf1-7f27-46ee-a28c-eb1f3e0b0e51", "SAMA-NS-02"),
    sama_entry("SAMA_NS02_SQLMIPublic",       "9dfea752-dd46-4766-aed1-c355fa93fb91", "SAMA-NS-02"),
    # ── SAMA-DP-02  Data Protection ───────────────────────────────
    sama_entry("SAMA_DP02_CMKPostgres",       "18adea5e-f416-4d0f-8aa8-d24321e3e274", "SAMA-DP-02"),
    sama_entry("SAMA_DP02_SQLTDE",            "7595c971-233d-4bcf-bd18-596129188c49", "SAMA-DP-02"),
    sama_entry("SAMA_DP02_SecureTransfer",    "404c3081-a854-4457-ae30-26a93ef643f9", "SAMA-DP-02"),
    sama_entry("SAMA_DP02_TLSVersion",        "4733ea7b-a883-42fe-8cac-97454c2a9e4a", "SAMA-DP-02"),
    sama_entry("SAMA_DP02_CMKMySQL",          "0a370ff3-6cab-4e85-8995-295fd854c5b8", "SAMA-DP-02"),
    sama_entry("SAMA_DP02_TempDiskEncrypt",   "0961003e-5a0a-4549-abde-af6a37f2724d", "SAMA-DP-02"),
    sama_entry("SAMA_DP02_StorageCMK",        "a4af4a39-4135-4a60-8bf6-d34b2a1d4f2c", "SAMA-DP-02"),
    sama_entry("SAMA_DP02_CosmosDBCMK",       "1f905d99-2622-4c13-100b-f7c8e2078bc5", "SAMA-DP-02"),
    sama_entry("SAMA_DP02_SQLDataClass",      "0b60c0b2-2dc2-4e1c-b5c9-abbed971de53", "SAMA-DP-02"),
    # ── SAMA-LM-01  Logging & Monitoring ──────────────────────────
    sama_entry("SAMA_LM01_ActivityLog",       "818719e5-1338-4776-9a9d-3c31e4df5986", "SAMA-LM-01", LOG_PARAM),
    sama_entry("SAMA_LM01_DiagSettings",      "428256e6-1fac-4f48-a757-df34c2b3336d", "SAMA-LM-01"),
    sama_entry("SAMA_LM01_SQLAudit",          "89099bee-89e0-4b26-a5f4-165451757743", "SAMA-LM-01"),
    sama_entry("SAMA_LM01_SQLMIAudit",        "b954148f-4c11-4c38-8221-be76711e194e", "SAMA-LM-01"),
    # ── SAMA-VM-01  Vulnerability Management ──────────────────────
    sama_entry("SAMA_VM01_SystemUpdates",     "86b3d65f-7626-441e-b690-81a8b71cff60", "SAMA-VM-01"),
    sama_entry("SAMA_VM01_UpdateCheck",       "bd876905-5b84-4f73-ab2d-2e7a7c4568d9", "SAMA-VM-01"),
    sama_entry("SAMA_VM01_VMSSUpdates",       "9c276cf7-4e72-4578-b1ef-9d0a3b94f61e", "SAMA-VM-01"),
    sama_entry("SAMA_VM01_EndpointProt",      "4da35fc9-8a1e-4f77-bb53-96d4c4e4a64f", "SAMA-VM-01"),
    sama_entry("SAMA_VM01_AdaptiveApp",       "8e86a5b6-b9bd-49d1-8e21-4bb8a0862222", "SAMA-VM-01"),
    sama_entry("SAMA_VM01_VulnSQL",           "e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f", "SAMA-VM-01"),
    sama_entry("SAMA_VM01_VulnSQLMI",         "1b7aa243-0aae-4b6f-a25b-a9e7430c5e29", "SAMA-VM-01"),
    sama_entry("SAMA_VM01_AdaptiveNet",       "83e0d761-a202-44ec-a836-340498e1b9fe", "SAMA-VM-01"),
    # ── SAMA-AI-03  Cognitive Services Security ───────────────────
    # NOTE: 55d1f543 removed (DINE policy with logAnalytics version conflict)
    sama_entry("SAMA_AI03_CogSvcCMK",        "67121cc7-4b87-484c-b351-8d39bda0a285", "SAMA-AI-03"),
    sama_entry("SAMA_AI03_CogSvcPublicNet",   "0725b4dd-7e76-479c-a078-d51d9a7e9891", "SAMA-AI-03"),
]

# ──────────────────────────────────────────────────────────────────
# Generic helper for camelCase frameworks
# ──────────────────────────────────────────────────────────────────
def entry(ref_id, guid, groups, params=None):
    return {
        "policyDefinitionReferenceId": ref_id,
        "policyDefinitionId": pid(guid),
        "parameters": params or {},
        "groupNames": groups if isinstance(groups, list) else [groups]
    }

# ──────────────────────────────────────────────────────────────────
# ADHICS (healthcare/UAE)
# ──────────────────────────────────────────────────────────────────
ADHICS_POLICIES = [
    # ── ADHICS_GOV  Governance ────────────────────────────────────
    entry("ADHICS_GOV_CustomRBAC",       "0015ea4d-1bef-4a42-83a4-621c6455c474", "ADHICS_GOV"),
    entry("ADHICS_GOV_RBAC_K8s",         "34c877ad-507e-4c82-993e-3452a6e0ad3c", "ADHICS_GOV"),
    entry("ADHICS_GOV_SecurityContact",  "b0d14bf4-d4fb-44cd-94a8-e7c8e6be68a5", "ADHICS_GOV"),

    entry("ADHICS_GOV_ExtWrite",         "5c607a2e-c700-4744-8254-d77e7c9eb5e4", "ADHICS_GOV"),
    # ── ADHICS_PHI  Protected Health Information ──────────────────
    entry("ADHICS_PHI_CMKPostgres",      "18adea5e-f416-4d0f-8aa8-d24321e3e274", "ADHICS_PHI"),
    entry("ADHICS_PHI_CMKDisk",          "702dd420-7fcc-42c5-afe8-4026edd20fe0", "ADHICS_PHI"),
    entry("ADHICS_PHI_CMKMySQL",         "0a370ff3-6cab-4e85-8995-295fd854c5b8", "ADHICS_PHI"),
    entry("ADHICS_PHI_StorageCMK",       "a4af4a39-4135-4a60-8bf6-d34b2a1d4f2c", "ADHICS_PHI"),
    entry("ADHICS_PHI_SQLTDE",           "7595c971-233d-4bcf-bd18-596129188c49", "ADHICS_PHI"),
    entry("ADHICS_PHI_SecureTransfer",   "404c3081-a854-4457-ae30-26a93ef643f9", "ADHICS_PHI"),
    entry("ADHICS_PHI_TempDiskEncrypt",  "0961003e-5a0a-4549-abde-af6a37f2724d", "ADHICS_PHI"),
    entry("ADHICS_PHI_SQLDataClass",     "0b60c0b2-2dc2-4e1c-b5c9-abbed971de53", "ADHICS_PHI"),
    # ── ADHICS_IAM  Identity & Access Management ──────────────────
    entry("ADHICS_IAM_MFA_Owners",       "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b", "ADHICS_IAM"),
    entry("ADHICS_IAM_MFA_Write",        "9297c21d-2d0a-4958-8955-00b9f6db96d0", "ADHICS_IAM"),
    entry("ADHICS_IAM_MFA_Read",         "e3576e28-8602-4d61-b977-31a496128c53", "ADHICS_IAM"),
    entry("ADHICS_IAM_JIT",              "1f314764-cb73-4fc9-b863-8eca98ac36e9", "ADHICS_IAM"),
    entry("ADHICS_IAM_MgmtPorts",        "0b15565f-aa9e-48ba-8619-45960f2c314d", "ADHICS_IAM"),
    entry("ADHICS_IAM_DeprecatedOwner",  "a8eff44e-8a0e-49e8-b78f-6424f5f5b9a6", "ADHICS_IAM"),
    entry("ADHICS_IAM_DeprecatedAccts",  "94e1c2ac-cbbe-4cac-a2b5-389c812dee87", "ADHICS_IAM"),
    entry("ADHICS_IAM_AADAdmin_SQL",     "9bc48460-f641-4ef6-b0d7-e6e3c6a51acf", "ADHICS_IAM"),
    entry("ADHICS_IAM_AADAdmin_SQLMI",   "abfb7388-7082-4c07-bde4-9494d6b4e4b0", "ADHICS_IAM"),
    # ── ADHICS_NET  Network Security ─────────────────────────────
    entry("ADHICS_NET_NSG_Subnets",      "e71308d3-144b-4262-b144-efdc3cc90517", "ADHICS_NET"),
    entry("ADHICS_NET_NSG_Subnets2",     "2c89a2e5-a4bb-42d5-8a17-af8c0bcc1e79", "ADHICS_NET"),
    entry("ADHICS_NET_VMInternet_NSG",   "09024ccc-0c5f-475e-9457-b7c0d9ed487b", "ADHICS_NET"),
    entry("ADHICS_NET_PrivateLink",      "ca610c1d-041c-4332-9d88-7ed3094967c7", "ADHICS_NET"),
    entry("ADHICS_NET_PE_KeyVault",      "1c06e275-d469-4136-9c30-cc65e2a9bfb6", "ADHICS_NET"),
    entry("ADHICS_NET_KV_Firewall",      "1e66c121-a66d-4b99-b523-e2cf4bf16934", "ADHICS_NET"),
    # ── ADHICS_APP  Application Security ─────────────────────────
    entry("ADHICS_APP_SystemUpdates",    "86b3d65f-7626-441e-b690-81a8b71cff60", "ADHICS_APP"),
    entry("ADHICS_APP_TLSVersion",       "4733ea7b-a883-42fe-8cac-97454c2a9e4a", "ADHICS_APP"),
    entry("ADHICS_APP_RemoteDbgWeb",     "bb91dfba-f30e-4b18-ac8b-4d4e2b57d7c8", "ADHICS_APP"),
    entry("ADHICS_APP_RemoteDbgFunc",    "cb510bfd-1cba-4d9f-a1ea-5d395ade7625", "ADHICS_APP"),
    entry("ADHICS_APP_RemoteDbgAPI",     "f9d614c5-c173-4d34-b42f-e7d0c5d9f89f", "ADHICS_APP"),
    entry("ADHICS_APP_SQLMIPublic",      "9dfea752-dd46-4766-aed1-c355fa93fb91", "ADHICS_APP"),
    # ── ADHICS_DEV  Medical Device Security ──────────────────────
    entry("ADHICS_DEV_JIT",              "1f314764-cb73-4fc9-b863-8eca98ac36e9", "ADHICS_DEV"),
    entry("ADHICS_DEV_MgmtPorts",        "0b15565f-aa9e-48ba-8619-45960f2c314d", "ADHICS_DEV"),
    entry("ADHICS_DEV_EndpointProt",     "ac076320-ddcf-4066-b451-6154267e8ad2", "ADHICS_DEV"),
    entry("ADHICS_DEV_AdaptiveApp",      "8e86a5b6-b9bd-49d1-8e21-4bb8a0862222", "ADHICS_DEV"),
    # ── ADHICS_DATA  Data Management ─────────────────────────────
    entry("ADHICS_DATA_SQLAudit",        "89099bee-89e0-4b26-a5f4-165451757743", "ADHICS_DATA"),
    entry("ADHICS_DATA_SQLMIAudit",      "b954148f-4c11-4c38-8221-be76711e194e", "ADHICS_DATA"),
    entry("ADHICS_DATA_BackupVM",        "013e242c-8828-4970-87b3-ab247555486d", "ADHICS_DATA"),
    entry("ADHICS_DATA_GeoBackupSQL",    "22bee202-a82f-4305-9a2a-6d7f44d4dedb", "ADHICS_DATA"),
    entry("ADHICS_DATA_DiagSettings",    "428256e6-1fac-4f48-a757-df34c2b3336d", "ADHICS_DATA"),
    # ── ADHICS_COMP  Compliance ───────────────────────────────────
    entry("ADHICS_COMP_VulnSQL",         "e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f", "ADHICS_COMP"),
    entry("ADHICS_COMP_VulnSQLMI",       "1b7aa243-0aae-4b6f-a25b-a9e7430c5e29", "ADHICS_COMP"),
    entry("ADHICS_COMP_AdaptiveNet",     "83e0d761-a202-44ec-a836-340498e1b9fe", "ADHICS_COMP"),
    entry("ADHICS_COMP_VulnAssessVM",    "44e1ad92-5222-4c49-a0f3-0a2b023a47f9", "ADHICS_COMP"),
    entry("ADHICS_COMP_CustomRBAC",      "0015ea4d-1bef-4a42-83a4-621c6455c474", "ADHICS_COMP"),
    # ── ADHICS_BC  Business Continuity ────────────────────────────
    entry("ADHICS_BC_BackupVM",          "013e242c-8828-4970-87b3-ab247555486d", "ADHICS_BC"),
    entry("ADHICS_BC_GeoBackupSQL",      "22bee202-a82f-4305-9a2a-6d7f44d4dedb", "ADHICS_BC"),
    entry("ADHICS_BC_VMSSUpdates",       "9c276cf7-4e72-4578-b1ef-9d0a3b94f61e", "ADHICS_BC"),
]

# ──────────────────────────────────────────────────────────────────
# KSA – Saudi Arabia Government  (12 groups)
# ──────────────────────────────────────────────────────────────────
KSA_POLICIES = [
    # ── KSA_GOV  Cybersecurity Governance ─────────────────────────
    entry("KSA_GOV_CustomRBAC",         "0015ea4d-1bef-4a42-83a4-621c6455c474", "KSA_GOV"),
    entry("KSA_GOV_RBAC_K8s",           "34c877ad-507e-4c82-993e-3452a6e0ad3c", "KSA_GOV"),
    entry("KSA_GOV_SecurityContact",    "b0d14bf4-d4fb-44cd-94a8-e7c8e6be68a5", "KSA_GOV"),
    entry("KSA_GOV_DiagSettings",       "428256e6-1fac-4f48-a757-df34c2b3336d", "KSA_GOV"),
    # ── KSA_INF  Infrastructure Security ──────────────────────────
    entry("KSA_INF_UpdateCheck",        "bd876905-5b84-4f73-ab2d-2e7a7c4568d9", "KSA_INF"),
    entry("KSA_INF_NSG_Subnets",        "e71308d3-144b-4262-b144-efdc3cc90517", "KSA_INF"),
    entry("KSA_INF_CMKDisk",            "702dd420-7fcc-42c5-afe8-4026edd20fe0", "KSA_INF"),
    entry("KSA_INF_VMSSUpdates",        "9c276cf7-4e72-4578-b1ef-9d0a3b94f61e", "KSA_INF"),
    entry("KSA_INF_TempDiskEncrypt",    "0961003e-5a0a-4549-abde-af6a37f2724d", "KSA_INF"),
    entry("KSA_INF_EndpointProt",       "ac076320-ddcf-4066-b451-6154267e8ad2", "KSA_INF"),
    # ── KSA_PLA  Platform Security ────────────────────────────────
    entry("KSA_PLA_SQLMIPublic",        "9dfea752-dd46-4766-aed1-c355fa93fb91", "KSA_PLA"),
    entry("KSA_PLA_RemoteDbgWeb",       "bb91dfba-f30e-4b18-ac8b-4d4e2b57d7c8", "KSA_PLA"),
    entry("KSA_PLA_RemoteDbgFunc",      "cb510bfd-1cba-4d9f-a1ea-5d395ade7625", "KSA_PLA"),
    entry("KSA_PLA_RemoteDbgAPI",       "f9d614c5-c173-4d34-b42f-e7d0c5d9f89f", "KSA_PLA"),
    entry("KSA_PLA_TLSVersion",         "4733ea7b-a883-42fe-8cac-97454c2a9e4a", "KSA_PLA"),
    entry("KSA_PLA_VMInternet_NSG",     "09024ccc-0c5f-475e-9457-b7c0d9ed487b", "KSA_PLA"),
    # ── KSA_DAT  Data Security ─────────────────────────────────────
    entry("KSA_DAT_CMKPostgres",        "18adea5e-f416-4d0f-8aa8-d24321e3e274", "KSA_DAT"),
    entry("KSA_DAT_SQLTDE",             "7595c971-233d-4bcf-bd18-596129188c49", "KSA_DAT"),
    entry("KSA_DAT_SecureTransfer",     "404c3081-a854-4457-ae30-26a93ef643f9", "KSA_DAT"),
    entry("KSA_DAT_CMKMySQL",           "0a370ff3-6cab-4e85-8995-295fd854c5b8", "KSA_DAT"),
    entry("KSA_DAT_StorageCMK",         "a4af4a39-4135-4a60-8bf6-d34b2a1d4f2c", "KSA_DAT"),
    entry("KSA_DAT_SQLDataClass",       "0b60c0b2-2dc2-4e1c-b5c9-abbed971de53", "KSA_DAT"),
    entry("KSA_DAT_SQLAudit",           "89099bee-89e0-4b26-a5f4-165451757743", "KSA_DAT"),
    entry("KSA_DAT_SQLMIAudit",         "b954148f-4c11-4c38-8221-be76711e194e", "KSA_DAT"),
    # ── KSA_IAM  Identity & Access Management ─────────────────────
    entry("KSA_IAM_MFA_Owners",         "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b", "KSA_IAM"),
    entry("KSA_IAM_MFA_Write",          "9297c21d-2d0a-4958-8955-00b9f6db96d0", "KSA_IAM"),
    entry("KSA_IAM_MFA_Read",           "e3576e28-8602-4d61-b977-31a496128c53", "KSA_IAM"),
    entry("KSA_IAM_JIT",                "1f314764-cb73-4fc9-b863-8eca98ac36e9", "KSA_IAM"),
    entry("KSA_IAM_MgmtPorts",          "0b15565f-aa9e-48ba-8619-45960f2c314d", "KSA_IAM"),
    entry("KSA_IAM_DeprecatedOwner",    "a8eff44e-8a0e-49e8-b78f-6424f5f5b9a6", "KSA_IAM"),
    entry("KSA_IAM_DeprecatedAccts",    "94e1c2ac-cbbe-4cac-a2b5-389c812dee87", "KSA_IAM"),
    entry("KSA_IAM_AADAdmin_SQL",       "9bc48460-f641-4ef6-b0d7-e6e3c6a51acf", "KSA_IAM"),
    # ── KSA_NET  Network Security ──────────────────────────────────
    entry("KSA_NET_PrivateLink",        "ca610c1d-041c-4332-9d88-7ed3094967c7", "KSA_NET"),
    entry("KSA_NET_NSG_Subnets",        "2c89a2e5-a4bb-42d5-8a17-af8c0bcc1e79", "KSA_NET"),
    entry("KSA_NET_PE_KeyVault",        "1c06e275-d469-4136-9c30-cc65e2a9bfb6", "KSA_NET"),
    entry("KSA_NET_KV_Firewall",        "1e66c121-a66d-4b99-b523-e2cf4bf16934", "KSA_NET"),
    entry("KSA_NET_PE_SQL",             "ae89ebf1-7f27-46ee-a28c-eb1f3e0b0e51", "KSA_NET"),
    # ── KSA_SEC  Security Operations ──────────────────────────────
    entry("KSA_SEC_SystemUpdates",      "86b3d65f-7626-441e-b690-81a8b71cff60", "KSA_SEC"),
    entry("KSA_SEC_VulnSQL",            "e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f", "KSA_SEC"),
    entry("KSA_SEC_VulnSQLMI",          "1b7aa243-0aae-4b6f-a25b-a9e7430c5e29", "KSA_SEC"),
    entry("KSA_SEC_AdaptiveNet",        "83e0d761-a202-44ec-a836-340498e1b9fe", "KSA_SEC"),
    entry("KSA_SEC_AdaptiveApp",        "8e86a5b6-b9bd-49d1-8e21-4bb8a0862222", "KSA_SEC"),
    entry("KSA_SEC_VulnVM",             "44e1ad92-5222-4c49-a0f3-0a2b023a47f9", "KSA_SEC"),
    # ── KSA_COM  Compliance & Audit ────────────────────────────────
    entry("KSA_COM_DiagSettings",       "428256e6-1fac-4f48-a757-df34c2b3336d", "KSA_COM"),
    entry("KSA_COM_SQLAudit",           "89099bee-89e0-4b26-a5f4-165451757743", "KSA_COM"),
    entry("KSA_COM_RBAC_K8s",           "a451c1ef-c6ca-483d-87ed-f49761e3ffb5", "KSA_COM"),
    # ── KSA_DR  Disaster Recovery ──────────────────────────────────
    entry("KSA_DR_BackupVM",            "013e242c-8828-4970-87b3-ab247555486d", "KSA_DR"),
    entry("KSA_DR_GeoBackupSQL",        "22bee202-a82f-4305-9a2a-6d7f44d4dedb", "KSA_DR"),
    entry("KSA_DR_VMSSUpdates",         "9c276cf7-4e72-4578-b1ef-9d0a3b94f61e", "KSA_DR"),
    # ── KSA_NDM  Data Management (NDMO) ───────────────────────────
    entry("KSA_NDM_RBAC",               "a451c1ef-c6ca-483d-87ed-f49761e3ffb5", "KSA_NDM"),
    entry("KSA_NDM_SQLDataClass",       "0b60c0b2-2dc2-4e1c-b5c9-abbed971de53", "KSA_NDM"),
    entry("KSA_NDM_SQLTDE",             "7595c971-233d-4bcf-bd18-596129188c49", "KSA_NDM"),
    # ── KSA_NDP  Data Privacy (PDPL) ──────────────────────────────
    entry("KSA_NDP_StorageCMK",         "a4af4a39-4135-4a60-8bf6-d34b2a1d4f2c", "KSA_NDP"),
    entry("KSA_NDP_DeprecatedOwner",    "a8eff44e-8a0e-49e8-b78f-6424f5f5b9a6", "KSA_NDP"),
    entry("KSA_NDP_SecureTransfer",     "404c3081-a854-4457-ae30-26a93ef643f9", "KSA_NDP"),
    # ── KSA_NDS  Data Sharing (NDMO) ──────────────────────────────
    entry("KSA_NDS_SecureTransfer",     "404c3081-a854-4457-ae30-26a93ef643f9", "KSA_NDS"),
    entry("KSA_NDS_TLSVersion",         "4733ea7b-a883-42fe-8cac-97454c2a9e4a", "KSA_NDS"),
    entry("KSA_NDS_PE_SQL",             "ae89ebf1-7f27-46ee-a28c-eb1f3e0b0e51", "KSA_NDS"),
]

# ──────────────────────────────────────────────────────────────────
# SAG – South African Government  (9 groups)
# ──────────────────────────────────────────────────────────────────
SAG_POLICIES = [
    # ── SAG_DGV  Digital Strategy & Governance ────────────────────
    entry("SAG_DGV_CustomRBAC",         "0015ea4d-1bef-4a42-83a4-621c6455c474", "SAG_DGV"),
    entry("SAG_DGV_RBAC_K8s",           "34c877ad-507e-4c82-993e-3452a6e0ad3c", "SAG_DGV"),
    entry("SAG_DGV_SecurityContact",    "b0d14bf4-d4fb-44cd-94a8-e7c8e6be68a5", "SAG_DGV"),
    entry("SAG_DGV_DiagSettings",       "428256e6-1fac-4f48-a757-df34c2b3336d", "SAG_DGV"),
    entry("SAG_DGV_SQLAudit",           "89099bee-89e0-4b26-a5f4-165451757743", "SAG_DGV"),
    # ── SAG_PDP  Personal Data Protection (POPIA) ─────────────────
    entry("SAG_PDP_CMKDisk",            "702dd420-7fcc-42c5-afe8-4026edd20fe0", "SAG_PDP"),
    entry("SAG_PDP_CMKPostgres",        "18adea5e-f416-4d0f-8aa8-d24321e3e274", "SAG_PDP"),
    entry("SAG_PDP_CMKMySQL",           "0a370ff3-6cab-4e85-8995-295fd854c5b8", "SAG_PDP"),
    entry("SAG_PDP_StorageCMK",         "a4af4a39-4135-4a60-8bf6-d34b2a1d4f2c", "SAG_PDP"),
    entry("SAG_PDP_DeprecatedOwner",    "a8eff44e-8a0e-49e8-b78f-6424f5f5b9a6", "SAG_PDP"),
    entry("SAG_PDP_SecureTransfer",     "404c3081-a854-4457-ae30-26a93ef643f9", "SAG_PDP"),
    entry("SAG_PDP_SQLTDE",             "7595c971-233d-4bcf-bd18-596129188c49", "SAG_PDP"),
    # ── SAG_CLD  Cloud Architecture & Sovereignty ─────────────────
    entry("SAG_CLD_UpdateCheck",        "bd876905-5b84-4f73-ab2d-2e7a7c4568d9", "SAG_CLD"),
    entry("SAG_CLD_SystemUpdates",      "86b3d65f-7626-441e-b690-81a8b71cff60", "SAG_CLD"),
    entry("SAG_CLD_DiagSettings",       "428256e6-1fac-4f48-a757-df34c2b3336d", "SAG_CLD"),
    entry("SAG_CLD_AdaptiveApp",        "8e86a5b6-b9bd-49d1-8e21-4bb8a0862222", "SAG_CLD"),
    entry("SAG_CLD_VMSSUpdates",        "9c276cf7-4e72-4578-b1ef-9d0a3b94f61e", "SAG_CLD"),
    # ── SAG_NET  Network Security ──────────────────────────────────
    entry("SAG_NET_NSG_Subnets",        "e71308d3-144b-4262-b144-efdc3cc90517", "SAG_NET"),
    entry("SAG_NET_NSG_Subnets2",       "2c89a2e5-a4bb-42d5-8a17-af8c0bcc1e79", "SAG_NET"),
    entry("SAG_NET_VMInternet_NSG",     "09024ccc-0c5f-475e-9457-b7c0d9ed487b", "SAG_NET"),
    entry("SAG_NET_PrivateLink",        "ca610c1d-041c-4332-9d88-7ed3094967c7", "SAG_NET"),
    entry("SAG_NET_PE_KeyVault",        "1c06e275-d469-4136-9c30-cc65e2a9bfb6", "SAG_NET"),
    entry("SAG_NET_KV_Firewall",        "1e66c121-a66d-4b99-b523-e2cf4bf16934", "SAG_NET"),
    entry("SAG_NET_RemoteDbgWeb",       "bb91dfba-f30e-4b18-ac8b-4d4e2b57d7c8", "SAG_NET"),
    entry("SAG_NET_RemoteDbgFunc",      "cb510bfd-1cba-4d9f-a1ea-5d395ade7625", "SAG_NET"),
    entry("SAG_NET_PE_SQL",             "ae89ebf1-7f27-46ee-a28c-eb1f3e0b0e51", "SAG_NET"),
    # ── SAG_IAM  Identity & Access Management ─────────────────────
    entry("SAG_IAM_MFA_Owners",         "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b", "SAG_IAM"),
    entry("SAG_IAM_MFA_Write",          "9297c21d-2d0a-4958-8955-00b9f6db96d0", "SAG_IAM"),
    entry("SAG_IAM_MFA_Read",           "e3576e28-8602-4d61-b977-31a496128c53", "SAG_IAM"),
    entry("SAG_IAM_JIT",                "1f314764-cb73-4fc9-b863-8eca98ac36e9", "SAG_IAM"),
    entry("SAG_IAM_MgmtPorts",          "0b15565f-aa9e-48ba-8619-45960f2c314d", "SAG_IAM"),
    entry("SAG_IAM_DeprecatedOwner",    "a8eff44e-8a0e-49e8-b78f-6424f5f5b9a6", "SAG_IAM"),
    entry("SAG_IAM_DeprecatedAccts",    "94e1c2ac-cbbe-4cac-a2b5-389c812dee87", "SAG_IAM"),
    entry("SAG_IAM_AADAdmin_SQL",       "9bc48460-f641-4ef6-b0d7-e6e3c6a51acf", "SAG_IAM"),
    # ── SAG_DAT  Data Security ─────────────────────────────────────
    entry("SAG_DAT_CMKDisk",            "702dd420-7fcc-42c5-afe8-4026edd20fe0", "SAG_DAT"),
    entry("SAG_DAT_SQLTDE",             "7595c971-233d-4bcf-bd18-596129188c49", "SAG_DAT"),
    entry("SAG_DAT_SecureTransfer",     "404c3081-a854-4457-ae30-26a93ef643f9", "SAG_DAT"),
    entry("SAG_DAT_TLSVersion",         "4733ea7b-a883-42fe-8cac-97454c2a9e4a", "SAG_DAT"),
    entry("SAG_DAT_SQLDataClass",       "0b60c0b2-2dc2-4e1c-b5c9-abbed971de53", "SAG_DAT"),
    entry("SAG_DAT_SQLAudit",           "89099bee-89e0-4b26-a5f4-165451757743", "SAG_DAT"),
    entry("SAG_DAT_TempDiskEncrypt",    "0961003e-5a0a-4549-abde-af6a37f2724d", "SAG_DAT"),
    # ── SAG_SEC  Security Operations ──────────────────────────────
    entry("SAG_SEC_SystemUpdates",      "86b3d65f-7626-441e-b690-81a8b71cff60", "SAG_SEC"),
    entry("SAG_SEC_UpdateCheck",        "bd876905-5b84-4f73-ab2d-2e7a7c4568d9", "SAG_SEC"),
    entry("SAG_SEC_VulnSQL",            "e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f", "SAG_SEC"),
    entry("SAG_SEC_VulnSQLMI",          "1b7aa243-0aae-4b6f-a25b-a9e7430c5e29", "SAG_SEC"),
    entry("SAG_SEC_AdaptiveNet",        "83e0d761-a202-44ec-a836-340498e1b9fe", "SAG_SEC"),
    entry("SAG_SEC_EndpointProt",       "ac076320-ddcf-4066-b451-6154267e8ad2", "SAG_SEC"),
    entry("SAG_SEC_VulnVM",             "44e1ad92-5222-4c49-a0f3-0a2b023a47f9", "SAG_SEC"),
    # ── SAG_GOV  Compliance & Governance ──────────────────────────
    entry("SAG_GOV_CustomRBAC",         "0015ea4d-1bef-4a42-83a4-621c6455c474", "SAG_GOV"),
    entry("SAG_GOV_SQLMIPublic",        "9dfea752-dd46-4766-aed1-c355fa93fb91", "SAG_GOV"),
    entry("SAG_GOV_SQLAudit",           "89099bee-89e0-4b26-a5f4-165451757743", "SAG_GOV"),
    entry("SAG_GOV_RBAC_K8s",           "a451c1ef-c6ca-483d-87ed-f49761e3ffb5", "SAG_GOV"),
    # ── SAG_BCM  Business Continuity ──────────────────────────────
    entry("SAG_BCM_BackupVM",           "013e242c-8828-4970-87b3-ab247555486d", "SAG_BCM"),
    entry("SAG_BCM_GeoBackupSQL",       "22bee202-a82f-4305-9a2a-6d7f44d4dedb", "SAG_BCM"),
    entry("SAG_BCM_VMSSUpdates",        "9c276cf7-4e72-4578-b1ef-9d0a3b94f61e", "SAG_BCM"),
    entry("SAG_BCM_DiagSettings",       "428256e6-1fac-4f48-a757-df34c2b3336d", "SAG_BCM"),
]

# ──────────────────────────────────────────────────────────────────
# Oman Government  (10 groups) – remove b79fa14e and 55d1f543
# ──────────────────────────────────────────────────────────────────
OMN_LOG_PARAM = {"logAnalytics": {"value": "[parameters('logAnalytics')]"}}

OMAN_POLICIES = [
    # ── OMN_NET  Network Security ─────────────────────────────────
    entry("OMN_NET_AzFirewall",         "fc5e4038-4584-4632-8c85-c0448d374b2c", "OMN_NET"),
    entry("OMN_NET_NSG_Subnets",        "e71308d3-144b-4262-b144-efdc3cc90517", "OMN_NET"),
    entry("OMN_NET_NSG_Subnets2",       "2c89a2e5-a4bb-42d5-8a17-af8c0bcc1e79", "OMN_NET"),
    entry("OMN_NET_VMInternet_NSG",     "09024ccc-0c5f-475e-9457-b7c0d9ed487b", "OMN_NET"),
    entry("OMN_NET_RemoteDbgWeb",       "bb91dfba-f30e-4b18-ac8b-4d4e2b57d7c8", "OMN_NET"),
    entry("OMN_NET_RemoteDbgFunc",      "cb510bfd-1cba-4d9f-a1ea-5d395ade7625", "OMN_NET"),
    entry("OMN_NET_PE_SQL",             "ae89ebf1-7f27-46ee-a28c-eb1f3e0b0e51", "OMN_NET"),
    # ── OMN_IAM  Identity & Access ────────────────────────────────
    entry("OMN_IAM_RBAC_K8s",           "34c877ad-507e-4c82-993e-3452a6e0ad3c", "OMN_IAM"),
    entry("OMN_IAM_JIT",                "1f314764-cb73-4fc9-b863-8eca98ac36e9", "OMN_IAM"),
    entry("OMN_IAM_MgmtPorts",          "0b15565f-aa9e-48ba-8619-45960f2c314d", "OMN_IAM"),
    entry("OMN_IAM_MFA_Owners",         "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b", "OMN_IAM"),
    entry("OMN_IAM_MFA_Write",          "9297c21d-2d0a-4958-8955-00b9f6db96d0", "OMN_IAM"),
    entry("OMN_IAM_DeprecatedOwner",    "a8eff44e-8a0e-49e8-b78f-6424f5f5b9a6", "OMN_IAM"),
    entry("OMN_IAM_DeprecatedAccts",    "94e1c2ac-cbbe-4cac-a2b5-389c812dee87", "OMN_IAM"),
    entry("OMN_IAM_AADAdmin_SQL",       "9bc48460-f641-4ef6-b0d7-e6e3c6a51acf", "OMN_IAM"),
    # ── OMN_MON  Logging & Monitoring ─────────────────────────────
    # NOTE: b79fa14e removed (DINE v4.0.0 logAnalytics param conflict)
    entry("OMN_MON_ActivityLog",        "818719e5-1338-4776-9a9d-3c31e4df5986", "OMN_MON", OMN_LOG_PARAM),
    entry("OMN_MON_DiagSettings",       "428256e6-1fac-4f48-a757-df34c2b3336d", "OMN_MON"),
    entry("OMN_MON_SQLAudit",           "89099bee-89e0-4b26-a5f4-165451757743", "OMN_MON"),
    entry("OMN_MON_SQLMIAudit",         "b954148f-4c11-4c38-8221-be76711e194e", "OMN_MON"),
    # ── OMN_RSK  Risk Management & Compliance ─────────────────────
    entry("OMN_RSK_VulnSQL",            "e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f", "OMN_RSK"),
    entry("OMN_RSK_VulnSQLMI",          "1b7aa243-0aae-4b6f-a25b-a9e7430c5e29", "OMN_RSK"),
    entry("OMN_RSK_CustomRBAC",         "0015ea4d-1bef-4a42-83a4-621c6455c474", "OMN_RSK"),
    entry("OMN_RSK_SecurityContact",    "b0d14bf4-d4fb-44cd-94a8-e7c8e6be68a5", "OMN_RSK"),
    # ── OMN_DAT  Data Protection & Privacy ────────────────────────
    # NOTE: 55d1f543 removed (DINE Cognitive Services diag – logAnalytics param conflict)
    entry("OMN_DAT_SQLDataClass",       "0b60c0b2-2dc2-4e1c-b5c9-abbed971de53", "OMN_DAT"),
    entry("OMN_DAT_SQLTDE",             "7595c971-233d-4bcf-bd18-596129188c49", "OMN_DAT"),
    entry("OMN_DAT_SecureTransfer",     "404c3081-a854-4457-ae30-26a93ef643f9", "OMN_DAT"),
    entry("OMN_DAT_TLSVersion",         "4733ea7b-a883-42fe-8cac-97454c2a9e4a", "OMN_DAT"),
    entry("OMN_DAT_CMKDisk",            "702dd420-7fcc-42c5-afe8-4026edd20fe0", "OMN_DAT"),
    entry("OMN_DAT_CMKPostgres",        "18adea5e-f416-4d0f-8aa8-d24321e3e274", "OMN_DAT"),
    entry("OMN_DAT_CMKMySQL",           "0a370ff3-6cab-4e85-8995-295fd854c5b8", "OMN_DAT"),
    entry("OMN_DAT_PrivateLink",        "ca610c1d-041c-4332-9d88-7ed3094967c7", "OMN_DAT"),
    entry("OMN_DAT_StorageCMK",         "a4af4a39-4135-4a60-8bf6-d34b2a1d4f2c", "OMN_DAT"),
    entry("OMN_DAT_CogSvcCMK",         "67121cc7-4b87-484c-b351-8d39bda0a285", "OMN_DAT"),
    entry("OMN_DAT_TempDiskEncrypt",    "0961003e-5a0a-4549-abde-af6a37f2724d", "OMN_DAT"),
    # ── OMN_END  Endpoint Protection ──────────────────────────────
    entry("OMN_END_BackupVM",           "013e242c-8828-4970-87b3-ab247555486d", "OMN_END"),
    entry("OMN_END_EndpointProt",       "ac076320-ddcf-4066-b451-6154267e8ad2", "OMN_END"),
    entry("OMN_END_AdaptiveApp",        "8e86a5b6-b9bd-49d1-8e21-4bb8a0862222", "OMN_END"),
    # ── OMN_VUL  Vulnerability Management ─────────────────────────
    entry("OMN_VUL_SystemUpdates",      "86b3d65f-7626-441e-b690-81a8b71cff60", "OMN_VUL"),
    entry("OMN_VUL_UpdateCheck",        "bd876905-5b84-4f73-ab2d-2e7a7c4568d9", "OMN_VUL"),
    entry("OMN_VUL_VMSSUpdates",        "9c276cf7-4e72-4578-b1ef-9d0a3b94f61e", "OMN_VUL"),
    entry("OMN_VUL_AdaptiveNet",        "83e0d761-a202-44ec-a836-340498e1b9fe", "OMN_VUL"),
    entry("OMN_VUL_VulnVM",             "44e1ad92-5222-4c49-a0f3-0a2b023a47f9", "OMN_VUL"),
    # ── OMN_BCM  Business Continuity & DR ─────────────────────────
    entry("OMN_BCM_BackupVM",           "013e242c-8828-4970-87b3-ab247555486d", "OMN_BCM"),
    entry("OMN_BCM_GeoBackupSQL",       "22bee202-a82f-4305-9a2a-6d7f44d4dedb", "OMN_BCM"),
    entry("OMN_BCM_VMSSUpdates",        "9c276cf7-4e72-4578-b1ef-9d0a3b94f61e", "OMN_BCM"),
    # ── OMN_INC  Incident Response ─────────────────────────────────
    entry("OMN_INC_DiagSettings",       "428256e6-1fac-4f48-a757-df34c2b3336d", "OMN_INC"),
    entry("OMN_INC_SQLAudit",           "89099bee-89e0-4b26-a5f4-165451757743", "OMN_INC"),
    entry("OMN_INC_SecurityContact",    "b0d14bf4-d4fb-44cd-94a8-e7c8e6be68a5", "OMN_INC"),
    entry("OMN_INC_SQLMIAudit",         "b954148f-4c11-4c38-8221-be76711e194e", "OMN_INC"),
    # ── OMN_GOV  Cybersecurity Governance ─────────────────────────
    entry("OMN_GOV_SQLDataClass",       "0b60c0b2-2dc2-4e1c-b5c9-abbed971de53", "OMN_GOV"),
    entry("OMN_GOV_CustomRBAC",         "0015ea4d-1bef-4a42-83a4-621c6455c474", "OMN_GOV"),
    entry("OMN_GOV_RBAC_K8s",           "34c877ad-507e-4c82-993e-3452a6e0ad3c", "OMN_GOV"),
    entry("OMN_GOV_SecurityContact",    "b0d14bf4-d4fb-44cd-94a8-e7c8e6be68a5", "OMN_GOV"),
]

# ──────────────────────────────────────────────────────────────────
# Write files
# ──────────────────────────────────────────────────────────────────
def write(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Written {len(data):3d} policies → {path}")

FRAMEWORKS = [
    ("SAMA",                   SAMA_POLICIES,  "SAMA"),
    ("ADHICS",                 ADHICS_POLICIES,"ADHICS"),
    ("Saudi Arabia Government",KSA_POLICIES,   "KSA"),
    ("South African Government",SAG_POLICIES,  "SAG"),
    ("Oman Government",        OMAN_POLICIES,  "Oman"),
]

print("\nExpanding policies.json for all 5 frameworks...")
for fw_dir, policies, label in FRAMEWORKS:
    path = os.path.join(BASE, fw_dir, "policies.json")
    write(path, policies)
    # Count per-group coverage
    groups = {}
    for p in policies:
        glist = p.get("GroupNames") or p.get("groupNames") or []
        for g in glist:
            groups[g] = groups.get(g, 0) + 1
    print(f"    {label} group coverage: {groups}")
    print()

print("Done.\n")
