# South African Frameworks - Quick Reference Guide

## Overview
This guide provides quick reference information for the three South African regulatory frameworks in the Cloud Compliance Toolkit.

---

## 1. POPIA (Protection of Personal Information Act)

### About POPIA
- **Full Name:** Protection of Personal Information Act, 2013 (Act No. 4 of 2013)
- **Jurisdiction:** South Africa
- **Scope:** Protection of personal information processed by public and private bodies
- **Enforcement:** Information Regulator South Africa
- **Effective Date:** July 1, 2021

### Key Requirements

#### The 8 Conditions for Lawful Processing
1. **Accountability** - Must ensure compliance with all conditions
2. **Processing Limitation** - Process lawfully, reasonably, with consent
3. **Purpose Specification** - Collect for specific, explicit purposes
4. **Further Processing** - Compatible with original purpose
5. **Information Quality** - Ensure accuracy and completeness
6. **Openness** - Notify data subjects about collection
7. **Security Safeguards** - Protect against unauthorized access
8. **Data Subject Participation** - Provide access to personal information

#### Additional Key Controls
- **Consent Management** (POPIA-09) - Obtain valid, informed consent
- **Cross-Border Transfer** (POPIA-10) - Adequate protection for transfers
- **Data Breach** (POPIA-12) - Notify regulator and data subjects
- **Information Officer** (POPIA-14) - Designate responsible person

### Azure Implementation

| POPIA Requirement | Azure Service/Feature |
|-------------------|----------------------|
| Security Safeguards | Azure Encryption, Key Vault, Defender for Cloud |
| Access Controls | Azure AD, RBAC, PIM |
| Audit Logging | Azure Monitor, Log Analytics |
| Data Residency | South Africa regions (Johannesburg, Cape Town) |
| Encryption | Customer-managed keys, TDE, disk encryption |
| Consent Management | Custom applications, Azure AD Terms of Use |
| Breach Detection | Defender for Cloud, Sentinel |

### Compliance Checklist
- [ ] Designate Information Officer
- [ ] Document processing purposes
- [ ] Implement consent mechanisms
- [ ] Enable encryption at rest and in transit
- [ ] Configure audit logging
- [ ] Establish data retention policies
- [ ] Create breach notification procedures
- [ ] Conduct privacy impact assessments
- [ ] Deploy resources in SA regions
- [ ] Implement data subject access procedures

---

## 2. eGovernment Framework

### About eGovernment
- **Full Name:** South African eGovernment Framework
- **Jurisdiction:** South Africa
- **Scope:** Digital transformation of government services
- **Authority:** Department of Public Service and Administration (DPSA)
- **Focus:** Service delivery, interoperability, digital identity

### Key Domains

#### Strategic Pillars
1. **Digital Strategy** - National digital transformation
2. **Service Delivery** - Online government services
3. **Interoperability** - System integration standards
4. **Cloud First** - Cloud adoption strategy
5. **Digital Identity** - National identity infrastructure

#### Operational Areas
6. **Cybersecurity** - Government IT security
7. **Data Protection** - Citizen data protection
8. **Open Standards** - Avoid vendor lock-in
9. **Transparency** - Digital operations transparency
10. **Infrastructure** - Reliable IT infrastructure

#### Enablers
11. **Data Sharing** - Inter-agency data sharing
12. **Citizen Access** - Accessible digital services
13. **Innovation** - Service delivery innovation
14. **Capacity Building** - Digital skills development
15. **Mobile Services** - Mobile-first approach

### Azure Implementation

| eGov Requirement | Azure Service/Feature |
|------------------|----------------------|
| Cloud-First | Azure Government, Azure regions SA |
| Digital Identity | Azure AD, B2C, Verified ID |
| Interoperability | API Management, Logic Apps, Service Bus |
| Data Sharing | Private Link, Data Share, Synapse |
| Cybersecurity | Defender for Cloud, Sentinel, Firewall |
| Mobile Services | App Service, API Management, CDN |
| Infrastructure | Virtual Networks, ExpressRoute, Bastion |
| Innovation | AI Services, IoT Hub, Digital Twins |

### Implementation Priorities
1. **High Priority**
   - EGOV-07: Cloud-First Policy
   - EGOV-06: Digital Identity Services
   - EGOV-09: Government Cybersecurity
   - EGOV-10: Citizen Data Protection

2. **Medium Priority**
   - EGOV-02: Online Service Delivery
   - EGOV-03: Interoperability Standards
   - EGOV-04: Government Data Sharing
   - EGOV-14: Government IT Infrastructure

3. **Long-Term**
   - EGOV-01: National Digital Strategy
   - EGOV-12: Digital Innovation
   - EGOV-13: Digital Skills Development

---

## 3. IGR Framework (Intergovernmental Relations)

### About IGR
- **Full Name:** Intergovernmental Relations Framework Act, 2005 (Act No. 13 of 2005)
- **Jurisdiction:** South Africa
- **Scope:** Coordination between national, provincial, and local government
- **Purpose:** Facilitate cooperation and prevent disputes
- **Government Spheres:** National, Provincial (9), Local (257+ municipalities)

### Key Principles

#### Coordination Mechanisms (IGR-01)
- Establish formal coordination structures
- Regular intergovernmental forums
- Shared decision-making processes

#### Information Sharing (IGR-02)
- Share information across government spheres
- Common data standards
- Secure information exchange

#### Dispute Resolution (IGR-03)
- Formal dispute resolution mechanisms
- Mediation and negotiation procedures
- Escalation protocols

### Azure Implementation

| IGR Requirement | Azure Service/Feature |
|-----------------|----------------------|
| Information Sharing | Private Link, VPN Gateway, ExpressRoute |
| Coordination Platforms | SharePoint, Teams, Power Platform |
| Data Standards | API Management, Data Factory, Synapse |
| Secure Communication | Network Security Groups, Firewall, Private DNS |
| Performance Monitoring | Azure Monitor, Log Analytics, Dashboards |
| Resource Coordination | Azure Policy, Management Groups, Blueprints |
| Collaboration Tools | Microsoft 365, Teams, SharePoint |

### Implementation Architecture

```
National Government (Sphere 1)
    ├── Azure Management Groups
    ├── Central Monitoring
    └── Shared Services
         ├── Identity (Azure AD)
         ├── Security (Defender, Sentinel)
         └── Networking (Hub VNet)

Provincial Government (Sphere 2) - 9 Provinces
    ├── Provincial Subscriptions
    ├── Spoke VNets
    └── Provincial Services
         ├── Regional Data Sharing
         └── Provincial Applications

Local Government (Sphere 3) - 257+ Municipalities
    ├── Municipal Subscriptions
    ├── Local Spoke VNets
    └── Municipal Services
         ├── Service Delivery Apps
         └── Citizen Portals
```

### Key Capabilities

1. **Central Coordination** (IGR-01, IGR-10)
   - Azure Management Groups for governance hierarchy
   - Centralized policy enforcement
   - Shared service model

2. **Data Sharing** (IGR-02, IGR-04)
   - Private endpoints between spheres
   - API-based integration
   - Secure data exchange patterns

3. **Monitoring** (IGR-08)
   - Unified monitoring across spheres
   - Performance dashboards
   - Compliance reporting

4. **Resource Management** (IGR-06)
   - Resource tagging by sphere
   - Cost allocation and tracking
   - Capacity planning

---

## Cross-Framework Integration

### How the Three Frameworks Work Together

```
┌─────────────────────────────────────────────────────┐
│         South African Government Cloud              │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │  POPIA (Data Protection Layer)              │  │
│  │  - Personal information protection          │  │
│  │  - Privacy by design                        │  │
│  │  - Consent management                       │  │
│  └─────────────────────────────────────────────┘  │
│                       ▲                             │
│                       │                             │
│  ┌─────────────────────────────────────────────┐  │
│  │  eGovernment (Service Delivery Layer)       │  │
│  │  - Digital services                         │  │
│  │  - Interoperability                         │  │
│  │  - Cloud-first                              │  │
│  └─────────────────────────────────────────────┘  │
│                       ▲                             │
│                       │                             │
│  ┌─────────────────────────────────────────────┐  │
│  │  IGR (Coordination Layer)                   │  │
│  │  - Inter-sphere coordination                │  │
│  │  - Information sharing                      │  │
│  │  - Resource allocation                      │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### Integrated Compliance Approach

1. **IGR Framework** - Establishes governance structure
2. **eGovernment Framework** - Defines service delivery model
3. **POPIA** - Protects citizen personal information

### Example: Citizen Portal Implementation

| Layer | Framework | Requirements |
|-------|-----------|-------------|
| **Data Protection** | POPIA | Consent, encryption, privacy notice, data subject rights |
| **Service Delivery** | eGov | Digital identity, cloud-first, mobile services, interoperability |
| **Coordination** | IGR | Information sharing between spheres, joint planning, monitoring |

### Combined Controls

| Use Case | POPIA | eGov | IGR | Azure Services |
|----------|-------|------|-----|----------------|
| **Citizen Authentication** | POPIA-09 | EGOV-06 | - | Azure AD B2C, Verified ID |
| **Data Sharing** | POPIA-10 | EGOV-04 | IGR-02 | Private Link, API Management |
| **Security** | POPIA-07 | EGOV-09 | - | Defender for Cloud, Key Vault |
| **Monitoring** | POPIA-13 | - | IGR-08 | Azure Monitor, Log Analytics |
| **Cloud Services** | POPIA-07 | EGOV-07 | IGR-06 | Azure South Africa regions |

---

## Azure Region Considerations

### South Africa Regions
- **Johannesburg** (Primary) - South Africa North
- **Cape Town** (Secondary) - South Africa West

### Data Residency
- POPIA requires data to remain in SA (or adequate protection for transfers)
- eGovernment framework encourages local cloud services
- IGR coordination benefits from centralized SA hosting

### Region Architecture
```
South Africa North (Johannesburg)
├── Primary services
├── National government workloads
└── Hub for connectivity

South Africa West (Cape Town)
├── DR/backup services
├── Regional government workloads
└── Geographic redundancy
```

---

## Common Implementation Patterns

### Pattern 1: Multi-Sphere Government Portal
**Frameworks:** All three
**Components:**
- Azure AD for identity (EGOV-06, POPIA-07)
- App Service for portal (EGOV-02, EGOV-15)
- Private Link for data sharing (IGR-02, POPIA-10)
- Key Vault for secrets (POPIA-07, EGOV-09)
- Log Analytics for monitoring (POPIA-13, IGR-08)

### Pattern 2: Inter-Agency Data Sharing
**Frameworks:** IGR + POPIA
**Components:**
- Private endpoints (IGR-02)
- API Management (EGOV-03)
- Data Factory (IGR-04)
- Consent management (POPIA-09)
- Audit logging (POPIA-13, IGR-08)

### Pattern 3: Citizen Self-Service
**Frameworks:** eGov + POPIA
**Components:**
- Azure AD B2C (EGOV-06, POPIA-09)
- Static Web Apps (EGOV-15)
- Functions for APIs (EGOV-02)
- Cosmos DB with encryption (POPIA-07)
- Privacy controls (POPIA-08)

---

## Quick Start Guide

### Step 1: Assess Current State
1. Review POPIA compliance status
2. Evaluate eGovernment maturity
3. Map IGR coordination needs

### Step 2: Design Architecture
1. Define governance hierarchy (IGR)
2. Plan service delivery model (eGov)
3. Implement privacy controls (POPIA)

### Step 3: Deploy Foundation
1. Set up Azure landing zones
2. Configure Azure AD tenants
3. Establish network connectivity
4. Enable monitoring and logging

### Step 4: Implement Controls
1. Deploy Azure Policies
2. Configure Defender for Cloud
3. Set up compliance dashboards
4. Establish evidence collection

### Step 5: Operationalize
1. Train staff on frameworks
2. Document procedures
3. Conduct regular assessments
4. Maintain compliance evidence

---

## Support Resources

### Official Documentation
- **POPIA:** [justice.gov.za/inforeg](https://www.justice.gov.za/inforeg/)
- **eGovernment:** DPSA official website
- **IGR:** [cogta.gov.za](https://www.cogta.gov.za/)

### Azure Resources
- Azure South Africa regions documentation
- Azure Government cloud guidance
- Microsoft Compliance Manager

### Toolkit Resources
- `/catalogues/` - Full Azure mappings
- `/templates/` - Control templates
- `/reference_documents/` - Source PDFs

---

**Version:** 1.0
**Last Updated:** December 4, 2025
**Author:** Warren du Toit, Cloud Solution Architect @ Microsoft
