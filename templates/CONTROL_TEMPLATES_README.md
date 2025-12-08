# Control Template CSV Files - Summary

## Overview
Created four standardized control template CSV files following the format of `standard_control_template.csv`. Each file contains the simplified 4-column structure suitable for control documentation and mapping.

## Files Created

### 1. SAMA_Controls_Template.csv
**Location:** `/reference_documents/SAMA_Controls_Template.csv`
**Framework:** Saudi Arabian Monetary Authority (SAMA) Cybersecurity Framework
**Total Controls:** 37 controls
**Format:**
- Control ID (e.g., SAMA-GOV-01)
- Control Domain (e.g., Cybersecurity Governance)
- Control Title (e.g., Establish cybersecurity policy)
- Control Description (detailed requirement)

**Control Domains:**
- Cybersecurity Governance (3 controls)
- Risk Management & Compliance (3 controls)
- Third-Party Security (1 control)
- Business Continuity & DR (2 controls)
- Incident Response (2 controls)
- Identity & Access Control (4 controls)
- Network Security (4 controls)
- Data Protection & Privacy (4 controls)
- Logging & Monitoring (3 controls)
- Vulnerability Management (1 control)
- Secure Development & Change (2 controls)
- AI Governance (4 controls)
- Productivity AI (Copilot) (4 controls)

### 2. CCC_Controls_Template.csv
**Location:** `/reference_documents/CCC_Controls_Template.csv`
**Framework:** Cloud Computing Controls (CCC) Framework
**Total Controls:** 32 controls
**Format:** Same 4-column structure

**Control Domains:**
- Infrastructure Security (4 controls)
- Platform Security (4 controls)
- Data Security (4 controls)
- Identity & Access (4 controls)
- Network Security (4 controls)
- Security Operations (4 controls)
- Compliance (4 controls)
- Disaster Recovery (4 controls)

### 3. ADHICS_Controls_Template.csv
**Location:** `/reference_documents/ADHICS_Controls_Template.csv`
**Framework:** Abu Dhabi Health Information and Cyber Security (ADHICS) Standard v2
**Total Controls:** 36 controls
**Format:** Same 4-column structure

**Control Domains:**
- Governance (3 controls)
- Protected Health Information (5 controls)
- Identity & Access Management (4 controls)
- Network Security (4 controls)
- Application Security (4 controls)
- Medical Device Security (4 controls)
- Data Management (4 controls)
- Compliance (4 controls)
- Business Continuity (4 controls)

### 4. SITA_Controls_Template.csv
**Location:** `/reference_documents/SITA_Controls_Template.csv`
**Framework:** Microsoft-SITA Reference Architecture for Government Cloud
**Total Controls:** 38 controls
**Format:** Same 4-column structure

**Control Domains:**
- Sovereign Cloud Architecture (14 controls - SPO-01 through SPO-14)
- Network Architecture (4 controls)
- Identity & Access Management (4 controls)
- Data Security (4 controls)
- Security Operations (4 controls)
- Compliance & Governance (4 controls)
- Business Continuity (4 controls)

### 5. POPIA_Controls_Template.csv
**Location:** `/templates/POPIA_Controls_Template.csv`
**Framework:** Protection of Personal Information Act (POPIA) - South Africa
**Total Controls:** 16 controls
**Format:** Same 4-column structure

**Control Domains:**
- Accountability (1 control)
- Processing Limitation (1 control)
- Purpose Specification (1 control)
- Further Processing (1 control)
- Information Quality (1 control)
- Openness (1 control)
- Security Safeguards (1 control)
- Data Subject Participation (1 control)
- Consent Management (1 control)
- Cross-Border Transfer (1 control)
- Direct Marketing (1 control)
- Data Breach (1 control)
- Records (1 control)
- Data Officer (1 control)
- Privacy Impact (1 control)
- Retention (1 control)

### 6. eGovernment_Controls_Template.csv
**Location:** `/templates/eGovernment_Controls_Template.csv`
**Framework:** South African eGovernment Framework
**Total Controls:** 15 controls
**Format:** Same 4-column structure

**Control Domains:**
- Digital Strategy (1 control)
- Service Delivery (1 control)
- Interoperability (1 control)
- Data Sharing (1 control)
- Citizen Access (1 control)
- Digital Identity (1 control)
- Cloud First (1 control)
- Open Standards (1 control)
- Cybersecurity (1 control)
- Data Protection (1 control)
- Transparency (1 control)
- Innovation (1 control)
- Capacity Building (1 control)
- Infrastructure (1 control)
- Mobile Services (1 control)

### 7. IGR_Controls_Template.csv
**Location:** `/templates/IGR_Controls_Template.csv`
**Framework:** Intergovernmental Relations Framework Act 13 of 2005
**Total Controls:** 10 controls
**Format:** Same 4-column structure

**Control Domains:**
- Intergovernmental Coordination (1 control)
- Information Sharing (1 control)
- Dispute Resolution (1 control)
- Joint Planning (1 control)
- Service Delivery (1 control)
- Resource Allocation (1 control)
- Policy Alignment (1 control)
- Monitoring & Reporting (1 control)
- Capacity Support (1 control)
- Communication (1 control)

## File Structure

All files follow this consistent CSV format:
```csv
Control ID,Control Domain,Control Title,Control Description
```

### Column Descriptions

| Column | Description | Example |
|--------|-------------|---------|
| **Control ID** | Unique identifier for the control using framework prefix | SAMA-GOV-01, CCC-IaaS-01, ADHICS-PHI-01, SITA-SPO-01 |
| **Control Domain** | High-level category or domain | Cybersecurity Governance, Infrastructure Security, Protected Health Information |
| **Control Title** | Short descriptive name | Establish cybersecurity policy, Data Residency, PHI Encryption at Rest |
| **Control Description** | Detailed requirement description | "Define, approve, and annually review an enterprise cybersecurity policy..." |

## Relationship to Mapping Files

These template files are derived from the comprehensive mapping CSV files located in `/catalogues/`:

| Template File | Source Mapping File | Additional Columns in Mapping |
|---------------|---------------------|-------------------------------|
| SAMA_Controls_Template.csv | SAMA_Catalog_Azure_Mappings.csv | Control_Type, Evidence_Examples, Azure_Policy_Name, Azure_Policy_ID, Defender_Control, Defender_Recommendation |
| CCC_Controls_Template.csv | CCC_Framework_Azure_Mappings.csv | Same additional columns |
| ADHICS_Controls_Template.csv | ADHICS_Framework_Azure_Mappings.csv | Same additional columns |
| SITA_Controls_Template.csv | SITA_Architecture_Azure_Mappings.csv | Same additional columns |
| POPIA_Controls_Template.csv | POPIA_Framework_Azure_Mappings.csv | Same additional columns |
| eGovernment_Controls_Template.csv | eGovernment_Framework_Azure_Mappings.csv | Same additional columns |
| IGR_Controls_Template.csv | IGR_Framework_Azure_Mappings.csv | Same additional columns |

## Use Cases

### Template Files (4 columns)
- **Control documentation** for presentations and reports
- **Initial framework mapping** exercises
- **Control selection** worksheets
- **Gap analysis** documentation
- **Simplified control views** for stakeholders

### Mapping Files (10 columns)
- **Implementation planning** with Azure-specific guidance
- **Policy deployment** activities
- **Compliance evidence** collection
- **Technical implementation** details
- **Audit and assessment** activities

## Integration with Existing Template

The new template files align with the format of `standard_control_template.csv`, which already contains:
- ISO/IEC 27002 controls
- Existing SAMA controls (some overlap with new comprehensive list)
- Azure-specific implementation guidance

Organizations can:
1. Use these templates as standalone frameworks
2. Merge controls into the master `standard_control_template.csv`
3. Cross-reference between templates for multi-framework compliance

## Example Usage

### Gap Analysis Workflow
1. Open template file (e.g., `SAMA_Controls_Template.csv`)
2. Add columns: "Current State", "Gap", "Priority", "Owner"
3. Assess each control against current implementation
4. Reference mapping file for Azure-specific implementation details

### Control Selection
1. Review Control Domain and Control Title columns
2. Select applicable controls for your organization
3. Export selected controls
4. Reference full mapping files for implementation guidance

### Documentation
1. Use template format for control registers
2. Import into compliance management tools
3. Generate control matrices and reports
4. Present simplified view to leadership

## Updates and Maintenance

These template files should be updated when:
- Framework versions change (e.g., SAMA v2, ADHICS v3)
- New controls are added to frameworks
- Control descriptions are revised
- Organizational interpretations are refined

Maintain version control and document changes in the toolkit repository.

## Framework Summary

| Framework | Jurisdiction | Primary Focus | Total Controls |
|-----------|-------------|---------------|----------------|
| SAMA | Saudi Arabia | Financial Sector Cybersecurity | 37 |
| CCC | UAE | Multi-Cloud Security | 32 |
| ADHICS | UAE | Healthcare Information Security | 36 |
| SITA | South Africa | Sovereign Cloud Architecture | 38 |
| POPIA | South Africa | Data Protection & Privacy | 16 |
| eGovernment | South Africa | Digital Government Services | 15 |
| IGR | South Africa | Intergovernmental Cooperation | 10 |
| **Total** | **MENA & Africa** | **Comprehensive Compliance** | **184** |

---

**Created:** November 28, 2025
**Last Updated:** December 4, 2025
**Toolkit Version:** 1.1
**Format Version:** Standard 4-column CSV
**Author:** Warren du Toit, Cloud Solution Architect @ Microsoft
