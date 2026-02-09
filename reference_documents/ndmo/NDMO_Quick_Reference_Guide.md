# NDMO to Azure Quick Reference Guide

## Key Policy Mappings at a Glance

### Domain 13: Data Classification

| NDMO Requirement | Azure Control | Implementation | Alerts |
|------------------|---------------|----------------|--------|
| Classify all data assets | Microsoft Purview Data Classification | Auto-scanning + manual classification | Classification change alerts |
| Maintain classification register | Purview Data Catalog | Centralized catalog with metadata | Asset registration alerts |
| Sensitivity labeling | Microsoft Information Protection | Sensitivity labels (Public, Internal, Confidential, Highly Confidential) | Label change notifications |
| Impact assessment | Purview Classification Dashboard | Classification impact scoring | High-impact classification alerts |

### Domain 14: Data Privacy

| NDMO Requirement | Azure Control | Implementation | Alerts |
|------------------|---------------|----------------|--------|
| Protect personal data | Purview Information Protection + DLP | Automated DLP policies | Policy violation alerts |
| Data subject rights | Purview Privacy Risk Management | DSR automation workflows | DSR request notifications |
| Consent management | Purview Consent Manager | Consent tracking system | Consent withdrawal alerts |
| Privacy breach notification | Defender for Cloud + Sentinel | Automated incident detection | Breach detection alerts |

### Domain 15: Data Protection (Security)

#### Encryption

| NDMO Requirement | Azure Policy | ID | Alert |
|------------------|--------------|-----|-------|
| Encryption at rest - SQL | Transparent Data Encryption on SQL databases should be enabled | 17k78e20-9358-41c9-923c-fb736d382a12 | Yes |
| Encryption at rest - VMs | Virtual machines should encrypt temp disks, caches, and data flows | fc4d8e41-e223-45ea-9bf5-eada37891d87 | Yes |
| Encryption at rest - Storage | Storage accounts should use customer-managed key | 6fac406b-40ca-413b-bf8e-0bf964659c25 | Yes |
| Encryption in transit | Secure transfer to storage accounts should be enabled | 404c3081-a854-4457-ae30-26a93ef643f9 | Yes |
| TLS 1.2+ enforcement | Windows machines should use secure communication protocols | 5752e6d6-1206-46d8-8ab1-ecc2f71a8112 | Yes |

#### Access Control

| NDMO Requirement | Azure Policy | ID | Alert |
|------------------|--------------|-----|-------|
| RBAC enforcement | Audit usage of custom RBAC roles | a451c1ef-c6ca-483d-87ed-f49761e3ffb5 | Yes |
| MFA for admins | MFA should be enabled on accounts with owner permissions | aa633080-8b72-40c4-a2d7-d00c03e80bed | Yes |
| Entra ID integration | Microsoft Entra administrator should be provisioned for SQL servers | 1f314764-cb73-4fc9-b863-8eca98ac36e2 | Yes |
| Privileged access | N/A - Use PIM | N/A | Yes via PIM alerts |

#### Logging & Monitoring

| NDMO Requirement | Azure Policy | ID | Alert |
|------------------|--------------|-----|-------|
| Activity log retention | Activity log should be retained for at least one year | b02aacc0-b073-424e-8298-42b22829ee0a | Yes |
| SQL audit logging | Auditing on SQL server should be enabled | a6fb4358-5bf4-4ad7-ba82-2cd2f41ce5e9 | Yes |
| SQL audit retention | SQL servers with auditing should have 90 days retention or higher | 89099bee-89e0-4b26-a5f4-165451757743 | Yes |
| Resource logging | App Service apps should have resource logs enabled | 91a78b24-f231-4a8a-8da9-02c35b2b6510 | Yes |

#### Backup & Recovery

| NDMO Requirement | Azure Policy | ID | Alert |
|------------------|--------------|-----|-------|
| VM backup | Azure Backup should be enabled for Virtual Machines | 013e242c-8828-4970-87b3-ab247555486d | Yes |
| Geo-redundant backup | Geo-redundant backup should be enabled for databases | Multiple | Yes |
| Retention enforcement | Adhere to retention periods defined | 1ecb79d7-1a06-9a3b-3be8-f434d04d1ec1 | Yes |

## Microsoft Defender Plans Required

| Plan | Purpose | NDMO Domains Covered | Monthly Cost (Approx) |
|------|---------|---------------------|---------------------|
| Defender for Servers P2 | VM security, vulnerability mgmt, JIT access | 1, 13, 14, 15 | $15/server |
| Defender for Storage | Malware scanning, threat detection | 13, 14, 15 | $10/account + scanning |
| Defender for SQL | SQL security, vulnerability assessment | 13, 14, 15 | $15/server |
| Defender for Containers | Container security, K8s security | 15 | $7/vCore |
| Defender for Key Vault | Secrets and key protection | 15 | $0.02/10K txns |
| Defender for APIs | API security monitoring | 8, 15 | $0.03/10K calls |
| Defender for Resource Manager | Control plane security | 1, 15 | $5/million calls |
| Defender for DNS | DNS threat detection | 15 | $2/million queries |
| Defender CSPM | Compliance and posture mgmt | All | Included with plans |

## Alert Priority Matrix

### Priority 1: Critical - Immediate Response (<15 minutes)

| Alert | Source | NDMO Domain |
|-------|--------|-------------|
| Ransomware detected | Defender for Servers | 15 |
| Data exfiltration | Defender for Storage/SQL | 14, 15 |
| Malware upload | Defender for Storage | 15 |
| Public exposure of classified data | Defender for Storage/SQL | 13, 14, 15 |

### Priority 2: High - Response Within 1 Hour

| Alert | Source | NDMO Domain |
|-------|--------|-------------|
| SQL injection attempt | Defender for SQL | 15 |
| Privilege escalation | Defender for Cloud | 15 |
| Unauthorized Key Vault access | Defender for Key Vault | 15 |
| MFA disabled for admin | Entra ID Protection | 15 |
| Encryption disabled | Azure Policy | 15 |

### Priority 3: Medium - Response Within 4 Hours

| Alert | Source | NDMO Domain |
|-------|--------|-------------|
| Policy violation | Azure Policy | All |
| Backup failure | Azure Backup | 4 |
| Classification violation | Purview | 13 |
| Suspicious sign-in | Entra ID Protection | 15 |
| Certificate expiration warning | Key Vault | 15 |

## Quick Start Commands

### Enable Defender Plans (Azure CLI)

```bash
# Enable Defender for Servers P2
az security pricing create --name VirtualMachines --tier Standard --subplan P2

# Enable Defender for Storage
az security pricing create --name StorageAccounts --tier Standard

# Enable Defender for SQL
az security pricing create --name SqlServers --tier Standard
az security pricing create --name SqlServerVirtualMachines --tier Standard

# Enable Defender for Containers
az security pricing create --name Containers --tier Standard

# Enable Defender for Key Vault
az security pricing create --name KeyVaults --tier Standard

# Enable Defender for Resource Manager
az security pricing create --name Arm --tier Standard

# Enable Defender for DNS
az security pricing create --name Dns --tier Standard
```

### Assign Azure Policy Initiative

```bash
# Assign Microsoft Cloud Security Benchmark
az policy assignment create \
  --name 'MCSB-Assignment' \
  --display-name 'Microsoft Cloud Security Benchmark' \
  --scope '/subscriptions/<subscription-id>' \
  --policy-set-definition '/providers/Microsoft.Authorization/policySetDefinitions/1f3afdf9-d0c9-4c3d-847f-89da613e70a8'
```

### Create Action Group

```bash
# Create action group for security alerts
az monitor action-group create \
  --name 'SecurityTeam' \
  --resource-group 'rg-security' \
  --short-name 'SecTeam' \
  --email-receiver 'Security Team' security@company.com \
  --sms-receiver 'On-Call' 1 5551234567
```

### Enable Diagnostic Settings

```bash
# Enable diagnostics for subscription
az monitor diagnostic-settings subscription create \
  --name 'subscription-logs' \
  --location 'eastus' \
  --workspace '/subscriptions/<sub-id>/resourceGroups/rg-monitoring/providers/Microsoft.OperationalInsights/workspaces/law-central' \
  --logs '[{"category":"Administrative","enabled":true},{"category":"Security","enabled":true},{"category":"Policy","enabled":true}]'
```

## Key Stakeholders & Responsibilities

| Role | Responsibilities | NDMO Domains |
|------|-----------------|--------------|
| Chief Data Officer | Overall NDMO compliance, data governance | 1-15 |
| CISO | Security controls, incident response | 15 |
| Compliance Officer | Compliance monitoring, audit management | 1-15 |
| Data Stewards | Data classification, quality management | 2, 3, 13 |
| Security Operations | Alert monitoring, incident response | 15 |
| Database Admins | Database security, SQL auditing | 15 |
| Backup Team | Backup operations, DR testing | 4 |

## NDMO Compliance Score Calculation

**Total Controls:** 77
**Total Specifications:** 191

**Score Formula:**
```
Compliance Score = (Implemented Specifications / Total Specifications) × 100
Target Score: >95% (>181 specifications)
```

**By Domain:**
Each domain must achieve >95% compliance for overall compliance.

## Common Issues & Solutions

| Issue | Solution | Verification |
|-------|----------|--------------|
| Policy showing non-compliant | Review exemptions, remediate resources | Azure Policy compliance dashboard |
| Alerts not received | Check action group configuration | Test action group |
| Classification not auto-applying | Review classification rules, permissions | Purview classification dashboard |
| Backup failures | Check VM agent, network connectivity | Backup center |
| High false positive rate | Tune alert thresholds, create exceptions | Alert analytics |
| Encryption not enabled | Apply DeployIfNotExists policy | Policy compliance report |

## Important URLs

- **Azure Portal:** https://portal.azure.com
- **Microsoft Purview:** https://purview.microsoft.com
- **Defender for Cloud:** https://portal.azure.com/#view/Microsoft_Azure_Security/SecurityMenuBlade
- **Azure Policy:** https://portal.azure.com/#view/Microsoft_Azure_Policy/PolicyMenuBlade
- **NDMO Official Site:** https://sdaia.gov.sa/ndmo/
- **Microsoft Learn:** https://learn.microsoft.com

## Support Contacts

**Microsoft Support:**
- Professional Direct: 24/7 support
- Phone: Check your Azure portal for regional numbers
- Portal: Create support ticket in Azure portal

**Internal Contacts:**
- Security Team: security@company.com
- Compliance Team: compliance@company.com
- IT Support: itsupport@company.com
- Emergency Hotline: [Your emergency number]

## Next Steps

1. Review detailed mapping document: `NDMO_Azure_Controls_Mapping.md`
2. Review implementation checklist: `NDMO_Implementation_Checklist.md`
3. Schedule kickoff meeting with implementation team
4. Obtain necessary licenses and approvals
5. Begin Phase 1 implementation
6. Schedule weekly status reviews
7. Set target completion date
8. Plan for NDMO audit

---

**Document Version:** 1.0  
**Last Updated:** October 29, 2025  
**For:** NDMO Compliance Implementation  
**Classification:** Internal Use Only
