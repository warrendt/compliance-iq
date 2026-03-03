# SAMA Cybersecurity Framework to Azure Policy & Microsoft Defender Controls Mapping

## Executive Summary

This document provides a comprehensive mapping of the Saudi Arabian Monetary Authority (SAMA) Cybersecurity Framework controls to Azure Policy and Microsoft Defender for Cloud controls with alerting capabilities.

The SAMA Cybersecurity Framework applies to all financial institutions operating in the Kingdom of Saudi Arabia, including banks, insurance companies, and finance companies regulated by SAMA. It defines a set of cybersecurity controls across **8 domains** organized around the NIST Cybersecurity Framework with 4 maturity levels (Initial → Developing → Defined → Managed).

**All licensing options included:** Microsoft Defender for Cloud (all plans), Azure Policy, Microsoft Sentinel, and related services.

---

## SAMA Framework Overview

The SAMA Cybersecurity Framework covers **8 control domains** applicable to financial institutions:

1. Access Control
2. Identity & Authentication
3. Network Security (Perimeter)
4. Network Infrastructure Security
5. Data Protection
6. Logging & Monitoring
7. Vulnerability Management
8. Cognitive Services (AI) Security

---

## Domain-by-Domain Mapping

### Domain 1: Access Control (SAMA-AC-01)

**SAMA Requirements:**
- Implement role-based access control (RBAC) aligned to least privilege
- Enforce separation of duties for critical financial functions
- Remove or disable unused accounts and external guest accounts
- Review all privileged access rights at least quarterly
- Implement multi-factor authentication for all users

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
| [Deprecated]: External accounts with write permissions should be removed | 5c607a2e-c700-4744-8254-d77e7c9eb5e4 | Audit | Yes | Defender for Cloud |
| Guest accounts with read permissions on Azure resources should be removed | e9ac8f8e-ce22-4355-8f04-99b911d6be52 | AuditIfNotExists | Yes | Defender for Cloud |

**Microsoft Defender Controls:**
- **Microsoft Entra ID (formerly Azure AD)**
  - Conditional Access policies for financial workloads
  - Privileged Identity Management (PIM) for just-in-time admin access
  - Access reviews (quarterly reviews of privileged roles)
  - Entitlement management for application access

- **Microsoft Defender for Cloud — Security Posture**
  - Secure Score tracking for identity recommendations
  - Just-in-time VM access to reduce attack surface
  - Recommendations for over-privileged accounts

**Alerts & Monitoring:**
- Role assignment change alerts (Activity Log alert)
- Guest account addition alerts
- PIM role activation alerts
- Privileged role change email notifications
- MFA disabled or bypassed alerts

---

### Domain 2: Identity & Authentication (SAMA-AC-03)

**SAMA Requirements:**
- Enforce strong authentication (MFA) for remote access and privileged accounts
- Audit use of custom RBAC roles to detect privilege escalation
- Enforce Entra ID-only authentication for SQL workloads
- Maintain subscription security contact information

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |
| An Azure Active Directory administrator should be provisioned for SQL servers | 1f314764-cb73-4fc9-b863-8eca98ac36e9 | AuditIfNotExists | Yes | Defender for SQL |
| Azure SQL Managed Instance should have Microsoft Entra-only authentication enabled | 0c28c3fb-c244-42d5-a9bf-f35f2999577b | Audit | Yes | Defender for SQL |
| Subscriptions should have a contact email address for security issues | 4f4f78b8-e367-4b10-a341-d9a4ad5cf1c7 | AuditIfNotExists | Yes | Defender for Cloud |
| There should be more than one owner assigned to your subscription | 09024ccc-0c5f-475e-9457-b7c0d9ed487b | AuditIfNotExists | Yes | Defender for Cloud |

**Microsoft Defender Controls:**
- **Privileged Identity Management (PIM)**
  - Time-bound privileged access for SAMA-regulated systems
  - Approval workflows for critical role activation
  - Alert on permanent privileged role assignments

- **Microsoft Entra ID Protection**
  - Risk-based Conditional Access for high-risk sign-ins
  - Leaked credential detection
  - Sign-in risk policies

**Alerts & Monitoring:**
- Anonymous IP address sign-in alerts
- Impossible travel detection
- Malicious IP address sign-in
- Suspicious inbox manipulation
- Custom RBAC role creation alerts

---

### Domain 3: Network Security — Perimeter (SAMA-NS-01)

**SAMA Requirements:**
- Implement network segmentation between financial systems
- Associate Network Security Groups (NSGs) with all subnets
- Disable remote debugging on internet-facing applications
- Ensure subscription ownership redundancy

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Subnets should be associated with a Network Security Group | e71308d3-144b-4262-b144-efdc3cc90517 | AuditIfNotExists | Yes | Defender for Cloud |
| [Deprecated]: Unattached disks should be encrypted | 2c89a2e5-7285-40fe-afe0-ae8654b92fb2 | Audit | Yes | Defender for Cloud |
| There should be more than one owner assigned to your subscription | 09024ccc-0c5f-475e-9457-b7c0d9ed487b | AuditIfNotExists | Yes | Defender for Cloud |
| App Service apps should have remote debugging turned off | cb510bfd-1cba-4d9f-a230-cb0976f4bb71 | Audit, Deny | Yes | Foundation |
| Function apps should have remote debugging turned off | 0e60b895-3786-45da-8377-9c6b4b6ac5f9 | Audit, Deny | Yes | Foundation |
| [Deprecated]: Remote debugging should be turned off for API Apps | e9c8d085-d9cc-4b17-9cdc-059f1f01f19e | Audit | Yes | Foundation |

**Microsoft Defender Controls:**
- **Microsoft Defender for Cloud — Network Hardening**
  - Adaptive network hardening recommendations
  - Network security group recommendations
  - Internet-facing VM exposure analysis

- **Azure Network Security Features**
  - Network Security Groups with security rules
  - Azure Firewall with threat intelligence
  - DDoS Protection Standard

**Alerts & Monitoring:**
- NSG rule change alerts
- Internet-exposed VM alerts
- Suspicious network traffic alerts
- Port scanning detection
- Data exfiltration alerts

---

### Domain 4: Network Infrastructure Security (SAMA-NS-02)

**SAMA Requirements:**
- Use private endpoints and private link for PaaS services
- Restrict public network access to Key Vault
- Enforce private connectivity for configuration services
- Disable public network access for SQL Managed Instances

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| App Configuration should use private link | ca610c1d-041c-4332-9d88-7ed3094967c7 | AuditIfNotExists | Yes | Foundation |
| Azure Key Vaults should use private link | a6abeaec-4d90-4a02-805f-6b26c4d3fbe9 | AuditIfNotExists | Yes | Foundation |
| Azure Key Vault should have firewall enabled or public network access disabled | 55615ac9-af46-4a59-874e-391cc3dfb490 | Audit, Deny | Yes | Foundation |
| Private endpoint connections on Azure SQL Database should be enabled | 7698e800-9299-47a6-b3b6-5a0fee576eed | Audit | Yes | Defender for SQL |
| Azure SQL Managed Instances should disable public network access | 9dfea752-dd46-4766-aed1-c355fa93fb91 | Audit, Deny | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Azure Private Link**
  - Private endpoints for all PaaS services
  - Private DNS zones for name resolution
  - Service Endpoints as fallback for legacy workloads

- **Azure Firewall Premium**
  - TLS inspection for encrypted traffic
  - IDPS (Intrusion Detection and Prevention System)
  - Application and network rule collections

**Alerts & Monitoring:**
- Public endpoint exposure alerts
- Key Vault access from unapproved networks
- SQL public access enabled alerts
- Private endpoint health alerts

---

### Domain 5: Data Protection (SAMA-DP-02)

**SAMA Requirements:**
- Encrypt all data at rest using customer-managed keys (CMK)
- Enforce TLS/secure transfer for all data in transit
- Implement storage infrastructure encryption
- Enable deletion protection for cryptographic key vaults
- Protect Cosmos DB and SQL databases with CMK

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| PostgreSQL servers should use customer-managed keys to encrypt data at rest | 18adea5e-f416-4d0f-8aa8-d24321e3e274 | AuditIfNotExists | Yes | Defender for Databases |
| Private endpoint should be enabled for MySQL servers | 7595c971-233d-4bcf-bd18-596129188c49 | AuditIfNotExists | Yes | Defender for Databases |
| Secure transfer to storage accounts should be enabled | 404c3081-a854-4457-ae30-26a93ef643f9 | Audit, Deny | Yes | Defender for Storage |
| Storage accounts should have infrastructure encryption | 4733ea7b-a883-42fe-8cac-97454c2a9e4a | Audit, Deny | Yes | Defender for Storage |
| SQL servers should use customer-managed keys to encrypt data at rest | 0a370ff3-6cab-4e85-8995-295fd854c5b8 | AuditIfNotExists | Yes | Defender for SQL |
| [Deprecated]: Virtual machines should encrypt temp disks, caches, and data flows | 0961003e-5a0a-4549-abde-af6a37f2724d | Audit | Yes | Defender for Servers |
| Storage accounts should use customer-managed key for encryption | 6fac406b-40ca-413b-bf8e-0bf964659c25 | Audit | Yes | Defender for Storage |
| Azure Cosmos DB accounts should use customer-managed keys to encrypt data at rest | 1f905d99-2ab7-462c-a6b0-f709acca6c8f | Audit, Deny | Yes | Foundation |
| Key vaults should have deletion protection enabled | 0b60c0b2-2dc2-4e1c-b5c9-abbed971de53 | Audit, Deny | Yes | Foundation |
| OS and data disks should be encrypted with a customer-managed key | 702dd420-7fcc-42c5-afe8-4026edd20fe0 | Audit | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Azure Key Vault with HSM Protection**
  - FIPS 140-3 Level 3 hardware security for CMK
  - Key rotation policies for compliance
  - Managed HSM for dedicated HSM workloads

- **Microsoft Purview Information Protection**
  - Sensitive financial data classification
  - Data Loss Prevention for financial PII
  - Automatic labeling for banking data

- **Microsoft Defender for Storage**
  - Malware scanning on upload
  - Anomalous access pattern detection
  - Sensitive data exposure monitoring

**Alerts & Monitoring:**
- Encryption disabled alerts
- Insecure HTTP transfer detected
- Key Vault key expiration warnings
- CMK disabled on database alerts
- Data exfiltration anomaly alerts

---

### Domain 6: Logging & Monitoring (SAMA-LM-01)

**SAMA Requirements:**
- Enable comprehensive audit logging for all financial workloads
- Retain SQL audit logs for a minimum of 90 days
- Enable resource logs for all applicable Azure services
- Enable auditing on SQL servers for transaction tracking
- Enable Log Analytics for centralized log management

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Enable logging by category group for Log Analytics workspaces to Log Analytics | 818719e5-1338-4776-9a9d-3c31e4df5986 | DeployIfNotExists | Yes | Foundation |
| Resource logs in Batch accounts should be enabled | 428256e6-1fac-4f48-a757-df34c2b3336d | AuditIfNotExists | Yes | Foundation |
| SQL servers with auditing to storage account should be configured with 90+ days retention | 89099bee-89e0-4b26-a5f4-165451757743 | AuditIfNotExists | Yes | Defender for SQL |
| Auditing on SQL server should be enabled | a6fb4358-5bf4-4ad7-ba82-2cd2f41ce5e9 | AuditIfNotExists | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Microsoft Sentinel**
  - SIEM/SOAR for financial institution threat detection
  - SAMA-specific detection rules and workbooks
  - Automated incident response playbooks
  - Threat intelligence integration (MISP, MSTIC)

- **Microsoft Defender for Cloud — Security Alerts**
  - 90-day alert retention
  - MITRE ATT&CK-mapped alerts
  - Alert export to Sentinel and SIEM systems

- **Azure Monitor Log Analytics**
  - Centralized log collection and analysis
  - KQL-based queries for SAMA audit reporting
  - Diagnostic settings for all Azure services

**Alerts & Monitoring:**
- Audit logging disabled alerts
- Retention policy violation notifications
- Log ingestion gap alerts
- SQL audit configuration drift
- Security alert suppression detection

---

### Domain 7: Vulnerability Management (SAMA-VM-01)

**SAMA Requirements:**
- Apply regular system updates and patches
- Enable vulnerability assessment scanning
- Configure Microsoft Defender for Servers
- Implement endpoint protection across all virtual machines
- Enable adaptive network hardening

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| [Deprecated]: System updates should be installed on your machines | 86b3d65f-7626-441e-b690-81a8b71cff60 | AuditIfNotExists | Yes | Defender for Servers |
| Machines should be configured to periodically check for missing system updates | bd876905-5b84-4f73-ab2d-2e7a7c4568d9 | AuditIfNotExists | Yes | Azure Update Manager |
| [Deprecated]: System updates on virtual machine scale sets should be installed | c3f317a7-a95c-4547-b7e7-11017ebdf2fe | AuditIfNotExists | Yes | Defender for Servers |
| [Deprecated]: Endpoint protection should be installed on your machines | 1f7c564c-0a90-4d44-b7e1-9d456cffaee8 | AuditIfNotExists | Yes | Defender for Servers |
| Configure Azure Defender for servers to be enabled | 8e86a5b6-b9bd-49d1-8e21-4bb8a0862222 | DeployIfNotExists | Yes | Defender for Servers P1/P2 |
| Azure Machine Learning Computes should have local authentication methods disabled | e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f | Audit, Deny | Yes | Foundation |
| Vulnerability assessment should be enabled on SQL Managed Instance | 1b7aa243-30e4-4c9e-bca8-d0d3022b634a | AuditIfNotExists | Yes | Defender for SQL |
| [Deprecated]: Adaptive network hardening recommendations should be applied on internet-facing VMs | 08e6af2d-db70-460a-bfe9-d5bd474ba9d6 | AuditIfNotExists | Yes | Defender for Servers P2 |
| A vulnerability assessment solution should be enabled on your virtual machines | 501541f7-f7e7-4cd6-868c-4190fdad3ac9 | AuditIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Microsoft Defender for Servers (Plan 2)**
  - Integrated Qualys/TVM vulnerability assessment (agentless)
  - File integrity monitoring (FIM) for financial workloads
  - Adaptive application controls
  - Just-in-time VM access

- **Azure Update Manager**
  - Centralized patch management
  - Compliance reports for update state
  - Scheduled maintenance windows

- **Defender for Cloud Secure Score**
  - Continuous compliance measurement
  - Security recommendation prioritization
  - Attack path analysis

**Alerts & Monitoring:**
- Critical vulnerability discovery alerts
- Missing patch alerts
- Exploit kit activity detection
- Fileless attack detection
- Antimalware signature out-of-date alerts

---

### Domain 8: Cognitive Services (AI) Security (SAMA-AI-03)

**SAMA Requirements:**
- Disable public network access for AI/Cognitive Services
- Encrypt AI service data with customer-managed keys
- Secure AI model endpoints from unauthorized access

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| [Deprecated]: Cognitive Services accounts should use customer-owned storage or enable data encryption | 11566b39-f7f7-4b82-ab06-68d8700eb0a4 | Audit | Yes | Foundation |
| Configure Cognitive Services accounts to disable public network access | 47ba1dd7-28d9-4b07-a8d5-9813bed64e0c | Modify | Yes | Foundation |

**Microsoft Defender Controls:**
- **Azure AI Content Safety**
  - Content moderation for AI-generated outputs
  - Jailbreak attempt detection
  - Sensitive information detection in AI responses

- **Azure API Management**
  - Rate limiting and throttling for AI APIs
  - API key management and rotation
  - Request/response logging for audit

**Alerts & Monitoring:**
- Public AI endpoint exposure alerts
- Unusual AI API consumption patterns
- Key rotation compliance alerts
- Content safety policy violations

---

## SAMA Defender Plan Summary

| Defender Plan | SAMA Domains Covered | Estimated Monthly Cost |
|--------------|---------------------|----------------------|
| Defender for Cloud Foundation | All domains (baseline) | Included |
| Defender for Servers P2 | VM-01, NS-01 | $15/server/month |
| Defender for SQL | AC-03, DP-02, LM-01, VM-01 | $15/server/month |
| Defender for Storage | DP-02 | $10/storage account/month |
| Defender for Databases | DP-02 | $15/server/month |
| Defender for APIs | NS-01, NS-02 | $5/API/month |
| Microsoft Sentinel | LM-01 | Based on data volume |

---

## Compliance Reporting

**Azure Policy Compliance Dashboard:**
- Navigate to: Azure Portal → Policy → Compliance → SAMA Cybersecurity Framework Initiative
- Filter by: Subscription, Resource Group, Resource Type
- Export: CSV/JSON for SAMA auditors

**Key Compliance Metrics for SAMA Auditors:**
- % of resources with MFA enforced
- % of data encrypted with CMK
- % of VMs with vulnerability assessment enabled
- SQL audit log retention compliance rate
- % of network resources with NSG associations

---

## References

- [SAMA Cybersecurity Framework v1.0](https://www.sama.gov.sa/en-US/RulesInstructions/BankingRules/Saudi%20Arabian%20Monetary%20Authority%20Cyber%20Security%20Framework.pdf)
- [Azure Policy - SAMA Initiative](https://learn.microsoft.com/en-us/azure/governance/policy/samples/)
- [Microsoft Defender for Cloud Plans](https://learn.microsoft.com/en-us/azure/defender-for-cloud/defender-for-cloud-introduction)
- [SAMA Circular on Cloud Computing Security](https://www.sama.gov.sa)
