# South African Government Frameworks to Azure Policy & Microsoft Defender Controls Mapping

## Executive Summary

This document provides a comprehensive mapping of South Africa's government cybersecurity and data protection frameworks to Azure Policy and Microsoft Defender for Cloud controls. The mapping covers:

- **POPIA** — Protection of Personal Information Act, 2013 (Act 4 of 2013)
- **SITA Act** — State Information Technology Agency Act, 1998 (Act 88 of 1998)
- **PFMA** — Public Finance Management Act digitisation requirements
- **eGovernment Framework** — DPSA (Department of Public Service and Administration) digital governance

This combined framework applies to South African government departments, state-owned enterprises, and cloud service providers processing personal information of South African data subjects. The mapping spans **9 domains** covering **56 Azure Policy controls**.

**All licensing options included:** Microsoft Defender for Cloud (all plans), Azure Policy, Microsoft Purview, Microsoft Sentinel, and related services.

---

## Framework Overview

| Framework | Issuing Authority | Scope |
|-----------|-----------------|-------|
| POPIA | Information Regulator (South Africa) | All entities processing personal information of SA residents |
| SITA Act | State Information Technology Agency | Government departments and state-owned enterprises |
| PFMA | National Treasury | Financial information security for public entities |
| eGovernment | DPSA / GCIS | Digital public service delivery |

The combined framework covers **9 domains**:

1. Digital Strategy & Governance (SAG_DGV)
2. Personal Data Protection — POPIA (SAG_PDP)
3. Cloud Architecture & Sovereignty (SAG_CLD)
4. Network Security (SAG_NET)
5. Identity & Access Management (SAG_IAM)
6. Data Security (SAG_DAT)
7. Security Operations (SAG_SEC)
8. Compliance & Governance (SAG_GOV)
9. Business Continuity (SAG_BCM)

---

## Domain-by-Domain Mapping

### Domain 1: Digital Strategy & Governance (SAG_DGV)

**SITA Act + eGovernment Requirements:**
- Establish an IT governance framework aligned with King IV and COBIT
- Define government cloud adoption strategy with SITA-approved service providers
- Implement data governance policies for government information assets
- Conduct annual information security audits by Auditor-General SA (AGSA)
- Maintain resource audit logs for all government cloud workloads

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |
| Storage accounts should restrict network access | 34c877ad-507e-4c82-993e-3452a6e0ad3c | Audit, Deny | Yes | Defender for Storage |
| Subscriptions should have a contact email address for security issues | 4f4f78b8-e367-4b10-a341-d9a4ad5cf1c7 | AuditIfNotExists | Yes | Defender for Cloud |
| Resource logs in Batch accounts should be enabled | 428256e6-1fac-4f48-a757-df34c2b3336d | AuditIfNotExists | Yes | Foundation |
| SQL servers with auditing to storage account should be configured with 90+ days retention | 89099bee-89e0-4b26-a5f4-165451757743 | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Microsoft Defender for Cloud — Governance**
  - SITA-aligned governance rules with defined SLAs for recommendation remediation
  - King IV/COBIT-aligned risk management posture
  - Security score tracking with departmental accountability

- **Microsoft Purview Compliance Manager**
  - POPIA compliance assessment templates
  - AGSA audit-ready evidence collection
  - Continuous compliance monitoring with scoring

**Alerts & Monitoring:**
- Governance rule SLA breach (overdue recommendations)
- Security contact missing for government subscription
- Custom RBAC role created without SITA approval
- Audit log gap detected on government workload
- SQL audit retention below AGSA minimum (90 days)

---

### Domain 2: Personal Data Protection — POPIA (SAG_PDP)

**POPIA Requirements (Conditions for Lawful Processing):**
- Apply customer-managed encryption keys to personal information stores
- Enforce HTTPS/TLS for all personal data in transit
- Enable private endpoints for databases containing personal information
- Restrict custom subscription owner roles to prevent unauthorized access
- Maintain complete record of processing activities (ROPA)

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| OS and data disks should be encrypted with a customer-managed key | 702dd420-7fcc-42c5-afe8-4026edd20fe0 | Audit | Yes | Defender for Servers |
| PostgreSQL servers should use customer-managed keys to encrypt data at rest | 18adea5e-f416-4d0f-8aa8-d24321e3e274 | AuditIfNotExists | Yes | Defender for Databases |
| SQL servers should use customer-managed keys to encrypt data at rest | 0a370ff3-6cab-4e85-8995-295fd854c5b8 | AuditIfNotExists | Yes | Defender for SQL |
| Storage accounts should use customer-managed key for encryption | 6fac406b-40ca-413b-bf8e-0bf964659c25 | Audit | Yes | Defender for Storage |
| [Deprecated]: Custom subscription owner roles should not exist | 10ee2ea2-fb4d-45b8-a7e9-a2e770044cd9 | Audit | Yes | Foundation |
| Secure transfer to storage accounts should be enabled | 404c3081-a854-4457-ae30-26a93ef643f9 | Audit, Deny | Yes | Defender for Storage |
| Private endpoint should be enabled for MySQL servers | 7595c971-233d-4bcf-bd18-596129188c49 | AuditIfNotExists | Yes | Defender for Databases |

**Microsoft Defender Controls:**
- **Microsoft Purview — POPIA Compliance**
  - Sensitive information types for SA ID numbers, South African personal data
  - POPIA-specific sensitivity labels (General, Confidential, Secret)
  - Automated POPIA data subject access request (DSAR) processing
  - Data Loss Prevention for personal information (Section 22 breach prevention)

- **Microsoft Defender for Storage**
  - Personal data anomalous access detection
  - Malware scanning for uploads containing PI
  - Sensitive data discovery and classification aligned to POPIA

**Alerts & Monitoring:**
- Personal information stored without CMK encryption
- POPIA data subject request SLA breach (72-hour notification requirement)
- Insecure data transfer of personal information
- Large-scale personal data export detected
- POPIA breach notification trigger

---

### Domain 3: Cloud Architecture & Sovereignty (SAG_CLD)

**SITA + eGovernment Requirements:**
- Enforce SITA-approved cloud deployment models for government data
- Enable Microsoft Defender for all government cloud subscriptions
- Enforce patch and update management per SITA Change Management Policy
- Maintain South African data residency for classified government information

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Machines should be configured to periodically check for missing system updates | bd876905-5b84-4f73-ab2d-2e7a7c4568d9 | AuditIfNotExists | Yes | Azure Update Manager |
| [Deprecated]: System updates should be installed on your machines | 86b3d65f-7626-441e-b690-81a8b71cff60 | AuditIfNotExists | Yes | Defender for Servers |
| Resource logs in Batch accounts should be enabled | 428256e6-1fac-4f48-a757-df34c2b3336d | AuditIfNotExists | Yes | Foundation |
| Configure Azure Defender for servers to be enabled | 8e86a5b6-b9bd-49d1-8e21-4bb8a0862222 | DeployIfNotExists | Yes | Defender for Servers |
| [Deprecated]: System updates on virtual machine scale sets should be installed | c3f317a7-a95c-4547-b7e7-11017ebdf2fe | AuditIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Azure South Africa Region Deployment**
  - Azure Policy restricting deployments to South Africa North/West
  - Government community cloud options for classified workloads
  - Sovereign compliance for Cabinet-classified information

- **Microsoft Defender for Servers**
  - Endpoint protection for government VM fleets via Defender for Endpoint
  - File Integrity Monitoring for SITA-required change control evidence
  - Just-in-time VM access compliance

**Alerts & Monitoring:**
- Government workload deployed outside South Africa regions
- Defender for Servers disabled on government VM
- OS patch compliance below SITA SLA
- Data residency violation detected

---

### Domain 4: Network Security (SAG_NET)

**SITA Requirements:**
- Require NSGs on all government subnets
- Disable remote debugging on all government-facing applications
- Enable private endpoints for production SQL databases
- Enforce Key Vault private link and firewall for cryptographic assets

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Subnets should be associated with a Network Security Group | e71308d3-144b-4262-b144-efdc3cc90517 | AuditIfNotExists | Yes | Defender for Cloud |
| [Deprecated]: Unattached disks should be encrypted | 2c89a2e5-7285-40fe-afe0-ae8654b92fb2 | Audit | Yes | Defender for Cloud |
| There should be more than one owner assigned to your subscription | 09024ccc-0c5f-475e-9457-b7c0d9ed487b | AuditIfNotExists | Yes | Defender for Cloud |
| App Configuration should use private link | ca610c1d-041c-4332-9d88-7ed3094967c7 | AuditIfNotExists | Yes | Foundation |
| Azure Key Vaults should use private link | a6abeaec-4d90-4a02-805f-6b26c4d3fbe9 | AuditIfNotExists | Yes | Foundation |
| Azure Key Vault should have firewall enabled or public network access disabled | 55615ac9-af46-4a59-874e-391cc3dfb490 | Audit, Deny | Yes | Foundation |
| App Service apps should have remote debugging turned off | cb510bfd-1cba-4d9f-a230-cb0976f4bb71 | Audit, Deny | Yes | Foundation |
| Function apps should have remote debugging turned off | 0e60b895-3786-45da-8377-9c6b4b6ac5f9 | Audit, Deny | Yes | Foundation |
| Private endpoint connections on Azure SQL Database should be enabled | 7698e800-9299-47a6-b3b6-5a0fee576eed | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Azure Firewall Premium for South African Government**
  - IDPS for government perimeter with threat intelligence from Microsoft
  - Network topology enforcement (hub-spoke aligned to SITA enterprise architecture)
  - Traffic filtering for .gov.za eServices

- **Microsoft Defender for Cloud — Network Security**
  - Adaptive network hardening recommendations
  - Open management ports detection on government VMs
  - Internet-exposed endpoints detection and remediation

**Alerts & Monitoring:**
- NSG missing from government subnet
- Remote debugging enabled on production government app
- Key Vault firewall disabled
- Lateral movement detected between government network segments
- DDoS attack on .gov.za portal

---

### Domain 5: Identity & Access Management (SAG_IAM)

**SITA + Government IT Requirements:**
- Enforce MFA for all government officials with cloud access
- Remove guest and external accounts with write access
- Provision Entra ID administrators on all government SQL servers
- Enforce MFA on all read-level government data access
- Implement access review cycles for privileged government roles

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Users must authenticate with MFA to create or update resources | 4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b | Audit | Yes | Foundation |
| [Deprecated]: MFA should be enabled for accounts with write permissions | 9297c21d-2ed6-4474-b48f-163f75654ce3 | AuditIfNotExists | Yes | Defender for Cloud |
| [Deprecated]: Accounts with read permissions should be MFA enabled | 81b3ccb4-e6e8-4e4a-8d05-5df25cd29fd4 | AuditIfNotExists | Yes | Defender for Cloud |
| An Azure Active Directory administrator should be provisioned for SQL servers | 1f314764-cb73-4fc9-b863-8eca98ac36e9 | AuditIfNotExists | Yes | Defender for SQL |
| Email notification to subscription owner for high severity alerts should be enabled | 0b15565f-aa9e-48ba-8619-45960f2c314d | AuditIfNotExists | Yes | Defender for Cloud |
| [Deprecated]: Custom subscription owner roles should not exist | 10ee2ea2-fb4d-45b8-a7e9-a2e770044cd9 | Audit | Yes | Foundation |
| Guest accounts with write permissions on Azure resources should be removed | 94e1c2ac-cbbe-4cac-a2b5-389c812dee87 | AuditIfNotExists | Yes | Defender for Cloud |

**Microsoft Defender Controls:**
- **Microsoft Entra ID for South African Government**
  - Conditional Access with SA government network location awareness
  - PIM for Just-in-Time access to PFMA financial systems
  - Smart Lockout and sign-in risk policies for government accounts
  - Automated access reviews for Auditor-General compliance

- **Government Identity Federation**
  - South African government employee integration via Entra ID
  - Cross-department B2B access governance
  - Third-party contractor access policies with entitlement management

**Alerts & Monitoring:**
- Government official bypassed MFA
- External account with PFMA financial system write access
- Privileged escalation outside SITA change window
- Inactive government account retaining privileged access
- Government SQL server missing Entra ID admin

---

### Domain 6: Data Security (SAG_DAT)

**POPIA + SITA Data Security Requirements:**
- Encrypt all personal information at rest with CMK
- Enable private endpoints for all production databases
- Enforce HTTPS for all data transfers
- Enable storage infrastructure encryption for government data
- Enable deletion protection on Key Vaults
- Configure SQL audit logging with 90-day retention

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| OS and data disks should be encrypted with a customer-managed key | 702dd420-7fcc-42c5-afe8-4026edd20fe0 | Audit | Yes | Defender for Servers |
| Private endpoint should be enabled for MySQL servers | 7595c971-233d-4bcf-bd18-596129188c49 | AuditIfNotExists | Yes | Defender for Databases |
| Secure transfer to storage accounts should be enabled | 404c3081-a854-4457-ae30-26a93ef643f9 | Audit, Deny | Yes | Defender for Storage |
| Storage accounts should have infrastructure encryption | 4733ea7b-a883-42fe-8cac-97454c2a9e4a | Audit, Deny | Yes | Defender for Storage |
| Key vaults should have deletion protection enabled | 0b60c0b2-2dc2-4e1c-b5c9-abbed971de53 | Audit, Deny | Yes | Foundation |
| SQL servers with auditing to storage account should be configured with 90+ days retention | 89099bee-89e0-4b26-a5f4-165451757743 | AuditIfNotExists | Yes | Defender for SQL |
| [Deprecated]: Virtual machines should encrypt temp disks, caches, and data flows | 0961003e-5a0a-4549-abde-af6a37f2724d | Audit | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Microsoft Defender for SQL — AGSA Audit Support**
  - Advanced threat protection for government databases
  - SQL vulnerability assessment with quarterly reporting
  - PFMA financial data audit log tamper detection

- **Microsoft Purview — POPIA Data Governance**
  - SA ID number, passport number, and SA personal data classification
  - Data estate mapping for POPIA Section 14 accountability
  - Cross-border transfer detection (Chapter 9 POPIA requirements)

**Alerts & Monitoring:**
- Personal data stored without CMK encryption (POPIA Section 19)
- Government database exposed to public internet
- Infrastructure encryption disabled on government storage
- Large-scale government data exfiltration attempt
- Key Vault deletion protection removed

---

### Domain 7: Security Operations (SAG_SEC)

**SITA + Government Cybersecurity Requirements:**
- Enable Microsoft Defender for Cloud across all government subscriptions
- Configure vulnerability assessments for all VMs and databases
- Enable adaptive network hardening
- Conduct quarterly security reviews for government workloads
- Integrate with CSIRT (Computer Security Incident Response Team)

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| [Deprecated]: System updates should be installed on your machines | 86b3d65f-7626-441e-b690-81a8b71cff60 | AuditIfNotExists | Yes | Defender for Servers |
| Machines should be configured to periodically check for missing system updates | bd876905-5b84-4f73-ab2d-2e7a7c4568d9 | AuditIfNotExists | Yes | Azure Update Manager |
| Azure Machine Learning Computes should have local authentication methods disabled | e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f | Audit, Deny | Yes | Foundation |
| Vulnerability assessment should be enabled on SQL Managed Instance | 1b7aa243-30e4-4c9e-bca8-d0d3022b634a | AuditIfNotExists | Yes | Defender for SQL |
| [Deprecated]: Adaptive network hardening recommendations should be applied on internet-facing VMs | 08e6af2d-db70-460a-bfe9-d5bd474ba9d6 | AuditIfNotExists | Yes | Defender for Servers P2 |
| Enable Microsoft Defender for Cloud on your subscription | ac076320-ddcf-4066-b451-6154267e8ad2 | DeployIfNotExists | Yes | Foundation |
| A vulnerability assessment solution should be enabled on your virtual machines | 501541f7-f7e7-4cd6-868c-4190fdad3ac9 | AuditIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Microsoft Sentinel — South African Government SIEM**
  - Government department security incident tracking
  - Integration with CSIRT/CERT-SA threat intelligence
  - Automated playbooks for POPIA breach notification workflows
  - AGSA audit log export and evidence management

- **Defender XDR for Government**
  - Endpoint, email, identity, and cloud workload correlation
  - Criminal ransomware group TTP detection (South Africa-specific threat actors)
  - Automated Attack Disruption capability

**Alerts & Monitoring:**
- Government VM critical vulnerability beyond SITA SLA
- ML workload local authentication enabled
- Suspicious SQL activity on PFMA financial database
- Defender for Cloud plan disabled on government subscription
- South African CSIRT incident reporting trigger

---

### Domain 8: Compliance & Governance (SAG_GOV)

**SITA + POPIA + PFMA Requirements:**
- Maintain SQL audit evidence for AGSA reviews
- Disable public network access on government SQL Managed Instances
- Audit all RBAC role usage against approved government role catalog

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |
| Azure SQL Managed Instances should disable public network access | 9dfea752-dd46-4766-aed1-c355fa93fb91 | Audit, Deny | Yes | Defender for SQL |
| SQL servers with auditing to storage account should be configured with 90+ days retention | 89099bee-89e0-4b26-a5f4-165451757743 | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Regulatory Compliance Dashboard — POPIA/SITA**
  - Real-time POPIA compliance score
  - AGSA-ready evidence export functionality
  - Control-owner assignment and SLA tracking

**Alerts & Monitoring:**
- AGSA compliance score degradation
- SQL MI publicly accessible
- RBAC custom role usage outside approved catalog
- Compliance evidence gap detected

---

### Domain 9: Business Continuity (SAG_BCM)

**SITA Business Continuity Requirements:**
- Enable VM Backup for all critical government services
- Enable secure Redis cache connections for government session assets
- Enforce system update compliance for scale sets
- Maintain log evidence for Business Continuity Plans (BCPs)

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Azure Backup should be enabled for Virtual Machines | 013e242c-8828-4970-87b3-ab247555486d | AuditIfNotExists | Yes | Foundation |
| Only secure connections to your Azure Cache for Redis should be enabled | 22bee202-a82f-4305-9a2a-6d7f44d4dedb | Audit, Deny | Yes | Foundation |
| [Deprecated]: System updates on virtual machine scale sets should be installed | c3f317a7-a95c-4547-b7e7-11017ebdf2fe | AuditIfNotExists | Yes | Defender for Servers |
| Resource logs in Batch accounts should be enabled | 428256e6-1fac-4f48-a757-df34c2b3336d | AuditIfNotExists | Yes | Foundation |

**Microsoft Defender Controls:**
- **Azure Site Recovery for South African Government**
  - In-country failover between South Africa North and West
  - Automated failover testing for SITA-required BCP drills
  - Priority recovery for PFMA and service delivery systems

- **Azure Backup Vault**
  - Immutable backup storage for government workload data
  - Multi-user authorization for backup deletion (anti-ransomware)
  - Legal hold for AGSA evidence preservation

**Alerts & Monitoring:**
- Government service VM backup failure
- BCP validation test overdue (bi-annual SITA requirement)
- Redis cache SSL downgrade attempt (government session data at risk)
- DR RTO breach on priority service delivery system

---

## South African Government Defender Plan Summary

| Defender Plan | Domains Covered | Key Government Use Case |
|--------------|-----------------|------------------------|
| Defender for Cloud Foundation | DGV, NET, IAM, GOV, BCM | Baseline SITA compliance |
| Defender for Servers P2 | CLD, NET, SEC | Government VM + FIM |
| Defender for SQL | PDP, DAT, GOV, BCM | PFMA and citizen databases |
| Defender for Storage | PDP, DAT | POPIA personal data protection |
| Defender for Databases | PDP, DAT | MySQL/PostgreSQL government DBs |
| Microsoft Sentinel | SEC (cross-domain) | Government SIEM + AGSA audit |
| Microsoft Purview | PDP, DAT | POPIA compliance + ROPA |

---

## Compliance Reporting

**South African Government Reporting Requirements:**
- **POPIA**: Information Regulator (South Africa) breach notification within 72 hours; annual compliance reports
- **SITA**: Government IT security posture reports submitted to DPSA and SITA
- **PFMA**: Auditor-General South Africa (AGSA) audit evidence collection

**Key Metrics for Information Regulator / AGSA:**
- % of personal information stores with CMK encryption
- % of government VMs with backup coverage
- MFA compliance rate for government officials
- SQL audit log retention compliance rate (target: 100% ≥ 90 days)
- Count of POPIA breach incidents and notification timeliness

---

## References

- [POPIA — Act 4 of 2013, Information Regulator South Africa](https://inforegulator.org.za/)
- [SITA Act — Act 88 of 1998, State Information Technology Agency](https://sita.co.za/)
- [DPSA eGovernment Framework](https://www.dpsa.gov.za/)
- [Microsoft Azure South Africa Compliance Documentation](https://learn.microsoft.com/en-us/azure/compliance/)
- [Microsoft Azure POPIA Compliance Guide](https://learn.microsoft.com/en-us/compliance/regulatory/offering-popia)
- [Azure Policy Built-in Definitions](https://learn.microsoft.com/en-us/azure/governance/policy/samples/built-in-policies)
