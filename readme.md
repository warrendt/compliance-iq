# 🛡️ Cloud Compliance Toolkit (CCToolkit)

<div align="center">

**Sovereign Landing Zone Policy Pack for Azure & Defender CSPM**

*Accelerate compliance across Government, Healthcare, and Financial sectors*

[![Azure](https://img.shields.io/badge/Azure-0078D4?style=flat&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![Compliance](https://img.shields.io/badge/Compliance-ISO%2027001%20%7C%20NIST%20800--53-green)](https://www.iso.org/isoiec-27001-information-security.html)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

</div>

---

## 🌟 Overview

The **Cloud Compliance Toolkit** is a comprehensive framework for implementing security and compliance controls in Azure sovereign cloud environments. Designed for regulated industries, this toolkit provides pre-mapped control catalogs aligned with multiple international standards and Azure-native security services.

### ✨ Key Features

- 🎯 **Multi-Framework Support** - SAMA, ADHICS, CCC, and SITA frameworks included
- 🔗 **Azure-Native Mappings** - Pre-mapped Azure Policy definitions and Defender for Cloud controls
- 📊 **143+ Security Controls** - Comprehensive coverage across 4 major compliance frameworks
- 🚀 **Deployment Ready** - Control catalogs ready for Infrastructure as Code (IaC) implementation
- 📈 **Continuous Compliance** - Integration with Microsoft Defender CSPM for ongoing monitoring

---

## 🎯 What's Inside

### 📦 Control Catalogs (Comprehensive 10-Column Mappings)

Located in [`catalogues/`](catalogues/):

| Framework | Controls | Focus Area | File |
|-----------|----------|------------|------|
| **SAMA** | 36 | Financial Sector | [`SAMA_Catalog_Azure_Mappings.csv`](catalogues/SAMA_Catalog_Azure_Mappings.csv) |
| **CCC** | 32 | Cloud Computing | [`CCC_Framework_Azure_Mappings.csv`](catalogues/CCC_Framework_Azure_Mappings.csv) |
| **ADHICS** | 36 | Healthcare | [`ADHICS_Framework_Azure_Mappings.csv`](catalogues/ADHICS_Framework_Azure_Mappings.csv) |
| **SITA** | 38 | Government/Sovereign | [`SITA_Architecture_Azure_Mappings.csv`](catalogues/SITA_Architecture_Azure_Mappings.csv) |

Each catalog includes:
- ✅ Control ID, domain, and detailed requirements
- ✅ Azure Policy names and definition IDs (GUIDs)
- ✅ Microsoft Defender for Cloud control mappings
- ✅ Evidence examples and implementation guidance

📖 **[View Catalog Summary](catalogues/CATALOG_SUMMARY.md)** for detailed mapping information.

### 📋 Control Templates (Simplified 4-Column Format)

Located in [`reference_documents/`](reference_documents/):

Perfect for gap analysis, documentation, and stakeholder presentations:

- [`SAMA_Controls_Template.csv`](reference_documents/SAMA_Controls_Template.csv) - 37 controls
- [`CCC_Controls_Template.csv`](reference_documents/CCC_Controls_Template.csv) - 32 controls
- [`ADHICS_Controls_Template.csv`](reference_documents/ADHICS_Controls_Template.csv) - 36 controls
- [`SITA_Controls_Template.csv`](reference_documents/SITA_Controls_Template.csv) - 38 controls

📖 **[View Template Guide](reference_documents/CONTROL_TEMPLATES_README.md)** for usage instructions.

### 📚 Documentation

- 📘 **[Process Documentation](PROCESS_DOCUMENTATION.md)** - Step-by-step replication guide
- 📊 **[Catalog Summary](catalogues/CATALOG_SUMMARY.md)** - Comprehensive catalog documentation
- 📝 **[Control Templates Guide](reference_documents/CONTROL_TEMPLATES_README.md)** - Template usage and workflows

---

## 🚀 Quick Start

### For Security Architects

```bash
# 1. Clone the repository
git clone https://github.com/warrendt/cctoolkit_v1.git
cd cctoolkit_v1

# 2. Review the catalog for your industry
cat catalogues/SAMA_Catalog_Azure_Mappings.csv  # Financial sector
cat catalogues/ADHICS_Framework_Azure_Mappings.csv  # Healthcare
cat catalogues/SITA_Architecture_Azure_Mappings.csv  # Government

# 3. Extract Azure Policy IDs for deployment
grep -o '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
  catalogues/SAMA_Catalog_Azure_Mappings.csv | sort -u
```

### For Compliance Teams

1. **Gap Analysis** - Use control templates in `reference_documents/`
2. **Evidence Mapping** - Reference "Evidence_Examples" column in catalogs
3. **Audit Preparation** - Map existing controls to framework requirements

### For DevOps/IaC Teams

1. **Extract Policy IDs** from catalog files
2. **Create Policy Assignments** using Azure CLI, PowerShell, or Bicep
3. **Implement Defender for Cloud** recommendations from mappings

---

## 🏗️ Architecture

### Framework Coverage

```
┌─────────────────────────────────────────────────────────────┐
│                  Cloud Compliance Toolkit                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────┐│
│  │   SAMA     │  │    CCC     │  │  ADHICS    │  │ SITA  ││
│  │ Financial  │  │   Cloud    │  │ Healthcare │  │  Gov  ││
│  │ 36 ctrl    │  │  32 ctrl   │  │  36 ctrl   │  │38 ctrl││
│  └────────────┘  └────────────┘  └────────────┘  └───────┘│
│         │              │                │            │      │
│         └──────────────┴────────────────┴────────────┘      │
│                          │                                  │
│              ┌───────────▼──────────┐                       │
│              │  Azure Policy Engine │                       │
│              └───────────┬──────────┘                       │
│                          │                                  │
│         ┌────────────────┴────────────────┐                │
│         │                                  │                │
│  ┌──────▼─────────┐            ┌──────────▼──────┐        │
│  │ Azure Policies │            │ Defender CSPM   │        │
│  │ 50+ Built-in   │            │ Security Score  │        │
│  └────────────────┘            └─────────────────┘        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Control Domains Covered

- 🔐 **Identity & Access Management** - MFA, RBAC, Conditional Access
- 🌐 **Network Security** - NSGs, Private Link, Firewalls
- 🔒 **Data Protection** - Encryption at rest/transit, CMK, DLP
- 📊 **Logging & Monitoring** - Diagnostic settings, SIEM integration
- 🛡️ **Threat Protection** - Defender for Cloud, vulnerability management
- 📋 **Governance & Compliance** - Azure Policy, regulatory controls
- 🏥 **Healthcare-Specific** - PHI protection, HIPAA, medical devices
- 🏦 **Financial-Specific** - Transaction security, fraud detection
- 🏛️ **Government-Specific** - Data sovereignty, classified data

---

## 📖 Compliance Frameworks

### 🏦 SAMA - Saudi Arabian Monetary Authority

**Target:** Financial institutions, banks, fintech
**Controls:** 36 across 13 domains
**Key Focus:** Cybersecurity governance, AI risk management, Copilot security

**Domains Include:**
- Cybersecurity Governance
- Risk Management & Compliance
- Third-Party Security
- Business Continuity & Disaster Recovery
- Identity & Access Control
- AI Governance & Productivity AI (Copilot)

[→ View SAMA Catalog](catalogues/SAMA_Catalog_Azure_Mappings.csv)

### ☁️ CCC - Cloud Computing Controls

**Target:** Multi-cloud environments, cloud service providers
**Controls:** 32 across 8 domains
**Key Focus:** IaaS/PaaS security, container security, cloud-native controls

**Domains Include:**
- Infrastructure Security (IaaS)
- Platform Security (PaaS)
- Data Security
- Security Operations
- Disaster Recovery

[→ View CCC Catalog](catalogues/CCC_Framework_Azure_Mappings.csv)

### 🏥 ADHICS - Abu Dhabi Health Information & Cyber Security

**Target:** Healthcare providers, hospitals, health information systems
**Controls:** 36 across 9 domains
**Key Focus:** PHI protection, EHR security, medical device management

**Domains Include:**
- Protected Health Information (PHI)
- Clinical Systems Security
- Medical Device & IoT Security
- Healthcare Compliance (HIPAA alignment)
- Patient Privacy Rights

[→ View ADHICS Catalog](catalogues/ADHICS_Framework_Azure_Mappings.csv)

### 🏛️ SITA - Microsoft-SITA Reference Architecture

**Target:** Government agencies, sovereign cloud deployments
**Controls:** 38 including 14 Sovereign Principles (SPO)
**Key Focus:** Data sovereignty, government compliance, classified data

**Domains Include:**
- Sovereign Cloud Architecture (SPO-01 to SPO-14)
- Data Residency & Sovereignty
- Government Identity Federation
- National Compliance (POPIA)
- Security Clearances

[→ View SITA Catalog](catalogues/SITA_Architecture_Azure_Mappings.csv)

---

## 🛠️ Implementation Guide

### Step 1: Select Your Framework

Choose the framework(s) applicable to your organization:

```bash
# Financial Sector → SAMA
# Healthcare → ADHICS
# Government → SITA
# Multi-cloud → CCC
```

### Step 2: Review Control Mappings

Open the comprehensive mapping catalog:

```bash
# Example: Financial sector
code catalogues/SAMA_Catalog_Azure_Mappings.csv
```

Examine the 10-column structure:
1. Control ID
2. Domain
3. Control Name
4. Requirement Summary
5. Control Type
6. Evidence Examples
7. Azure Policy Name
8. Azure Policy ID (GUID)
9. Defender Control Category
10. Defender Recommendation

### Step 3: Deploy Azure Policies

Extract policy IDs and deploy using your preferred method:

**Using Azure CLI:**
```bash
# Assign MFA policy (example from SAMA-AC-01)
az policy assignment create \
  --name "Require-MFA-for-Resources" \
  --policy "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b" \
  --scope "/subscriptions/{subscription-id}"
```

**Using Bicep:**
```bicep
resource mfaPolicy 'Microsoft.Authorization/policyAssignments@2022-06-01' = {
  name: 'require-mfa-policy'
  properties: {
    policyDefinitionId: '/providers/Microsoft.Authorization/policyDefinitions/4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b'
    displayName: 'Require MFA for resource operations'
  }
}
```

**Using PowerShell:**
```powershell
# Assign private endpoint policy (example from SAMA-NS-02)
New-AzPolicyAssignment `
  -Name "Require-Private-Endpoints" `
  -PolicyDefinition (Get-AzPolicyDefinition -Id "ca610c1d-041c-4332-9d88-7ed3094967c7") `
  -Scope "/subscriptions/{subscription-id}"
```

### Step 4: Enable Defender for Cloud

Configure Microsoft Defender for Cloud:

```bash
# Enable Defender plans
az security pricing create \
  --name VirtualMachines \
  --tier Standard

az security pricing create \
  --name SqlServers \
  --tier Standard

az security pricing create \
  --name AppServices \
  --tier Standard
```

### Step 5: Monitor Compliance

- 📊 Review **Secure Score** in Defender for Cloud
- ✅ Track **Policy Compliance** in Azure Policy
- 🔍 Validate **Control Evidence** using audit logs
- 📈 Generate **Compliance Reports** for auditors

---

## 🎓 Use Cases

### 🏦 Financial Institution (SAMA Compliance)

**Scenario:** Saudi Arabian bank implementing cybersecurity framework

**Solution:**
1. Deploy SAMA control catalog
2. Implement Azure Policies for governance
3. Enable Defender for Cloud for CSPM
4. Configure AI governance controls for Copilot usage
5. Establish continuous compliance monitoring

**Result:** Full SAMA compliance with automated policy enforcement

### 🏥 Healthcare Provider (ADHICS Compliance)

**Scenario:** Abu Dhabi hospital protecting PHI

**Solution:**
1. Deploy ADHICS healthcare controls
2. Implement PHI encryption policies
3. Segment clinical networks
4. Secure medical device connectivity
5. Enable HIPAA-aligned monitoring

**Result:** ADHICS-compliant healthcare cloud with PHI protection

### 🏛️ Government Agency (SITA Compliance)

**Scenario:** South African government sovereign cloud

**Solution:**
1. Deploy SITA sovereign principles
2. Enforce data residency in South Africa
3. Implement classified data controls
4. Configure government identity federation
5. Ensure POPIA compliance

**Result:** Fully sovereign government cloud with data sovereignty

---

## 📊 Statistics

| Metric | Count |
|--------|-------|
| **Total Controls** | 143 |
| **Azure Policies Mapped** | 50+ |
| **Defender Controls** | 8 categories |
| **Frameworks Covered** | 4 |
| **Industry Sectors** | 3 (Finance, Healthcare, Government) |
| **Control Domains** | 35+ |

---

## 🔄 Maintenance & Updates

### Keeping Current

The toolkit is designed for easy maintenance as regulations and Azure services evolve:

1. **Quarterly Reviews** - Check for new Azure Policy definitions
2. **Framework Updates** - Monitor regulatory changes (SAMA, ADHICS updates)
3. **Azure Updates** - Track new Defender for Cloud recommendations
4. **Version Control** - Use Git to track all changes

### Contributing Updates

1. Fork the repository
2. Update relevant catalog files
3. Document changes in CHANGELOG.md
4. Submit pull request with detailed description

---

## 📚 Additional Resources

### Official Documentation

- 🔗 [Microsoft Sovereign Cloud](https://learn.microsoft.com/industry/sovereign-cloud/)
- 🔗 [Azure Policy Built-in Definitions](https://learn.microsoft.com/azure/governance/policy/samples/built-in-policies)
- 🔗 [Microsoft Defender for Cloud](https://learn.microsoft.com/azure/defender-for-cloud/)
- 🔗 [Azure Security Benchmark](https://learn.microsoft.com/security/benchmark/azure/)

### Framework References

- 📄 [SAMA Cybersecurity Framework](reference_documents/SAMA_EN_3837_VER1.pdf)
- 📄 [ADHICS Standard v2](reference_documents/ADHICS-v2-standard%20(3).pdf)
- 📄 [CCC Framework](reference_documents/ccc-en.pdf)
- 📄 [Microsoft-SITA Reference Architecture](reference_documents/Microsoft_SITA%20Reference%20Architecture%20Document.pdf)

### Internal Documentation

- 📘 [Process Documentation](PROCESS_DOCUMENTATION.md) - Complete replication guide
- 📊 [Catalog Summary](catalogues/CATALOG_SUMMARY.md) - Detailed mappings
- 📝 [Template Guide](reference_documents/CONTROL_TEMPLATES_README.md) - Usage workflows

---

## 🤝 Support & Community

### Getting Help

- 📧 **Questions?** Open an issue in GitHub
- 💬 **Discussions?** Start a discussion thread
- 🐛 **Found a bug?** Submit a bug report
- 💡 **Feature ideas?** Share your suggestions

### Acknowledgments

Special thanks to:
- Microsoft Sovereign Cloud team
- SAMA for comprehensive cybersecurity framework
- Abu Dhabi Department of Health for ADHICS standard
- SITA (State Information Technology Agency) South Africa

---

## 👨‍💼 Author

**Warren du Toit**  
Cloud Solution Architect @ Microsoft

*Specializing in sovereign cloud architectures, compliance frameworks, and secure Azure deployments for regulated industries.*

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🌟 Star This Repository

If you find this toolkit useful, please consider giving it a star ⭐ to help others discover it!

---

<div align="center">

**Built with ❤️ for Secure & Compliant Cloud Deployments**

[Report Bug](https://github.com/warrendt/cctoolkit_v1/issues) · [Request Feature](https://github.com/warrendt/cctoolkit_v1/issues) · [Documentation](PROCESS_DOCUMENTATION.md)

</div>
