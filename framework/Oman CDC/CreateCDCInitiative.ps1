# Create Oman CDC Policy Initiative
# Cyber Defense Centre (CDC) of Oman - Cloud Controls Framework
# Reference: https://cdc.om/

# Description: This policy initiative implements controls from the Oman Cyber Defense Centre's
# cloud security framework, covering technical requirements (CDC-TR-*), policy requirements (CDC-POL-*),
# and contractual requirements (CDC-CON-*) for external cloud service usage.

# Prerequisites:
# - Azure CLI installed and authenticated
# - Appropriate permissions to create policy initiatives at the desired scope
# - Files in current directory: cdc_groups.json, cdc_policies.json, cdc_params.json

param(
    [Parameter(Mandatory=$false)]
    [string]$Scope = "",
    
    [Parameter(Mandatory=$false)]
    [string]$ManagementGroupId = "",
    
    [Parameter(Mandatory=$false)]
    [switch]$AssignAfterCreation
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Oman CDC Policy Initiative Creator" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Determine scope
if ($ManagementGroupId) {
    $Scope = "/providers/Microsoft.Management/managementGroups/$ManagementGroupId"
    Write-Host "Targeting Management Group: $ManagementGroupId" -ForegroundColor Yellow
} elseif (-not $Scope) {
    # Use current subscription context
    $context = Get-AzContext
    $Scope = "/subscriptions/$($context.Subscription.Id)"
    Write-Host "Targeting Subscription: $($context.Subscription.Name)" -ForegroundColor Yellow
}

Write-Host "Scope: $Scope" -ForegroundColor Gray
Write-Host ""

# Verify files exist
$requiredFiles = @("cdc_groups.json", "cdc_policies.json", "cdc_params.json")
foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-Error "Required file not found: $file"
        exit 1
    }
}

Write-Host "Loading policy definition files..." -ForegroundColor Green

try {
    # Load JSON files
    $groups = Get-Content -Raw cdc_groups.json
    $policies = Get-Content -Raw cdc_policies.json
    $params = Get-Content -Raw cdc_params.json
    
    Write-Host "✓ Loaded groups, policies, and parameters" -ForegroundColor Green
    Write-Host ""
    
    # Create the policy initiative
    Write-Host "Creating Oman CDC Policy Initiative..." -ForegroundColor Green
    
    $initiative = New-AzPolicySetDefinition `
        -Name 'OmanCDC_Cloud_Compliance' `
        -DisplayName 'Oman CDC Cloud Security Controls' `
        -Description 'Cyber Defense Centre (CDC) of Oman cloud security controls framework covering technical requirements (CDC-TR-*), policy requirements (CDC-POL-*), and contractual requirements (CDC-CON-*) for external cloud service usage. Includes controls for network security, identity & access, encryption, logging, backup, AI governance, and data protection.' `
        -Metadata '{"category":"Regulatory Compliance","version":"1.0.0","country":"Oman","authority":"Cyber Defense Centre (CDC)"}' `
        -GroupDefinition $groups `
        -PolicyDefinition $policies `
        -Parameter $params `
        -ManagementGroupName $(if ($ManagementGroupId) { $ManagementGroupId } else { $null })
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "✓ Initiative Created Successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Initiative Details:" -ForegroundColor Cyan
    Write-Host "  Name: $($initiative.Name)" -ForegroundColor White
    Write-Host "  Display Name: $($initiative.Properties.DisplayName)" -ForegroundColor White
    Write-Host "  Resource ID: $($initiative.ResourceId)" -ForegroundColor White
    Write-Host ""
    
    # Assignment option
    if ($AssignAfterCreation) {
        Write-Host "Creating policy assignment..." -ForegroundColor Green
        
        $assignmentName = "OmanCDC-" + (Get-Date -Format "yyyyMMdd")
        $assignment = New-AzPolicyAssignment `
            -Name $assignmentName `
            -DisplayName "Oman CDC Cloud Controls - $(Get-Date -Format 'yyyy-MM-dd')" `
            -Scope $Scope `
            -PolicySetDefinition $initiative `
            -Description "Assignment of Oman CDC cloud security controls for regulatory compliance monitoring" `
            -Location "uaenorth"
        
        Write-Host "✓ Policy assigned successfully!" -ForegroundColor Green
        Write-Host "  Assignment Name: $($assignment.Name)" -ForegroundColor White
        Write-Host ""
    }
    
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "1. Review the initiative in Azure Portal > Policy > Definitions" -ForegroundColor White
    Write-Host "2. Assign the initiative to desired scope(s)" -ForegroundColor White
    Write-Host "3. Configure Microsoft Defender for Cloud for enhanced monitoring" -ForegroundColor White
    Write-Host "4. Review compliance dashboard after 24 hours" -ForegroundColor White
    Write-Host "5. Document CDC approval and set renewal reminder (2-year validity)" -ForegroundColor White
    Write-Host ""
    Write-Host "Important Notes:" -ForegroundColor Yellow
    Write-Host "- Many CDC controls require manual attestation (POL, CON series)" -ForegroundColor Gray
    Write-Host "- Ensure data classification is complete before cloud deployment" -ForegroundColor Gray
    Write-Host "- Submit semi-annual security audit reports to CDC" -ForegroundColor Gray
    Write-Host "- Maintain documentation for CDC approval renewals" -ForegroundColor Gray
    Write-Host ""
    
} catch {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "✗ Error Creating Initiative" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Error $_.Exception.Message
    Write-Host ""
    Write-Host "Troubleshooting Tips:" -ForegroundColor Yellow
    Write-Host "- Verify you have appropriate permissions (Policy Contributor role)" -ForegroundColor Gray
    Write-Host "- Ensure Azure CLI is authenticated: az login" -ForegroundColor Gray
    Write-Host "- Check that all JSON files are valid and in current directory" -ForegroundColor Gray
    Write-Host "- Verify policy definition IDs exist in your Azure environment" -ForegroundColor Gray
    exit 1
}
