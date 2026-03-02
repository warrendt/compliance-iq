# SAMA AI Quick Reference - Azure AI Foundry & M365 Copilot

## Critical Path for AI Implementation (60 Days)

### Week 1-2: AI Governance Foundation

**Must-Have AI Controls (10 items)**

| Priority | SAMA Control | AI Solution | Immediate Action |
|----------|--------------|-------------|------------------|
| 1 | AI Security Contacts (3.1.1) | Defender for Cloud AI alerts | Configure AI security email |
| 2 | MFA for AI Access (3.3.5.10) | Entra ID CA for AI resources | Deploy AI-specific MFA policy |
| 3 | Privileged AI Access (3.3.5.13) | Entra ID PIM for AI admins | Enable PIM for AI administrators |
| 4 | AI Audit Logging (3.3.14.3) | Purview Audit + Azure Monitor | Configure AI logging |
| 5 | Prompt Injection Protection (3.2.1) | AI Content Safety | Enable jailbreak detection |
| 6 | AI Data Classification (3.3.3.4) | Purview sensitivity labels | Label AI training data |
| 7 | AI Encryption at Rest (3.3.9.1) | Azure Key Vault CMK | Enable CMK for AI data |
| 8 | AI Network Isolation (3.3.8.11) | Azure Private Endpoints | Deploy AI in VNet |
| 9 | AI DLP Policies (3.2.1.4) | Purview DLP for Copilot | Block PII in AI prompts |
| 10 | AI Incident Response (3.3.15.1) | Defender XDR | Create AI incident playbooks |

**Quick Deploy - AI Security Baseline**

```powershell
# AI FOUNDRY QUICK DEPLOY (Run with Global Admin)

# 1. Enable MFA for AI Foundry access
$aiPolicy = @{
    DisplayName = "SAMA-MFA-AI-Resources"
    State = "enabled"
    Conditions = @{
        Applications = @{
            IncludeApplications = @("Azure-ML-Service-ID", "Azure-OpenAI-ID")
        }
        Users = @{ IncludeUsers = "All" }
    }
    GrantControls = @{
        Operator = "AND"
        BuiltInControls = @("mfa", "compliantDevice")
        AuthenticationStrength = @{ DisplayName = "Phishing-resistant MFA" }
    }
}
New-MgIdentityConditionalAccessPolicy -BodyParameter $aiPolicy

# 2. Enable PIM for AI administrators
$aiAdminRole = Get-MgDirectoryRole | Where-Object { $_.DisplayName -eq "AI Administrator" }
Enable-MgPrivilegedAccessRoleAssignment -RoleId $aiAdminRole.Id

# 3. Configure AI audit logging
Set-PurviewAuditConfig -Workload "AzureAI" -LoggingLevel "Verbose" -RetentionDays 2555

# 4. Deploy AI Foundry with security baseline
$aiFoundry = @{
    WorkspaceName = "sama-ai-prod"
    Location = "saudiarabia"
    PublicNetworkAccess = "Disabled"
    ManagedIdentity = "SystemAssigned"
    CustomerManagedKey = $keyVaultKeyUrl
    Tags = @{
        "SAMA-Compliance" = "true"
        "Environment" = "Production"
        "DataClassification" = "Confidential"
    }
}
New-AzMLWorkspace @aiFoundry
```

```powershell
# M365 COPILOT QUICK DEPLOY

# 1. Enable Copilot with data governance
Set-SPOTenant -EnableAIPIntegration $true
Set-SPOTenant -OneDriveStorageQuota 1024000

# 2. Configure Copilot DLP
$copilotDLP = @{
    Name = "SAMA-Copilot-Confidential-Data"
    Location = @("CopilotInteraction")
    Rules = @{
        Name = "Block-PII-In-Copilot"
        ContentContainsSensitiveInformation = @(
            @{Name="Credit Card Number"},
            @{Name="Saudi Arabia National ID"},
            @{Name="IBAN"},
            @{Name="SWIFT Code"}
        )
        BlockAccess = $true
        NotifyUser = $true
    }
}
New-DlpCompliancePolicy @copilotDLP

# 3. Enable Copilot audit logging
Set-AdminAuditLogConfig -UnifiedAuditLogIngestionEnabled $true
Enable-Mailbox -Identity "*" -AuditEnabled $true

# 4. Configure oversharing controls
Set-SPOSite -Identity "https://contoso.sharepoint.com/sites/finance" `
    -RestrictedAccessControl $true `
    -RestrictedAccessControlGroups "Finance-Authorized-Group"

# 5. Enable DSPM for AI
Enable-PurviewDSPMForAI -TenantId $tenantId
```

---

### Week 3-4: AI Data Protection

**AI Data Security Controls (8 items)**

| Control | Implementation | PowerShell/CLI Command |
|---------|----------------|------------------------|
| Sensitivity Labels for AI | Purview Information Protection | `New-Label -Name "SAMA-AI-Training-Data"` |
| DLP for Copilot | Purview DLP | `New-DlpCompliancePolicy -Name "SAMA-Copilot-DLP"` |
| AI Model Encryption | Azure Key Vault CMK | `Set-AzMLWorkspace -CustomerManagedKey $keyUrl` |
| Copilot Double Key Encryption | Purview DKE | `Enable-PurviewDoubleKeyEncryption` |
| AI Private Networking | Azure Private Link | `New-AzPrivateEndpoint -Name "ai-pe"` |
| Copilot Oversharing Control | SharePoint Advanced Management | `Set-SPOSite -RestrictedAccessControl $true` |

**Deploy AI Content Safety**

```bash
# Azure AI Content Safety deployment
az cognitiveservices account create \
  --name sama-content-safety \
  --resource-group rg-ai-security \
  --kind ContentSafety \
  --sku S0 \
  --location saudiarabia \
  --custom-domain sama-ai-safety \
  --public-network-access Disabled
```

---

### Week 5-6: AI Monitoring & Detection

**AI Security Monitoring (12 items)**

```kql
// SENTINEL DETECTION RULES FOR AI

// Rule 1: Prompt Injection Detection
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.COGNITIVESERVICES"
| where OperationName == "ChatCompletion"
| extend Prompt = tostring(parse_json(properties_s).messages[0].content)
| where Prompt contains_any ("ignore previous", "system:", "ADMIN MODE", 
    "bypass filter", "reveal instructions")
| project TimeGenerated, CallerIpAddress, Prompt, UserId = Caller_s
| extend ThreatLevel = "Critical"

// Rule 2: AI Data Exfiltration
MicrosoftPurviewAuditLogs
| where Operation == "CopilotInteraction"
| extend ResponseTokens = toint(AdditionalProperties.ResponseTokens)
| where ResponseTokens > 10000
| summarize LargeResponses = count(), TotalTokens = sum(ResponseTokens) 
    by UserId, ClientIP, bin(TimeGenerated, 5m)
| where LargeResponses > 20 or TotalTokens > 100000

// Rule 3: Unauthorized AI Model Deployment
AzureActivity
| where ResourceProvider == "Microsoft.MachineLearningServices"
| where OperationNameValue == "Microsoft.MachineLearningServices/workspaces/onlineEndpoints/deployments/write"
| where ActivityStatusValue == "Success"
| join kind=leftanti (
    // Approved model deployments from change management
    ApprovedChangeRequests
) on CorrelationId
| extend Deployer = tostring(Claims.["upn"])

// Rule 4: Shadow AI Detection
CloudAppEvents
| where Application in~ ("ChatGPT", "Claude", "Bard", "Perplexity")
| where ActionType == "FileUploaded"
| extend SensitivityLabel = tostring(RawEventData.SensitivityLabel)
| where SensitivityLabel in~ ("Confidential", "Highly Confidential")

// Rule 5: AI Model Tampering
AzureActivity
| where ResourceProvider == "Microsoft.MachineLearningServices"
| where OperationNameValue contains "Model"
| where ActivityStatusValue == "Success"
| where CallerIpAddress !in~ (KnownDataScienceIPs)
| extend AnomalyScore = 100

// Rule 6: Copilot PII Leakage
MicrosoftPurviewAuditLogs
| where Operation == "CopilotInteraction"
| extend PromptText = tostring(AdditionalProperties.Prompt)
| extend ResponseText = tostring(AdditionalProperties.Response)
| where PromptText contains_regex @"\b\d{16}\b"  // Credit card
    or ResponseText contains_regex @"\b\d{10}\b"  // National ID
    or ResponseText contains_regex @"[A-Z]{2}\d{2}[A-Z0-9]{10,30}"  // IBAN

// Rule 7: Anomalous AI Compute Usage
AzureMetrics
| where ResourceProvider == "MICROSOFT.MACHINELEARNINGSERVICES"
| where MetricName == "GpuUtilization"
| summarize AvgGPU = avg(Average) by Resource, bin(TimeGenerated, 10m)
| where AvgGPU > 95
| join kind=inner (
    AzureActivity
    | where OperationNameValue == "Microsoft.MachineLearningServices/workspaces/jobs/action"
) on Resource
| summarize JobCount = count() by Resource, tostring(Claims.["upn"])
| where JobCount > 100

// Rule 8: Copilot Admin Privilege Abuse
AuditLogs
| where OperationName == "Add member to role"
| where TargetResources[0].modifiedProperties[0].displayName == "Role.DisplayName"
| extend Role = tostring(TargetResources[0].modifiedProperties[0].newValue)
| where Role contains "Copilot"
| where InitiatedBy.user.userPrincipalName !in~ (ApprovedCopilotAdmins)
```

---

### Week 7-8: AI Compliance & Governance

**AI Regulatory Compliance (6 items)**

| Regulation | Implementation | Validation |
|------------|----------------|------------|
| ISO 42001 (AI Management) | Purview Compliance Manager | AI management assessment |
| EU AI Act readiness | Azure AI governance | High-risk AI classification |
| GDPR for AI | Purview data governance | AI data processing records |
| SAMA CSF AI controls | Azure Policy initiatives | AI compliance dashboard |
| PCI-DSS for AI payment systems | Defender for Cloud PCI-DSS | AI handling payment data |
| Model transparency | AI Foundry model cards | Model documentation |

**AI Compliance Dashboard**

```kql
// SAMA AI Compliance KPIs
let AISecurityScore = 
    SecurityRecommendation
    | where RecommendationDisplayName contains "AI" or RecommendationName contains "MachineLearning"
    | summarize AIScore = avg(RecommendationScore) * 100;

let CopilotDLPViolations = 
    DLPEvent
    | where Location == "CopilotInteraction"
    | where TimeGenerated > ago(30d)
    | summarize DLPViolations = count();

let AIIncidents = 
    SecurityIncident
    | where Title contains "AI" or Title contains "Copilot"
    | where TimeGenerated > ago(30d)
    | summarize CriticalAI = countif(Severity == "Critical"), 
                HighAI = countif(Severity == "High");

let PromptInjections = 
    AzureDiagnostics
    | where ResourceProvider == "MICROSOFT.COGNITIVESERVICES"
    | where properties_s contains "jailbreak" or properties_s contains "injection"
    | where TimeGenerated > ago(30d)
    | summarize InjectionAttempts = count();

let CopilotUsage = 
    MicrosoftPurviewAuditLogs
    | where Operation == "CopilotInteraction"
    | where TimeGenerated > ago(30d)
    | summarize TotalInteractions = count(), 
                UniqueUsers = dcount(UserId),
                AvgTokensPerUser = avg(toint(AdditionalProperties.TotalTokens));

print 
    SAMAAISecurityScore = toscalar(AISecurityScore),
    CopilotDLPViolations = toscalar(CopilotDLPViolations),
    CriticalAIIncidents = toscalar(AIIncidents.CriticalAI),
    HighAIIncidents = toscalar(AIIncidents.HighAI),
    PromptInjectionAttempts = toscalar(PromptInjections),
    CopilotInteractions = toscalar(CopilotUsage.TotalInteractions),
    CopilotUsers = toscalar(CopilotUsage.UniqueUsers)
```

---

## AI-Specific Azure Policy Assignment

```json
{
  "displayName": "SAMA AI Security Framework v1.0",
  "description": "Comprehensive SAMA compliance for AI Foundry and M365 Copilot",
  "parameters": {
    "effect": "Audit",
    "allowedLocations": ["saudiarabia", "uaenorth"],
    "requireEncryption": true,
    "requirePrivateEndpoint": true,
    "enableAILogging": true,
    "requireMFA": true,
    "blockPublicAI": true
  },
  "policyDefinitions": [
    {
      "policyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/ai-require-private-endpoint",
      "parameters": { "effect": { "value": "Deny" } }
    },
    {
      "policyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/ai-require-cmk",
      "parameters": { "effect": { "value": "Audit" } }
    },
    {
      "policyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/ai-audit-logging",
      "parameters": { "effect": { "value": "DeployIfNotExists" } }
    },
    {
      "policyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/ai-region-restriction",
      "parameters": { 
        "effect": { "value": "Deny" },
        "allowedLocations": { "value": ["saudiarabia", "uaenorth"] }
      }
    }
  ],
  "scope": "/subscriptions/{subscription-id}",
  "enforcementMode": "Default"
}
```

---

## AI Licensing Cost Calculator

### AI Foundry Costs (Monthly - per Saudi Riyal approximation)

| Component | Unit | Cost (USD) | Cost (SAR) | SAMA Controls |
|-----------|------|-----------|-----------|---------------|
| AI Foundry workspace | Per workspace | $0 | 0 | 3.1.1, 3.3.3 |
| Azure OpenAI (GPT-4) | Per 1K tokens | $0.03-0.12 | 0.11-0.45 | 3.3.6, 3.3.13 |
| Azure AI Content Safety | Per 1K requests | $1-5 | 3.75-18.75 | 3.2.1, 3.3.6 |
| Compute (GPU - Standard_NC6s_v3) | Per hour | $3.06 | 11.48 | 3.3.8 |
| Storage (Premium SSD) | Per GB/month | $0.135 | 0.51 | 3.3.9 |
| Private Endpoint | Per endpoint | $7.30 | 27.38 | 3.3.8.11 |
| Defender for AI workload | Per resource | $15 | 56.25 | 3.3.16, 3.3.17 |

### M365 Copilot Costs (Monthly per user)

| License | USD/user | SAR/user | Required For |
|---------|----------|----------|--------------|
| Microsoft 365 E5 | $57 | 213.75 | Base Copilot access |
| Copilot for Microsoft 365 | $30 | 112.50 | AI capabilities |
| **Total per user** | **$87** | **326.25** | Full compliance |

### Total AI Compliance Cost Estimates

**Small Financial Institution (100 users, minimal AI)**
- M365 Copilot: 100 × $87 = $8,700/month
- AI Foundry: ~$500/month (development only)
- Defender + monitoring: ~$2,000/month
- **Total: ~$11,200/month or SAR 42,000/month**

**Medium Financial Institution (500 users, moderate AI)**
- M365 Copilot: 500 × $87 = $43,500/month
- AI Foundry: ~$3,000/month (prod + dev)
- Defender + monitoring: ~$8,000/month
- **Total: ~$54,500/month or SAR 204,375/month**

**Large Bank (2000+ users, extensive AI)**
- M365 Copilot: 2000 × $87 = $174,000/month
- AI Foundry: ~$15,000/month (multi-region prod)
- Defender + monitoring: ~$25,000/month
- **Total: ~$214,000/month or SAR 802,500/month**

---

## Critical AI Alerts Configuration

### Tier 1 AI Alerts (15 min SLA)

```yaml
SAMA_AI_Critical_Alerts:
  - Name: "AI-001-Prompt-Injection"
    Description: "Malicious prompt injection attempt detected"
    Source: "Azure AI Content Safety / Copilot"
    Trigger: "Jailbreak pattern in prompt or response"
    Severity: "Critical"
    Action: 
      - "Block user session immediately"
      - "Alert AI security team (SMS + Email)"
      - "Preserve full audit trail"
      - "Notify CISO within 15 minutes"
    SAMA_Control: "3.2.1.AI.3, 3.3.15"
    
  - Name: "AI-002-Data-Exfiltration"
    Description: "Large-scale data exfiltration via AI detected"
    Source: "Purview DLP + Azure Monitor"
    Trigger: "Token usage >100K/hour or file access >10GB/hour via AI"
    Severity: "Critical"
    Action:
      - "Terminate AI sessions for user"
      - "Disable user account immediately"
      - "Notify SAMA within 1 hour"
      - "Initiate forensics investigation"
    SAMA_Control: "3.2.1.AI.4, 3.3.15"
    
  - Name: "AI-003-Unauthorized-Model-Deploy"
    Description: "AI model deployed to production without approval"
    Source: "Azure Activity Log"
    Trigger: "Model deployment without change approval"
    Severity: "Critical"
    Action:
      - "Rollback deployment automatically"
      - "Alert change management team"
      - "Audit deployment logs"
      - "Escalate to AI governance committee"
    SAMA_Control: "3.3.6.AI.6, 3.3.7"
    
  - Name: "AI-004-PII-In-Copilot"
    Description: "Sensitive PII detected in Copilot interaction"
    Source: "Purview DLP"
    Trigger: "Credit card, IBAN, or National ID in prompt/response"
    Severity: "Critical"
    Action:
      - "Block Copilot response"
      - "Purge interaction from logs (GDPR right to erasure)"
      - "User warning notification"
      - "Security awareness re-training triggered"
    SAMA_Control: "3.3.13.AI.5"
    
  - Name: "AI-005-Admin-Account-Compromise"
    Description: "AI administrator account showing anomalous activity"
    Source: "Entra ID Protection"
    Trigger: "Impossible travel, new device, or risky sign-in for AI admin"
    Severity: "Critical"
    Action:
      - "Revoke all active sessions"
      - "Require MFA re-registration"
      - "Temporary privilege suspension"
      - "Forensics investigation"
    SAMA_Control: "3.3.5.AI.3, 3.3.15"
    
  - Name: "AI-006-Shadow-AI-Usage"
    Description: "Unsanctioned AI tool usage with corporate data"
    Source: "Defender for Cloud Apps"
    Trigger: "Upload of confidential data to ChatGPT, Claude, etc."
    Severity: "Critical"
    Action:
      - "Block cloud app access"
      - "DLP policy enforcement"
      - "User notification and training"
      - "Manager escalation"
    SAMA_Control: "3.3.16.AI.5"
```

### Tier 2 AI Alerts (1 hour SLA)

```yaml
SAMA_AI_High_Alerts:
  - Name: "AI-101-Model-Drift"
    Description: "AI model performance degradation detected"
    Trigger: "Model accuracy <80% of baseline"
    Action: "Investigate data quality, consider retraining"
    
  - Name: "AI-102-Copilot-Oversharing"
    Description: "Copilot accessing overly permissive SharePoint sites"
    Trigger: "Copilot accessing sites with org-wide sharing"
    Action: "Review site permissions, restrict access"
    
  - Name: "AI-103-Unusual-Token-Consumption"
    Description: "Abnormal AI token usage pattern"
    Trigger: "5x average token usage per user"
    Action: "Investigate usage pattern, potential abuse"
```

---

## Implementation Checklist - AI-Specific

### Phase 1: AI Foundation (Days 1-30) ✓

**AI Governance**
- [ ] AI governance committee with SAMA representation
- [ ] Board approval for AI adoption strategy
- [ ] AI usage policy documented and approved
- [ ] AI risk appetite defined

**AI Access Control**
- [ ] MFA for AI Foundry and Copilot access
- [ ] PIM for AI administrator roles
- [ ] Conditional Access for AI resources
- [ ] Service principals using managed identities

**AI Data Protection**
- [ ] Sensitivity labels for AI data deployed
- [ ] DLP policies for Copilot configured
- [ ] AI model encryption with CMK
- [ ] Private endpoints for AI Foundry

**AI Monitoring**
- [ ] AI audit logging enabled (7-year retention)
- [ ] Sentinel AI connectors deployed
- [ ] Critical AI alerts configured
- [ ] SOC team trained on AI threats

### Phase 2: AI Security Controls (Days 31-60) ✓

**AI Content Safety**
- [ ] Azure AI Content Safety deployed
- [ ] Prompt injection detection enabled
- [ ] Harmful content filters configured
- [ ] Output validation implemented

**AI Network Security**
- [ ] AI workloads in VNet isolation
- [ ] NSG rules for AI traffic
- [ ] Private DNS for AI endpoints
- [ ] DDoS protection for AI APIs

**AI Threat Protection**
- [ ] Defender for Cloud AI plan enabled
- [ ] AI vulnerability scanning scheduled
- [ ] Red team AI penetration testing planned
- [ ] Shadow AI detection policies active

**Copilot Governance**
- [ ] Oversharing controls implemented
- [ ] Restricted SharePoint search configured
- [ ] Copilot plugin governance
- [ ] DSPM for AI enabled

### Phase 3: AI Compliance (Days 61-90) ✓

**Regulatory Compliance**
- [ ] ISO 42001 gap assessment completed
- [ ] EU AI Act risk classification
- [ ] SAMA CSF AI mapping validated
- [ ] Compliance dashboard operational

**AI Documentation**
- [ ] AI model cards generated
- [ ] AI system documentation (SPDX format)
- [ ] AI risk assessment reports
- [ ] SAMA notification procedures

**AI Operations**
- [ ] AI incident response playbooks tested
- [ ] AI forensics capabilities validated
- [ ] Continuous AI monitoring operational
- [ ] Quarterly AI security reviews scheduled

---

## Emergency AI Incident Response

### SAMA Notification Requirements for AI

**High-Severity AI Incidents (1 hour notification)**:
1. Prompt injection leading to unauthorized data access
2. AI-generated misinformation affecting >1000 customers
3. Large-scale PII exposure via AI (>100 customers)
4. Unauthorized production AI model deployment
5. AI administrator account compromise

**Medium-Severity AI Incidents (24 hour notification)**:
1. Multiple failed prompt injection attempts (>50/hour)
2. Shadow AI tool usage with confidential data
3. AI model performance degradation affecting customers
4. Copilot DLP policy violations (>10/day)

### AI Incident Response Contacts

**Internal**:
- AI Governance Committee: ai-committee@org.sa
- CISO Office: ciso@org.sa
- AI Security Team: ai-security@org.sa

**External**:
- SAMA Cyber Security: cybersecurity@sama.gov.sa
- SAMA Emergency: +966-11-SAMA-CERT
- Microsoft Support: Azure Portal → AI Foundry → Support

---

## Success Metrics - AI Specific

### AI Security Posture KPIs

| Metric | Target | Measurement | SAMA Control |
|--------|--------|-------------|--------------|
| AI Security Score | ≥85% | Defender for Cloud | 3.1.1 |
| Prompt Injection Block Rate | 100% | AI Content Safety | 3.2.1 |
| AI Vulnerability Remediation | Critical: 7 days | Defender for Cloud | 3.3.17 |
| AI Audit Log Coverage | 100% | Azure Monitor | 3.3.14 |
| Copilot DLP Block Rate | ≥95% | Purview DLP | 3.2.1 |
| AI Model Documentation | 100% | AI Foundry | 3.2.2 |
| AI MTTD (Mean Time to Detect) | ≤15 min | Sentinel | 3.3.15 |
| AI MTTR (Mean Time to Respond) | ≤1 hour | Sentinel | 3.3.15 |

### AI Operational Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| AI Incident False Positive Rate | ≤10% | Sentinel tuning |
| AI Model Uptime | ≥99.9% | Azure Monitor |
| Copilot User Adoption | Track | M365 analytics |
| AI Training Completion | 100% | Learning records |
| AI Governance Review Frequency | Quarterly | Committee records |

---

## Additional Resources

### AI-Specific Documentation
- [Azure AI Foundry Security Baseline](https://learn.microsoft.com/security/benchmark/azure/baselines/azure-ai-foundry-security-baseline)
- [Microsoft 365 Copilot Security](https://learn.microsoft.com/copilot/microsoft-365/microsoft-365-copilot-ai-security)
- [Microsoft Responsible AI Standard](https://aka.ms/RAI)
- [OWASP Top 10 for LLM](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

### Training & Certification
- SC-100: Microsoft Cybersecurity Architect (AI security module)
- AI-102: Designing and Implementing Microsoft Azure AI Solution
- MS-600: Building Applications and Solutions with Microsoft 365 Core Services (Copilot module)

### Community Resources
- [Microsoft AI Security Community](https://techcommunity.microsoft.com/t5/ai-security/ct-p/AISecurity)
- [Azure AI Foundry GitHub](https://github.com/Azure/azure-ai-foundry)
- [Responsible AI Toolbox](https://responsibleaitoolbox.ai/)

---

**Document Version**: 1.0  
**Last Updated**: October 31, 2025  
**Next Review**: January 31, 2026 (Quarterly)

---

*This AI-specific quick reference extends SAMA compliance to generative AI workloads. Validate all controls with compliance and legal teams, and obtain SAMA approval before deploying AI systems with customer financial data.*
