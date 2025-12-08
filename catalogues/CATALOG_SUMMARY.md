# Cloud Compliance Toolkit - Control Catalogs with Azure Mappings

## Overview
This toolkit provides comprehensive control catalogs for multiple compliance frameworks, each mapped to specific Azure Policy definitions and Microsoft Defender for Cloud recommendations.

## Generated Catalogs

### 1. SAMA_Catalog_Azure_Mappings.csv
**Framework:** Saudi Arabian Monetary Authority (SAMA) Cybersecurity Framework
**Controls:** 36 controls covering financial sector cybersecurity requirements
**Key Domains:**
- Cybersecurity Governance
- Risk Management & Compliance
- Third-Party Security
- Business Continuity & Disaster Recovery
- Incident Response
- Identity & Access Control
- Network Security
- Data Protection & Privacy
- Logging & Monitoring
- Vulnerability Management
- Secure Development & Change Management
- AI Governance
- Productivity AI (Microsoft 365 Copilot)

**Azure Mappings Include:**
- Azure Policy: MFA enforcement, network security, encryption, logging
- Defender for Cloud: Identity management, network security, data protection, vulnerability management

### 2. CCC_Framework_Azure_Mappings.csv
**Framework:** Cloud Computing Controls (CCC) Framework
**Controls:** 32 controls covering multi-cloud governance and security
**Key Domains:**
- Infrastructure Security (IaaS)
- Platform Security (PaaS)
- Data Security
- Identity & Access Management
- Network Security
- Security Operations
- Compliance
- Disaster Recovery

**Azure Mappings Include:**
- Azure Policy: VM hardening, network segmentation, encryption, database security
- Defender for Cloud: Container security, serverless security, vulnerability scanning

### 3. ADHICS_Framework_Azure_Mappings.csv
**Framework:** Abu Dhabi Health Information and Cyber Security (ADHICS) Standard v2
**Controls:** 36 controls covering healthcare sector cybersecurity
**Key Domains:**
- Governance
- Protected Health Information (PHI)
- Identity & Access Management
- Network Security (Clinical & Medical Device)
- Application Security (EHR, PACS, LIS)
- Medical Device Security
- Data Management
- Compliance (HIPAA, Patient Privacy)
- Business Continuity

**Azure Mappings Include:**
- Azure Policy: PHI encryption, MFA enforcement, network segmentation
- Defender for Cloud: Healthcare-specific data protection, clinical system security

### 4. SITA_Architecture_Azure_Mappings.csv
**Framework:** Microsoft-SITA Reference Architecture for Government Cloud
**Controls:** 36 controls covering sovereign cloud requirements
**Key Domains:**
- Sovereign Cloud Architecture (SPO 1-14)
- Network Architecture
- Identity & Access Management
- Data Security (Classified Data)
- Security Operations (Government SOC)
- Compliance & Governance (POPIA)
- Business Continuity

**Azure Mappings Include:**
- Azure Policy: MFA, network security, customer-managed encryption keys
- Defender for Cloud: Data sovereignty, government compliance, classified data protection

### 5. POPIA_Framework_Azure_Mappings.csv
**Framework:** Protection of Personal Information Act (POPIA) - South African Data Protection Law
**Controls:** 16 controls covering data protection and privacy requirements
**Key Domains:**
- Accountability
- Processing Limitation
- Purpose Specification
- Information Quality
- Security Safeguards
- Data Subject Rights
- Consent Management
- Cross-Border Transfer
- Data Breach Notification
- Privacy Impact Assessment

**Azure Mappings Include:**
- Azure Policy: Encryption, access controls, audit logging
- Defender for Cloud: Data protection, regulatory compliance, information security

### 6. eGovernment_Framework_Azure_Mappings.csv
**Framework:** South African eGovernment Framework
**Controls:** 15 controls covering digital government transformation
**Key Domains:**
- Digital Strategy
- Service Delivery
- Interoperability
- Data Sharing
- Digital Identity
- Cloud-First Policy
- Cybersecurity
- Innovation & Capacity Building
- Mobile Services

**Azure Mappings Include:**
- Azure Policy: Cloud security, identity management, data protection
- Defender for Cloud: Government cybersecurity, identity & access management

### 7. IGR_Framework_Azure_Mappings.csv
**Framework:** Intergovernmental Relations (IGR) Framework Act 13 of 2005
**Controls:** 10 controls covering government coordination and cooperation
**Key Domains:**
- Intergovernmental Coordination
- Information Sharing
- Dispute Resolution
- Joint Planning
- Service Delivery Coordination
- Resource Allocation
- Policy Alignment
- Performance Monitoring

**Azure Mappings Include:**
- Azure Policy: Data sharing controls, monitoring, governance
- Defender for Cloud: Governance, logging & monitoring, regulatory compliance

## CSV File Structure

Each catalog CSV file contains the following columns:

| Column | Description |
|--------|-------------|
| `[Framework]_ID` | Unique control identifier (e.g., SAMA-AC-01) |
| `Domain` | Control domain/category |
| `Control_Name` | Short name of the control |
| `Requirement_Summary` | Detailed description of the control requirement |
| `Control_Type` | Type: Management, Operational, or Technical |
| `Evidence_Examples` | Examples of evidence for compliance |
| `Azure_Policy_Name` | Name of the mapped Azure Policy (if applicable) |
| `Azure_Policy_ID` | Azure Policy definition ID (GUID) |
| `Defender_Control` | Defender for Cloud control category |
| `Defender_Recommendation` | Specific Defender recommendation or control |

## Key Azure Policy Mappings

### Identity & Access Control
- **Policy ID:** `4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b`
- **Name:** Users must authenticate with multi-factor authentication to create or update resources
- **Maps to:** SAMA-AC-01, ADHICS-IAM-01, SITA-IAM-02

### Network Security
- **Policy ID:** `e71308d3-144b-4262-b144-efdc3cc90517`
- **Name:** Subnets should be associated with a Network Security Group
- **Maps to:** SAMA-NS-01, CCC-IaaS-02, ADHICS-Net-01, SITA-Net-01

- **Policy ID:** `ca610c1d-041c-4332-9d88-7ed3094967c7`
- **Name:** App Configuration should use private link
- **Maps to:** SAMA-NS-02, CCC-Net-03, SITA-Net-03

### Encryption & Data Protection
- **Policy ID:** `702dd420-7fcc-42c5-afe8-4026edd20fe0`
- **Name:** OS and data disks should be encrypted with a customer-managed key
- **Maps to:** SAMA-AC-03, CCC-IaaS-03, SITA-Data-02

- **Policy ID:** `18adea5e-f416-4d0f-8aa8-d24321e3e274`
- **Name:** PostgreSQL servers should use customer-managed keys to encrypt data at rest
- **Maps to:** SAMA-DP-02, ADHICS-PHI-01

### Logging & Monitoring
- **Policy ID:** `818719e5-1338-4776-9a9d-3c31e4df5986`
- **Name:** Enable logging by category group for Log Analytics workspaces to Log Analytics
- **Maps to:** SAMA-LM-01

### Vulnerability Management
- **Policy ID:** `e1145ab1-eb4f-43d8-911b-36ddf771d13f`
- **Name:** System updates should be installed on your machines (powered by Azure Update Manager)
- **Maps to:** SAMA-VM-01, CCC-Sec-04, ADHICS-App-02, SITA-Sec-04

- **Policy ID:** `bd876905-5b84-4f73-ab2d-2e7a7c4568d9`
- **Name:** Machines should be configured to periodically check for missing system updates
- **Maps to:** CCC-IaaS-01

### Database Security
- **Policy ID:** `9dfea752-dd46-4766-aed1-c355fa93fb91`
- **Name:** Azure SQL Managed Instances should disable public network access
- **Maps to:** CCC-PaaS-02

### AI & Cognitive Services
- **Policy ID:** `55d1f543-d1b0-4811-9663-d6d0dbc6326d`
- **Name:** Cognitive Services should use private link
- **Maps to:** SAMA-AI-03

## Microsoft Defender for Cloud Control Categories

### Core Security Controls
1. **Enable MFA** - Multi-factor authentication for all users (Score: 10)
2. **Manage access and permissions** - Least privilege and RBAC (Score: 4)
3. **Restrict unauthorized network access** - Network segmentation and controls (Score: 4)
4. **Enable encryption at rest** - Data encryption with CMK (Score: 4)
5. **Encrypt data in transit** - TLS 1.2+ enforcement (Score: 4)
6. **Enable auditing and logging** - Comprehensive log collection (Score: 1)
7. **Apply system updates** - Vulnerability and patch management (Score: 6)
8. **Remediate vulnerabilities** - Continuous vulnerability assessment (Score: 6)

## Usage Instructions

### 1. Implementing Controls
For each control in the catalog:
1. Review the `Requirement_Summary` to understand the control objective
2. Check if an `Azure_Policy_ID` is provided
3. If yes, deploy the policy using Azure Policy or Azure Blueprints
4. Review the `Defender_Recommendation` for additional security posture improvements
5. Collect `Evidence_Examples` for compliance audits

### 2. Deploying Azure Policies
```powershell
# Example: Assign MFA policy
$policyDefinition = Get-AzPolicyDefinition -Id "/providers/Microsoft.Authorization/policyDefinitions/4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"
New-AzPolicyAssignment -Name "Require-MFA" -PolicyDefinition $policyDefinition -Scope "/subscriptions/{subscription-id}"
```

### 3. Enabling Defender for Cloud Recommendations
1. Navigate to Microsoft Defender for Cloud in Azure Portal
2. Review Secure Score and Recommendations
3. Filter by control category (e.g., "Identity & Access Management")
4. Implement fixes using the "Fix" button or follow remediation guidance

### 4. Generating Compliance Reports
Use Azure Policy Compliance view to generate reports showing:
- Compliant vs. non-compliant resources
- Control coverage percentage
- Remediation status

## Cross-Framework Mapping

Many controls map across multiple frameworks:

| Control Area | SAMA | CCC | ADHICS | SITA | POPIA | eGov | IGR |
|--------------|------|-----|--------|------|-------|------|-----|
| MFA Enforcement | AC-01 | IAM-01 | IAM-01 | IAM-02 | - | EGOV-06 | - |
| Network Segmentation | NS-01 | IaaS-02, Net-03 | Net-01 | Net-01 | - | EGOV-09 | - |
| Encryption at Rest | DP-02, AC-03 | IaaS-03, Data-01 | PHI-01 | Data-02 | POPIA-07 | EGOV-10 | - |
| Private Endpoints | NS-02 | Net-03 | Net-03 | Net-03 | - | - | - |
| Vulnerability Management | VM-01 | Sec-04 | App-02 | Sec-04 | - | EGOV-14 | - |
| Audit Logging | LM-01, LM-03 | Comp-02 | PHI-05 | SPO-10 | POPIA-13 | - | IGR-08 |
| Data Protection | DP-01, DP-02 | Data-01 | PHI-01 | Data-01 | POPIA-07 | EGOV-10 | - |
| Privacy & Consent | - | - | PHI-03 | Comp-02 | POPIA-09 | - | - |
| Data Subject Rights | - | - | PHI-04 | - | POPIA-08 | - | - |
| Data Breach Response | IR-02 | - | - | IR-02 | POPIA-12 | - | - |
| Interoperability | - | - | - | - | - | EGOV-03 | IGR-01 |
| Information Sharing | - | - | - | SITA-Sec-02 | - | EGOV-04 | IGR-02 |
| Cloud Strategy | - | CCC-All | - | SITA-SPO | - | EGOV-07 | - |
| Digital Identity | - | IAM-01 | IAM-01 | IAM-01 | - | EGOV-06 | - |

## Next Steps

1. **Review Controls:** Review each catalog to identify applicable controls for your environment
2. **Gap Analysis:** Compare current state against control requirements
3. **Policy Deployment:** Deploy mapped Azure Policies to enforce controls
4. **Enable Defender:** Ensure Microsoft Defender for Cloud plans are enabled
5. **Monitor Compliance:** Set up continuous compliance monitoring
6. **Evidence Collection:** Establish processes to collect and maintain evidence
7. **Regular Reviews:** Schedule periodic reviews and updates

## Additional Resources

- [Azure Policy Built-in Definitions](https://learn.microsoft.com/en-us/azure/governance/policy/samples/built-in-policies)
- [Microsoft Defender for Cloud Recommendations](https://learn.microsoft.com/en-us/azure/defender-for-cloud/recommendations-reference)
- [Azure Security Benchmark](https://learn.microsoft.com/en-us/security/benchmark/azure/)
- [Microsoft Cloud Security Benchmark](https://learn.microsoft.com/en-us/security/benchmark/azure/mcsb-overview)

## Support

For questions or issues with these catalogs, please refer to:
- Microsoft Learn documentation for Azure Policy and Defender for Cloud
- Reference documents in the `reference_documents/` folder
- Compliance framework official documentation

---

**Last Updated:** December 4, 2025
**Toolkit Version:** 1.1
**Author:** Warren du Toit, Cloud Solution Architect @ Microsoft

## Framework Summary Statistics

| Framework | Controls | Primary Focus | Jurisdiction |
|-----------|----------|---------------|--------------|
| SAMA | 36 | Financial Sector Cybersecurity | Saudi Arabia |
| CCC | 32 | Multi-Cloud Security | UAE |
| ADHICS | 36 | Healthcare Information Security | UAE |
| SITA | 36 | Sovereign Cloud Architecture | South Africa |
| POPIA | 16 | Data Protection & Privacy | South Africa |
| eGovernment | 15 | Digital Government Services | South Africa |
| IGR | 10 | Intergovernmental Cooperation | South Africa |
| **Total** | **181** | **Comprehensive Compliance** | **MENA & Africa** |
