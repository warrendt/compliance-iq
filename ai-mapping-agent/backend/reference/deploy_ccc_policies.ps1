<#!
Manual deployment helper for CCC mappings (preview):
- Assigns MCSB v2 initiative at subscription scope.
- Assigns core public access disable, private endpoint, CMK, TLS, WAF, VA, disk encryption, Key Vault purge protection policies.
Prereqs: Az PowerShell modules installed; user with Policy Contributor at scope.
Usage:
  pwsh ./deploy_ccc_policies.ps1 -SubscriptionId <subId> -Location <region> [-AssignmentSuffix 'ccc'] \
    [-PrivateEndpointSubnetId "/subscriptions/.../subnets/pe"] \
    [-AllowedEncryptionSets "/subscriptions/.../diskEncryptionSets/des1"]
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [string]$SubscriptionId,
  [Parameter(Mandatory = $true)] [string]$Location,
  [string]$AssignmentSuffix = "ccc",
  [string]$PrivateEndpointSubnetId,
  [string[]]$AllowedEncryptionSets
)

# Core scopes
$scope = "/subscriptions/$SubscriptionId"

# Initiatives
$initiativeMcsbV2 = "/providers/Microsoft.Authorization/policySetDefinitions/e3ec7e09-768c-4b64-882c-fcada3772047"  # MCSB v2 (preview)

# Definitions (built-in)
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
}

function Ensure-AzContext {
  param([string]$SubId)
  $ctx = Get-AzContext -ErrorAction SilentlyContinue
  if (-not $ctx -or $ctx.Subscription.Id -ne $SubId) {
    Connect-AzAccount -ErrorAction Stop | Out-Null
    Set-AzContext -SubscriptionId $SubId -ErrorAction Stop | Out-Null
  }
}

function New-Assignment {
  param(
    [string]$Name,
    [string]$PolicyId,
    [string]$Scope,
    [hashtable]$Params = @{}
  )
  Write-Host "Assigning $Name -> $PolicyId" -ForegroundColor Cyan
  $common = @{
    Name            = $Name
    DisplayName     = $Name
    Scope           = $Scope
    PolicyDefinition= $PolicyId
    Location        = $Location
    IdentityType    = 'SystemAssigned'
    EnforcementMode = 'Default'
  }
  New-AzPolicyAssignment @common @Params | Out-Null
}

Ensure-AzContext -SubId $SubscriptionId

# 1) Assign MCSB v2 initiative
$mcsbName = "mcsb-v2-$AssignmentSuffix"
Write-Host "Assigning initiative $mcsbName" -ForegroundColor Green
New-AzPolicyAssignment -Name $mcsbName -DisplayName $mcsbName -Scope $scope -PolicySetDefinition $initiativeMcsbV2 -Location $Location -IdentityType SystemAssigned -EnforcementMode Default | Out-Null

# 2) Public network access deny bundle
$pnaDefs = @(
  $defs.Storage_RestrictNetworkAccess,
  $defs.PNA_EventHub,
  $defs.PNA_DataFactory,
  $defs.PNA_Databricks,
  $defs.PNA_KeyVault,
  $defs.PNA_Cosmos
)
$pnaDefs | ForEach-Object {
  $name = "pna-" + ($_ -split "/")[-1] + "-$AssignmentSuffix"
  New-Assignment -Name $name -PolicyId $_ -Scope $scope
}

# 3) Private endpoints bundle
$peDefs = @(
  $defs.Storage_PrivateLink,
  $defs.PE_KeyVault,
  $defs.PE_RecoveryServices
)
$peDefs | ForEach-Object {
  $name = "pe-" + ($_ -split "/")[-1] + "-$AssignmentSuffix"
  if ($_ -eq $defs.PE_KeyVault -and -not $PrivateEndpointSubnetId) {
    Write-Warning "Skipping $name (requires -PrivateEndpointSubnetId)"
    return
  }
  $params = @{}
  if ($_ -eq $defs.PE_KeyVault) {
    $params = @{ PolicyParameterObject = @{ privateEndpointSubnetId = @{ value = $PrivateEndpointSubnetId } } }
  }
  New-Assignment -Name $name -PolicyId $_ -Scope $scope -Params $params
}

# 4) CMK enforcement (storage + SQL)
$cmkDefs = @(
  $defs.CMK_Storage,
  $defs.CMK_SQL
)
$cmkDefs | ForEach-Object {
  $name = "cmk-" + ($_ -split "/")[-1] + "-$AssignmentSuffix"
  New-Assignment -Name $name -PolicyId $_ -Scope $scope
}

# 5) TLS minimum versions (App Service, Functions)
$tlsDefs = @(
  $defs.TLS_AppService,
  $defs.TLS_Functions
)
$tlsDefs | ForEach-Object {
  $name = "tls-" + ($_ -split "/")[-1] + "-$AssignmentSuffix"
  New-Assignment -Name $name -PolicyId $_ -Scope $scope
}

# 6) WAF requirements (Front Door, App Gateway)
$wafDefs = @(
  $defs.WAF_FrontDoor,
  $defs.WAF_AppGateway_Mode
)
$wafDefs | ForEach-Object {
  $name = "waf-" + ($_ -split "/")[-1] + "-$AssignmentSuffix"
  New-Assignment -Name $name -PolicyId $_ -Scope $scope
}

# 7) Vulnerability assessment (VMs, SQL)
$vaDefs = @(
  $defs.VA_Machines,
  $defs.VA_SQL
)
$vaDefs | ForEach-Object {
  $name = "va-" + ($_ -split "/")[-1] + "-$AssignmentSuffix"
  New-Assignment -Name $name -PolicyId $_ -Scope $scope
}

# 8) Key Vault purge protection
New-Assignment -Name "kv-purge-$AssignmentSuffix" -PolicyId $defs.KeyVault_Purge -Scope $scope

# 9) Disk encryption sets and batch
$deDefs = @(
  $defs.DiskEncryption_DES,
  $defs.BatchPool_DiskEncryption
)
$deDefs | ForEach-Object {
  $name = "disk-" + ($_ -split "/")[-1] + "-$AssignmentSuffix"
  if ($_ -eq $defs.DiskEncryption_DES -and -not $AllowedEncryptionSets) {
    Write-Warning "Skipping $name (requires -AllowedEncryptionSets with DES resource IDs)"
    return
  }
  $params = @{}
  if ($_ -eq $defs.DiskEncryption_DES) {
    $params = @{ PolicyParameterObject = @{ allowedEncryptionSets = @{ value = $AllowedEncryptionSets } } }
  }
  New-Assignment -Name $name -PolicyId $_ -Scope $scope -Params $params
}

Write-Host "Done." -ForegroundColor Green
