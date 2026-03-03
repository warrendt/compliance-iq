# Saudi Arabia Government Frameworks to Azure Policy & Microsoft Defender Controls Mapping

## Executive Summary

This document provides a comprehensive mapping of Saudi Arabia's national cybersecurity and data governance frameworks to Azure Policy and Microsoft Defender for Cloud controls. The mapping covers three interlocking regulatory bodies:

- **NCA CSCC** — National Cybersecurity Authority Cloud Security Controls (الهيئة الوطنية للأمن السيبراني)
- **NDMO Data Governance** — National Data Management Office data classification and management requirements
- **PDPL** — Personal Data Protection Law (نظام حماية البيانات الشخصية, Royal Decree M/19)

This combined framework applies to Saudi government entities, critical national infrastructure operators, and cloud service providers offering services in the Kingdom of Saudi Arabia. The mapping spans **12 domains** covering **58 Azure Policy controls**.

**All licensing options included:** Microsoft Defender for Cloud (all plans), Azure Policy, Microsoft Purview, Microsoft Sentinel, and related services.

---

## Framework Overview

The Saudi Arabia Government compliance posture spans:

| Framework | Issuing Authority | Scope |
|-----------|-----------------|-------|
| NCA CSCC | National Cybersecurity Authority (NCA) | All government entities + operators of critical national infrastructure |
| NDMO | National Data Management Office | Government data governance and classification |
| PDPL | Personal Data Protection Law | Any entity processing personal data of Saudi residents |

The combined framework covers **12 domains**, aligned to the primary NCA CSCC structural categories:

1. Cybersecurity Governance (KSA_GOV)
2. Infrastructure Security (KSA_INF)
3. Platform Security (KSA_PLA)
4. Data Security (KSA_DAT)
5. Identity & Access Management (KSA_IAM)
6. Network Security (KSA_NET)
7. Security Operations (KSA_SEC)
8. Compliance & Audit (KSA_COM)
9. Disaster Recovery (KSA_DR)
10. Data Management — NDMO (KSA_NDM)
11. Data Privacy — PDPL (KSA_NDP)
12. Data Sharing — NDMO (KSA_NDS)

---

## Domain-by-Domain Mapping

### Domain 1: Cybersecurity Governance (KSA_GOV)

**NCA CSCC Requirements:**
- Develop and maintain a cybersecurity strategy aligned with the National Cybersecurity Strategy
- Establish a cybersecurity committee with C-level ownership
- Conduct annual third-party cybersecurity assessments
- Implement a cybersecurity risk management framework
- Define cybersecurity roles, responsibilities, and accountability

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |
| Storage accounts should restrict network access | 34c877ad-507e-4c82-993e-3452a6e0ad3c | Audit, Deny | Yes | Defender for Storage |
| Subscriptions should have a contact email address for security issues | 4f4f78b8-e367-4b10-a341-d9a4ad5cf1c7 | AuditIfNotExists | Yes | Defender for Cloud |
| Resource logs in Batch accounts should be enabled | 428256e6-1fac-4f48-a757-df34c2b3336d | AuditIfNotExists | Yes | Foundation |

**Microsoft Defender Controls:**
- **Microsoft Defender for Cloud — Governance**
  - Executive-level security score with governance assignment rules
  - Risk-based prioritization aligned to NCA risk rating model
  - Regulatory compliance dashboard mapped to NCA CSCC controls

- **Microsoft Purview Compliance Portal**
  - Compliance Manager assessment for NCA CSCC
  - Audit log access for NCA reviewer submissions
  - Insider risk management governance posture

**Alerts & Monitoring:**
- Security contact email missing alerts
- Custom RBAC role modification
- Governance rule breach (recommendation past due date)
- Subscription owner role changes
- NCA-required audit log gap detected

---

### Domain 2: Infrastructure Security (KSA_INF)

**NCA CSCC Requirements:**
- Enforce regular OS and VM patch management with defined SLAs
- Protect all virtual machine disk data in transit and at rest
- Enable Microsoft Defender for Servers across all Saudi-hosted workloads
- Enforce NSG controls on all infrastructure subnets
- Encrypt storage disks for all government cloud workloads

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Machines should be configured to periodically check for missing system updates | bd876905-5b84-4f73-ab2d-2e7a7c4568d9 | AuditIfNotExists | Yes | Azure Update Manager |
| Subnets should be associated with a Network Security Group | e71308d3-144b-4262-b144-efdc3cc90517 | AuditIfNotExists | Yes | Defender for Cloud |
| OS and data disks should be encrypted with a customer-managed key | 702dd420-7fcc-42c5-afe8-4026edd20fe0 | Audit | Yes | Defender for Servers |
| [Deprecated]: System updates on virtual machine scale sets should be installed | c3f317a7-a95c-4547-b7e7-11017ebdf2fe | AuditIfNotExists | Yes | Defender for Servers |
| [Deprecated]: Virtual machines should encrypt temp disks, caches, and data flows | 0961003e-5a0a-4549-abde-af6a37f2724d | Audit | Yes | Defender for Servers |
| Enable Microsoft Defender for Cloud on your subscription | ac076320-ddcf-4066-b451-6154267e8ad2 | DeployIfNotExists | Yes | Foundation |

**Microsoft Defender Controls:**
- **Microsoft Defender for Servers (Plan 2)**
  - File Integrity Monitoring (FIM) for critical system files
  - Just-in-time VM access to reduce exposure of management ports
  - Endpoint Detection and Response via Microsoft Defender for Endpoint
  - Agentless machine scanning for vulnerability assessment

- **Azure Update Manager**
  - Patch compliance reporting across KSA government subscriptions
  - Maintenance windows aligned to NCA approved change management

**Alerts & Monitoring:**
- Critical OS patch missing beyond NCA SLA
- VM disk left unencrypted
- VMSS missing updates alert
- Defender for Servers plan disabled
- Management port (RDP/SSH) exposed to internet

---

### Domain 3: Platform Security (KSA_PLA)

**ADHICS Requirements:**
- Disable public network access on all SQL Managed Instances
- Disable remote debugging on all internet-facing applications
- Enforce infrastructure encryption for storage containing government data
- Enforce at least 2 subscription owners for administration continuity

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Azure SQL Managed Instances should disable public network access | 9dfea752-dd46-4766-aed1-c355fa93fb91 | Audit, Deny | Yes | Defender for SQL |
| App Service apps should have remote debugging turned off | cb510bfd-1cba-4d9f-a230-cb0976f4bb71 | Audit, Deny | Yes | Foundation |
| Function apps should have remote debugging turned off | 0e60b895-3786-45da-8377-9c6b4b6ac5f9 | Audit, Deny | Yes | Foundation |
| [Deprecated]: Remote debugging should be turned off for API Apps | e9c8d085-d9cc-4b17-9cdc-059f1f01f19e | Audit | Yes | Foundation |
| Storage accounts should have infrastructure encryption | 4733ea7b-a883-42fe-8cac-97454c2a9e4a | Audit, Deny | Yes | Defender for Storage |
| There should be more than one owner assigned to your subscription | 09024ccc-0c5f-475e-9457-b7c0d9ed487b | AuditIfNotExists | Yes | Defender for Cloud |

**Microsoft Defender Controls:**
- **Microsoft Defender for App Service**
  - Government portal threat detection
  - Dangling DNS hijacking prevention for .gov.sa domains
  - API security for Saudi eGov services

- **Microsoft Defender for Databases**
  - SQL Managed Instance advanced threat protection
  - Suspicious query pattern detection (SQL injection, unusual data export)
  - Database activity monitoring for eGov platforms

**Alerts & Monitoring:**
- Remote debugging enabled on production platform
- SQL MI public network access enabled
- Infrastructure encryption disabled
- Single subscription owner alert
- Government application vulnerability exploited

---

### Domain 4: Data Security (KSA_DAT)

**NCA CSCC + NDMO Requirements:**
- Encrypt all government-classified data using customer-managed keys
- Enable private endpoints for all databases holding classified data
- Enforce TLS/HTTPS for data in transit
- Enable full SQL audit logging with 90-day minimum retention
- Enable deletion protection on cryptographic key vaults

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| PostgreSQL servers should use customer-managed keys to encrypt data at rest | 18adea5e-f416-4d0f-8aa8-d24321e3e274 | AuditIfNotExists | Yes | Defender for Databases |
| Private endpoint should be enabled for MySQL servers | 7595c971-233d-4bcf-bd18-596129188c49 | AuditIfNotExists | Yes | Defender for Databases |
| Secure transfer to storage accounts should be enabled | 404c3081-a854-4457-ae30-26a93ef643f9 | Audit, Deny | Yes | Defender for Storage |
| SQL servers should use customer-managed keys to encrypt data at rest | 0a370ff3-6cab-4e85-8995-295fd854c5b8 | AuditIfNotExists | Yes | Defender for SQL |
| Storage accounts should use customer-managed key for encryption | 6fac406b-40ca-413b-bf8e-0bf964659c25 | Audit | Yes | Defender for Storage |
| Key vaults should have deletion protection enabled | 0b60c0b2-2dc2-4e1c-b5c9-abbed971de53 | Audit, Deny | Yes | Foundation |
| SQL servers with auditing to storage account should be configured with 90+ days retention | 89099bee-89e0-4b26-a5f4-165451757743 | AuditIfNotExists | Yes | Defender for SQL |
| Auditing on SQL server should be enabled | a6fb4358-5bf4-4ad7-ba82-2cd2f41ce5e9 | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Microsoft Purview — NDMO Data Classification**
  - Sensitive information types for Saudi ID numbers, IQAMA, government data
  - Automatic labeling for classified, restricted, and general government data
  - NDMO data classification schema enforcement

- **Microsoft Defender for Storage + SQL**
  - Anomalous data exfiltration detection
  - Sensitive data discovery for NDMO classification
  - SQL threat protection for government databases

**Alerts & Monitoring:**
- Government-classified data stored without CMK encryption
- SQL audit retention below NCA minimum (90 days)
- Data transfer to unauthorized regions (outside KSA)
- Key Vault deletion protection disabled
- Large-scale classified data download from government storage

---

### Domain 5: Identity & Access Management (KSA_IAM)

**NCA CSCC Requirements:**
- Enforce MFA for all government employee cloud accounts
- Remove guest accounts with write access from government subscriptions
- Provision Entra ID administrators on all SQL servers
- Disable custom owner roles not approved by NCA
- Send immediate alerts for high-severity identity events

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
- **Microsoft Entra ID Governance for Saudi Government**
  - Access reviews for all privileged government roles (quarterly NCA requirement)
  - PIM for Just-In-Time access to CNII systems
  - Cross-agency B2B access governance with conditional access

- **CIAM for Saudi eGov Services**
  - External Identity integration with Nafath (Saudi national authentication)
  - Conditional Access with location-based restrictions (Saudi IP ranges)

**Alerts & Monitoring:**
- Government account MFA bypass detected
- Guest account with write access to classified resource
- Privileged escalation outside Nafath-authenticated session
- Orphaned high-privilege account detected
- Custom owner role creation without NCA approval

---

### Domain 6: Network Security (KSA_NET)

**NCA CSCC Requirements:**
- Enable private endpoints for all SQL databases in government cloud
- Enforce Key Vault private link and firewall for all cryptographic assets
- Require App Configuration private link for government service configuration

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| App Configuration should use private link | ca610c1d-041c-4332-9d88-7ed3094967c7 | AuditIfNotExists | Yes | Foundation |
| [Deprecated]: Unattached disks should be encrypted | 2c89a2e5-7285-40fe-afe0-ae8654b92fb2 | Audit | Yes | Defender for Cloud |
| Azure Key Vaults should use private link | a6abeaec-4d90-4a02-805f-6b26c4d3fbe9 | AuditIfNotExists | Yes | Foundation |
| Azure Key Vault should have firewall enabled or public network access disabled | 55615ac9-af46-4a59-874e-391cc3dfb490 | Audit, Deny | Yes | Foundation |
| Private endpoint connections on Azure SQL Database should be enabled | 7698e800-9299-47a6-b3b6-5a0fee576eed | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Azure Virtual WAN + Azure Firewall Premium**
  - Centralized government network traffic inspection
  - IDPS for encrypted traffic (TLS inspection) on CNII networks
  - Network topology enforcement (hub-spoke for government agencies)

- **DDoS Protection Standard**
  - Saudi government portal protection from volumetric attacks
  - Adaptive attack mitigation tuned to government eServices traffic

**Alerts & Monitoring:**
- Key Vault public access detected
- SQL database endpoint exposed publicly
- Unencrypted disk left unattached and accessible
- Azure Firewall IDPS signature triggered
- DDoS threshold breach on government portal

---

### Domain 7: Security Operations (KSA_SEC)

**NCA CSCC Requirements:**
- Enable Microsoft Defender for Cloud across all subscriptions
- Configure vulnerability assessment for all VMs and SQL instances
- Enable adaptive network hardening
- Monitor and respond to machine learning workload security findings

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| [Deprecated]: System updates should be installed on your machines | 86b3d65f-7626-441e-b690-81a8b71cff60 | AuditIfNotExists | Yes | Defender for Servers |
| Azure Machine Learning Computes should have local authentication methods disabled | e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f | Audit, Deny | Yes | Foundation |
| Vulnerability assessment should be enabled on SQL Managed Instance | 1b7aa243-30e4-4c9e-bca8-d0d3022b634a | AuditIfNotExists | Yes | Defender for SQL |
| [Deprecated]: Adaptive network hardening recommendations should be applied on internet-facing VMs | 08e6af2d-db70-460a-bfe9-d5bd474ba9d6 | AuditIfNotExists | Yes | Defender for Servers P2 |
| Configure Azure Defender for servers to be enabled | 8e86a5b6-b9bd-49d1-8e21-4bb8a0862222 | DeployIfNotExists | Yes | Defender for Servers |
| A vulnerability assessment solution should be enabled on your virtual machines | 501541f7-f7e7-4cd6-868c-4190fdad3ac9 | AuditIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Microsoft Sentinel — NCA SOC Integration**
  - NCA CSCC-aligned detection rules
  - Saudi CERT (CERT-SA) threat intelligence feed integration
  - Automated incident response for CNII threats
  - Nation-state threat actor TTPs (MITRE ATT&CK for ICS)

- **Defender XDR for Government**
  - Cross-workload threat correlation (endpoints, email, identity, cloud)
  - Automated Attack Disruption for ransomware
  - Government incident response playbooks

**Alerts & Monitoring:**
- ML compute local authentication enabled
- Adaptive network hardening bypassed
- Critical vulnerability on CNII-classified VM
- NCA incident reporting trigger (P1/P2 severity)
- Threat actor known TTP detected on government network

---

### Domain 8: Compliance & Audit (KSA_COM)

**NCA CSCC Requirements:**
- Maintain comprehensive resource audit logs
- Enforce SQL audit logging minimum retention
- Conduct NCA compliance self-assessments annually

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Resource logs in Batch accounts should be enabled | 428256e6-1fac-4f48-a757-df34c2b3336d | AuditIfNotExists | Yes | Foundation |
| SQL servers with auditing to storage account should be configured with 90+ days retention | 89099bee-89e0-4b26-a5f4-165451757743 | AuditIfNotExists | Yes | Defender for SQL |
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |

**Microsoft Defender Controls:**
- **NCA CSCC Regulatory Compliance Dashboard**
  - Real-time NCA CSCC compliance score
  - Per-control evidence collection and assignment
  - Compliance trend reporting for NCSC annual assessment

**Alerts & Monitoring:**
- NCA compliance score falls below threshold
- Audit log retention gap detected
- Evidence collection gap for NCA assessment

---

### Domain 9: Disaster Recovery (KSA_DR)

**NCA CSCC Requirements:**
- Ensure RTO/RPO compliance for CNII systems per NCA classification
- Enable VM Backup for all production government workloads
- Validate DR plans bi-annually

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Azure Backup should be enabled for Virtual Machines | 013e242c-8828-4970-87b3-ab247555486d | AuditIfNotExists | Yes | Foundation |
| Only secure connections to your Azure Cache for Redis should be enabled | 22bee202-a82f-4305-9a2a-6d7f44d4dedb | Audit, Deny | Yes | Foundation |
| [Deprecated]: System updates on virtual machine scale sets should be installed | c3f317a7-a95c-4547-b7e7-11017ebdf2fe | AuditIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Azure Site Recovery for CNII**
  - Multi-region failover within KSA Azure datacenters
  - Automatic failover testing with validation reports for NCA
  - Priority-based recovery ordering for CNII workloads

- **Azure Backup Vault**
  - Immutable backup storage for government workloads
  - Multi-user authorization for backup deletion
  - Soft delete and backup alerting

**Alerts & Monitoring:**
- Government VM backup job failure
- RPO/RTO noncompliance for CNII system
- DR validation overdue alert
- Backup vault immutability disabled

---

### Domain 10: Data Management — NDMO (KSA_NDM)

**NDMO Requirements:**
- Implement national data classification taxonomy
- Enable deletion protection on all data governance key vaults
- Enable private endpoints for government master data stores
- Maintain audit trails on all classified government data

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |
| Key vaults should have deletion protection enabled | 0b60c0b2-2dc2-4e1c-b5c9-abbed971de53 | Audit, Deny | Yes | Foundation |
| Private endpoint should be enabled for MySQL servers | 7595c971-233d-4bcf-bd18-596129188c49 | AuditIfNotExists | Yes | Defender for Databases |

**Microsoft Defender Controls:**
- **Microsoft Purview — NDMO Data Governance**
  - National data classification taxonomy (Public, Internal, Restricted, Confidential, Top Secret)
  - Automated sensitivity labeling for NDMO categories
  - Data lineage and catalog for government data assets

**Alerts & Monitoring:**
- Classified government dataset accessed without label
- NDMO classification label removed from dataset
- Data moved across classification tiers without approval

---

### Domain 11: Data Privacy — PDPL (KSA_NDP)

**PDPL Requirements:**
- Protect personal data of Saudi residents processed in cloud
- Enable customer-managed key encryption for all personal data stores
- Enforce HTTPS/TLS for all personal data transfers
- Remove custom subscription owner roles that could enable unauthorized access

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Storage accounts should use customer-managed key for encryption | 6fac406b-40ca-413b-bf8e-0bf964659c25 | Audit | Yes | Defender for Storage |
| [Deprecated]: Custom subscription owner roles should not exist | 10ee2ea2-fb4d-45b8-a7e9-a2e770044cd9 | Audit | Yes | Foundation |
| Secure transfer to storage accounts should be enabled | 404c3081-a854-4457-ae30-26a93ef643f9 | Audit, Deny | Yes | Defender for Storage |

**Microsoft Defender Controls:**
- **Microsoft Purview — PDPL Data Subject Rights**
  - Data subject access request (DSAR) automation
  - PII discovery for Saudi ID numbers, IQAMA, phone numbers, addresses
  - Consent management tracking

- **Data Residency Enforcement**
  - Azure Policy to restrict resource deployment to Saudi Arabia North/West
  - Geo-fencing for personal data of Saudi citizens

**Alerts & Monitoring:**
- Personal data transferred outside Saudi Arabia
- PDPL data subject request SLA breach
- Encryption removed from personal data store
- PDPL personal data discovered in non-compliant location

---

### Domain 12: Data Sharing — NDMO (KSA_NDS)

**NDMO Requirements:**
- Enforce HTTPS on all inter-government data exchange
- Enable storage infrastructure encryption for shared data repositories
- Enable private SQL endpoints for shared government data services

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Secure transfer to storage accounts should be enabled | 404c3081-a854-4457-ae30-26a93ef643f9 | Audit, Deny | Yes | Defender for Storage |
| Storage accounts should have infrastructure encryption | 4733ea7b-a883-42fe-8cac-97454c2a9e4a | Audit, Deny | Yes | Defender for Storage |
| Private endpoint connections on Azure SQL Database should be enabled | 7698e800-9299-47a6-b3b6-5a0fee576eed | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Azure API Management for Government Data Sharing**
  - API policies for NDMO-compliant inter-agency data exchange
  - Rate limiting, authentication, and audit logging for shared APIs
  - OAuth 2.0 / OIDC with Nafath integration for data access consent

- **Azure Data Share**
  - Secure in-place sharing of NDMO-classified datasets between agencies
  - Audit trail for all data share events

**Alerts & Monitoring:**
- Data shared without NDMO-required metadata tagging
- Insecure data transfer API endpoint discovered
- Unauthorized access to government shared dataset
- Private endpoint disabled on shared SQL database

---

## Saudi Arabia Government Defender Plan Summary

| Defender Plan | Domains Covered | Key Government Use Case |
|--------------|-----------------|------------------------|
| Defender for Cloud Foundation | GOV, PLA, NET, COM, DR, NDM | Baseline government posture |
| Defender for Servers P2 | INF, SEC | CNII VM protection + FIM |
| Defender for SQL | DAT, IAM, SEC, COM | Government database security |
| Defender for Storage | DAT, NET, NDP, NDS | Government file and object security |
| Defender for Databases | DAT, NDM | MySQL/PostgreSQL government data |
| Defender for App Service | PLA | eGovernment portal security |
| Microsoft Sentinel | SEC (cross-domain) | NCA SOC + CERT-SA integration |
| Microsoft Purview | DAT, NDM, NDP, NDS | NDMO governance + PDPL compliance |

---

## Compliance Reporting

**KSA Framework Reporting Requirements:**
- **NCA CSCC**: Annual self-assessment submission via NCA portal; evidence artifacts from Azure Defender for Cloud
- **PDPL**: Saudi Data and AI Authority (SDAIA) oversight; breach notification within 72 hours
- **NDMO**: NDMO compliance report on data governance maturity; annual submission with evidence from Microsoft Purview

**Key Metrics for NCA/SDAIA Auditors:**
- % of CNII workloads with Defender for Cloud enabled
- % of government databases with CMK encryption
- % of production VMs with backup coverage
- MFA compliance rate for government user accounts
- Open critical security recommendations count (target: 0 P1)

---

## References

- [National Cybersecurity Authority — Cloud Security Controls (NCA CSCC)](https://nca.gov.sa/)
- [NDMO National Data Governance Framework](https://ndmo.gov.sa/)
- [Personal Data Protection Law (PDPL) — Royal Decree M/19](https://sdaia.gov.sa/)
- [Microsoft Azure Compliance — Saudi Arabia](https://learn.microsoft.com/en-us/azure/compliance/)
- [NCA CSCC to Azure Policy Built-in Mappings](https://learn.microsoft.com/en-us/azure/governance/policy/samples/)
- [Saudi Vision 2030 Digital Transformation](https://www.vision2030.gov.sa/)
