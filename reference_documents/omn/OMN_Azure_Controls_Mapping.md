# Oman Government Cybersecurity Framework to Azure Policy & Microsoft Defender Controls Mapping

## Executive Summary

This document provides a comprehensive mapping of the Sultanate of Oman's national cybersecurity framework to Azure Policy and Microsoft Defender for Cloud controls. The mapping covers:

- **Oman CDC** — Cloud Data Center Security Framework (OCERT/ITA criteria for cloud service providers)
- **Oman Information Technology Authority (ITA)** — National Cloud Policy and eGovernment security requirements
- **Oman National CERT (OCERT)** — Cybersecurity incident response and operational standards

This framework applies to Omani government entities, critical national infrastructure operators, and cloud service providers holding data residency obligations under Oman's national cloud policy. The mapping spans **10 domains** covering **53 Azure Policy controls**.

**All licensing options included:** Microsoft Defender for Cloud (all plans), Azure Policy, Microsoft Purview, Microsoft Sentinel, and related services.

---

## Framework Overview

| Framework | Issuing Authority | Scope |
|-----------|-----------------|-------|
| Oman CDC | Information Technology Authority (ITA) | Cloud service providers; government data hosting |
| OCERT Standards | Oman National CERT | Cybersecurity incident response; security operations |
| eGovernment Security | ITA / MOTC | All government digital services |

The Oman CDC framework covers **10 domains**:

1. Network Security (OMN_NET)
2. Identity & Access Control (OMN_IAM)
3. Logging & Monitoring (OMN_MON)
4. Risk Management & Compliance (OMN_RSK)
5. Data Protection & Privacy (OMN_DAT)
6. Endpoint Protection (OMN_END)
7. Vulnerability Management (OMN_VUL)
8. Business Continuity & DR (OMN_BCM)
9. Incident Response (OMN_INC)
10. Cybersecurity Governance (OMN_GOV)

---

## Domain-by-Domain Mapping

### Domain 1: Network Security (OMN_NET)

**Oman CDC Requirements:**
- Route all government internet traffic through an approved firewall
- Require NSGs on all cloud subnets
- Disable remote debugging on production applications
- Enable private endpoints for SQL databases

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| [Preview]: All Internet traffic should be routed via your deployed Azure Firewall | fc5e4038-4584-4632-8c85-c0448d374b2c | AuditIfNotExists | Yes | Foundation |
| Subnets should be associated with a Network Security Group | e71308d3-144b-4262-b144-efdc3cc90517 | AuditIfNotExists | Yes | Defender for Cloud |
| [Deprecated]: Unattached disks should be encrypted | 2c89a2e5-7285-40fe-afe0-ae8654b92fb2 | Audit | Yes | Defender for Cloud |
| There should be more than one owner assigned to your subscription | 09024ccc-0c5f-475e-9457-b7c0d9ed487b | AuditIfNotExists | Yes | Defender for Cloud |
| App Service apps should have remote debugging turned off | cb510bfd-1cba-4d9f-a230-cb0976f4bb71 | Audit, Deny | Yes | Foundation |
| Function apps should have remote debugging turned off | 0e60b895-3786-45da-8377-9c6b4b6ac5f9 | Audit, Deny | Yes | Foundation |
| Private endpoint connections on Azure SQL Database should be enabled | 7698e800-9299-47a6-b3b6-5a0fee576eed | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Azure Firewall Premium — Oman Government Traffic Inspection**
  - IDPS for encrypted and unencrypted government internet traffic
  - FQDN-based filtering for approved .gov.om services
  - Network topology enforcement (hub-spoke per ITA enterprise architecture)

- **Microsoft Defender for Cloud — Network Recommendations**
  - Adaptive network hardening for internet-facing government VMs
  - Open management port detection (RDP/SSH)
  - Network topology map for ITA network security reviews

- **Azure DDoS Protection Standard**
  - Protection for Oman eGovernment portals from volumetric attacks
  - Real-time attack mitigation monitoring

**Alerts & Monitoring:**
- Internet traffic bypassing Azure Firewall
- NSG missing from government production subnet
- Remote debugging enabled on .gov.om application
- Government SQL database publicly exposed
- DDoS threshold breach alert

---

### Domain 2: Identity & Access Control (OMN_IAM)

**Oman CDC + ITA Requirements:**
- Restrict network access from unauthorized accounts
- Provision dedicated Entra ID administrators for government SQL servers
- Enforce alert notifications for all high-severity security events
- Enforce MFA for all cloud resource creation and management
- Remove external guest accounts with write permissions
- Disable custom subscription owner roles

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Storage accounts should restrict network access | 34c877ad-507e-4c82-993e-3452a6e0ad3c | Audit, Deny | Yes | Defender for Storage |
| An Azure Active Directory administrator should be provisioned for SQL servers | 1f314764-cb73-4fc9-b863-8eca98ac36e9 | AuditIfNotExists | Yes | Defender for SQL |
| Email notification to subscription owner for high severity alerts should be enabled | 0b15565f-aa9e-48ba-8619-45960f2c314d | AuditIfNotExists | Yes | Defender for Cloud |
| Users must authenticate with MFA to create or update resources | 4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b | Audit | Yes | Foundation |
| [Deprecated]: MFA should be enabled for accounts with write permissions | 9297c21d-2ed6-4474-b48f-163f75654ce3 | AuditIfNotExists | Yes | Defender for Cloud |
| [Deprecated]: Custom subscription owner roles should not exist | 10ee2ea2-fb4d-45b8-a7e9-a2e770044cd9 | Audit | Yes | Foundation |
| Guest accounts with write permissions on Azure resources should be removed | 94e1c2ac-cbbe-4cac-a2b5-389c812dee87 | AuditIfNotExists | Yes | Defender for Cloud |

**Microsoft Defender Controls:**
- **Microsoft Entra ID for Oman Government**
  - Conditional Access with Oman IP range enforcement
  - Privileged Identity Management for JIT access to critical government systems
  - Access reviews for government official roles (aligned to ITA quarterly cycle)
  - Smart Lockout aligned to OCERT brute-force thresholds

- **Identity Threat Detection**
  - Entra ID Protection: sign-in risk and user risk policies
  - Atypical travel and impossible travel session detection
  - Leaked credential scanning for government identities

**Alerts & Monitoring:**
- Government MFA bypass detected
- Guest account with write access to government resource
- High-severity identity alert without notification configured
- Privileged role activated outside OCERT-approved window
- SQL server without Entra ID administrator

---

### Domain 3: Logging & Monitoring (OMN_MON)

**Oman CDC + OCERT Requirements:**
- Enable logging for all Log Analytics workspaces and audit trails
- Enable resource logging for data processing and batch workloads
- Configure SQL audit logging with 90-day retention minimum
- Enable SQL server auditing for all production databases

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Enable logging by category group for Log Analytics workspaces to Log Analytics | 818719e5-1338-4776-9a9d-3c31e4df5986 | DeployIfNotExists | Yes | Foundation |
| Resource logs in Batch accounts should be enabled | 428256e6-1fac-4f48-a757-df34c2b3336d | AuditIfNotExists | Yes | Foundation |
| SQL servers with auditing to storage account should be configured with 90+ days retention | 89099bee-89e0-4b26-a5f4-165451757743 | AuditIfNotExists | Yes | Defender for SQL |
| Auditing on SQL server should be enabled | a6fb4358-5bf4-4ad7-ba82-2cd2f41ce5e9 | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Microsoft Sentinel — Oman Government SIEM**
  - OCERT threat intelligence feed integration
  - Oman CDC-aligned detection rules
  - Real-time log correlation across government workloads
  - Automated playbooks for OCERT incident notification workflows

- **Azure Monitor + Log Analytics**
  - Centralized log collection for all ITA-managed subscriptions
  - Log Analytics workspace per classification level
  - OCERT reporting dashboards with KQL queries

- **Microsoft Defender for Cloud — Monitoring**
  - Security events aggregation and correlation
  - Continuous assessment of logging completeness

**Alerts & Monitoring:**
- Log Analytics workspace logging disabled
- SQL audit log retention below 90-day minimum
- Log gap detected (ingestion failure alert)
- Government batch workload without resource logging
- SIEM ingestion anomaly (volume drop)

---

### Domain 4: Risk Management & Compliance (OMN_RSK)

**Oman CDC + ITA Requirements:**
- Enable vulnerability assessment for all SQL Managed Instances
- Audit all RBAC role usage against approved government role catalog
- Maintain security contact email for all government subscriptions
- Disable local authentication on all ML workloads

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Azure Machine Learning Computes should have local authentication methods disabled | e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f | Audit, Deny | Yes | Foundation |
| Vulnerability assessment should be enabled on SQL Managed Instance | 1b7aa243-30e4-4c9e-bca8-d0d3022b634a | AuditIfNotExists | Yes | Defender for SQL |
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |
| Subscriptions should have a contact email address for security issues | 4f4f78b8-e367-4b10-a341-d9a4ad5cf1c7 | AuditIfNotExists | Yes | Defender for Cloud |

**Microsoft Defender Controls:**
- **Regulatory Compliance Dashboard — Oman CDC**
  - Real-time compliance posture for CDC framework controls
  - Risk-based prioritization aligned to Oman threat landscape
  - Control-owner assignment with ITA-defined remediation SLAs

- **Microsoft Purview Compliance Manager**
  - Oman CDC compliance assessment template
  - Continuous monitoring with evidence collection
  - Risk register integration for ITA audit submissions

**Alerts & Monitoring:**
- Oman CDC compliance score degradation
- SQL MI vulnerability assessment disabled
- ML workload using local (non-Entra) authentication
- Security contact email not configured on government subscription
- RBAC role usage outside approved government catalog

---

### Domain 5: Data Protection & Privacy (OMN_DAT)

**Oman CDC + ITA Data Residency Requirements:**
- Enable deletion protection on all key vaults
- Enable private endpoints for MySQL servers
- Enforce HTTPS on all government storage accounts
- Enforce storage infrastructure encryption
- Encrypt all disks using customer-managed keys
- Encrypt PostgreSQL and SQL servers with CMK
- Encrypt all Azure storage with CMK
- Enable private link for App Configuration (Oman government APIs)
- Encrypt Cosmos DB with CMK
- Encrypt unattached disks
- Configure Cognitive Services to disable public network access

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Key vaults should have deletion protection enabled | 0b60c0b2-2dc2-4e1c-b5c9-abbed971de53 | Audit, Deny | Yes | Foundation |
| Private endpoint should be enabled for MySQL servers | 7595c971-233d-4bcf-bd18-596129188c49 | AuditIfNotExists | Yes | Defender for Databases |
| Secure transfer to storage accounts should be enabled | 404c3081-a854-4457-ae30-26a93ef643f9 | Audit, Deny | Yes | Defender for Storage |
| Storage accounts should have infrastructure encryption | 4733ea7b-a883-42fe-8cac-97454c2a9e4a | Audit, Deny | Yes | Defender for Storage |
| OS and data disks should be encrypted with a customer-managed key | 702dd420-7fcc-42c5-afe8-4026edd20fe0 | Audit | Yes | Defender for Servers |
| PostgreSQL servers should use customer-managed keys to encrypt data at rest | 18adea5e-f416-4d0f-8aa8-d24321e3e274 | AuditIfNotExists | Yes | Defender for Databases |
| SQL servers should use customer-managed keys to encrypt data at rest | 0a370ff3-6cab-4e85-8995-295fd854c5b8 | AuditIfNotExists | Yes | Defender for SQL |
| App Configuration should use private link | ca610c1d-041c-4332-9d88-7ed3094967c7 | AuditIfNotExists | Yes | Foundation |
| Storage accounts should use customer-managed key for encryption | 6fac406b-40ca-413b-bf8e-0bf964659c25 | Audit | Yes | Defender for Storage |
| [Deprecated]: Cognitive Services accounts should use CMK or enable data encryption | 11566b39-f7f7-4b82-ab06-68d8700eb0a4 | Audit | Yes | Cognitive Services |
| [Deprecated]: Virtual machines should encrypt temp disks, caches, and data flows | 0961003e-5a0a-4549-abde-af6a37f2724d | Audit | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Microsoft Purview — Oman Data Residency**
  - Azure Policy to restrict deployment to UAE North (nearest compliant region) or approved sovereign regions
  - Data residency labels for Oman government-classified data
  - Personal data discovery for Oman residents (Omani National ID/Civil ID)

- **Microsoft Defender for Storage + Databases**
  - Anomalous government data access detection
  - Sensitive data classification for ITA-defined categories
  - Malware scanning for government document uploads

- **Azure Key Vault with Managed HSM**
  - FIPS 140-3 Level 3 key protection for government CMK
  - Automatic key rotation aligned to ITA key management policy
  - Key access audit logs for compliance

**Alerts & Monitoring:**
- Government data stored without CMK encryption
- Key Vault deletion protection disabled
- Storage encryption downgrade detected
- Cognitive Services public access enabled
- Data transfer outside approved Oman/GCC regions

---

### Domain 6: Endpoint Protection (OMN_END)

**Oman CDC Requirements:**
- Enable Azure Backup for all production government VMs
- Enable Microsoft Defender for Cloud across all subscriptions
- Configure Defender for Servers on all government workloads

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Azure Backup should be enabled for Virtual Machines | 013e242c-8828-4970-87b3-ab247555486d | AuditIfNotExists | Yes | Foundation |
| Enable Microsoft Defender for Cloud on your subscription | ac076320-ddcf-4066-b451-6154267e8ad2 | DeployIfNotExists | Yes | Foundation |
| Configure Azure Defender for servers to be enabled | 8e86a5b6-b9bd-49d1-8e21-4bb8a0862222 | DeployIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Microsoft Defender for Endpoint on Government VMs**
  - Real-time malware and ransomware protection
  - Behavioral analysis and advanced threat detection
  - Automated investigation and remediation (AIR)
  - Tamper protection for government endpoint configuration

- **Microsoft Defender for Servers (Plan 2)**
  - File Integrity Monitoring (FIM) for critical system files
  - Just-in-time VM access for government admin management ports
  - Agentless machine scanning

**Alerts & Monitoring:**
- Defender for Servers disabled on government VM
- Azure Backup missing for production government VM
- Endpoint malware or ransomware detected
- File Integrity Monitoring alert (unauthorized system change)
- JIT access request outside approved window

---

### Domain 7: Vulnerability Management (OMN_VUL)

**Oman CDC + OCERT Requirements:**
- Maintain patch compliance within OCERT-defined SLAs (Critical: 72 hrs, High: 7 days)
- Enable vulnerability assessment for all VMs
- Enforce adaptive network hardening on internet-facing VMs

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| [Deprecated]: System updates should be installed on your machines | 86b3d65f-7626-441e-b690-81a8b71cff60 | AuditIfNotExists | Yes | Defender for Servers |
| Machines should be configured to periodically check for missing system updates | bd876905-5b84-4f73-ab2d-2e7a7c4568d9 | AuditIfNotExists | Yes | Azure Update Manager |
| [Deprecated]: System updates on virtual machine scale sets should be installed | c3f317a7-a95c-4547-b7e7-11017ebdf2fe | AuditIfNotExists | Yes | Defender for Servers |
| [Deprecated]: Adaptive network hardening recommendations should be applied on internet-facing VMs | 08e6af2d-db70-460a-bfe9-d5bd474ba9d6 | AuditIfNotExists | Yes | Defender for Servers P2 |
| A vulnerability assessment solution should be enabled on your virtual machines | 501541f7-f7e7-4cd6-868c-4190fdad3ac9 | AuditIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Microsoft Defender Vulnerability Management**
  - Continuous vulnerability discovery across government VMs
  - CVSS-based prioritization aligned to OCERT risk thresholds
  - Browser extension vulnerability detection
  - Agentless scanning for unmanaged government devices

- **Azure Update Manager**
  - Patch compliance reporting across Oman government subscriptions
  - Maintenance windows aligned to ITA change management calendar
  - Multi-subscription patch orchestration

**Alerts & Monitoring:**
- Critical CVE on government VM beyond OCERT 72-hour SLA
- Vulnerability assessment solution not deployed
- VMSS missing system updates
- Adaptive network hardening bypass detected
- Zero-day exploit targeting government infrastructure

---

### Domain 8: Business Continuity & DR (OMN_BCM)

**Oman CDC + ITA BCP Requirements:**
- Enable VM Backup for all critical eGovernment services
- Enable secure Redis cache connections for session state
- Enforce update compliance for VMSS to enable zero-downtime patching
- Test DR plans bi-annually; submit evidence to ITA

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Azure Backup should be enabled for Virtual Machines | 013e242c-8828-4970-87b3-ab247555486d | AuditIfNotExists | Yes | Foundation |
| Only secure connections to your Azure Cache for Redis should be enabled | 22bee202-a82f-4305-9a2a-6d7f44d4dedb | Audit, Deny | Yes | Foundation |
| [Deprecated]: System updates on virtual machine scale sets should be installed | c3f317a7-a95c-4547-b7e7-11017ebdf2fe | AuditIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Azure Site Recovery for Oman eGov**
  - Automated failover with ITA-validated RPO/RTO targets
  - DR test runbooks with evidence for ITA bi-annual review
  - Priority recovery ordering for national service delivery systems

- **Azure Backup with Immutable Storage**
  - Ransomware-resistant backup configuration
  - Soft delete and multi-user authorization for deletion protection
  - Backup vault monitoring and alerting

**Alerts & Monitoring:**
- eGovernment VM backup failure
- DR test evidence overdue for ITA submission
- Redis cache SSL disabled (government session security risk)
- RTO/RPO SLA breach for critical government service
- Immutable backup disabled on vault

---

### Domain 9: Incident Response (OMN_INC)

**OCERT + ITA Requirements:**
- Enable resource logging for all government workloads
- Configure SQL audit trail for forensic investigation support
- Maintain security contact list for OCERT notification
- Enable SQL server auditing for incident attribution

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Resource logs in Batch accounts should be enabled | 428256e6-1fac-4f48-a757-df34c2b3336d | AuditIfNotExists | Yes | Foundation |
| SQL servers with auditing to storage account should be configured with 90+ days retention | 89099bee-89e0-4b26-a5f4-165451757743 | AuditIfNotExists | Yes | Defender for SQL |
| Subscriptions should have a contact email address for security issues | 4f4f78b8-e367-4b10-a341-d9a4ad5cf1c7 | AuditIfNotExists | Yes | Defender for Cloud |
| Auditing on SQL server should be enabled | a6fb4358-5bf4-4ad7-ba82-2cd2f41ce5e9 | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Microsoft Sentinel — OCERT Incident Response Automation**
  - Automated OCERT incident ticket creation via Logic Apps
  - IR playbooks for ransomware, data breach, and DDoS scenarios
  - Forensic evidence preservation workflow (log immutability)
  - Cross-workload attack chain analysis

- **Microsoft Defender XDR**
  - Unified incident view across endpoints, email, identity, and cloud
  - Automated attack disruption for active government incidents
  - Threat hunting capabilities for OCERT analysts

**Alerts & Monitoring:**
- OCERT P1 incident auto-escalation trigger
- Forensic log access denied or deleted
- SQL audit trail gap during active investigation
- Government workload breach notification trigger
- Incident response SLA breach (OCERT 1-hour response target)

---

### Domain 10: Cybersecurity Governance (OMN_GOV)

**Oman CDC + ITA Governance Requirements:**
- Align to Oman National Cybersecurity Strategy objectives
- Enable deletion protection on all key governance vaults
- Audit custom RBAC roles and enforce least privilege
- Restrict network access on critical government storage
- Maintain security contact for all government subscriptions

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Key vaults should have deletion protection enabled | 0b60c0b2-2dc2-4e1c-b5c9-abbed971de53 | Audit, Deny | Yes | Foundation |
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |
| Storage accounts should restrict network access | 34c877ad-507e-4c82-993e-3452a6e0ad3c | Audit, Deny | Yes | Defender for Storage |
| Subscriptions should have a contact email address for security issues | 4f4f78b8-e367-4b10-a341-d9a4ad5cf1c7 | AuditIfNotExists | Yes | Defender for Cloud |

**Microsoft Defender Controls:**
- **Microsoft Defender for Cloud — Governance (ITA-aligned)**
  - Governance rules assigning recommendations to government owners
  - Compliance benchmark aligned to Oman CDC control objectives
  - Monthly security posture report for ITA leadership

- **Microsoft Purview Compliance Manager**
  - Oman CDC and ITA compliance assessment
  - Risk score tracking and remediation workflows
  - Annual compliance reporting evidence collection

**Alerts & Monitoring:**
- ITA governance SLA breach (unassigned security recommendation)
- Key Vault deletion protection disabled
- Custom RBAC role created without ITA authorization
- Government storage public access enabled
- Security contact missing for government subscription

---

## Oman Government CDC Defender Plan Summary

| Defender Plan | Domains Covered | Key Government Use Case |
|--------------|-----------------|------------------------|
| Defender for Cloud Foundation | NET, IAM, RSK, END, GOV | Baseline ITA compliance posture |
| Defender for Servers P2 | VUL, END | Government VM protection + FIM |
| Defender for SQL | IAM, MON, RSK, INC | Government database security |
| Defender for Storage | DAT, GOV | Government file security + data classification |
| Defender for Databases | DAT | MySQL/PostgreSQL government data |
| Defender for IoT | NET | OT/ICS for Oman critical national infrastructure |
| Microsoft Sentinel | MON, INC (cross-domain) | OCERT SIEM/SOAR integration |
| Microsoft Purview | DAT, RSK, GOV | Data classification + PDPL compliance |

---

## Compliance Reporting

**Oman Framework Reporting Requirements:**
- **ITA CDC**: Annual cloud security compliance submission to ITA; evidence from Azure Defender for Cloud
- **OCERT**: Incident reports within defined OCERT SLAs; security posture updates
- **eGovernment**: ITA-required annual security assessment for digital service delivery

**Key Metrics for ITA / OCERT Auditors:**
- % of government workloads with Defender for Cloud enabled
- % of government data stores with CMK encryption
- % of production government VMs with backup coverage
- MFA compliance rate for government officials (target: 100%)
- Open P1/P2 security recommendations (target: 0)
- Patch compliance rate within OCERT SLAs (Critical/72hrs, High/7days)

---

## References

- [Information Technology Authority — Oman (ITA)](https://ita.gov.om/)
- [Oman National CERT (OCERT)](https://ocert.gov.om/)
- [Oman National Cybersecurity Strategy 2021-2025](https://ncss.gov.om/)
- [Microsoft Azure Gulf Region Compliance Documentation](https://learn.microsoft.com/en-us/azure/compliance/)
- [Azure Policy Built-in Definitions Reference](https://learn.microsoft.com/en-us/azure/governance/policy/samples/built-in-policies)
- [Microsoft Defender for IoT — Critical Infrastructure Protection](https://learn.microsoft.com/en-us/azure/defender-for-iot/)
