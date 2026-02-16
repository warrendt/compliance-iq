# CCC Policy Scripts

This folder contains PowerShell helpers to deploy the CCC control bundle on Azure Policy.

## Scripts
- `deploy_ccc_policies.ps1`: Assigns the core CCC built-in policies individually at subscription scope.
- `create_ccc_initiative.ps1`: Creates (or updates) a custom initiative that bundles the same CCC policies (plus optional extensions) and assigns it at subscription scope with a managed identity.
- `create_ccc_initiative_quick.ps1`: Minimal initiative with defaults (no Log Analytics, PE subnet, or DES allowlist) for fast smoke testing; now includes allowed locations, DDoS protections, and AMA rollouts.

## Prereqs
- Az PowerShell modules installed (Az.Resources).
- Permissions: Policy Contributor (or higher) on the target subscription.
- Policies that need parameters are skipped if inputs are missing (PE subnet, disk encryption set list).

## Quick start (parameter-free smoke test)
```pwsh
pwsh ./create_ccc_initiative_quick.ps1 \
  -SubscriptionId <subId> \
  -Location <region> \
  -InitiativeName CCC_Core_Quick \
  -AssignmentSuffix quick \
  -AllowedLocations uaenorth
```
- No extra infra parameters needed; assigns a trimmed bundle: PNA, private endpoints (storage + RSV), CMK, TLS mins, WAF, VA, Key Vault purge, Batch pool disk encryption, allowed locations (resources), DDoS (plan + vNet association + public IP logs), and AMA for VM/VMSS/Arc/SQL VM.
- Use this to validate pipeline/permissions before wiring subnet/workspace/vault inputs.
- Optional parameters require existing resources:
  - Private endpoint subnet ID (for Key Vault PE policy).
  - Disk Encryption Set IDs (for disk encryption allowlist policy).
  - Log Analytics workspace ID (for diagnostics extensions).
  - Recovery Services vault ID (for backup extensions).

## Quick start (initiative recommended)
```pwsh
pwsh ./create_ccc_initiative.ps1 \
  -SubscriptionId <subId> \
  -Location <region> \
  -InitiativeName CCC_Core \
  -AssignmentSuffix ccc \
  -PrivateEndpointSubnetId "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/<subnet>" \
  -AllowedEncryptionSets "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Compute/diskEncryptionSets/<desName>" \
  -LogAnalyticsWorkspaceId "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<ws>" \
  -RecoveryServicesVaultId "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.RecoveryServices/vaults/<vault>" \
  -RequiredTagName "costCenter" \
  -RequiredTagValue "required" \
  -AllowedLocations uaenorth
```
- The script creates the initiative definition (custom) and assigns it with a system-assigned managed identity. Any optional policy with a blank definition ID is skipped.
- Replace placeholder definition IDs in the script for marketplace disable, diagnostics, backup, endpoint protection, JIT, and generic PNA deny as needed.

## Quick start (individual assignments)
```pwsh
pwsh ./deploy_ccc_policies.ps1 \
  -SubscriptionId <subId> \
  -Location <region> \
  -AssignmentSuffix ccc \
  -PrivateEndpointSubnetId "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/<subnet>" \
  -AllowedEncryptionSets "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Compute/diskEncryptionSets/<desName>"
```
- Assigns each built-in policy separately (PNA, private endpoints, CMK, TLS minimums, WAF, vulnerability assessment, Key Vault purge protection, disk encryption). Managed identity is applied to cover DeployIfNotExists/Modify effects.
- Policies that need parameters are skipped if inputs are missing (PE subnet, disk encryption set list).

## What gets enforced (core set)
- Public network access deny: Storage, Event Hubs, Data Factory, Databricks, Key Vault, Cosmos DB.
- Private endpoints: Storage, Key Vault (requires subnet ID), Recovery Services Vaults.
- Customer-managed keys: Storage, SQL.
- TLS minimums: App Service, Functions.
- WAF: Front Door, App Gateway mode.
- Vulnerability assessment: VMs, SQL.
- Key Vault: purge protection.
- Disk encryption: allowed Disk Encryption Sets, Batch pool disk encryption.
- DDoS: plan enablement, vNet protection, public IP diagnostics.
- Monitoring: Azure Monitor Agent rollout for VMs/VMSS/Arc/SQL VM.

## Policy groups (initiative definitions)
- Core: PNA, PrivateEndpoints, CMK, TLS, WAF, VulnerabilityAssessment, KeyVault, Disk, Location.
- Added: DDoS, Monitoring (for AMA rollout).

## Quick compliance check (CLI)
Summarize compliance for the initiative assignment:
```bash
az policy state summarize \
  --subscription <subId> \
  --name "Cloud Cybersecurity Controls-assign-ccc"
```
View individual non-compliant resources:
```bash
az policy state list \
  --subscription <subId> \
  --filter "policyAssignmentName eq 'Cloud Cybersecurity Controls-assign-ccc' and complianceState eq 'NonCompliant'" \
  --query "[].[resourceId, policyDefinitionName, complianceState]" -o table
```

## Portal navigation (compliance)
- Definitions: Azure Portal → Policy → Definitions → filter Scope to the subscription → Initiative definitions (Custom) → select the CCC initiative.
- Assignment status: Policy → Assignments → find `Cloud Cybersecurity Controls-assign-ccc` → Compliance tab for summary.
- Per-resource details: Policy → Compliance → select the CCC initiative → drill into non-compliant resources.

## Log Analytics (policy compliance) queries
Use the PolicyInsights table after enabling diagnostic export to Log Analytics.
- Non-compliant counts by policy definition:
```kusto
PolicyResources
| where ComplianceState == "NonCompliant"
| summarize nonCompliantResources = dcount(ResourceId) by PolicyDefinitionName
| order by nonCompliantResources desc
```
- Non-compliant resources for this assignment only:
```kusto
let assignmentName = "Cloud Cybersecurity Controls-assign-ccc";
PolicyResources
| where PolicyAssignmentName == assignmentName and ComplianceState == "NonCompliant"
| project TimeGenerated, ResourceId, PolicyDefinitionName, ComplianceState
| order by TimeGenerated desc
```

### Enable Policy Insights export to Log Analytics
- Portal: Policy → Diagnostics settings → select the subscription → add diagnostic setting → send `PolicyInsights` to your Log Analytics workspace.
- CLI example:
```bash
az monitor diagnostic-settings create \
  --name policy-insights-to-la \
  --resource "/subscriptions/<subId>" \
  --workspace "/subscriptions/<subId>/resourceGroups/<rg>/providers/Microsoft.OperationalInsights/workspaces/<workspace>" \
  --logs '[{"category":"PolicyInsights","enabled":true}]'
```

## Compliance timing and blades to watch
- Propagation: New assignments typically take 5–15 minutes to show in Compliance; DeployIfNotExists/Modify effects may take longer to remediate.
- Remediation jobs: For deploy effects, trigger remediation if resources pre-exist. Portal: Policy → Remediation → select the assignment → Start remediation.
- Key blades: Policy → Assignments (status), Policy → Compliance (initiative view), Policy → Remediation (job runs), Activity Log (deploy failures), Log Analytics (PolicyInsights) if enabled.
- Common delays: newly created resources may appear non-compliant until policy evaluation cycles run; wait a few minutes or trigger remediation.

## Extensions (initiative only, optional)
- Tagging baseline: require a specific tag name/value.
- Network: deny public IP on NICs; optional generic PNA deny.
- Diagnostics: deploy subscription Activity Log diagnostic settings to Log Analytics (needs workspace ID).
- Backup: configure VM backup (needs vault ID and policy, set definition ID in script).
- Endpoint protection: deploy antimalware/EDR to VMs (set definition ID in script).
- JIT: deploy Just-In-Time VM access (set definition ID in script).
- Marketplace: disable unapproved marketplace images/types (set definition ID in script).

## Where to see results
- Initiative/definition: Azure Portal → Policy → Definitions → Initiative definitions (Custom).
- Assignment and compliance: Azure Portal → Policy → Assignments and Policy → Compliance. Compliance may take several minutes to populate after assignment.
