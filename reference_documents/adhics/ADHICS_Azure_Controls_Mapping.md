# ADHICS v2 to Azure Policy & Microsoft Defender Controls Mapping

## Executive Summary

This document provides a comprehensive mapping of the Abu Dhabi Healthcare Information and Cyber Security (ADHICS) Standard Version 2 controls to Azure Policy and Microsoft Defender for Cloud controls with alerting capabilities.

ADHICS is the official cybersecurity framework for healthcare organizations in the Emirate of Abu Dhabi, published by the Health Data Services (HDS) function of the Department of Health — Abu Dhabi. It establishes mandatory controls for the protection of Patient Health Information (PHI) across **9 domains** and aligns with ISO 27001, HIPAA, and NESA/UAE IA standards.

**All licensing options included:** Microsoft Defender for Cloud (all plans), Azure Policy, Microsoft Purview, Microsoft Sentinel, and related services.

---

## ADHICS Framework Overview

The ADHICS v2 Standard covers **9 domains**:

1. Governance
2. Protected Health Information (PHI)
3. Identity & Access Management
4. Network Security
5. Application Security
6. Medical Device Security
7. Data Management
8. Compliance
9. Business Continuity

---

## Domain-by-Domain Mapping

### Domain 1: Governance (ADHICS_GOV)

**ADHICS Requirements:**
- Establish a healthcare cybersecurity policy and governance framework
- Appoint a Chief Information Security Officer (CISO) for health entities
- Implement a formal risk management framework aligned with ISO 27005
- Conduct third-party supplier risk assessments
- Define and enforce acceptable use policies
- Perform annual cybersecurity audits

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |
| Storage accounts should restrict network access | 34c877ad-507e-4c82-993e-3452a6e0ad3c | Audit, Deny | Yes | Defender for Storage |
| Subscriptions should have a contact email address for security issues | 4f4f78b8-e367-4b10-a341-d9a4ad5cf1c7 | AuditIfNotExists | Yes | Defender for Cloud |
| Email notification to subscription owner for high severity alerts should be enabled | 0b15565f-aa9e-48ba-8619-45960f2c314d | AuditIfNotExists | Yes | Defender for Cloud |

**Microsoft Defender Controls:**
- **Microsoft Defender for Cloud — Governance**
  - Governance rules to assign risk owners to security recommendations
  - Regulatory compliance dashboard (HIPAA, ISO 27001)
  - Security posture management (CSPM)

- **Microsoft Purview Compliance Manager**
  - ADHICS and HIPAA compliance assessments
  - Risk score tracking and remediation actions
  - Audit-ready compliance reports for DoH-Abu Dhabi

**Alerts & Monitoring:**
- Security contact email missing alerts
- High-severity security finding notifications
- Custom RBAC role usage alerts
- Governance SLA breach notifications (overdue recommendations)

---

### Domain 2: Protected Health Information (ADHICS_PHI)

**ADHICS Requirements:**
- Encrypt PHI at rest using AES-256 with customer-managed keys
- Enforce TLS 1.2+ for all PHI transmission
- Enable private endpoints for databases containing PHI
- Implement storage infrastructure encryption for healthcare data
- Enable deletion protection on key vaults storing health encryption keys
- Audit and log all access to PHI data stores
- Disable public access to SQL Managed Instances holding patient records

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| PostgreSQL servers should use customer-managed keys to encrypt data at rest | 18adea5e-f416-4d0f-8aa8-d24321e3e274 | AuditIfNotExists | Yes | Defender for Databases |
| OS and data disks should be encrypted with a customer-managed key | 702dd420-7fcc-42c5-afe8-4026edd20fe0 | Audit | Yes | Defender for Servers |
| SQL servers should use customer-managed keys to encrypt data at rest | 0a370ff3-6cab-4e85-8995-295fd854c5b8 | AuditIfNotExists | Yes | Defender for SQL |
| Storage accounts should use customer-managed key for encryption | 6fac406b-40ca-413b-bf8e-0bf964659c25 | Audit | Yes | Defender for Storage |
| Private endpoint should be enabled for MySQL servers | 7595c971-233d-4bcf-bd18-596129188c49 | AuditIfNotExists | Yes | Defender for Databases |
| Secure transfer to storage accounts should be enabled | 404c3081-a854-4457-ae30-26a93ef643f9 | Audit, Deny | Yes | Defender for Storage |
| [Deprecated]: Virtual machines should encrypt temp disks, caches, and data flows | 0961003e-5a0a-4549-abde-af6a37f2724d | Audit | Yes | Defender for Servers |
| Key vaults should have deletion protection enabled | 0b60c0b2-2dc2-4e1c-b5c9-abbed971de53 | Audit, Deny | Yes | Foundation |

**Microsoft Defender Controls:**
- **Microsoft Purview Information Protection (Healthcare)**
  - Sensitive information types for ICD codes, MRN numbers, PHI identifiers
  - Automatic labeling for EMR/EHR exports
  - HIPAA data loss prevention (DLP) templates

- **Microsoft Defender for Storage**
  - Malware scanning for medical imaging uploads (DICOM files)
  - Anomalous PHI data access detection
  - Sensitive data discovery and classification

- **Azure Key Vault with Managed HSM**
  - FIPS 140-3 Level 3 key storage for healthcare CMK
  - Automatic key rotation for PHI encryption keys
  - Key access auditing for compliance

**Alerts & Monitoring:**
- PHI encryption disabled alerts
- Unencrypted PHI data store detected
- Key Vault PHI key expiration warnings
- Anomalous large-scale PHI data download
- TLS downgrade attack detection

---

### Domain 3: Identity & Access Management (ADHICS_IAM)

**ADHICS Requirements:**
- Enforce MFA for all healthcare user accounts
- Implement Privileged Access Management (PAM) for clinical system administrators
- Disable external/guest accounts with write access to health systems
- Enforce Entra ID-only authentication for SQL databases containing patient records
- Conduct quarterly access reviews for roles with PHI access
- Remove deprecated accounts with standing privileges

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
| An Azure Active Directory administrator should be provisioned for SQL servers | 1f314764-cb73-4fc9-b863-8eca98ac36e9 | AuditIfNotExists | Yes | Defender for SQL |
| Azure SQL Managed Instance should have Microsoft Entra-only authentication enabled | 0c28c3fb-c244-42d5-a9bf-f35f2999577b | Audit | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Microsoft Entra ID (formerly Azure AD)**
  - Conditional Access for clinical staff and location-aware policies
  - Just-in-time access for EHR administrator roles via PIM
  - Access reviews for all PHI-privileged roles (quarterly)
  - Azure AD B2B governance for third-party healthcare partners

- **Microsoft Entra Permissions Management**
  - Permission Creep Index for ADHICS-scoped subscriptions
  - Recommendations for right-sizing clinical system access
  - Unused credentials and access key rotation

**Alerts & Monitoring:**
- Guest account with PHI access detected
- MFA disabled for clinical staff account
- Privileged role activated outside approved hours
- Patient data access from unrecognized location
- Deprecated account with active PHI access

---

### Domain 4: Network Security (ADHICS_NET)

**ADHICS Requirements:**
- Segment clinical networks from administrative and public networks
- Require Network Security Groups on all subnets
- Enforce multiple subscription owners for administration resilience
- Use private endpoints or App Configuration private link for clinical APIs
- Enable Key Vault firewall for all healthcare cryptographic material

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Subnets should be associated with a Network Security Group | e71308d3-144b-4262-b144-efdc3cc90517 | AuditIfNotExists | Yes | Defender for Cloud |
| [Deprecated]: Unattached disks should be encrypted | 2c89a2e5-7285-40fe-afe0-ae8654b92fb2 | Audit | Yes | Defender for Cloud |
| There should be more than one owner assigned to your subscription | 09024ccc-0c5f-475e-9457-b7c0d9ed487b | AuditIfNotExists | Yes | Defender for Cloud |
| App Configuration should use private link | ca610c1d-041c-4332-9d88-7ed3094967c7 | AuditIfNotExists | Yes | Foundation |
| Azure Key Vaults should use private link | a6abeaec-4d90-4a02-805f-6b26c4d3fbe9 | AuditIfNotExists | Yes | Foundation |
| Azure Key Vault should have firewall enabled or public network access disabled | 55615ac9-af46-4a59-874e-391cc3dfb490 | Audit, Deny | Yes | Foundation |

**Microsoft Defender Controls:**
- **Network Security for Healthcare**
  - Azure Firewall Premium with IDPS for clinical network traffic
  - Medical device network isolation (VLAN/NSG segmentation)
  - Azure Application Gateway + WAF for patient portal protection
  - DDoS Protection Standard for healthcare portals

- **Microsoft Defender for Cloud — Network Recommendations**
  - Network topology visibility
  - Open management ports (RDP/SSH) detection on clinical VMs
  - Adaptive network hardening for internet-facing health apps

**Alerts & Monitoring:**
- Clinical network segment breach alerts
- Unusual lateral movement between VLANs
- Medical device network scanning detection
- NSG rule permitting all inbound traffic
- Healthcare API unauthorized access attempts

---

### Domain 5: Application Security (ADHICS_APP)

**ADHICS Requirements:**
- Apply regular system updates to all clinical application servers
- Enforce infrastructure encryption for healthcare storage
- Disable remote debugging on EHR and clinical portal applications
- Secure API apps and function apps from remote debugging
- Enforce private SQL database connectivity for patient management systems

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| [Deprecated]: System updates should be installed on your machines | 86b3d65f-7626-441e-b690-81a8b71cff60 | AuditIfNotExists | Yes | Defender for Servers |
| Storage accounts should have infrastructure encryption | 4733ea7b-a883-42fe-8cac-97454c2a9e4a | Audit, Deny | Yes | Defender for Storage |
| App Service apps should have remote debugging turned off | cb510bfd-1cba-4d9f-a230-cb0976f4bb71 | Audit, Deny | Yes | Foundation |
| Function apps should have remote debugging turned off | 0e60b895-3786-45da-8377-9c6b4b6ac5f9 | Audit, Deny | Yes | Foundation |
| [Deprecated]: Remote debugging should be turned off for API Apps | e9c8d085-d9cc-4b17-9cdc-059f1f01f19e | Audit | Yes | Foundation |
| Azure SQL Managed Instances should disable public network access | 9dfea752-dd46-4766-aed1-c355fa93fb91 | Audit, Deny | Yes | Defender for SQL |

**Microsoft Defender Controls:**
- **Microsoft Defender for App Service**
  - OWASP threat detection for patient portals
  - Dangling DNS subdomain hijacking prevention
  - Suspicious file upload detection in clinical apps

- **Microsoft Defender for APIs**
  - Healthcare API endpoint discovery and inventory
  - HL7/FHIR API security monitoring
  - API abuse and data harvesting detection

- **Microsoft Defender for Containers**
  - Container image vulnerability scanning for clinical apps
  - Runtime threat detection in containerized EHR deployments
  - CI/CD pipeline security for healthcare DevOps

**Alerts & Monitoring:**
- Remote debugging enabled on EHR application server
- Clinical application vulnerability exploited
- HL7 FHIR API abuse pattern detected
- Healthcare container image vulnerability alert
- SQL injection attempt on patient database

---

### Domain 6: Medical Device Security (ADHICS_DEV)

**ADHICS Requirements:**
- Maintain an inventory of all IoT/medical devices with network access
- Enforce system updates and patch management with vendor coordination
- Enable Microsoft Defender coverage for devices
- Monitor device communication patterns for anomalies

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| An Azure Active Directory administrator should be provisioned for SQL servers | 1f314764-cb73-4fc9-b863-8eca98ac36e9 | AuditIfNotExists | Yes | Defender for SQL |
| Email notification to subscription owner for high severity alerts should be enabled | 0b15565f-aa9e-48ba-8619-45960f2c314d | AuditIfNotExists | Yes | Defender for Cloud |
| Enable Microsoft Defender for Cloud on your subscription | ac076320-ddcf-4066-b451-6154267e8ad2 | DeployIfNotExists | Yes | Foundation |
| Configure Azure Defender for servers to be enabled | 8e86a5b6-b9bd-49d1-8e21-4bb8a0862222 | DeployIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Microsoft Defender for IoT**
  - Medical device discovery and inventory (passive scanning)
  - Anomaly detection for device communications (e.g., infusion pumps, imaging equipment)
  - Vulnerability assessment for medical device firmware
  - Protocol-aware detection for DICOM, HL7, and proprietary medical protocols

- **Azure IoT Hub Security**
  - Device-to-cloud authentication with X.509 certificates
  - Device twin security state monitoring
  - Message routing with audit logging

**Alerts & Monitoring:**
- New unrecognized medical device on network
- Device firmware vulnerability exploited
- Unusual communication pattern from imaging device
- Medical device attempting lateral movement
- DICOM protocol abuse detection

---

### Domain 7: Data Management (ADHICS_DATA)

**ADHICS Requirements:**
- Configure audit logging with minimum 90-day SQL retention
- Enable SQL server auditing for patient data tracking
- Enable Azure Backup for all clinical data VMs
- Enable secure connections for health data caches (Redis)
- Enable resource logging for data processing pipelines

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| SQL servers with auditing to storage account should be configured with 90+ days retention | 89099bee-89e0-4b26-a5f4-165451757743 | AuditIfNotExists | Yes | Defender for SQL |
| Auditing on SQL server should be enabled | a6fb4358-5bf4-4ad7-ba82-2cd2f41ce5e9 | AuditIfNotExists | Yes | Defender for SQL |
| Azure Backup should be enabled for Virtual Machines | 013e242c-8828-4970-87b3-ab247555486d | AuditIfNotExists | Yes | Foundation |
| Only secure connections to your Azure Cache for Redis should be enabled | 22bee202-a82f-4305-9a2a-6d7f44d4dedb | Audit, Deny | Yes | Foundation |
| Resource logs in Batch accounts should be enabled | 428256e6-1fac-4f48-a757-df34c2b3336d | AuditIfNotExists | Yes | Foundation |

**Microsoft Defender Controls:**
- **Healthcare Data Lifecycle Management**
  - Azure Backup with geo-redundant recovery for clinical workloads
  - Retention policies compliant with UAE Health Records Law
  - Soft-delete for accidental clinical data deletion prevention

- **Microsoft Purview Data Catalog for Healthcare**
  - Clinical data asset discovery and metadata cataloging
  - PHI data lineage tracking across EHR integrations
  - Data quality monitoring for FHIR data pipelines

**Alerts & Monitoring:**
- Backup job failure for clinical VM
- SQL audit log retention below 90 days
- Healthcare data pipeline failure
- Cache encryption downgrade attempt
- EHR data export without classification label

---

### Domain 8: Compliance (ADHICS_COMP)

**ADHICS Requirements:**
- Enable vulnerability assessment for SQL Managed Instances
- Enable Microsoft Defender for Cloud to measure compliance posture
- Implement adaptive network hardening for internet-facing healthcare apps
- Audit all resource access patterns for ADHICS compliance reporting
- Maintain custom RBAC audit logs for DoH-Abu Dhabi inspectors

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Azure Machine Learning Computes should have local authentication methods disabled | e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f | Audit, Deny | Yes | Foundation |
| Vulnerability assessment should be enabled on SQL Managed Instance | 1b7aa243-30e4-4c9e-bca8-d0d3022b634a | AuditIfNotExists | Yes | Defender for SQL |
| [Deprecated]: Adaptive network hardening recommendations should be applied on internet-facing VMs | 08e6af2d-db70-460a-bfe9-d5bd474ba9d6 | AuditIfNotExists | Yes | Defender for Servers P2 |
| A vulnerability assessment solution should be enabled on your virtual machines | 501541f7-f7e7-4cd6-868c-4190fdad3ac9 | AuditIfNotExists | Yes | Defender for Servers |
| Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Audit | Yes | Foundation |

**Microsoft Defender Controls:**
- **Regulatory Compliance Dashboard — ADHICS/HIPAA**
  - Real-time ADHICS compliance score
  - Control-level pass/fail breakdown
  - Exportable compliance reports for DoH-Abu Dhabi audits

- **Microsoft Sentinel — ADHICS Workbook**
  - Healthcare-specific KQL queries
  - PHI access anomaly dashboards
  - Breach notification readiness reports

**Alerts & Monitoring:**
- ADHICS compliance score degradation alerts
- Vulnerability assessment not enabled alert
- High-severity finding without assigned owner
- Control failure exceeding remediation SLA
- Unauthorized access to compliance reports

---

### Domain 9: Business Continuity (ADHICS_BC)

**ADHICS Requirements:**
- Maintain VM backup coverage for all clinical systems
- Enable secure Redis cache connections for session state
- Ensure scale set update policies for zero-downtime patching
- Test DR runbooks for EHR systems at least annually

**Azure Policy Controls:**

| Policy Name | Policy ID | Effect | Alert Capable | Defender Plan |
|------------|-----------|---------|---------------|---------------|
| Azure Backup should be enabled for Virtual Machines | 013e242c-8828-4970-87b3-ab247555486d | AuditIfNotExists | Yes | Foundation |
| Only secure connections to your Azure Cache for Redis should be enabled | 22bee202-a82f-4305-9a2a-6d7f44d4dedb | Audit, Deny | Yes | Foundation |
| [Deprecated]: System updates on virtual machine scale sets should be installed | c3f317a7-a95c-4547-b7e7-11017ebdf2fe | AuditIfNotExists | Yes | Defender for Servers |

**Microsoft Defender Controls:**
- **Azure Site Recovery for Healthcare**
  - EHR system failover with validated RPO/RTO
  - Automated failover testing runbooks
  - Multi-region replication for critical patient data

- **Azure Backup with MARS Agent**
  - Clinical workload backup with geo-redundant storage
  - Backup center for centralized backup management
  - Long-term retention (7 years) for healthcare compliance

**Alerts & Monitoring:**
- Clinical system VM backup failure alert
- RPO/RTO threshold breach alert
- Cache SSL disabled alert (patient session at risk)
- DR test overdue alert (annual requirement)
- Business continuity plan last-tested date alert

---

## ADHICS Defender Plan Summary

| Defender Plan | ADHICS Domains Covered | Key Healthcare Use Case |
|--------------|------------------------|------------------------|
| Defender for Cloud Foundation | GOV, IAM, NET, BC | Baseline posture for DoH compliance |
| Defender for Servers P2 | APP, DEV, COMP | Clinical VM protection + FIM |
| Defender for SQL | PHI, IAM, DATA, COMP | Patient database security |
| Defender for Storage | PHI | DICOM and EHR file security |
| Defender for Databases | PHI | MySQL/PostgreSQL PHI encryption |
| Defender for Containers | APP | Containerized EHR security |
| Defender for IoT | DEV | Medical device network protection |
| Defender for APIs | APP | HL7/FHIR API security |
| Microsoft Sentinel | LM (cross-domain) | ADHICS SIEM/SOAR |

---

## Compliance Reporting

**ADHICS Compliance Reporting Requirements:**
- Annual submission to Health Data Services (HDS), Department of Health — Abu Dhabi
- Evidence package: Azure Policy compliance export + Defender for Cloud recommendations report
- PHI breach notification: within 72 hours of detection (aligned with ADHICS and UAE data protection)

**Key Metrics for DoH Auditors:**
- % of PHI datastores encrypted with CMK
- % of clinical VMs with backup coverage
- % of identity accounts with MFA enabled
- Count of open critical/high Defender for Cloud recommendations
- SQL audit log retention compliance rate (target: 100% ≥ 90 days)

---

## References

- [ADHICS Standard Version 2 — Department of Health Abu Dhabi](https://www.doh.gov.ae/)
- [HIPAA to Azure Policy Built-in Mappings](https://learn.microsoft.com/en-us/azure/governance/policy/samples/hipaa-hitrust-9-2)
- [Microsoft Defender for IoT for Healthcare](https://learn.microsoft.com/en-us/azure/defender-for-iot/)
- [Microsoft Azure HIPAA/HITECH Compliance Guide](https://learn.microsoft.com/en-us/azure/compliance/offerings/offering-hipaa-us)
- [UAE Health Records Law — HAAD](https://www.doh.gov.ae)
