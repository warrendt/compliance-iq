# Oman CDC Cloud Controls - Quick Reference Guide

## 🎯 Overview
**Authority**: Cyber Defense Centre (CDC), Oman  
**Framework**: Cloud Security Controls for External Cloud Services  
**Target**: Organizations in Oman using public cloud services  
**Approval Validity**: 2 years (requires renewal)

## 📊 Control Categories

### Technical Requirements (CDC-TR-*)
16 technical controls for cloud security implementation

### Policy Requirements (CDC-POL-*)
14 governance and policy compliance controls

### Contractual Requirements (CDC-CON-*)
17 contractual obligations with cloud providers

**Total**: 47 controls (28 mappable to Azure Policy)

---

## 🔑 Key Technical Controls

### 🛡️ Network Security

| Control | Title | Azure Implementation |
|---------|-------|---------------------|
| **CDC-TR-01a** | Firewalls & DDoS | Azure Firewall Premium + DDoS Network Protection |
| **CDC-TR-01b** | OS Hardening | Guest Configuration (CIS benchmarks) |

**Azure Policies**:
- Azure DDoS Network Protection should be enabled
- Azure Firewall should be enabled
- Subnets should be associated with NSG

### 🔐 Identity & Access

| Control | Title | Azure Implementation |
|---------|-------|---------------------|
| **CDC-TR-02** | Centralized IAM | Microsoft Entra ID + RBAC + PIM |
| **CDC-TR-04a** | Multi-Factor Authentication | Conditional Access (MFA for all users) |
| **CDC-TR-04b** | Geographic Restrictions | Named Locations + Conditional Access |
| **CDC-TR-07c** | Least Privilege | JIT VM Access + PIM roles |

**Azure Policies**:
- MFA should be enabled on accounts with write permissions
- RBAC should be used on Kubernetes Services
- JIT network access control should be applied

### 🔒 Data Protection

| Control | Title | Azure Implementation |
|---------|-------|---------------------|
| **CDC-TR-06** | Data Classification | Microsoft Purview Data Map + Sensitivity Labels |
| **CDC-TR-07a** | Encryption at Rest & Transit | Storage Encryption + TLS 1.2+ + SQL TDE |
| **CDC-TR-07b** | Customer-Managed Keys | Key Vault CMK for classified data |
| **CDC-TR-08** | Cloud DLP | Microsoft Purview DLP + Defender for Cloud Apps |

**Azure Policies**:
- Storage accounts should use customer-managed key for encryption
- Transparent Data Encryption should be enabled on SQL databases
- Secure transfer to storage accounts should be enabled
- PostgreSQL/MySQL should use customer-managed keys

### 📝 Logging & Monitoring

| Control | Title | Azure Implementation |
|---------|-------|---------------------|
| **CDC-TR-03** | SIEM Integration | Microsoft Sentinel + Log Analytics |
| **CDC-CON-07** | Log Retention | Diagnostic Settings (6-month minimum) |

**Azure Policies**:
- Enable logging by category group for Log Analytics workspaces
- Diagnostic settings should be enabled
- Activity log should be retained for at least one year

### 🛠️ Operations

| Control | Title | Azure Implementation |
|---------|-------|---------------------|
| **CDC-TR-09** | Antivirus/Antimalware | Defender for Endpoint + Defender for Servers |
| **CDC-TR-10** | Patch Management | Azure Update Manager |
| **CDC-TR-11** | Backup & Recovery | Recovery Services Vault + Azure Backup (GRS) |

**Azure Policies**:
- System updates should be installed on machines
- Endpoint protection solution should be installed
- Azure Backup should be enabled for VMs
- Geo-redundant backup should be enabled

---

## 📋 Critical Policy Requirements

### 🚫 Prohibitions

| Control | Requirement | Action |
|---------|-------------|--------|
| **CDC-POL-10** | No Secret/Top Secret data in cloud | Apply deny policies for tagged resources |

### ✅ Prerequisites

| Control | Requirement | Timeline |
|---------|-------------|----------|
| **CDC-POL-01** | Data classification complete | Before cloud deployment |
| **CDC-POL-05** | Risk assessment documented | Before CDC approval request |
| **CDC-POL-03** | Geographic approval obtained | Before data hosting |

### 🔄 Recurring Requirements

| Control | Frequency | Deliverable |
|---------|-----------|-------------|
| **CDC-POL-06** | Semi-annual | Security audit report to CDC |
| **CDC-POL-11** | Every 2 years | CDC approval renewal |
| **CDC-TR-05** | Annual | Penetration test report |

---

## 🌍 Geographic Controls

### Allowed Regions (CDC-POL-03)
- Requires CDC approval for specific regions
- Verify data protection law compatibility
- **Recommended for Oman**: UAE North, UAE Central

### Azure Policy Implementation
```powershell
# Restrict to approved regions
New-AzPolicyAssignment `
  -Name "CDC-Approved-Regions" `
  -PolicyDefinition (Get-AzPolicyDefinition -Id "e56962a6-4747-49cd-b67b-bf8b01975c4c") `
  -Scope "/subscriptions/{id}" `
  -PolicyParameter '{"listOfAllowedLocations":["uaenorth","uaecentral"]}'
```

---

## 🤖 AI Governance (CDC-POL-08)

### Requirements
- AI usage subject to MTCIT policies
- No training on customer data (CDC-CON-08)
- Implement content filtering
- Use private endpoints

### Azure OpenAI Configuration
- Deploy in private VNet
- Enable Customer Lockbox
- Apply DLP policies
- Configure content filters
- Opt out of model training

**Azure Policy**:
- Cognitive Services should use private link

---

## 🔑 Key Management (CDC-POL-13)

### Requirements
- Key expiration dates
- Rotation policies
- Soft delete + purge protection
- CMK for classified data

**Azure Policies**:
- Key Vault keys should have an expiration date
- Keys should have maximum validity period
- Secrets should have maximum validity period
- Certificates should have maximum validity period

---

## 📊 Compliance Dashboard

### Enable in Defender for Cloud
1. Navigate to **Regulatory Compliance**
2. Add **Oman CDC Cloud Security Controls**
3. View compliance score
4. Remediate failed assessments

### Generate Reports
```powershell
# Export compliance state
Get-AzPolicyState -PolicySetDefinitionName "OmanCDC_Cloud_Compliance" | 
  Export-Csv "CDC_Compliance_$(Get-Date -Format 'yyyyMMdd').csv"

# Get summary
Get-AzPolicyStateSummary -PolicySetDefinitionName "OmanCDC_Cloud_Compliance"
```

---

## 🎯 Implementation Roadmap

### Phase 1: Prerequisites (Week 1-2)
- [ ] Complete data classification (CDC-POL-01)
- [ ] Conduct risk assessment (CDC-POL-05)
- [ ] Request CDC geographic approval (CDC-POL-03)
- [ ] Document compliance approach

### Phase 2: Foundation (Week 3-4)
- [ ] Enable Defender for Cloud (all plans)
- [ ] Deploy Microsoft Sentinel
- [ ] Configure Log Analytics (6-month retention)
- [ ] Set up Microsoft Purview

### Phase 3: Identity & Access (Week 5-6)
- [ ] Configure Conditional Access + MFA
- [ ] Set up named locations (geo-blocking)
- [ ] Enable PIM for privileged roles
- [ ] Implement JIT VM Access

### Phase 4: Data Protection (Week 7-8)
- [ ] Deploy Key Vault with CMK
- [ ] Enable encryption at rest (Storage, SQL)
- [ ] Enforce TLS 1.2+ (all services)
- [ ] Configure Purview DLP policies

### Phase 5: Network Security (Week 9-10)
- [ ] Deploy Azure Firewall Premium
- [ ] Enable DDoS Network Protection
- [ ] Associate NSGs with all subnets
- [ ] Restrict to approved regions

### Phase 6: Policy Deployment (Week 11)
- [ ] Deploy CDC initiative
- [ ] Assign to subscriptions
- [ ] Review compliance dashboard
- [ ] Remediate non-compliant resources

### Phase 7: Operations (Week 12)
- [ ] Configure Azure Update Manager
- [ ] Enable Azure Backup (GRS)
- [ ] Deploy Defender for Endpoint
- [ ] Set up backup vaults (immutable)

### Phase 8: Documentation (Week 13-14)
- [ ] Document all controls
- [ ] Create compliance evidence
- [ ] Schedule recurring tasks
- [ ] Prepare CDC submission

---

## 🔧 Defender for Cloud Setup

### Enable Enhanced Security Features
```powershell
# Enable all Defender plans
$plans = @("VirtualMachines", "StorageAccounts", "SqlServers", 
           "ContainerRegistry", "KeyVaults", "AppServices", "Dns", "Arm")
           
foreach ($plan in $plans) {
    Set-AzSecurityPricing -Name $plan -PricingTier "Standard"
}
```

### Configure Security Contacts
```powershell
Set-AzSecurityContact `
  -Name "default1" `
  -Email "security@organization.om" `
  -Phone "+968-XXXXXXXX" `
  -AlertAdmin $true `
  -NotifyOnAlert $true
```

---

## 📞 CDC Contact & Submission

### Semi-Annual Reports (CDC-POL-06)
**Frequency**: Every 6 months  
**Content**:
- Compliance dashboard export
- Security incidents summary
- Control implementation status
- Remediation plans

### CDC Approval Renewal (CDC-POL-11)
**Frequency**: Every 2 years  
**Reminder**: Set calendar alert 90 days before expiry  
**Documentation**:
- Updated risk assessment
- Compliance evidence
- Contract renewal details

---

## ⚠️ Manual Attestation Required

The following controls **cannot be automated** and require manual documentation:

### Governance
- CDC-POL-01, 02, 04, 06, 09, 11, 12, 14

### Contractual
- CDC-CON-01, 02, 04, 05, 08, 09, 10, 11, 12, 13, 14, 15, 16, 17

### Operational
- CDC-TR-04b (geo-blocking config)
- CDC-TR-05 (penetration testing)
- CDC-TR-08 (DLP configuration)
- CDC-TR-12 (incident response plan)

**Action**: Maintain compliance documentation repository with evidence for manual controls.

---

## 📚 Required Certifications

Verify cloud provider holds valid certifications:

| Certification | CDC Reference | Azure Status |
|--------------|---------------|--------------|
| ISO 27001 | CDC-REQ-ISO27001 | ✅ Certified |
| ISO 27002 | CDC-REQ-ISO27002 | ✅ Compliant |
| ISO 27017 | CDC-REQ-ISO27017 | ✅ Certified |
| ISO 27018 | CDC-REQ-ISO27018 | ✅ Certified |
| ISO 22237 | CDC-REQ-ISO22237 | ✅ Data center certified |
| SOC 2 Type II | CDC-REQ-SOC2 | ✅ Available |

**Verification**: https://servicetrust.microsoft.com/

---

## 🔗 Resources

### Oman CDC
- Website: https://cdc.om/
- Email: info@cdc.om

### Azure Documentation
- Azure Policy: https://aka.ms/azurepolicy
- Defender for Cloud: https://aka.ms/defendercloud
- Microsoft Purview: https://aka.ms/purview
- Microsoft Sentinel: https://aka.ms/sentinel

### Compliance Tools
- Microsoft Trust Center: https://servicetrust.microsoft.com/
- Azure Compliance Documentation: https://aka.ms/azurecompliance
- Cloud Compliance Toolkit: (this repository)

---

## ✅ Quick Deployment Checklist

```bash
# 1. Create initiative
cd "Oman CDC"
./CreateCDCInitiative.ps1

# 2. Enable Defender for Cloud
Set-AzSecurityPricing -Name "VirtualMachines" -PricingTier "Standard"
Set-AzSecurityPricing -Name "StorageAccounts" -PricingTier "Standard"

# 3. Configure region restrictions
New-AzPolicyAssignment `
  -Name "CDC-Regions" `
  -PolicyDefinition "e56962a6-4747-49cd-b67b-bf8b01975c4c" `
  -Scope "/subscriptions/{id}" `
  -PolicyParameter '{"listOfAllowedLocations":["uaenorth"]}'

# 4. Verify compliance
Get-AzPolicyStateSummary -PolicySetDefinitionName "OmanCDC_Cloud_Compliance"

# 5. Generate report
Get-AzPolicyState -PolicySetDefinitionName "OmanCDC_Cloud_Compliance" |
  Export-Csv "CDC_Compliance_Report.csv"
```

---

**Document Version**: 1.0.0  
**Last Updated**: January 2026  
**Maintained by**: Cloud Compliance Toolkit Team
