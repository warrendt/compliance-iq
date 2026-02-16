<#
Quick CCC initiative: no Log Analytics, no PE subnet, no DES allowlist parameters. Safe to run immediately for smoke testing.
Assigns a custom initiative and an assignment with system-assigned identity.
Usage:
  pwsh ./create_ccc_initiative_quick.ps1 -SubscriptionId <subId> -Location <region> [-InitiativeName CCC_Core_Quick] [-AssignmentSuffix quick]
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [string]$SubscriptionId,
  [Parameter(Mandatory = $true)] [string]$Location,
  [string]$InitiativeName = "CCC_Core_Quick",
  [string]$AssignmentSuffix = "quick",
  [string[]]$AllowedLocations = @("uaenorth")
)

$scope = "/subscriptions/$SubscriptionId"
$safeName = ($InitiativeName -replace "[^A-Za-z0-9-]", "-")

$defs = [ordered]@{
  Storage_PrivateLink          = "/providers/Microsoft.Authorization/policyDefinitions/1604f626-4d8d-4124-8bb8-b1e5f95562de"
  Storage_RestrictNetworkAccess= "/providers/Microsoft.Authorization/policyDefinitions/34c877ad-507e-4c82-993e-3452a6e0ad3c"
  PNA_EventHub                 = "/providers/Microsoft.Authorization/policyDefinitions/0602787f-9896-402a-a6e1-39ee63ee435e"
  PNA_DataFactory              = "/providers/Microsoft.Authorization/policyDefinitions/08b1442b-7789-4130-8506-4f99a97226a7"
  PNA_Databricks               = "/providers/Microsoft.Authorization/policyDefinitions/0e7849de-b939-4c50-ab48-fc6b0f5eeba2"
  PNA_KeyVault                 = "/providers/Microsoft.Authorization/policyDefinitions/19ea9d63-adee-4431-a95e-1913c6c1c75f"
  PNA_Cosmos                   = "/providers/Microsoft.Authorization/policyDefinitions/797b37f7-06b8-444c-b1ad-fc62867f335a"
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
  BatchPool_DiskEncryption     = "/providers/Microsoft.Authorization/policyDefinitions/1760f9d4-7206-436e-a28f-d9f3a5c8a227"
  DDoS_VNet                    = "/providers/Microsoft.Authorization/policyDefinitions/94de2ad3-e0c1-4caf-ad78-5d47bbc83d3d"
  DDoS_Enable                  = "/providers/Microsoft.Authorization/policyDefinitions/a7aca53f-2ed4-4466-a25e-0b45ade68efd"
  DDoS_PublicIP_Logs           = "/providers/Microsoft.Authorization/policyDefinitions/752154a7-1e0f-45c6-a880-ac75a7e4f648"
  AMA_Linux_VM                 = "/providers/Microsoft.Authorization/policyDefinitions/1afdc4b6-581a-45fb-b630-f1e6051e3e7a"
  AMA_Windows_VM               = "/providers/Microsoft.Authorization/policyDefinitions/c02729e5-e5e7-4458-97fa-2b5ad0661f28"
  AMA_Linux_VMSS               = "/providers/Microsoft.Authorization/policyDefinitions/32ade945-311e-4249-b8a4-a549924234d7"
  AMA_Windows_VMSS             = "/providers/Microsoft.Authorization/policyDefinitions/3672e6f7-a74d-4763-b138-fcf332042f8f"
  AMA_Linux_Arc                = "/providers/Microsoft.Authorization/policyDefinitions/f17d891d-ff20-46f2-bad3-9e0a5403a4d3"
  AMA_Windows_Arc              = "/providers/Microsoft.Authorization/policyDefinitions/ec621e21-8b48-403d-a549-fc9023d4747f"
  AMA_SQL_VM                   = "/providers/Microsoft.Authorization/policyDefinitions/f91991d1-5383-4c95-8ee5-5ac423dd8bb1"
}

function Ensure-AzContext {
  param([string]$SubId)
  $ctx = Get-AzContext -ErrorAction SilentlyContinue
  if (-not $ctx -or $ctx.Subscription.Id -ne $SubId) {
    Connect-AzAccount -ErrorAction Stop | Out-Null
    Set-AzContext -SubscriptionId $SubId -ErrorAction Stop | Out-Null
  }
}

function Add-PolicyRef {
  param(
    [string]$Id,
    [string]$RefId,
    [string[]]$Groups,
    [hashtable]$Params = @{}
  )
  return @{ PolicyDefinitionId = $Id; PolicyDefinitionReferenceId = $RefId; Parameters = $Params; GroupNames = $Groups }
}

$policyDefinitions = @()
$policyDefinitions += Add-PolicyRef -Id $defs.Storage_RestrictNetworkAccess -RefId "pna-storage" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_EventHub                -RefId "pna-eventhub" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_DataFactory             -RefId "pna-datafactory" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_Databricks              -RefId "pna-databricks" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_KeyVault                -RefId "pna-keyvault" -Groups @("PNA")
$policyDefinitions += Add-PolicyRef -Id $defs.PNA_Cosmos                  -RefId "pna-cosmos" -Groups @("PNA")

$policyDefinitions += Add-PolicyRef -Id $defs.Storage_PrivateLink         -RefId "pe-storage" -Groups @("PrivateEndpoints")
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
$policyDefinitions += Add-PolicyRef -Id $defs.BatchPool_DiskEncryption    -RefId "batch-disk" -Groups @("Disk")

$policyDefinitions += Add-PolicyRef -Id "/providers/Microsoft.Authorization/policyDefinitions/e56962a6-4747-49cd-b67b-bf8b01975c4c" -RefId "loc-allowed" -Groups @("Location") -Params @{ listOfAllowedLocations = @{ value = $AllowedLocations } }
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

# Drop any null entries
$policyDefinitions = $policyDefinitions | Where-Object { $_ }

$groups = @(
  @{ Name = "PNA" },
  @{ Name = "PrivateEndpoints" },
  @{ Name = "CMK" },
  @{ Name = "TLS" },
  @{ Name = "WAF" },
  @{ Name = "VulnerabilityAssessment" },
  @{ Name = "KeyVault" },
  @{ Name = "Disk" },
  @{ Name = "Location" },
  @{ Name = "DDoS" },
  @{ Name = "Monitoring" }
)

Ensure-AzContext -SubId $SubscriptionId

$metadata = @{ version = "1.0.0-quick"; category = "Regulatory Compliance" }

Write-Host "Creating/updating initiative $InitiativeName" -ForegroundColor Green
New-AzPolicySetDefinition -Name $safeName `
  -DisplayName "$InitiativeName (CCC Core Quick)" `
  -Description "CCC quick bundle (no parameters): PNA, PE, CMK, TLS min, WAF, VA, KV purge, batch disk enc." `
  -Metadata ($metadata | ConvertTo-Json -Depth 5) `
  -PolicyDefinition ($policyDefinitions | ConvertTo-Json -Depth 10) `
  -GroupDefinition ($groups | ConvertTo-Json -Depth 5) `
  -ErrorAction Stop | Out-Null

$initiativeId = "$scope/providers/Microsoft.Authorization/policySetDefinitions/$safeName"
$assignmentName = "$InitiativeName-assign-$AssignmentSuffix"

Write-Host "Assigning initiative $assignmentName" -ForegroundColor Green
New-AzPolicyAssignment -Name $assignmentName `
  -DisplayName "$InitiativeName (CCC Core Quick)" `
  -Scope $scope `
  -PolicySetDefinition $initiativeId `
  -Location $Location `
  -IdentityType SystemAssigned `
  -EnforcementMode Default `
  -ErrorAction Stop | Out-Null

Write-Host "Done. View in Policy -> Definitions (Custom) and Policy -> Assignments/Compliance." -ForegroundColor Green
