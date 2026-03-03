# Cloud Compliance Toolkit - Process Documentation

## 🎯 Purpose
This document provides step-by-step instructions for replicating the process of creating comprehensive compliance control catalogs with Azure Policy and Microsoft Defender for Cloud mappings for multiple regulatory frameworks.

---

## 📋 Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Phase 1: Project Setup and Documentation Review](#phase-1-project-setup-and-documentation-review)
4. [Phase 2: Research Azure Mappings](#phase-2-research-azure-mappings)
5. [Phase 3: Create Comprehensive Mapping Catalogs](#phase-3-create-comprehensive-mapping-catalogs)
6. [Phase 4: Create Standard Control Templates](#phase-4-create-standard-control-templates)
7. [Phase 5: Documentation and Knowledge Transfer](#phase-5-documentation-and-knowledge-transfer)
8. [Quality Assurance](#quality-assurance)
9. [Maintenance and Updates](#maintenance-and-updates)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### What This Process Creates
This process generates a comprehensive Cloud Compliance Toolkit containing:
- **Compliance control catalogs** for multiple frameworks (SAMA, ADHICS, Saudi Arabia Government, South African Government, Oman Government)
- **Azure Policy mappings** with specific policy names and definition IDs
- **Microsoft Defender for Cloud** control and recommendation mappings
- **Standard control templates** in simplified CSV format
- **Comprehensive documentation** for implementation and usage

### Frameworks Covered
1. **SAMA** — Saudi Arabian Monetary Authority Cybersecurity Framework (Financial Sector) — 48 policies
2. **ADHICS** — Abu Dhabi Healthcare Information and Cyber Security Standard (Healthcare) — 50 policies
3. **Saudi Arabia Government** — NCA/NDMO aligned controls (Saudi Government Sector) — 58 policies
4. **South African Government** — DPPI/POPIA/SITA aligned controls (South African Government) — 56 policies
5. **Oman Government** — OIA/ISR aligned controls (Oman Government Sector) — 53 policies

### Time Estimate
- **Initial Setup:** 1-2 hours
- **Research Phase:** 3-4 hours per framework
- **Catalog Creation:** 2-3 hours per framework
- **GUID Validation & Fixing:** 1-2 hours (automated with `validate_guids.py`)
- **Documentation:** 2-3 hours
- **Total:** Approximately 25-35 hours for all five frameworks

---

## Prerequisites

### 1. Access Requirements
- ✅ Access to **Microsoft Learn** documentation
- ✅ Access to **Azure Portal** (for validating policy IDs)
- ✅ Access to **Microsoft Defender for Cloud** documentation
- ✅ **GitHub Copilot** or similar AI assistant with MCP server access (optional but recommended)

### 2. Reference Documents
Collect and organize the following documents in a `reference_documents/` folder:
- ✅ Framework-specific PDF documents (SAMA, ADHICS, Saudi Arabia, South Africa, Oman)
- ✅ Existing control templates or standards (ISO 27001, NIST 800-53)
- ✅ Azure Policy built-in definitions reference
- ✅ Microsoft Cloud Security Benchmark documentation

### 3. Tools and Software
- **Text Editor/IDE:** VS Code (recommended)
- **Spreadsheet Software:** Excel or Google Sheets
- **Version Control:** Git/GitHub repository
- **Markdown Editor:** Any markdown-compatible editor

### 4. Knowledge Requirements
- Understanding of compliance frameworks and control structures
- Familiarity with Azure services (Policy, Defender for Cloud, RBAC)
- Basic understanding of CSV file formats and data structures
- Knowledge of security domains (Identity, Network, Data Protection, etc.)

---

## Phase 1: Project Setup and Documentation Review

### Step 1.1: Initialize Project Structure
Create the following directory structure:

```
compliance-iq/
├── README.md
├── reference_documents/
│   ├── [Framework PDFs]
│   └── standard_control_template.csv
├── catalogues/
│   └── [Generated mapping files will go here]
└── app/
    └── [Application code]
```

**Commands:**
```bash
mkdir -p compliance-iq/reference_documents
mkdir -p compliance-iq/catalogues
mkdir -p compliance-iq/app
cd compliance-iq
git init
```

### Step 1.2: Create Initial README
Create a `readme.md` file documenting:
- Project objective and scope
- Frameworks to be covered
- Target compliance standards (ISO 27001, NIST 800-53)
- Alignment with Azure Landing Zones and Defender CSPM
- Prerequisites and reference materials

**Template Structure:**
```markdown
# README: Generating a Sovereign Landing Zone Policy Pack

## 🎯 Objective
[Describe the goal]

## 🧾 Prerequisites
[List required materials]

## 🧭 Process Overview
[High-level steps]

## 📁 Output
[Expected deliverables]

## 📚 References
[List all reference documents and links]
```

### Step 1.3: Gather Reference Documents
1. Collect all framework PDF documents
2. Place them in `reference_documents/` folder
3. Document the filename and version of each:
   - `Microsoft_SITA Reference Architecture Document.pdf`
   - `SAMA_EN_3837_VER1.pdf`
   - `ADHICS-v2-standard (3).pdf`
   - `ccc-en.pdf`

### Step 1.4: Review Existing Templates
Examine any existing control templates:
1. Open `standard_control_template.csv` (if exists)
2. Note the column structure:
   - Control ID
   - Control Domain
   - Control Title
   - Control Description
3. Identify any existing control mappings to use as examples

**Action:** Document the standard format in your notes for consistency.

---

## Phase 2: Research Azure Mappings

### Step 2.1: Enable Microsoft Learn MCP Server Access
If using GitHub Copilot with MCP servers:

1. Activate Microsoft documentation tools:
   ```
   Use the Microsoft Learn MCP server for documentation searches
   ```

2. Verify access to search capabilities:
   - `microsoft_docs_search` - Search documentation
   - `microsoft_docs_fetch` - Fetch complete documentation pages
   - `microsoft_code_sample_search` - Find code examples

### Step 2.2: Research Azure Policy Built-in Definitions

**Goal:** Find specific Azure Policy definitions that map to control requirements.

**Research Topics:**
1. **Identity & Access Control**
   - Search: "Azure Policy built-in definitions MFA multi-factor authentication"
   - Search: "Azure Policy RBAC role-based access control"
   - Search: "Azure Policy conditional access"

2. **Network Security**
   - Search: "Azure Policy network security private endpoints"
   - Search: "Azure Policy NSG network security groups"
   - Search: "Azure Policy public network access disable"

3. **Data Protection & Encryption**
   - Search: "Azure Policy encryption customer-managed keys"
   - Search: "Azure Policy TLS encryption data in transit"
   - Search: "Azure Policy storage encryption at rest"

4. **Logging & Monitoring**
   - Search: "Azure Policy diagnostic settings Log Analytics"
   - Search: "Azure Policy logging monitoring centralized"

5. **Vulnerability Management**
   - Search: "Azure Policy system updates patch management"
   - Search: "Azure Policy vulnerability assessment"

**Document Format:**
Create a research notes file with findings:

```markdown
## Azure Policy Research Notes

### MFA / Authentication
- **Policy Name:** Users must authenticate with multi-factor authentication to create or update resources
- **Policy ID:** 4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b
- **Effect:** Audit, Deny, Disabled
- **Applies to:** SAMA-AC-01, ADHICS-IAM-01, SITA-IAM-02

### Private Endpoints
- **Policy Name:** App Configuration should use private link
- **Policy ID:** ca610c1d-041c-4332-9d88-7ed3094967c7
- **Effect:** AuditIfNotExists, Disabled
- **Applies to:** SAMA-NS-02, CCC-Net-03, SITA-Net-03
```

### Step 2.3: Research Microsoft Defender for Cloud Controls

**Goal:** Identify Defender for Cloud recommendations that align with compliance controls.

**Research Topics:**
1. **Defender for Cloud Secure Score Controls**
   - Search: "Microsoft Defender for Cloud security controls secure score"
   - Note: Main control categories and their score weights

2. **Security Recommendations**
   - Search: "Microsoft Defender for Cloud recommendations reference"
   - Search: "Defender for Cloud network security recommendations"
   - Search: "Defender for Cloud encryption recommendations"

**Key Control Categories to Document:**
- Enable MFA (Score: 10)
- Manage access and permissions (Score: 4)
- Restrict unauthorized network access (Score: 4)
- Enable encryption at rest (Score: 4)
- Encrypt data in transit (Score: 4)
- Enable auditing and logging (Score: 1)
- Apply system updates (Score: 6)
- Remediate vulnerabilities (Score: 6)

### Step 2.4: Create Research Summary Document

Create `research_notes.md` with all findings organized by:
- Control domain
- Azure Policy mappings
- Defender for Cloud controls
- Cross-references between frameworks

---

## Phase 3: Create Comprehensive Mapping Catalogs

### Step 3.1: Define Catalog Structure

**Standard 10-Column Format:**
```csv
[Framework]_ID,Domain,Control_Name,Requirement_Summary,Control_Type,Evidence_Examples,Azure_Policy_Name,Azure_Policy_ID,Defender_Control,Defender_Recommendation
```

**Column Definitions:**
- **[Framework]_ID:** Unique control identifier (e.g., SAMA-AC-01)
- **Domain:** Control category/domain (e.g., Identity & Access Control)
- **Control_Name:** Short descriptive name
- **Requirement_Summary:** Detailed control description
- **Control_Type:** Management, Operational, or Technical
- **Evidence_Examples:** Examples of compliance evidence
- **Azure_Policy_Name:** Name of mapped Azure Policy (or N/A)
- **Azure_Policy_ID:** GUID of Azure Policy definition (or N/A)
- **Defender_Control:** Defender for Cloud control category
- **Defender_Recommendation:** Specific Defender recommendation text

### Step 3.2: Create SAMA Framework Catalog

**File:** `catalogues/SAMA_Catalog_Azure_Mappings.csv`

**Process:**
1. Start with existing SAMA controls from reference documents
2. For each control:
   - Define the control ID, domain, name, and description
   - Determine control type (Management/Operational/Technical)
   - List evidence examples
   - Search research notes for applicable Azure Policy
   - Map to Defender for Cloud control category
   - Document specific Defender recommendation

**Example Entry:**
```csv
SAMA-AC-01,Identity & Access Control,Strong authentication,"Enforce MFA for privileged and user access; disable legacy protocols where possible.",Technical,"MFA reports, conditional access policies",Users must authenticate with multi-factor authentication to create or update resources,4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b,Identity & Access Management,Enable MFA - Require multifactor authentication for all users
```

**Control Domains to Cover:**
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

### Step 3.3: Create CCC Framework Catalog

**File:** `catalogues/CCC_Framework_Azure_Mappings.csv`

**Process:**
1. Review CCC Framework document or define common cloud controls
2. Organize into domains:
   - Infrastructure Security (IaaS)
   - Platform Security (PaaS)
   - Data Security
   - Identity & Access Management
   - Network Security
   - Security Operations
   - Compliance
   - Disaster Recovery

3. For each domain, create 4-5 controls covering:
   - Core security requirements
   - Best practices
   - Azure-specific implementations

**Example Controls:**
```csv
CCC-IaaS-01,Infrastructure Security,Compute Instance Hardening,Harden virtual machine configurations and disable unnecessary services,Technical,"VM configs, baseline assessments",Machines should be configured to periodically check for missing system updates,bd876905-5b84-4f73-ab2d-2e7a7c4568d9,Posture Management,Remediate security configurations

CCC-Net-03,Network Security,Private Connectivity,Use private endpoints for PaaS services,Technical,"Private endpoint inventory, DNS configs",App Configuration should use private link,ca610c1d-041c-4332-9d88-7ed3094967c7,Network Security,Secure cloud services with private endpoints
```

### Step 3.4: Create ADHICS Healthcare Catalog

**File:** `catalogues/ADHICS_Framework_Azure_Mappings.csv`

**Focus Areas:**
1. **Protected Health Information (PHI)** - 5 controls
   - Encryption at rest and in transit
   - Access controls with RBAC
   - Data masking
   - Audit logging for all PHI access

2. **Healthcare-Specific Systems** - 4 controls
   - Electronic Health Records (EHR)
   - Medical imaging (PACS/DICOM)
   - Laboratory Information Systems
   - Healthcare APIs (FHIR, HL7)

3. **Medical Device Security** - 4 controls
   - Device inventory
   - Patch management with vendor coordination
   - Network isolation
   - Incident response for device events

4. **Compliance** - 4 controls
   - HIPAA compliance
   - Breach notification procedures
   - Patient privacy rights
   - Healthcare audit logging

**Example Entry:**
```csv
ADHICS-PHI-01,Protected Health Information,PHI Encryption at Rest,Encrypt all protected health information at rest,Technical,"Encryption configs, key management",PostgreSQL servers should use customer-managed keys to encrypt data at rest,18adea5e-f416-4d0f-8aa8-d24321e3e274,Data Protection,Enable encryption at rest for PHI
```

### Step 3.5: Create SITA Government/Sovereign Cloud Catalog

**File:** `catalogues/SITA_Architecture_Azure_Mappings.csv`

**Focus Areas:**
1. **Sovereign Cloud Architecture (SPO-01 through SPO-14)** - 14 controls
   - Data residency requirements
   - Sovereign identity services
   - Local key management
   - Government network connectivity
   - Compliance with national laws (POPIA)
   - Background-checked personnel
   - Sovereign backup and DR

2. **Government-Specific Security** - Controls covering:
   - Government identity federation
   - Security clearance integration
   - Classified data encryption
   - Government SOC integration
   - Threat intelligence sharing

**Example Entry:**
```csv
SITA-SPO-01,Sovereign Cloud Architecture,Data Residency,Ensure all data resides within South African borders,Technical,"Region configs, data location reports",N/A,N/A,Data Sovereignty,Enforce data residency in South Africa

SITA-IAM-02,Identity & Access Management,Multi-Factor Authentication,Enforce MFA for all government user access,Technical,"MFA configs, authentication policies",Users must authenticate with multi-factor authentication to create or update resources,4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b,Identity & Access Management,Enforce MFA for government access
```

### Step 3.6: Quality Check Mapping Catalogs

For each catalog, verify:
- ✅ All control IDs are unique
- ✅ Control domains are consistent within framework
- ✅ Azure Policy IDs are accurate (validate against Azure documentation)
- ✅ Defender controls align with Microsoft documentation
- ✅ No duplicate mappings unless intentional
- ✅ CSV format is valid (no unescaped quotes, proper delimiters)

**Validation Commands:**
```bash
# Count controls per framework
wc -l catalogues/*.csv

# Check for duplicate control IDs
cut -d',' -f1 catalogues/SAMA_Catalog_Azure_Mappings.csv | sort | uniq -d

# Validate CSV format
csvlint catalogues/*.csv
```

---

## Phase 4: Create Standard Control Templates

### Step 4.1: Understand Template Format

Review the `standard_control_template.csv` structure:
```csv
Control ID,Control Domain,Control Title,Control Description
```

This simplified 4-column format is used for:
- Control documentation
- Gap analysis worksheets
- Control selection exercises
- Stakeholder presentations

### Step 4.2: Extract Data from Mapping Catalogs

For each framework mapping file, extract the 4 core columns:

**Extraction Mapping:**
- Column 1: `[Framework]_ID` → `Control ID`
- Column 2: `Domain` → `Control Domain`
- Column 3: `Control_Name` → `Control Title`
- Column 4: `Requirement_Summary` → `Control Description`

### Step 4.3: Create Individual Template Files

**Files to Create:**
1. `reference_documents/SAMA_Controls_Template.csv`
2. `reference_documents/CCC_Controls_Template.csv`
3. `reference_documents/ADHICS_Controls_Template.csv`
4. `reference_documents/SITA_Controls_Template.csv`

**Process for Each File:**
1. Open the corresponding mapping catalog file
2. Copy columns 1-4 (ID, Domain, Control_Name, Requirement_Summary)
3. Create new CSV with header: `Control ID,Control Domain,Control Title,Control Description`
4. Paste the extracted data
5. Save in `reference_documents/` folder

**Automated Approach (Optional):**
```bash
# Extract columns 1-4 from mapping file
cut -d',' -f1-4 catalogues/SAMA_Catalog_Azure_Mappings.csv > temp.csv

# Add proper headers
echo "Control ID,Control Domain,Control Title,Control Description" > reference_documents/SAMA_Controls_Template.csv
tail -n +2 temp.csv >> reference_documents/SAMA_Controls_Template.csv
```

### Step 4.4: Validate Template Files

For each template file:
- ✅ Verify 4-column structure
- ✅ Check that all control IDs are present
- ✅ Ensure descriptions are complete (no truncation)
- ✅ Validate CSV formatting
- ✅ Compare row count with mapping catalog (should match)

---

## Phase 5: Documentation and Knowledge Transfer

### Step 5.1: Create Catalog Summary Document

**File:** `catalogues/CATALOG_SUMMARY.md`

**Contents:**
1. **Overview** - Purpose and scope of the catalogs
2. **Generated Catalogs** - List of all four frameworks with:
   - Framework name and description
   - Total control count
   - Key domains covered
   - Azure mapping highlights

3. **Key Azure Policy Mappings** - Table of most important policies:
   ```markdown
   | Policy Name | Policy ID | Maps to Controls |
   |-------------|-----------|------------------|
   | Users must authenticate with MFA | 4e6c27d5-... | SAMA-AC-01, ADHICS-IAM-01, SITA-IAM-02 |
   ```

4. **Defender for Cloud Control Categories** - List of all categories
5. **Usage Instructions** - How to use the catalogs
6. **Cross-Framework Mapping** - Table showing control overlap
7. **Next Steps** - Implementation guidance
8. **Additional Resources** - Links to documentation

### Step 5.2: Create Control Templates README

**File:** `reference_documents/CONTROL_TEMPLATES_README.md`

**Contents:**
1. **Overview** - Purpose of template files
2. **Files Created** - List with control counts
3. **File Structure** - Column definitions and examples
4. **Relationship to Mapping Files** - How templates relate to full catalogs
5. **Use Cases** - When to use templates vs. mapping files
6. **Example Usage** - Workflows for gap analysis, control selection
7. **Integration Guidance** - How to merge with existing templates

### Step 5.3: Create Process Documentation (This Document)

**File:** `PROCESS_DOCUMENTATION.md`

**Contents:**
- Complete step-by-step process
- Prerequisites and requirements
- Detailed instructions for each phase
- Quality assurance procedures
- Troubleshooting guidance
- Maintenance procedures

### Step 5.4: Update Main README

Update `readme.md` to include:
1. **New Frameworks** - Add ADHICS and CCC to the list
2. **Prerequisites** - Update with all four reference documents
3. **Process Overview** - Add new research and mapping steps
4. **Output Files** - Document all generated catalogs and templates
5. **References** - Add new reference document locations

**Example Updates:**
```markdown
## 🧾 Prerequisites

1. Access to the following reference materials (located in `reference_documents/`):
   - **Microsoft_SITA Reference Architecture Document.pdf**
   - **SAMA_EN_3837_VER1.pdf**
   - **ADHICS-v2-standard (3).pdf**
   - **ccc-en.pdf**
   - **External Standard Control Template.xlsx**
```

### Step 5.5: Create Quick Start Guide

**File:** `QUICKSTART.md`

**Contents:**
```markdown
# Quick Start Guide

## For Implementers
1. Review `CATALOG_SUMMARY.md`
2. Select applicable framework
3. Open mapping catalog in `/catalogues/`
4. Filter by control domain
5. Deploy Azure Policies from mappings

## For Auditors
1. Open control template in `/reference_documents/`
2. Perform gap analysis
3. Reference mapping catalog for evidence examples
4. Generate compliance reports

## For Developers
1. Review Azure Policy IDs in mapping catalogs
2. Use Policy definitions for Infrastructure as Code
3. Implement Defender for Cloud recommendations
4. Automate compliance checks
```

---

## Quality Assurance

### QA Checklist

#### File Structure
- [ ] All directories created correctly
- [ ] Files in correct locations
- [ ] Naming conventions consistent
- [ ] No duplicate filenames

#### Mapping Catalogs (10-column format)
- [ ] All control IDs unique within framework
- [ ] Control domains consistent
- [ ] Control types valid (Management/Operational/Technical)
- [ ] Azure Policy IDs validated against Microsoft documentation
- [ ] Defender control categories accurate
- [ ] CSV format valid (no parsing errors)
- [ ] Special characters properly escaped
- [ ] Line endings consistent (LF or CRLF)

#### Control Templates (4-column format)
- [ ] Column headers match standard format
- [ ] All controls from mapping catalog present
- [ ] Descriptions complete and accurate
- [ ] Row count matches mapping catalog
- [ ] CSV format valid

#### Documentation
- [ ] All markdown files render correctly
- [ ] Links work (internal and external)
- [ ] Code blocks formatted properly
- [ ] Tables display correctly
- [ ] Spelling and grammar checked
- [ ] Technical accuracy verified

### Validation Scripts

**Validate Control ID Uniqueness:**
```bash
#!/bin/bash
for file in catalogues/*_Mappings.csv; do
    echo "Checking $file"
    duplicates=$(cut -d',' -f1 "$file" | tail -n +2 | sort | uniq -d)
    if [ -n "$duplicates" ]; then
        echo "❌ Duplicates found: $duplicates"
    else
        echo "✅ No duplicates"
    fi
done
```

**Validate Azure Policy IDs:**
```bash
#!/bin/bash
# Extract all policy IDs
grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' catalogues/*_Mappings.csv | sort -u > policy_ids.txt

# Validate each ID exists in Azure
while read -r id; do
    if az policy definition show --name "$id" &>/dev/null; then
        echo "✅ $id valid"
    else
        echo "❌ $id invalid"
    fi
done < policy_ids.txt
```

**Count Controls Per Framework:**
```bash
#!/bin/bash
for file in catalogues/*_Mappings.csv; do
    count=$(($(wc -l < "$file") - 1))
    echo "$(basename "$file"): $count controls"
done
```

### Peer Review Process

1. **Technical Review**
   - Verify Azure Policy mappings are accurate
   - Confirm Defender control categories are correct
   - Validate control descriptions match framework requirements

2. **Compliance Review**
   - Ensure controls align with framework intent
   - Verify control domains are appropriate
   - Check evidence examples are realistic

3. **Documentation Review**
   - Verify process documentation is clear and complete
   - Check that examples are accurate
   - Ensure troubleshooting guidance is helpful

---

## Maintenance and Updates

### When to Update

**Framework Updates:**
- New framework versions released (e.g., SAMA v2)
- Control additions or modifications
- Control renumbering or reorganization

**Azure Updates:**
- New Azure Policy definitions released
- Policy definitions retired or deprecated
- New Defender for Cloud recommendations
- Changes to secure score weightings

**Organizational Changes:**
- Custom interpretations of controls
- Additional control domains needed
- New frameworks required

### Update Process

1. **Track Changes**
   ```bash
   git checkout -b update-sama-v2
   ```

2. **Update Mapping Catalog**
   - Add new controls
   - Modify existing control descriptions
   - Update Azure Policy mappings
   - Revise Defender recommendations

3. **Update Control Template**
   - Extract updated 4-column data
   - Regenerate template file

4. **Update Documentation**
   - Revise CATALOG_SUMMARY.md
   - Update version numbers
   - Document changes in CHANGELOG.md

5. **Commit Changes**
   ```bash
   git add .
   git commit -m "Update SAMA framework to v2"
   git push origin update-sama-v2
   ```

### Version Control

**Semantic Versioning:**
- **Major (X.0.0):** New framework added or major restructure
- **Minor (1.X.0):** Control additions or significant updates
- **Patch (1.0.X):** Minor corrections or documentation updates

**Maintain CHANGELOG.md:**
```markdown
# Changelog

## [1.1.0] - 2025-12-01
### Added
- ADHICS v2 framework controls
- CCC Framework controls

### Changed
- Updated SAMA controls with new AI governance section
- Revised Azure Policy IDs for network security controls

### Fixed
- Corrected duplicate control IDs in SITA catalog
```

---

## Troubleshooting

### Common Issues

#### Issue: Azure Policy ID Not Found
**Symptom:** Policy ID in mapping doesn't exist in Azure
**Solution:**
1. Search Microsoft Learn for current policy name
2. Check if policy was renamed or deprecated
3. Find replacement policy
4. Update mapping catalog
5. Document change in CHANGELOG

#### Issue: CSV Parsing Errors
**Symptom:** Excel or tools can't open CSV file
**Solution:**
1. Check for unescaped quotes in descriptions
2. Verify delimiter consistency (comma vs. semicolon)
3. Ensure line endings are consistent
4. Use CSV validation tool:
   ```bash
   csvlint catalogues/SAMA_Catalog_Azure_Mappings.csv
   ```

#### Issue: Control ID Duplicates
**Symptom:** Same control ID appears multiple times
**Solution:**
1. Run duplicate detection:
   ```bash
   cut -d',' -f1 catalogues/SAMA_Catalog_Azure_Mappings.csv | sort | uniq -d
   ```
2. Renumber duplicate controls
3. Update cross-references
4. Regenerate template file

#### Issue: Mismatched Control Counts
**Symptom:** Template has different row count than mapping catalog
**Solution:**
1. Compare row counts:
   ```bash
   wc -l catalogues/SAMA_Catalog_Azure_Mappings.csv
   wc -l reference_documents/SAMA_Controls_Template.csv
   ```
2. Check for missing controls in template
3. Regenerate template from mapping catalog
4. Verify extraction process

#### Issue: Defender Control Category Invalid
**Symptom:** Category doesn't match Defender for Cloud documentation
**Solution:**
1. Review current Defender control categories
2. Search Microsoft Learn for "Defender for Cloud security controls"
3. Update to valid category name
4. Verify across all frameworks

### Getting Help

**Resources:**
- Microsoft Learn: https://learn.microsoft.com
- Azure Policy Reference: https://learn.microsoft.com/azure/governance/policy/samples/built-in-policies
- Defender for Cloud Docs: https://learn.microsoft.com/azure/defender-for-cloud/
- Framework-specific documentation in `reference_documents/`

**Support Channels:**
- Internal security team
- Microsoft customer support
- Azure community forums
- GitHub repository issues

---

## Appendix

### A. Tool Recommendations

**CSV Editors:**
- Microsoft Excel
- Google Sheets
- LibreOffice Calc
- CSV Editor (VS Code extension)

**Markdown Editors:**
- VS Code with Markdown Preview
- Typora
- Mark Text
- MacDown (macOS)

**Validation Tools:**
- csvlint (Ruby gem)
- CSV Lint (online tool)
- Azure CLI (for policy validation)
- PowerShell (for automation)

### B. Useful Commands

**Git Commands:**
```bash
# Initialize repository
git init
git add .
git commit -m "Initial commit"

# Create feature branch
git checkout -b add-new-framework

# View changes
git diff
git status

# Commit and push
git add .
git commit -m "Add CCC framework controls"
git push origin add-new-framework
```

**CSV Processing:**
```bash
# Extract specific columns
cut -d',' -f1-4 input.csv > output.csv

# Count rows
wc -l file.csv

# Find text in CSV
grep "pattern" file.csv

# Sort by column
sort -t',' -k1 file.csv

# Remove duplicates
sort -u file.csv
```

**Azure CLI:**
```bash
# List policy definitions
az policy definition list --query "[?policyType=='BuiltIn']" -o table

# Get specific policy
az policy definition show --name "4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"

# Search policies
az policy definition list --query "[?contains(displayName, 'MFA')]"

# Trigger a compliance rescan (after deploying/updating initiatives)
az policy state trigger-scan
```

**GUID Validation Tooling** (use instead of manual lookups):
```bash
# Validate all GUIDs in all 5 frameworks against real Azure data
cd framework/
python3 validate_guids.py

# Force-refresh the Azure policy cache (bypasses 24h TTL)
python3 validate_guids.py --refresh-cache

# Search for a policy by keyword
python3 validate_guids.py --search "remote debugging"

# Apply the verified replacement map to fix invalid GUIDs
python3 fix_guids.py --dry-run    # preview changes
python3 fix_guids.py              # apply changes
```

> **Important:** Never manually guess or construct policy GUIDs. The `validate_guids.py` tool caches all 2,748 Azure built-in policies locally and validates every GUID against the real Azure list. Running `DeployAllInitiatives.ps1` automatically runs this check as a pre-flight step.

### C. Templates

**Control Entry Template:**
```csv
[FRAMEWORK]-[DOMAIN]-[NUMBER],[Domain Name],[Control Name],"[Detailed description]",[Type],"[Evidence examples]",[Azure Policy Name],[Azure Policy ID],[Defender Control],[Defender Recommendation]
```

**Documentation Section Template:**
```markdown
## [Section Title]

### Overview
[Brief description]

### Key Points
- Point 1
- Point 2
- Point 3

### Example
[Code or configuration example]

### References
- [Link to documentation]
```

### D. Glossary

**Terms:**
- **CMK:** Customer-Managed Key
- **CSPM:** Cloud Security Posture Management
- **DLP:** Data Loss Prevention
- **EHR:** Electronic Health Record
- **MFA:** Multi-Factor Authentication
- **NSG:** Network Security Group
- **PHI:** Protected Health Information
- **RBAC:** Role-Based Access Control
- **SIEM:** Security Information and Event Management
- **SOC:** Security Operations Center
- **TLS:** Transport Layer Security

---

## Document Information

**Created:** November 28, 2025
**Version:** 2.0
**Author:** Warren du Toit, Cloud Solution Architect @ Microsoft
**Last Updated:** March 3, 2026

**Change History:**
| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2025-11-28 | 1.0 | Warren du Toit | Initial creation |
| 2026-03-03 | 2.0 | Warren du Toit | Updated framework list to 5 live frameworks; removed CCC/SITA; added GUID validation tooling (`validate_guids.py`, `fix_guids.py`); updated policy counts (48/50/58/56/53); added compliance rescan command |

**Review Schedule:** Quarterly (March, June, September, December)

**Feedback:** Submit issues or suggestions via GitHub repository issues or contact the author directly.

---

**End of Process Documentation**
