# SAMA Cyber Security Framework - AI Foundry & M365 Copilot Controls Mapping

## Document Purpose
Comprehensive mapping of SAMA CSF v1.0 controls to Microsoft Azure AI Foundry and Microsoft 365 Copilot security, governance, and compliance capabilities. This extends the existing SAMA-to-Azure mapping to cover generative AI and AI agent workloads.

**Reference**: SAMA Cyber Security Framework v1.0 (May 2017)  
**Last Updated**: October 31, 2025

---

## Executive Summary

### AI Foundry Overview
Azure AI Foundry (formerly Azure AI Studio) is Microsoft's unified platform for building, testing, and deploying generative AI applications and agents. Security controls span identity, data protection, network isolation, model governance, and prompt injection prevention.

### M365 Copilot Overview
Microsoft 365 Copilot integrates AI capabilities across productivity applications. Security is enforced through existing Microsoft 365 data protection, Entra ID permissions, Purview policies, and built-in AI safety controls.

### Key Compliance Capabilities
- **ISO 42001** (AI Management Systems)
- **EU AI Act** readiness
- **GDPR, HIPAA, ISO 27001** compliance
- **PCI-DSS** applicable controls for payment data
- **Zero Trust architecture** enforcement

---

## Domain 3.1: Cyber Security Leadership and Governance

### 3.1.1 Cyber Security Governance (AI-Specific Controls)

| SAMA Control | AI Foundry Control | M365 Copilot Control | Implementation |
|--------------|-------------------|---------------------|----------------|
| 3.1.1 - AI governance committee | Azure Policy - AI Foundry custom policies | Purview Compliance Manager - AI assessments | Create dedicated AI governance committee with AI risk oversight |
| Security contacts for AI systems | Defender for Cloud - AI workload alerts | Microsoft 365 admin center - Copilot admin roles | Configure email alerts for AI security findings |
| Board endorsement of AI strategy | Azure AI Foundry - Governance documentation | Microsoft 365 admin - Copilot enablement policies | Document board approval for AI adoption strategy |
| Independent AI security function | Azure RBAC - Separation of AI roles | Entra ID - Copilot admin separation | Separate AI security oversight from operations |
| AI risk appetite definition | Azure Policy - AI risk policies | Purview DSPM for AI - Risk thresholds | Define acceptable AI risk levels and policy enforcement |

**Policy Example - AI Foundry Governance**:
```json
{
  "displayName": "SAMA-AI-Governance-Policy",
  "policyRule": {
    "if": {
      "allOf": [
        {
          "field": "type",
          "equals": "Microsoft.MachineLearningServices/workspaces"
        },
        {
          "field": "tags['SAMA-Compliance']",
          "notEquals": "true"
        }
      ]
    },
    "then": {
      "effect": "deny"
    }
  }
}
```

### 3.1.2 AI Security Strategy

| SAMA Control | AI Foundry Control | M365 Copilot Control | Implementation |
|--------------|-------------------|---------------------|----------------|
| 3.1.2.1 - AI strategy definition | Azure AI Foundry - Planning guide | Microsoft 365 Roadmap - Copilot rollout | Document AI adoption strategy aligned with SAMA requirements |
| 3.1.2.2 - Alignment with org objectives | Azure Management Groups - AI policy hierarchy | Microsoft 365 admin - Tenant-wide Copilot policies | Align AI capabilities with business objectives |
| 3.1.2.3 - Banking sector alignment | Defender for Cloud - Financial services benchmark | Purview - Financial compliance templates | Map to NIST, PCI-DSS, ISO 27001 for banking |
| AI risk management framework | Azure AI Foundry - Responsible AI dashboard | Purview DSPM for AI - Risk assessment | Implement Microsoft RAI Standard practices |

### 3.1.3 Cyber Security Policy (AI Extensions)

| SAMA Control | AI Foundry Control | M365 Copilot Control | Implementation |
|--------------|-------------------|---------------------|----------------|
| 3.1.3.1 - AI usage policy | Azure Policy - AI Foundry restrictions | Microsoft 365 - Copilot data governance policy | Define acceptable AI usage and prohibited activities |
| 3.1.3.2 - Periodic AI policy review | Azure Policy - Compliance dashboard | Purview Compliance Manager - AI regulation tracking | Review AI policies quarterly |
| 3.1.3.3 - AI security standards | Azure AI Foundry - Security baseline | Microsoft Security Copilot - Security automation | Implement Azure security baseline for AI |
| 3.1.3.4 - AI data classification | Purview Information Protection - AI data labels | Purview sensitivity labels - Copilot integration | Classify AI training and inference data |

---

## Domain 3.2: Cyber Security Risk Management (AI-Specific)

### 3.2.1 AI-Specific Risk Management

| SAMA Control | AI Foundry Control | M365 Copilot Control | Implementation Priority |
|--------------|-------------------|---------------------|------------------------|
| 3.2.1 - AI risk assessment | AI Foundry - Model risk evaluation | Purview - Copilot risk assessment quickstart | **Critical** - 30 days |
| AI model risk identification | AI Foundry - Responsible AI dashboard | Copilot transparency note - Risk mapping | **Critical** - 15 days |
| Prompt injection risk | Defender for Cloud - Prompt injection detection | Copilot built-in - Jailbreak protection | **Critical** - Enabled by default |
| Data leakage risk | Purview DLP - AI workload policies | Purview DLP - Copilot location policies | **Critical** - 30 days |
| Model hallucination monitoring | AI Foundry - Evaluation metrics | Copilot - Grounding with Microsoft Graph | **High** - 45 days |
| Bias and fairness assessment | AI Foundry - Fairness evaluation | Copilot - Responsible AI principles | **High** - 60 days |
| Third-party model risk | Azure Policy - Approved model catalog | N/A | **High** - 45 days |
| AI supply chain security | Defender for Cloud - Container scanning | N/A | **Medium** - 60 days |

**KQL Query - AI Risk Detection**:
```kql
// Detect potential AI data leakage
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.MACHINELEARNINGSERVICES"
| where OperationName == "ModelInference"
| extend Tokens = toint(ResponseTokens_d)
| where Tokens > 10000  // Large responses may indicate data exfiltration
| extend UserPrincipalName = tostring(parse_json(Identity_s).claims.upn)
| summarize LargeResponses = count(), TotalTokens = sum(Tokens) by UserPrincipalName, bin(TimeGenerated, 1h)
| where LargeResponses > 20
```

### 3.2.2 Regulatory Compliance (AI)

| SAMA Control | AI Foundry Control | M365 Copilot Control | Compliance Standard |
|--------------|-------------------|---------------------|---------------------|
| 3.2.2.1 - AI regulatory compliance | Azure Policy - AI regulatory initiatives | Purview Compliance Manager - AI regulations | ISO 42001, EU AI Act |
| AI transparency requirements | AI Foundry - AI reports (SPDX) | Copilot transparency note | Explainability documentation |
| AI audit trail | Azure Monitor - AI workload logs | Purview Audit - Copilot interactions | Log all AI decisions and inputs |
| AI model documentation | AI Foundry - Model cards | N/A | Document model capabilities and limitations |

### 3.2.4 AI Security Review

| SAMA Control | AI Foundry Control | M365 Copilot Control | Review Frequency |
|--------------|-------------------|---------------------|------------------|
| 3.2.4 - Periodic AI security review | AI Foundry - Security assessments | Purview DSPM for AI - Periodic scans | Quarterly |
| AI penetration testing | Defender for Cloud - Red team exercises | Microsoft-conducted assessments | Annual |
| Prompt injection testing | AI Foundry - Adversarial testing | Copilot - OWASP Top 10 for LLM testing | Quarterly |
| AI vulnerability scanning | Defender for Cloud - AI vulnerabilities | Defender XDR - Copilot threat detection | Continuous |

---

## Domain 3.3: Cyber Security Operations (AI)

### 3.3.3 AI Asset Management

| SAMA Control | AI Foundry Control | M365 Copilot Control | Alert Capability |
|--------------|-------------------|---------------------|------------------|
| 3.3.3.1 - AI asset inventory | Azure Resource Graph - AI resource queries | Microsoft 365 admin - Copilot license tracking | New AI resources deployed |
| 3.3.3.2 - AI model registry | AI Foundry - Model registry | N/A | Model version changes |
| 3.3.3.3 - AI data classification | Purview Data Map - AI data lineage | Purview sensitivity labels - Copilot data | Unclassified AI data detected |
| 3.3.3.4 - AI ownership | Azure tags - AI owner metadata | Microsoft 365 - Copilot admin owners | Resources without owners |

**PowerShell - AI Asset Discovery**:
```powershell
# Discover all AI Foundry resources
Get-AzResource -ResourceType "Microsoft.MachineLearningServices/workspaces" | 
  Select-Object Name, Location, ResourceGroupName, Tags |
  Where-Object { $_.Tags['SAMA-Classified'] -ne 'true' } |
  Export-Csv -Path "UnclassifiedAI_Resources.csv"

# Audit Copilot licenses
Get-MgUser -All | Where-Object { $_.AssignedLicenses.SkuId -contains "Copilot-GUID" } |
  Select-Object DisplayName, UserPrincipalName, Department
```

### 3.3.5 Identity and Access Management (AI)

| SAMA Control | AI Foundry Control | M365 Copilot Control | Alert Capability |
|--------------|-------------------|---------------------|------------------|
| 3.3.5.10 - MFA for AI access | Entra ID Conditional Access - AI resources | Entra ID CA - Copilot access | MFA failures for AI services |
| 3.3.5.11 - Phishing-resistant auth | Entra ID - FIDO2 for AI Foundry | Entra ID - Passkeys for M365 | Weak auth method detected |
| 3.3.5.13 - Privileged AI access | Entra ID PIM - AI admin roles | Entra ID PIM - Copilot administrator | Privilege elevation for AI |
| AI service principals | Entra ID - Managed identities | Workload identity - Copilot extensibility | Service principal misuse |
| AI RBAC controls | Azure RBAC - AI Foundry roles | Microsoft 365 - Copilot RBAC | Unauthorized role assignments |
| Just-in-time AI access | PIM - Time-bound AI access | PIM - Temporary Copilot admin | Permanent AI privileges detected |

**Conditional Access Policy - AI Foundry**:
```json
{
  "displayName": "SAMA-MFA-AI-Foundry",
  "conditions": {
    "applications": {
      "includeApplications": ["Azure-AI-Foundry-AppId"]
    },
    "users": {
      "includeUsers": "All"
    },
    "locations": {
      "includeLocations": "All",
      "excludeLocations": ["Saudi-Arabia-Named-Location"]
    }
  },
  "grantControls": {
    "operator": "AND",
    "builtInControls": ["mfa", "compliantDevice"],
    "authenticationStrength": "phishingResistant"
  }
}
```

### 3.3.6 Application Security (AI Applications)

| SAMA Control | AI Foundry Control | M365 Copilot Control | Security Measure |
|--------------|-------------------|---------------------|------------------|
| 3.3.6 - Secure AI SDLC | Defender for DevOps - AI code scanning | Copilot extensibility - Secure development | Static analysis of AI code |
| AI input validation | AI Foundry - Content filters | Copilot - Input sanitization | Block malicious prompts |
| AI output validation | Azure AI Content Safety | Copilot - Harmful content filter | Block unsafe outputs |
| AI API security | API Management - AI endpoint protection | Graph API - Copilot extensibility security | API rate limiting and auth |
| AI model security | AI Foundry - Model encryption | N/A | Encrypt models at rest |
| Secure AI deployment | AI Foundry - Deployment approvals | Microsoft 365 - Copilot gradual rollout | Approval gates for production |

### 3.3.8 Infrastructure Security (AI Infrastructure)

| SAMA Control | AI Foundry Control | M365 Copilot Control | Implementation |
|--------------|-------------------|---------------------|----------------|
| 3.3.8.11 - AI network segmentation | Azure VNet - Private endpoints for AI | Microsoft 365 - Data residency | Isolate AI workloads |
| 3.3.8.12 - AI workload protection | Defender for Cloud - AI workload plan | Defender XDR - Copilot protection | Monitor AI infrastructure |
| 3.3.8.13 - AI malware protection | Defender for Containers - AI containers | Defender for Endpoint - Copilot clients | Scan AI artifacts |
| AI DDoS protection | Azure DDoS - AI endpoints | Microsoft 365 - Built-in DDoS | Protect AI APIs |
| AI encryption at rest | Azure Storage - Customer-managed keys | Microsoft 365 - Data encryption | Encrypt AI data |
| AI encryption in transit | TLS 1.3 - AI Foundry connections | Microsoft 365 - TLS encryption | Enforce secure transport |

### 3.3.9 Cryptography (AI Data)

| SAMA Control | AI Foundry Control | M365 Copilot Control | Key Management |
|--------------|-------------------|---------------------|----------------|
| 3.3.9.1 - AI data encryption | Azure Key Vault - AI CMK | Purview - Double Key Encryption for Copilot | Customer-managed keys |
| AI key lifecycle | Key Vault - Automated key rotation | Purview DKE - Key rotation | 90-day rotation |
| AI secrets management | Key Vault - Secrets for AI credentials | Managed identities - Copilot extensibility | No hardcoded credentials |
| AI certificate management | Key Vault - AI certificate storage | Microsoft 365 - Certificate-based auth | Auto-renew certificates |

### 3.3.13 AI-Enabled Services Security

| SAMA Control | AI Foundry Control | M365 Copilot Control | Security Control |
|--------------|-------------------|---------------------|------------------|
| AI chatbot security | AI Foundry - Agent safety controls | Copilot - Built-in safety | Content moderation |
| AI in customer-facing apps | Azure AI Content Safety | Copilot - Customer data protection | Filter harmful content |
| AI fraud detection | AI Foundry - Anomaly detection models | Purview - Insider risk with Copilot | Detect suspicious AI usage |
| AI authentication | Entra ID - AI app authentication | Entra ID - Copilot SSO | MFA for AI services |

### 3.3.14 AI Event Management

| SAMA Control | AI Foundry Control | M365 Copilot Control | Monitoring |
|--------------|-------------------|---------------------|------------|
| 3.3.14 - AI event logging | Azure Monitor - AI Foundry logs | Purview Audit - Copilot logs | Centralized AI logging |
| AI SIEM integration | Microsoft Sentinel - AI connectors | Sentinel - M365 Copilot connector | Real-time AI alerts |
| AI anomaly detection | Defender for Cloud - AI anomalies | Purview Insider Risk - AI anomalies | Unusual AI behavior |
| AI performance monitoring | Azure Monitor - AI metrics | Microsoft 365 - Copilot usage analytics | Latency and errors |

**Sentinel Analytics Rule - AI Anomaly**:
```kql
// Detect anomalous AI usage patterns
let baseline = 
    MicrosoftPurviewAuditLogs
    | where TimeGenerated > ago(30d)
    | where Operation == "CopilotInteraction"
    | summarize AvgPrompts = avg(PromptCount) by UserId;
MicrosoftPurviewAuditLogs
| where TimeGenerated > ago(1h)
| where Operation == "CopilotInteraction"
| summarize CurrentPrompts = sum(PromptCount) by UserId
| join kind=inner baseline on UserId
| where CurrentPrompts > (AvgPrompts * 5)  // 5x normal usage
| project UserId, CurrentPrompts, AvgPrompts, AnomalyRatio = CurrentPrompts / AvgPrompts
```

### 3.3.15 AI Incident Management

| SAMA Control | AI Foundry Control | M365 Copilot Control | Incident Type |
|--------------|-------------------|---------------------|---------------|
| 3.3.15 - AI incident response | Defender XDR - AI incidents | Purview - Copilot incident playbooks | Prompt injection detected |
| AI breach notification | Azure Security Center - AI alerts | Microsoft 365 admin - Incident notifications | Data leak via AI |
| AI forensics | Azure Monitor - AI audit logs | Purview eDiscovery - Copilot prompts | Investigate AI misuse |
| AI incident reporting to SAMA | Custom workflow - SAMA notification | Microsoft 365 - Compliance reporting | High-severity AI incident |

**Critical AI Incidents Requiring SAMA Notification**:
1. Unauthorized AI model deployment in production
2. Prompt injection leading to sensitive data exposure
3. AI-generated misinformation affecting customers
4. Large-scale AI data exfiltration (>100K records)
5. AI system unavailability >4 hours during business hours
6. Compromise of AI administrator accounts

### 3.3.16 AI Threat Management

| SAMA Control | AI Foundry Control | M365 Copilot Control | Threat Type |
|--------------|-------------------|---------------------|-------------|
| 3.3.16 - AI threat intelligence | Defender Threat Intelligence - AI threats | Microsoft Security Copilot - Threat analysis | Emerging AI attack vectors |
| Prompt injection detection | AI Foundry - Input validation | Copilot - Jailbreak detection | Malicious prompt patterns |
| Model poisoning detection | AI Foundry - Model integrity checks | N/A | Compromised training data |
| AI adversarial attacks | Azure AI Content Safety | Copilot - Adversarial input filter | Evasion techniques |
| Shadow AI detection | Defender for Cloud Apps - AI app discovery | Purview - Unauthorized Copilot plugins | Unsanctioned AI tools |

### 3.3.17 AI Vulnerability Management

| SAMA Control | AI Foundry Control | M365 Copilot Control | Remediation SLA |
|--------------|-------------------|---------------------|-----------------|
| 3.3.17 - AI vulnerability scanning | Defender for Cloud - AI vulnerabilities | Defender XDR - Copilot vulnerabilities | Critical: 7 days |
| AI dependency scanning | Defender for DevOps - Supply chain | N/A | High: 30 days |
| AI model vulnerabilities | AI Foundry - Model security assessment | N/A | Critical: 14 days |
| AI API vulnerabilities | API Management - Security assessment | Graph API - Vulnerability scanning | High: 30 days |
| AI patch management | Azure Update Manager - AI infrastructure | Microsoft 365 - Automatic Copilot updates | Critical: 72 hours |

---

## Domain 3.4: Third Party Cyber Security (AI)

### 3.4.3 AI Cloud Services Security

| SAMA Control | AI Foundry Control | M365 Copilot Control | Implementation |
|--------------|-------------------|---------------------|----------------|
| 3.4.3 - AI cloud policy | Azure Policy - AI cloud restrictions | Microsoft 365 - Copilot data residency | Define AI cloud usage policy |
| AI data location | AI Foundry - Saudi Arabia regions | Microsoft 365 - EU Data Boundary option | Data must remain in Saudi Arabia |
| AI data sovereignty | Azure Policy - Region restrictions | Purview - Data residency labels | Enforce data location |
| AI vendor assessment | AI Foundry - Model provider evaluation | Microsoft 365 - Copilot extensibility review | Assess third-party AI vendors |
| AI SLA requirements | AI Foundry - Service guarantees | Microsoft 365 - Copilot SLA | 99.9% uptime requirement |
| AI exit strategy | Azure - Data export procedures | Microsoft 365 - Data portability | AI data export on termination |

**Azure Policy - Data Residency**:
```json
{
  "displayName": "SAMA-AI-Data-Residency",
  "policyRule": {
    "if": {
      "allOf": [
        {
          "field": "type",
          "equals": "Microsoft.MachineLearningServices/workspaces"
        },
        {
          "field": "location",
          "notIn": ["saudiarabia", "uaenorth"]
        }
      ]
    },
    "then": {
      "effect": "deny"
    }
  }
}
```

---

## SAMA-Specific AI Implementation Roadmap

### Phase 1: Foundation (Days 1-30) - **CRITICAL**

**Week 1-2: Governance & Access**
```powershell
# 1. Enable MFA for AI Foundry access
$aiCAPolicy = @{
    DisplayName = "SAMA-MFA-AI-Resources"
    State = "enabled"
    Conditions = @{
        Applications = @{
            IncludeApplications = @("Azure-ML", "Azure-OpenAI")
        }
        Users = @{ IncludeUsers = "All" }
    }
    GrantControls = @{
        Operator = "AND"
        BuiltInControls = @("mfa", "compliantDevice")
    }
}
New-MgIdentityConditionalAccessPolicy -BodyParameter $aiCAPolicy

# 2. Enable PIM for AI administrators
Enable-MgPrivilegedAccessResource -ResourceId "AI-Admin-Role"

# 3. Configure Copilot data governance
Set-SPOTenant -OneDriveStorageQuota 1024000
Set-SPOTenant -EnableAIPIntegration $true
```

**Week 3-4: Data Protection**
```powershell
# 1. Deploy sensitivity labels for AI data
$label = New-Label -Name "SAMA-AI-Confidential" `
    -DisplayName "AI Training Data - Confidential" `
    -Tooltip "Contains customer data for AI models" `
    -EncryptionEnabled $true

# 2. Configure DLP for Copilot
$dlpPolicy = @{
    Name = "SAMA-Copilot-DLP"
    Location = @("CopilotInteraction")
    Rules = @{
        SensitiveInfoTypes = @("CreditCard", "IBAN", "SSN")
        Action = "BlockAccess"
    }
}
New-DlpCompliancePolicy @dlpPolicy

# 3. Enable Purview DSPM for AI
Enable-PurviewDSPMForAI -SubscriptionId $subscriptionId
```

### Phase 2: Security Controls (Days 31-60) - **HIGH**

**AI Content Safety**
```python
# Azure AI Content Safety integration
from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions

client = ContentSafetyClient(endpoint, credential)

# Analyze AI outputs for harmful content
def analyze_ai_output(text):
    request = AnalyzeTextOptions(text=text)
    response = client.analyze_text(request)
    
    if any(severity > 2 for severity in response.hate_result.severity):
        # Block and alert on harmful content
        send_alert_to_soc("Harmful AI output detected")
        return None
    return text
```

**Prompt Injection Detection**
```kql
// Sentinel analytics rule
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.COGNITIVESERVICES"
| where OperationName == "ChatCompletion"
| extend Prompt = tostring(parse_json(properties_s).prompt)
| where Prompt contains "ignore previous" 
    or Prompt contains "system:" 
    or Prompt contains "ADMIN MODE"
| project TimeGenerated, CallerIpAddress, Prompt, UserId
| extend ThreatLevel = "High"
```

### Phase 3: Monitoring & Compliance (Days 61-90) - **MEDIUM**

**AI Audit Configuration**
```powershell
# Enable comprehensive AI audit logging
Set-PurviewAuditConfig -Workload "MicrosoftCopilot" -LoggingLevel "Verbose"
Set-PurviewAuditConfig -Workload "AzureAI" -LoggingLevel "Verbose"

# Configure audit retention (7 years for SAMA)
Set-PurviewAuditRetentionPolicy -Duration 2555 -PolicyName "SAMA-7-Year-Retention"

# Export audit logs to Sentinel
$exportConfig = @{
    Name = "AIAuditExport"
    WorkloadType = "Copilot,AzureML"
    Destination = "/subscriptions/.../Microsoft.OperationalInsights/workspaces/sentinel"
}
New-PurviewAuditExport @exportConfig
```

**AI Compliance Dashboard**
```kql
// SAMA AI Compliance KPIs
let AIResources = AzureActivity
    | where ResourceProvider contains "MachineLearning" or ResourceProvider contains "CognitiveServices"
    | distinct ResourceId;
let ComplianceChecks = union
    (SecurityRecommendation 
     | where RecommendationDisplayName contains "AI"
     | summarize AISecurityScore = avg(RecommendationScore)),
    (AzureDiagnostics 
     | where ResourceProvider in~ ("MICROSOFT.MACHINELEARNINGSERVICES", "MICROSOFT.COGNITIVESERVICES")
     | summarize AIIncidents = countif(Category == "Incident")),
    (MicrosoftPurviewAuditLogs 
     | where Operation == "CopilotInteraction"
     | summarize CopilotUsage = count(), UniqueUsers = dcount(UserId));
ComplianceChecks
```

---

## AI-Specific Licensing Requirements

### Minimum Licensing for SAMA Compliance

| Service | License Required | Monthly Cost (USD) | SAMA Controls Covered |
|---------|------------------|-------------------|----------------------|
| **Azure AI Foundry** | Azure subscription + compute | Variable ($50-5000/month) | 3.3.6, 3.3.17, 3.4.3 |
| **Defender for Cloud - AI Plans** | Standard tier | $15/resource/month | 3.3.8, 3.3.15, 3.3.16 |
| **Microsoft 365 E5** | Per user | $57/user/month | 3.3.5, 3.3.14, 3.2.2 |
| **Microsoft Purview E5** | Per user (included in M365 E5) | Included | 3.3.3, 3.3.9, 3.3.14 |
| **Azure AI Content Safety** | Per 1000 requests | $1-5/1000 requests | 3.3.6, 3.3.13 |
| **Microsoft Security Copilot** | Per SCU | $4/SCU/hour | 3.3.16, 3.3.15 |

**Total Estimated Cost for AI Compliance**:
- Small organization (100 users): $7,000-10,000/month
- Medium organization (500 users): $35,000-50,000/month
- Large organization (2000+ users): $140,000+/month

---

## Critical AI Security Alerts

### Tier 1 Alerts (Immediate Response - 15 min SLA)

```yaml
AI_Critical_Alerts:
  - Name: "SAMA-AI-Prompt-Injection-Detected"
    Source: "AI Content Safety / Copilot"
    Severity: "Critical"
    Trigger: "Malicious prompt pattern detected"
    Action: "Block user, alert CISO, preserve evidence"
    SAMA_Reference: "3.3.15.1 - Immediate incident reporting"
    
  - Name: "SAMA-AI-Data-Exfiltration"
    Source: "Purview DLP"
    Severity: "Critical"
    Trigger: "Large data egress via AI >10GB/hour"
    Action: "Block session, isolate account, notify SAMA"
    SAMA_Reference: "3.3.15 - High severity incident"
    
  - Name: "SAMA-AI-Unauthorized-Model-Deploy"
    Source: "Azure Activity Log"
    Severity: "Critical"
    Trigger: "Production model deployed without approval"
    Action: "Rollback deployment, audit trail, escalate"
    SAMA_Reference: "3.3.7.1 - Change management violation"
    
  - Name: "SAMA-AI-PII-Leak-Copilot"
    Source: "Purview Insider Risk"
    Severity: "Critical"
    Trigger: "Customer PII in Copilot prompt/response"
    Action: "Purge logs, disable user, investigate"
    SAMA_Reference: "3.3.9.1 - Data confidentiality breach"
    
  - Name: "SAMA-AI-Admin-Compromise"
    Source: "Entra ID Protection"
    Severity: "Critical"
    Trigger: "AI admin account anomalous activity"
    Action: "Revoke sessions, MFA reset, forensics"
    SAMA_Reference: "3.3.5.13 - Privileged access compromise"
```

### Tier 2 Alerts (High Priority - 1 hour SLA)

```yaml
AI_High_Alerts:
  - Name: "SAMA-AI-Shadow-AI-Detected"
    Source: "Defender for Cloud Apps"
    Severity: "High"
    Trigger: "Unauthorized AI service usage"
    Action: "Block app, user notification, policy review"
    
  - Name: "SAMA-AI-Model-Drift"
    Source: "AI Foundry Monitoring"
    Severity: "High"
    Trigger: "Model accuracy <80% baseline"
    Action: "Investigate data quality, retrain model"
    
  - Name: "SAMA-Copilot-Oversharing"
    Source: "Purview DSPM"
    Severity: "High"
    Trigger: "Copilot accessing overshared sites"
    Action: "Restrict site access, review permissions"
```

---

## AI Compliance Checklist

### Pre-Production AI Deployment

- [ ] **Governance** (3.1.1)
  - [ ] AI governance committee established with SAMA representation
  - [ ] Board approval documented for AI initiative
  - [ ] CISO briefed on AI risks and controls
  
- [ ] **Risk Assessment** (3.2.1)
  - [ ] AI risk assessment completed using Microsoft RAI framework
  - [ ] Prompt injection risks evaluated and mitigated
  - [ ] Data leakage risks assessed with DLP policies
  - [ ] Model bias and fairness evaluated
  
- [ ] **Data Protection** (3.3.3, 3.3.9)
  - [ ] AI training data classified with sensitivity labels
  - [ ] Customer data encrypted with CMK (if applicable)
  - [ ] Data retention policies configured (7 years minimum)
  - [ ] Data residency verified (Saudi Arabia/UAE regions only)
  
- [ ] **Access Control** (3.3.5)
  - [ ] MFA enforced for all AI resource access
  - [ ] Phishing-resistant authentication enabled for admins
  - [ ] Just-in-time access configured via PIM
  - [ ] Service principals using managed identities only
  
- [ ] **Security Testing** (3.2.4)
  - [ ] Penetration testing completed (OWASP Top 10 for LLM)
  - [ ] Red team exercises for prompt injection
  - [ ] Vulnerability scan results remediated
  - [ ] Security review sign-off obtained
  
- [ ] **Monitoring** (3.3.14)
  - [ ] AI audit logging enabled (verbose mode)
  - [ ] Sentinel analytics rules deployed
  - [ ] SOC team trained on AI security alerts
  - [ ] Incident response playbook documented
  
- [ ] **Compliance** (3.2.2)
  - [ ] Regulatory compliance assessment (ISO 42001, GDPR)
  - [ ] AI transparency documentation (model cards)
  - [ ] SAMA notification procedure documented
  - [ ] Annual review schedule established

### Post-Production AI Operations

- [ ] **Continuous Monitoring**
  - [ ] Daily review of AI security alerts
  - [ ] Weekly compliance dashboard review
  - [ ] Monthly security posture assessment
  - [ ] Quarterly penetration testing
  
- [ ] **Incident Management**
  - [ ] AI incident response tested
  - [ ] SAMA notification process verified
  - [ ] Forensics capabilities validated
  - [ ] Lessons learned documented

---

## Appendix: AI-Specific Sentinel Rules

### Copilot Data Leakage Detection
```kql
MicrosoftPurviewAuditLogs
| where TimeGenerated > ago(1h)
| where Operation == "CopilotInteraction"
| extend PromptText = tostring(AdditionalProperties.Prompt)
| extend ResponseText = tostring(AdditionalProperties.Response)
| where PromptText contains_cs "password" 
    or PromptText contains_cs "credit card"
    or ResponseText contains_regex @"\b\d{16}\b"  // Credit card pattern
| extend SensitiveDataType = case(
    PromptText contains "password", "Password",
    ResponseText contains_regex @"\b\d{16}\b", "Credit Card",
    "Unknown"
)
| project TimeGenerated, UserId, SensitiveDataType, ClientIP = CallerIpAddress
```

### AI Model Tampering Detection
```kql
AzureActivity
| where TimeGenerated > ago(24h)
| where ResourceProvider == "Microsoft.MachineLearningServices"
| where OperationNameValue in~ ("ModelVersions/write", "Models/write")
| where ActivityStatusValue != "Success" or CallerIpAddress !in~ (KnownDataScienceIPs)
| extend Caller = tostring(Claims.["http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn"])
| join kind=leftanti (
    AzureActivity
    | where TimeGenerated > ago(90d)
    | where OperationNameValue in~ ("ModelVersions/write", "Models/write")
    | summarize by Caller = tostring(Claims.["upn"])
) on Caller
| project TimeGenerated, Caller, Operation = OperationNameValue, ModelName = Resource, Result = ActivityStatusValue
```

### Anomalous AI Compute Usage
```kql
AzureMetrics
| where TimeGenerated > ago(1h)
| where ResourceProvider == "MICROSOFT.MACHINELEARNINGSERVICES"
| where MetricName == "GPUUtilization"
| summarize AvgGPU = avg(Average) by Resource, bin(TimeGenerated, 10m)
| where AvgGPU > 95  // Sustained high usage
| join kind=inner (
    AzureActivity
    | where TimeGenerated > ago(1h)
    | where ResourceProvider == "Microsoft.MachineLearningServices"
    | where OperationNameValue == "Jobs/action"
) on Resource
| extend Submitter = tostring(Claims.["upn"])
| summarize JobCount = count(), TotalGPUTime = sum(AvgGPU) by Submitter, Resource
| where JobCount > 100 or TotalGPUTime > 5000  // Unusual volume
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-10-31 | Security Architecture Team | Initial AI Foundry & Copilot mapping |

**Next Review**: 2026-01-31 (Quarterly)

**References**:
1. SAMA Cyber Security Framework v1.0 (May 2017)
2. [Azure AI Foundry Security Documentation](https://learn.microsoft.com/azure/ai-foundry)
3. [Microsoft 365 Copilot Security](https://learn.microsoft.com/copilot/microsoft-365)
4. [Microsoft Responsible AI Standard](https://aka.ms/RAI)
5. [ISO/IEC 42001:2023 - AI Management Systems](https://www.iso.org/standard/81230.html)
6. [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

---

*This mapping provides technical implementation guidance for SAMA compliance with AI workloads. Organizations must validate controls with internal compliance and legal teams, and obtain SAMA approval before production deployment of AI systems handling customer financial data.*
