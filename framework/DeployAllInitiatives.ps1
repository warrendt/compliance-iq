# ComplianceIQ - Deploy All Policy Initiatives
# Usage: ./DeployAllInitiatives.ps1 -TenantId <guid> -SubscriptionId <guid>
# Or:    set $tenantId and $subscriptionId in a local .env.ps1 file (git-ignored)

param(
    [string]$TenantId,
    [string]$SubscriptionId
)

# Load from local config file if present (git-ignored)
$localConfig = Join-Path $PSScriptRoot ".env.ps1"
if (Test-Path $localConfig) { . $localConfig }

# Override with params if supplied
if ($TenantId)       { $tenantId       = $TenantId }
if ($SubscriptionId) { $subscriptionId = $SubscriptionId }

# Prompt if still unset
if (-not $tenantId)       { $tenantId       = Read-Host "Enter Tenant ID" }
if (-not $subscriptionId) { $subscriptionId = Read-Host "Enter Subscription ID" }
$subScope      = "/subscriptions/$subscriptionId"
$base          = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Pre-flight: GUID validation ─────────────────────────────────────────────
Write-Host "`n▶ Pre-flight: Validating policy GUIDs against Azure..." -ForegroundColor Cyan
$validateScript = Join-Path $base "validate_guids.py"
if (Test-Path $validateScript) {
    $validationOutput = python3 $validateScript 2>&1
    $exitCode = $LASTEXITCODE
    # Detect any invalid GUIDs in the output
    if (($validationOutput | Select-String -Pattern "Invalid:\s+[^0]") -or $exitCode -ne 0) {
        Write-Host "`n  ❌ GUID validation FAILED — invalid policy GUIDs detected:" -ForegroundColor Red
        Write-Host ($validationOutput | Out-String)
        Write-Host "  Fix GUIDs before deploying (run: python3 fix_guids.py)" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  ✅ All policy GUIDs are valid" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  validate_guids.py not found — skipping GUID check" -ForegroundColor Yellow
}

# Connect
Connect-AzAccount -Tenant $tenantId
Set-AzContext -SubscriptionId $subscriptionId

# ── Framework definitions ───────────────────────────────────────────────────
$frameworks = @(
    @{
        Dir         = "SAMA"
        Name        = "SAMA-Cybersecurity-Framework"
        DisplayName = "SAMA Cybersecurity Framework"
        Description = "SAMA Cybersecurity Framework compliance controls for Saudi financial sector."
        Version     = "1.0.0"
    },
    @{
        Dir         = "ADHICS"
        Name        = "ADHICS-v2-Controls"
        DisplayName = "Abu Dhabi Healthcare Information and Cyber Security Standard v2"
        Description = "ADHICS v2 controls for healthcare organisations in Abu Dhabi."
        Version     = "2.0.0"
    },
    @{
        Dir         = "Saudi Arabia Government"
        Name        = "Saudi-Arabia-Government-Controls"
        DisplayName = "Saudi Arabia Government Cloud Security Controls"
        Description = "Consolidated KSA Government framework: NCA CSCC, NDMO, PDPL."
        Version     = "1.0.0"
    },
    @{
        Dir         = "South African Government"
        Name        = "South-African-Government-Controls"
        DisplayName = "South African Government Cloud Security Controls"
        Description = "Consolidated SA Government framework: POPIA, SITA, eGovernment, IGR."
        Version     = "1.0.0"
    },
    @{
        Dir         = "Oman Government"
        Name        = "Oman-Government-Controls"
        DisplayName = "Oman Government Cloud Security Controls"
        Description = "Oman CDC cloud security controls framework."
        Version     = "1.0.0"
    }
)

# ── Step 1: Create / update initiative definitions ──────────────────────────
foreach ($fw in $frameworks) {
    $dir = Join-Path $base $fw.Dir
    Write-Host "`n▶ Creating initiative: $($fw.DisplayName)" -ForegroundColor Cyan

    $existing = Get-AzPolicySetDefinition -Custom | Where-Object { $_.Name -eq $fw.Name }
    try {
        if ($existing) {
            Write-Host "  Initiative already exists — updating..." -ForegroundColor Yellow
            Set-AzPolicySetDefinition `
                -Name        $fw.Name `
                -DisplayName $fw.DisplayName `
                -Description $fw.Description `
                -Metadata    "{`"version`":`"$($fw.Version)`",`"category`":`"Regulatory Compliance`"}" `
                -GroupDefinition (Join-Path $dir "groups.json") `
                -PolicyDefinition (Join-Path $dir "policies.json") `
                -Parameter   (Join-Path $dir "params.json") `
                -ErrorAction Stop
        } else {
            New-AzPolicySetDefinition `
                -Name        $fw.Name `
                -DisplayName $fw.DisplayName `
                -Description $fw.Description `
                -Metadata    "{`"version`":`"$($fw.Version)`",`"category`":`"Regulatory Compliance`"}" `
                -GroupDefinition (Join-Path $dir "groups.json") `
                -PolicyDefinition (Join-Path $dir "policies.json") `
                -Parameter   (Join-Path $dir "params.json") `
                -ErrorAction Stop
        }
        Write-Host "  ✅ Done" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Failed: $_" -ForegroundColor Red
    }
}

# ── Step 2: Assign each initiative to the subscription ──────────────────────
Write-Host "`n▶ Assigning initiatives to subscription $subscriptionId" -ForegroundColor Cyan

foreach ($fw in $frameworks) {
    $assignmentName = "$($fw.Name)-assign"
    $def = Get-AzPolicySetDefinition -Custom | Where-Object { $_.Name -eq $fw.Name }

    if (-not $def) {
        Write-Host "  ⚠️ Skipping assignment — initiative not found (creation may have failed)" -ForegroundColor Red
        continue
    }

    $existingAssignment = Get-AzPolicyAssignment -Scope $subScope | Where-Object { $_.Name -eq $assignmentName }
    if ($existingAssignment) {
        if ($existingAssignment.IdentityType -eq 'SystemAssigned') {
            Write-Host "  Assignment already exists for $($fw.Name) — skipping" -ForegroundColor Yellow
            continue
        }
        Write-Host "  Existing assignment lacks managed identity — recreating..." -ForegroundColor Yellow
        Remove-AzPolicyAssignment -Name $assignmentName -Scope $subScope -ErrorAction SilentlyContinue
    }

    try {
        New-AzPolicyAssignment `
            -Name               $assignmentName `
            -DisplayName        $fw.DisplayName `
            -PolicySetDefinition $def `
            -Scope              $subScope `
            -IdentityType       'SystemAssigned' `
            -Location           'southafricanorth' `
            -ErrorAction        Stop
        Write-Host "  ✅ Assigned: $($fw.DisplayName)" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Assignment failed: $_" -ForegroundColor Red
    }
}

# ── Step 3: Trigger on-demand compliance scan ───────────────────────────────
Write-Host "`n▶ Triggering on-demand policy compliance scan..." -ForegroundColor Cyan
Start-AzPolicyComplianceScan -AsJob
Write-Host "  ✅ Scan started (runs in background, allow up to 24h for full results)`n" -ForegroundColor Green

Write-Host "═══ Deployment complete ═══" -ForegroundColor Cyan
Write-Host "Next: Open Defender for Cloud → Environment Settings → Security policies"
Write-Host "      Toggle each initiative to 'On' under 'Your custom initiatives'"
