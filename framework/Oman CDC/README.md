# Oman CDC Cloud Security Controls - Azure Policy Initiative

## Overview

This Azure Policy initiative implements the **Cyber Defense Centre (CDC) of Oman** cloud security controls framework for organizations using external cloud services. The initiative maps CDC requirements to Azure Policy definitions and provides a compliance dashboard for regulatory monitoring.

## About Oman CDC

The **Cyber Defense Centre (CDC)** is Oman's national authority for cybersecurity governance, operating under the Ministry of Transport, Communications and Information Technology (MTCIT). The CDC establishes controls and policies for organizations using external cloud computing services to ensure data protection, security, and compliance with Omani legislation.

## Framework Coverage

This initiative covers three main categories of CDC controls:

### Technical Requirements (CDC-TR-*)
- **CDC-TR-01a**: Firewalls and DDoS Protection
- **CDC-TR-01b**: OS and Network Hardening
- **CDC-TR-02**: Centralized Identity and Access Management
- **CDC-TR-03**: SIEM Integration and Log Aggregation
- **CDC-TR-04a**: Multi-Factor Authentication
- **CDC-TR-04b**: Geographic Access Restrictions
- **CDC-TR-05**: Penetration Testing and Risk Assessment
- **CDC-TR-06**: Data Classification
- **CDC-TR-07a**: Data Encryption in Transit and at Rest
- **CDC-TR-07b**: Customer-Managed Keys (BYOK)
- **CDC-TR-07c**: Least Privilege Access
- **CDC-TR-08**: Cloud Data Loss Prevention
- **CDC-TR-09**: Antivirus and Antimalware
- **CDC-TR-10**: Patch Management
- **CDC-TR-11**: Backup and Recovery
- **CDC-TR-12**: Cyber Incident Response Plan

### Policy Requirements (CDC-POL-*)
- **CDC-POL-01**: Data Classification Prerequisite
- **CDC-POL-02**: CDC Policy Compliance
- **CDC-POL-03**: Geographic Hosting Approval
- **CDC-POL-05**: Risk Assessment Documentation
- **CDC-POL-06**: Semi-Annual Security Audit Reports
- **CDC-POL-07**: Local Backup Retention
- **CDC-POL-08**: AI Application Usage
- **CDC-POL-10**: Prohibition on Secret Data
- **CDC-POL-13**: Encryption Key Management

### Contractual Requirements (CDC-CON-*)
- **CDC-CON-03**: Encryption at All Stages
- **CDC-CON-06**: Security Incident Notification
- **CDC-CON-07**: Audit Log Platform and Retention

## Files Included

- **`cdc_groups.json`** - Policy group definitions (control IDs)
- **`cdc_policies.json`** - Azure Policy mappings (37 policy definitions)
- **`cdc_params.json`** - Policy parameters (empty for this initiative)
- **`CreateCDCInitiative.ps1`** - PowerShell deployment script
- **`CDC_Initiative.json`** - Complete initiative definition
- **`README.md`** - This documentation

## Deployment Instructions

### Prerequisites

1. **Azure Subscription** with appropriate permissions
2. **Azure PowerShell** or **Azure CLI** installed
3. **Policy Contributor** role or higher
4. **Microsoft Defender for Cloud** enabled (recommended)

### Option 1: PowerShell Deployment

```powershell
# Navigate to the framework directory
cd "Oman CDC"

# Deploy to current subscription
./CreateCDCInitiative.ps1

# Deploy to management group
./CreateCDCInitiative.ps1 -ManagementGroupId "mg-omancdc"

# Deploy and assign immediately
./CreateCDCInitiative.ps1 -AssignAfterCreation
```

### Option 2: Azure CLI Deployment

```bash
# Create the policy initiative
az policy set-definition create \
  --name 'OmanCDC_Cloud_Compliance' \
  --display-name 'Oman CDC Cloud Security Controls' \
  --description 'CDC of Oman cloud security controls framework' \
  --metadata category='Regulatory Compliance' version='1.0.0' \
  --definitions cdc_policies.json \
  --definition-groups cdc_groups.json \
  --params cdc_params.json

# Assign the initiative
az policy assignment create \
  --name 'OmanCDC-Assignment' \
  --display-name 'Oman CDC Cloud Controls' \
  --policy-set-definition 'OmanCDC_Cloud_Compliance' \
  --scope /subscriptions/{subscription-id}
```

### Option 3: Azure Portal Deployment

1. Go to **Azure Portal** > **Policy** > **Definitions**
2. Click **+ Policy definition** > **Initiative definition**
3. Upload the JSON files or copy content
4. Save and assign to desired scope

## Policy Mappings

The initiative includes **37 Azure Policy definitions** mapped to CDC controls:

### Network Security
- Azure DDoS Network Protection should be enabled
- Azure Firewall should be enabled on virtual networks
- Subnets should be associated with a Network Security Group
- Network Watcher should be enabled

### Identity & Access Management
- MFA should be enabled on accounts with write permissions
- Role-Based Access Control (RBAC) should be used on Kubernetes Services
- Just-In-Time network access control should be applied on virtual machines
- Management ports should be closed on your virtual machines

### Data Protection & Encryption
- Transparent Data Encryption on SQL databases should be enabled
- Secure transfer to storage accounts should be enabled
- Storage accounts should use customer-managed key for encryption
- PostgreSQL servers should use customer-managed keys to encrypt data at rest
- OS and data disks should be encrypted with a customer-managed key

### Logging & Monitoring
- Enable logging by category group for Log Analytics workspaces
- Diagnostic settings for selected resource types should be enabled
- Activity log should be retained for at least one year

### Backup & DR
- Azure Backup should be enabled for Virtual Machines
- Geo-redundant backup should be enabled for Azure Database services

### Key Management
- Key Vault keys should have an expiration date
- Keys should have the specified maximum validity period
- Secrets should have the specified maximum validity period
- Certificates should have the specified maximum validity period

### Security Monitoring
- Microsoft Defender for servers should be enabled
- Microsoft Defender for Storage should be enabled
- Endpoint protection solution should be installed on virtual machines

## Implementation Guidance

### Step 1: Pre-Deployment Assessment

1. **Data Classification** (Required)
   - Complete data classification per Oman regulations
   - Document classification taxonomy
   - Apply sensitivity labels using Microsoft Purview

2. **Risk Assessment** (CDC-POL-05)
   - Conduct risk assessment for cloud hosting
   - Link findings to organizational risk register
   - Obtain approval from head of organization

3. **Region Selection** (CDC-POL-03)
   - Identify CDC-approved geographic regions
   - Request approval for data hosting locations
   - Document data protection law compatibility

### Step 2: Azure Configuration

1. **Enable Microsoft Defender for Cloud**
   ```powershell
   # Enable Defender for Cloud enhanced security features
   Set-AzSecurityPricing -Name "VirtualMachines" -PricingTier "Standard"
   Set-AzSecurityPricing -Name "StorageAccounts" -PricingTier "Standard"
   Set-AzSecurityPricing -Name "SqlServers" -PricingTier "Standard"
   Set-AzSecurityPricing -Name "KeyVaults" -PricingTier "Standard"
   ```

2. **Configure Azure Policy Allowed Locations**
   ```powershell
   # Restrict deployments to approved regions
   $params = @{
       listOfAllowedLocations = @("uaenorth", "uaecentral")
   }
   New-AzPolicyAssignment `
       -Name "CDC-Approved-Regions" `
       -PolicyDefinition (Get-AzPolicyDefinition -Name "e56962a6-4747-49cd-b67b-bf8b01975c4c") `
       -Scope "/subscriptions/{subscription-id}" `
       -PolicyParameterObject $params
   ```

3. **Deploy Microsoft Sentinel** (CDC-TR-03)
   - Create Log Analytics workspace
   - Enable Microsoft Sentinel
   - Configure data connectors
   - Set 6-month minimum retention

4. **Configure Conditional Access** (CDC-TR-04a, CDC-TR-04b)
   - Create MFA policy for all users
   - Configure named locations for Oman
   - Block access from high-risk countries

### Step 3: Post-Deployment Actions

1. **Review Compliance Dashboard**
   - Wait 24 hours for initial compliance evaluation
   - Review non-compliant resources
   - Create remediation plan

2. **Document Compliance Evidence**
   - Export compliance reports
   - Maintain audit trail
   - Document exceptions and compensating controls

3. **Schedule Recurring Tasks**
   - Semi-annual CDC audit reports (CDC-POL-06)
   - CDC approval renewal every 2 years (CDC-POL-11)
   - Quarterly access reviews
   - Annual penetration testing

## Manual Controls

The following CDC controls require **manual attestation** and cannot be fully automated via Azure Policy:

### Governance & Compliance
- **CDC-POL-01**: Data classification completion
- **CDC-POL-02**: Overall CDC policy compliance
- **CDC-POL-04**: Non-standard region approval documentation
- **CDC-POL-06**: Semi-annual security audit reports
- **CDC-POL-09**: Communication service approvals from TRA
- **CDC-POL-11**: CDC approval validity tracking
- **CDC-POL-12**: Existing hosting notification
- **CDC-POL-14**: Approval revocation procedures

### Contractual Requirements
- **CDC-CON-01**: Provider policy change consent
- **CDC-CON-02**: Prohibition on unauthorized data access
- **CDC-CON-04**: Data segregation requirements
- **CDC-CON-05**: Legal request notifications
- **CDC-CON-08**: AI training data usage restrictions
- **CDC-CON-09**: Training and knowledge transfer
- **CDC-CON-10**: Provider certifications (ISO 27001, SOC 2)
- **CDC-CON-11**: Subcontractor compliance
- **CDC-CON-12**: Support staff privacy requirements
- **CDC-CON-13**: Contract termination and migration
- **CDC-CON-14**: Data ownership and retrieval
- **CDC-CON-15**: Service Level Agreement
- **CDC-CON-16**: Data destruction procedures
- **CDC-CON-17**: Data residency compliance

### Operational Controls
- **CDC-TR-04b**: Geographic blocking configuration (Entra ID feature)
- **CDC-TR-05**: Penetration testing execution
- **CDC-TR-08**: DLP policy configuration (Microsoft Purview)
- **CDC-TR-12**: Incident response plan documentation

## Azure Service Mappings

### Required Services

| CDC Control | Azure Service | Configuration |
|-------------|---------------|---------------|
| CDC-TR-01a | Azure Firewall, DDoS Protection | Deploy Premium tier with threat intelligence |
| CDC-TR-02 | Microsoft Entra ID, PIM | Configure RBAC and just-in-time access |
| CDC-TR-03 | Microsoft Sentinel, Log Analytics | 6-month minimum retention |
| CDC-TR-04a | Conditional Access | MFA for all users |
| CDC-TR-04b | Named Locations | Geo-blocking for high-risk countries |
| CDC-TR-06 | Microsoft Purview | Data discovery and classification |
| CDC-TR-07a | Storage Encryption, SQL TDE | TLS 1.2+, encryption at rest |
| CDC-TR-07b | Key Vault, CMK | Customer-managed keys for sensitive data |
| CDC-TR-08 | Purview DLP, Defender for Cloud Apps | DLP policies across M365 and Azure |
| CDC-TR-09 | Defender for Endpoint, Antimalware | Real-time protection enabled |
| CDC-TR-10 | Azure Update Manager | Automatic assessment and patching |
| CDC-TR-11 | Recovery Services Vault, Azure Backup | Immutable vault, GRS, offline copies |

### Optional/Enhanced Services

- **Microsoft Defender for Cloud** - CSPM, attack path analysis
- **Azure Bastion** - Secure RDP/SSH access
- **Customer Lockbox** - Support access approval (CDC-CON-02)
- **Azure Dedicated Host** - Physical isolation (CDC-CON-04)
- **Application Insights** - Application monitoring
- **Azure Monitor** - Alerting and automation

## Compliance Monitoring

### Defender for Cloud Integration

The initiative integrates with Microsoft Defender for Cloud:

1. **Regulatory Compliance Dashboard**
   - Navigate to Defender for Cloud > Regulatory Compliance
   - Add "Oman CDC Cloud Security Controls"
   - View compliance score and failed assessments

2. **Secure Score**
   - Track security posture improvements
   - Prioritize recommendations by impact
   - Link to CDC control requirements

3. **Attack Path Analysis**
   - Identify critical risks (CDC-POL-05)
   - Visualize attack vectors
   - Implement risk mitigations

### Reporting

Generate compliance reports for CDC submission:

```powershell
# Export compliance state
$compliance = Get-AzPolicyState -PolicySetDefinitionName "OmanCDC_Cloud_Compliance"
$compliance | Export-Csv "CDC_Compliance_Report_$(Get-Date -Format 'yyyyMMdd').csv"

# Get compliance summary
Get-AzPolicyStateSummary -PolicySetDefinitionName "OmanCDC_Cloud_Compliance"
```

## Key Considerations

### Data Classification
- **Secret/Top Secret data**: Prohibited from cloud storage (CDC-POL-10)
- **Classified/Sensitive data**: Requires CDC geographic approval
- **Purview**: Use for automated discovery and labeling

### Geographic Restrictions
- Deploy to **CDC-approved regions only** (CDC-POL-03)
- Azure regions: UAE North/Central recommended for Oman proximity
- Non-approved regions require written CDC approval

### Encryption Requirements
- **TLS 1.2+** mandatory for data in transit
- **Customer-managed keys** for classified data (CDC-TR-07b)
- **Key rotation** and expiration policies enforced

### Backup & DR
- **Local backup copies** required (CDC-POL-07)
- Ability to process data within Oman if cloud unavailable
- **Immutable backups** with cross-region restore

### AI Governance
- AI usage subject to **MTCIT policies** (CDC-POL-08)
- **No training on customer data** (CDC-CON-08)
- Azure OpenAI with content filtering and private endpoints

### Audit & Reporting
- **6-month minimum** log retention (CDC-CON-07)
- **Semi-annual audit reports** to CDC (CDC-POL-06)
- Activity log retention: 12 months recommended

### Approval & Renewal
- CDC approval valid for **2 years** (CDC-POL-11)
- Renewal required with contract renewal
- Tag resources with approval date and expiry

## Troubleshooting

### Common Issues

1. **Policy Assignment Failures**
   - Verify permissions (Policy Contributor role)
   - Check policy definition IDs exist
   - Review JSON syntax for errors

2. **Compliance Evaluation Delays**
   - Initial evaluation takes 24 hours
   - Manual trigger: `Start-AzPolicyComplianceScan`
   - Check policy exemptions

3. **Defender for Cloud Not Showing Initiative**
   - Ensure Defender CSPM is enabled
   - Wait for sync (can take 1 hour)
   - Check initiative assignment scope

## Support & Resources

### Documentation
- **Oman CDC**: https://cdc.om/
- **Azure Policy**: https://learn.microsoft.com/azure/governance/policy/
- **Defender for Cloud**: https://learn.microsoft.com/azure/defender-for-cloud/

### Related Frameworks
- ISO 27001:2022 (required by CDC-REQ-ISO27001)
- ISO 27017:2015 (required by CDC-REQ-ISO27017)
- ISO 27018:2019 (required by CDC-REQ-ISO27018)
- SOC 2 Type II (required by CDC-REQ-SOC2)

### Azure Trust Center
- Verify Microsoft compliance certifications
- Review data processing terms
- Check regional data residency

## Changelog

### Version 1.0.0 (January 2026)
- Initial release
- 37 Azure Policy definitions mapped
- Coverage for 28 CDC controls
- Technical, policy, and contractual requirements

## Contributing

This initiative is maintained as part of the **Cloud Compliance Toolkit (CCToolkit)** project. To contribute:

1. Review existing mappings in `/catalogues`
2. Suggest additional policy mappings
3. Document implementation experiences
4. Share CDC compliance best practices

## License

This compliance mapping is provided as-is for reference purposes. Organizations are responsible for their own CDC compliance and should work with their legal and compliance teams to ensure full adherence to CDC requirements.

---

**Maintained by**: Cloud Compliance Toolkit Team  
**Last Updated**: January 2026  
**Version**: 1.0.0
