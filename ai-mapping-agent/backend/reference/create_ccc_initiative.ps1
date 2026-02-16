<#
Creates a custom initiative covering the CCC core policy bundle (PNA/PE/CMK/TLS/WAF/VA/KV purge/disk enc) and assigns it at subscription scope.
Prereqs: Az PowerShell modules; Policy Contributor at scope.
Usage:
  pwsh ./create_ccc_initiative.ps1 -SubscriptionId <subId> -Location <region> \
    [-InitiativeName CCC_Core] [-AssignmentSuffix ccc] \
    [-PrivateEndpointSubnetId "/subscriptions/.../subnets/pe"] \
    [-AllowedEncryptionSets "/subscriptions/.../diskEncryptionSets/des1","/subscriptions/.../des2"]
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [string]$SubscriptionId,
  [Parameter(Mandatory = $true)] [string]$Location,
  [string]$InitiativeName = "CCC_Core",
  [string]$AssignmentSuffix = "ccc",
  [string]$PrivateEndpointSubnetId,
  [string[]]$AllowedEncryptionSets,
  [string]$LogAnalyticsWorkspaceId,
  [string]$RecoveryServicesVaultId,
  [string]$RequiredTagName = "costCenter",
  [string]$RequiredTagValue = "required",
  [string[]]$AllowedLocations = @("uaenorth")
)

$scope = "/subscriptions/$SubscriptionId"

# Built-in policy definition IDs used in the CCC bundle
$defs = [ordered]@{
  Storage_PrivateLink          = "/providers/Microsoft.Authorization/policyDefinitions/1604f626-4d8d-4124-8bb8-b1e5f95562de"
  Storage_RestrictNetworkAccess= "/providers/Microsoft.Authorization/policyDefinitions/34c877ad-507e-4c82-993e-3452a6e0ad3c"
  PNA_EventHub                 = "/providers/Microsoft.Authorization/policyDefinitions/0602787f-9896-402a-a6e1-39ee63ee435e"
  PNA_DataFactory              = "/providers/Microsoft.Authorization/policyDefinitions/08b1442b-7789-4130-8506-4f99a97226a7"
  PNA_Databricks               = "/providers/Microsoft.Authorization/policyDefinitions/0e7849de-b939-4c50-ab48-fc6b0f5eeba2"
  PNA_KeyVault                 = "/providers/Microsoft.Authorization/policyDefinitions/19ea9d63-adee-4431-a95e-1913c6c1c75f"
  PNA_Cosmos                   = "/providers/Microsoft.Authorization/policyDefinitions/797b37f7-06b8-444c-b1ad-fc62867f335a"
  PE_KeyVault                  = "/providers/Microsoft.Authorization/policyDefinitions/9d4fad1f-5189-4a42-b29e-cf7929c6b6df"
  PE_RecoveryServices          = "/providers/Microsoft.Authorization/policyDefinitions/11e3da8c-1d68-4392-badd-0ff3c43ab5b0"
  CMK_Storage                  = "/providers/Microsoft.Authorization/policyDefinitions/6fac406b-40ca-413b-bf8e-0bf964659c25"
  CMK_SQL                      = "/providers/Microsoft.Authorization/policyDefinitions/0a370ff3-6cab-4e85-8995-295fd854c5b8"
  TLS_AppService               = "/providers/Microsoft.Authorization/policyDefinitions/014664e7-e348-41a3-aeb9-566e4ff6a9df"
  TLS_Functions                = "/providers/Microsoft.Authorization/policyDefinitions/1f01f1c7-539c-49b5-9ef4-d4ffa37d22e0"
  WAF_FrontDoor                = "/providers/Microsoft.Authorization/policyDefinitions/055aa869-bc98-4af8-bafc-23f1ab6ffe2c"
  WAF_AppGateway_Mode          = "/providers/Microsoft.Authorization/policyDefinitions/12430be1-6cc8-4527-a9a8-e3d38f250096"
  VA_Machines                  = "/providers/Microsoft.Authorization/policyDefinitions/501541f7-f7e7-4cd6-868c-4190fdad3ac9"
  VA_SQL                       = "/providers/Microsoft.Authorization/policyDefinitions/ef2a8f2a-b3d9-49cd-a8a8-9a3aaaf647d9"
  KeyVault_Purge               = "/providers/Microsoft.Authorization/policyDefinitions/c39ba22d-4428-4149-b981-70acb31fc383"
  DiskEncryption_DES           = "/providers/Microsoft.Authorization/policyDefinitions/d461a302-a187-421a-89ac-84acdb4edc04"
  BatchPool_DiskEncryption     = "/providers/Microsoft.Authorization/policyDefinitions/1760f9d4-7206-436e-a28f-d9f3a5c8a227"

  # Extended set (fill in/replace as needed; leave blank to skip)
  Require_Tag                  = "2a0e14a6-b0a6-4fab-991a-187a4f81c498"  # Require tag and its value (BuiltIn)
  Allowed_Locations            = "e56962a6-4747-49cd-b67b-bf8b01975c4c"  # Allowed locations (resources)
  Deny_PublicIP                = "1f3afdf9-d0c9-4c3d-847f-89da613e70a8"  # Deny public IP on NICs
  DDoS_VNet                    = "94de2ad3-e0c1-4caf-ad78-5d47bbc83d3d"  # VNet should be protected by DDoS
  DDoS_Enable                  = "a7aca53f-2ed4-4466-a25e-0b45ade68efd"  # DDoS plan enabled
  DDoS_PublicIP_Logs           = "752154a7-1e0f-45c6-a880-ac75a7e4f648"  # Public IPs should have DDoS resource logs
  AMA_Linux_VM                 = "1afdc4b6-581a-45fb-b630-f1e6051e3e7a"  # AMA on Linux VMs
  AMA_Windows_VM               = "c02729e5-e5e7-4458-97fa-2b5ad0661f28"  # AMA on Windows VMs
  AMA_Linux_VMSS               = "32ade945-311e-4249-b8a4-a549924234d7"  # AMA on Linux VMSS
  AMA_Windows_VMSS             = "3672e6f7-a74d-4763-b138-fcf332042f8f"  # AMA on Windows VMSS
  AMA_Linux_Arc                = "f17d891d-ff20-46f2-bad3-9e0a5403a4d3"  # AMA on Linux Arc
  AMA_Windows_Arc              = "ec621e21-8b48-403d-a549-fc9023d4747f"  # AMA on Windows Arc
  AMA_SQL_VM                   = "f91991d1-5383-4c95-8ee5-5ac423dd8bb1"  # AMA on SQL VM
  Marketplace_Disable          = ""                                     # Placeholder: set to built-in that blocks marketplace images/types
  Diagnostics_Subscription_LA  = ""                                     # Placeholder: Deploy diagnostic settings for Activity Log to LA
  Backup_VM                    = ""                                     # Placeholder: Configure backup on VMs with vault/policy
  EndpointProtection_VM        = ""                                     # Placeholder: Deploy endpoint protection for Windows/Linux VMs
  JIT_VM                       = ""                                     # Placeholder: Deploy JIT network access on VMs
  PNA_Generic_Deny             = ""                                     # Placeholder: deny public network access generic (catch-all)
}

function Ensure-AzContext {
  param([string]$SubId)
  $ctx = Get-AzContext -ErrorAction SilentlyContinue
  if (-not $ctx -or $ctx.Subscription.Id -ne $SubId) {
    Connect-AzAccount -ErrorAction Stop | Out-Null
    Set-AzContext -SubscriptionId $SubId -ErrorAction Stop | Out-Null
  }
}

# Initiative parameter schema (only two params are needed for the set)
$initiativeParameters = @{
  PrivateEndpointSubnetId = @{
    type = "String"
    metadata = @{ displayName = "Private endpoint subnet ID"; description = "Subnet resource ID to use for Key Vault private endpoints." }
  }
  AllowedEncryptionSets = @{
    type = "Array"
    metadata = @{ displayName = "Allowed Disk Encryption Sets"; description = "List of disk encryption set resource IDs allowed for disks." }
  }
  LogAnalyticsWorkspaceId = @{
    type = "String"
    metadata = @{ displayName = "Log Analytics workspace"; description = "Workspace resource ID for diagnostic settings." }
  }
  RecoveryServicesVaultId = @{
    type = "String"
    metadata = @{ displayName = "Recovery Services vault"; description = "Vault resource ID for VM backup." }
  }
  AllowedLocations = @{
    type = "Array"
    metadata = @{ displayName = "Allowed locations"; description = "List of allowed Azure regions." }
    defaultValue = $AllowedLocations
  }
  RequiredTagName = @{
    type = "String"
    metadata = @{ displayName = "Required tag name"; description = "Tag name to enforce." }
    defaultValue = $RequiredTagName
  }
  RequiredTagValue = @{
    type = "String"
    metadata = @{ displayName = "Required tag value"; description = "Tag value to enforce." }
    defaultValue = $RequiredTagValue
  }
}

function Add-PolicyRef {
  param(
    [string]$Id,
    [string]$RefId,
    [string[]]$Groups,
    [hashtable]$Params = @{}
  )
  if ([string]::IsNullOrWhiteSpace($Id)) { return $null }
  return @{ PolicyDefinitionId = ("/providers/Microsoft.Authorization/policyDefinitions/" + ($Id -replace "^/providers/Microsoft\.Authorization/policyDefinitions/", "")); PolicyDefinitionReferenceId = $RefId; Parameters = $Params; GroupNames = $Groups }
}

# Policy references with parameter wiring back to initiative parameters
$policyDefinitions = @()
$policyDefinitions += Add-PolicyRef -Id $defs.Storage_RestrictNetworkAccess -RefId "pna-storage" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_EventHub                -RefId "pna-eventhub" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_DataFactory             -RefId "pna-datafactory" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_Databricks              -RefId "pna-databricks" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_KeyVault                -RefId "pna-keyvault" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_Cosmos                  -RefId "pna-cosmos" -Groups @("PNA")

$policyDefinitions += Add-PolicyRef -Id $defs.Storage_PrivateLink         -RefId "pe-storage" -Groups @("PrivateEndpoints")
$policyDefinitions += Add-PolicyRef -Id $defs.PE_KeyVault                 -RefId "pe-keyvault" -Groups @("PrivateEndpoints") -Params @{ privateEndpointSubnetId = @{ value = "[parameters(''PrivateEndpointSubnetId'')]" } }
$policyDefinitions += Add-PolicyRef -Id $defs.PE_RecoveryServices         -RefId "pe-recoveryservices" -Groups @("PrivateEndpoints")

$policyDefinitions += Add-PolicyRef -Id $defs.CMK_Storage                 -RefId "cmk-storage" -Groups @("CMK")
$policyDefinitions += Add-PolicyRef -Id $defs.CMK_SQL                     -RefId "cmk-sql" -Groups @("CMK")

$policyDefinitions += Add-PolicyRef -Id $defs.TLS_AppService              -RefId "tls-appservice" -Groups @("TLS")
$policyDefinitions += Add-PolicyRef -Id $defs.TLS_Functions               -RefId "tls-functions" -Groups @("TLS")

$policyDefinitions += Add-PolicyRef -Id $defs.WAF_FrontDoor               -RefId "waf-frontdoor" -Groups @("WAF")
$policyDefinitions += Add-PolicyRef -Id $defs.WAF_AppGateway_Mode         -RefId "waf-appgw" -Groups @("WAF")

$policyDefinitions += Add-PolicyRef -Id $defs.VA_Machines                 -RefId "va-machines" -Groups @("VulnerabilityAssessment")
$policyDefinitions += Add-PolicyRef -Id $defs.VA_SQL                      -RefId "va-sql" -Groups @("VulnerabilityAssessment")

$policyDefinitions += Add-PolicyRef -Id $defs.KeyVault_Purge              -RefId "kv-purge" -Groups @("KeyVault")

$policyDefinitions += Add-PolicyRef -Id $defs.DiskEncryption_DES          -RefId "disk-des" -Groups @("Disk") -Params @{ allowedEncryptionSets = @{ value = "[parameters(''AllowedEncryptionSets'')]" } }
$policyDefinitions += Add-PolicyRef -Id $defs.BatchPool_DiskEncryption    -RefId "batch-disk" -Groups @("Disk")

# Extended/optional
$policyDefinitions += Add-PolicyRef -Id $defs.Require_Tag                 -RefId "tag-require" -Groups @("Tagging") -Params @{ tagName = @{ value = "[parameters(''RequiredTagName'')]" }; tagValue = @{ value = "[parameters(''RequiredTagValue'')]" } }
$policyDefinitions += Add-PolicyRef -Id $defs.Allowed_Locations           -RefId "loc-allowed" -Groups @("Location") -Params @{ listOfAllowedLocations = @{ value = "[parameters(''AllowedLocations'')]" } }
$policyDefinitions += Add-PolicyRef -Id $defs.Deny_PublicIP               -RefId "deny-publicip" -Groups @("Network")
$policyDefinitions += Add-PolicyRef -Id $defs.DDoS_VNet                   -RefId "ddos-vnet" -Groups @("DDoS")
$policyDefinitions += Add-PolicyRef -Id $defs.DDoS_Enable                 -RefId "ddos-enable" -Groups @("DDoS")
$policyDefinitions += Add-PolicyRef -Id $defs.DDoS_PublicIP_Logs          -RefId "ddos-publicip-logs" -Groups @("DDoS")
$policyDefinitions += Add-PolicyRef -Id $defs.AMA_Linux_VM                -RefId "ama-linux-vm" -Groups @("Monitoring")
$policyDefinitions += Add-PolicyRef -Id $defs.AMA_Windows_VM              -RefId "ama-windows-vm" -Groups @("Monitoring")
$policyDefinitions += Add-PolicyRef -Id $defs.AMA_Linux_VMSS              -RefId "ama-linux-vmss" -Groups @("Monitoring")
$policyDefinitions += Add-PolicyRef -Id $defs.AMA_Windows_VMSS            -RefId "ama-windows-vmss" -Groups @("Monitoring")
$policyDefinitions += Add-PolicyRef -Id $defs.AMA_Linux_Arc               -RefId "ama-linux-arc" -Groups @("Monitoring")
$policyDefinitions += Add-PolicyRef -Id $defs.AMA_Windows_Arc             -RefId "ama-windows-arc" -Groups @("Monitoring")
$policyDefinitions += Add-PolicyRef -Id $defs.AMA_SQL_VM                  -RefId "ama-sql-vm" -Groups @("Monitoring")
$policyDefinitions += Add-PolicyRef -Id $defs.Marketplace_Disable         -RefId "marketplace-disable" -Groups @("Marketplace")
$policyDefinitions += Add-PolicyRef -Id $defs.Diagnostics_Subscription_LA -RefId "diag-subscription" -Groups @("Diagnostics") -Params @{ workspaceId = @{ value = "[parameters(''LogAnalyticsWorkspaceId'')]" } }
$policyDefinitions += Add-PolicyRef -Id $defs.Backup_VM                   -RefId "backup-vm" -Groups @("Backup") -Params @{ vaultId = @{ value = "[parameters(''RecoveryServicesVaultId'')]" } }
$policyDefinitions += Add-PolicyRef -Id $defs.EndpointProtection_VM       -RefId "ep-vm" -Groups @("EndpointProtection") -Params @{}
$policyDefinitions += Add-PolicyRef -Id $defs.JIT_VM                      -RefId "jit-vm" -Groups @("JIT") -Params @{}
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_Generic_Deny            -RefId "pna-generic" -Groups @("PNA")

$groups = @(
  @{ Name = "PNA" },
  @{ Name = "PrivateEndpoints" },
  @{ Name = "CMK" },
  @{ Name = "TLS" },
  @{ Name = "WAF" },
  @{ Name = "VulnerabilityAssessment" },
  @{ Name = "KeyVault" },
  @{ Name = "Disk" },
  @{ Name = "Tagging" },
  @{ Name = "Location" },
  @{ Name = "Network" },
  @{ Name = "DDoS" },
  @{ Name = "Monitoring" },
  @{ Name = "Marketplace" },
  @{ Name = "Diagnostics" },
  @{ Name = "Backup" },
  @{ Name = "EndpointProtection" },
  @{ Name = "JIT" }
)

Ensure-AzContext -SubId $SubscriptionId

$metadata = @{ version = "1.0.0-preview"; category = "Regulatory Compliance" }

Write-Host "Creating/updating initiative $InitiativeName" -ForegroundColor Green
New-AzPolicySetDefinition -Name $InitiativeName `
  -DisplayName "$InitiativeName (CCC Core)" `
  -Description "CCC core bundle: PNA, private endpoints, CMK, TLS min, WAF, VA, KV purge, disk encryption." `
  -Metadata ($metadata | ConvertTo-Json -Depth 5) `
  -PolicyDefinition $policyDefinitions `
  -GroupDefinition $groups `
  -Parameter $initiativeParameters `
  -ErrorAction Stop | Out-Null

$initiativeId = "$scope/providers/Microsoft.Authorization/policySetDefinitions/$InitiativeName"
$assignmentName = "$InitiativeName-assign-$AssignmentSuffix"

# Build assignment params for required wires
$assignmentParams = @{}
if ($PrivateEndpointSubnetId) {
  $assignmentParams["PrivateEndpointSubnetId"] = @{ value = $PrivateEndpointSubnetId }
}
if ($AllowedEncryptionSets) {
  $assignmentParams["AllowedEncryptionSets"] = @{ value = $AllowedEncryptionSets }
}
if ($AllowedLocations) {
  $assignmentParams["AllowedLocations"] = @{ value = $AllowedLocations }
}

Write-Host "Assigning initiative $assignmentName" -ForegroundColor Green
New-AzPolicyAssignment -Name $assignmentName `
  -DisplayName "$InitiativeName (CCC Core)" `
  -Scope $scope `
  -PolicySetDefinition $initiativeId `
  -Location $Location `
  -IdentityType SystemAssigned `
  -PolicyParameterObject $assignmentParams `
  -EnforcementMode Default `
  -ErrorAction Stop | Out-Null

Write-Host "Done. View in Policy -> Definitions (initiative) and Policy -> Assignments/Compliance." -ForegroundColor Green
