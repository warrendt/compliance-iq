
# README: Generating a Sovereign Landing Zone Policy Pack for Azure & Defender CSPM (South African Government)

This README outlines the steps to replicate the process of generating a comprehensive set of security and compliance controls for a Sovereign Landing Zone (SLZ) tailored to the South African Government. The output is aligned with ISO/IEC 27001 and NIST SP 800-53 standards and excludes SAMA-specific controls.

---

## 🎯 Objective

To populate an Excel-based control template with relevant controls derived from:
- Microsoft Learn documentation (especially Sovereign Cloud and Azure Landing Zone guidance)
- Microsoft–SITA Reference Architecture (RA) for Government Cloud

The goal is to produce a structured, standards-aligned policy pack for deployment as part of a Sovereign Landing Zone in Azure, with continuous compliance monitoring via Microsoft Defender CSPM.

---

## 🧾 Prerequisites

1. Access to the following reference materials:
   - Microsoft_SITA Reference Architecture Document.pdf
   - External Standard Control Template.xlsx (used as the base for control population)

2. Access to Microsoft Learn documentation:
   - Sovereign Landing Zone (SLZ) architecture and controls
   - Azure Policy and Azure Security Benchmark
   - Microsoft Defender for Cloud CSPM documentation

---

## 🧭 Process Overview

### 1. Define Scope

- Tailor controls for the South African Government only
- Align with ISO/IEC 27001 and NIST SP 800-53
- Exclude SAMA-specific controls
- Separate controls into two sections:
  - Azure Landing Zone Controls
  - Defender CSPM Controls

### 2. Research Sources

- Microsoft Learn:
  - Sovereign Landing Zone (SLZ) documentation
  - Controls and principles in Sovereign Public Cloud
  - Azure Policy and Azure Security Benchmark
  - Defender for Cloud CSPM documentation

- Microsoft–SITA Reference Architecture:
  - Security Architecture Principles (e.g., SPO1–SPO14)
  - Data residency, encryption, and compliance expectations
  - Network architecture and deployment models for SA Government

### 3. Control Mapping

For each control:
- Define:
  - Control Domain
  - Control Title
  - Control Description
  - ISO/IEC 27001:2013 Annex A reference(s)
  - NIST SP 800-53 (Rev.5) control(s)
- Justify with references from Microsoft Learn and the SITA RA
- Ensure controls cover:
  - Data residency
  - Encryption (at rest, in transit, in use)
  - Identity & access management
  - Network security
  - Logging & monitoring
  - Secure development
  - Incident response
  - Business continuity
  - Compliance assurance

### 4. Defender CSPM Integration

- Define how Microsoft Defender for Cloud CSPM supports:
  - Continuous compliance assessment
  - Policy enforcement
  - Secure score tracking
  - Threat detection
  - Vulnerability scanning
  - Audit log integration
  - Incident response automation
  - Governance reporting

---

## 📁 Output

- A comprehensive control matrix (Excel or Markdown table) with:
  - Azure Landing Zone Controls
  - Defender CSPM Controls
- Each control includes mappings to ISO/NIST standards and references to Microsoft Learn and SITA RA

---

## 🔁 Reusability

This process can be reused for:
- Other national governments with similar sovereignty requirements
- Other compliance frameworks (e.g., GDPR, HIPAA) by adjusting the control mappings
- Updating policy packs as Microsoft Learn or regulatory standards evolve

---

## 📚 References

- Microsoft Learn: Sovereign Cloud Documentation
  - https://learn.microsoft.com/en-us/industry/sovereign-cloud/
- Microsoft–SITA Reference Architecture Document (2020)
- Azure Policy & Azure Security Benchmark
- Microsoft Defender for Cloud CSPM Documentation

---

## 🧩 Suggested Enhancements

- Automate control population into Excel using scripting (e.g., PowerShell or Python)
- Integrate with GitHub for version control of policy definitions
- Use Azure Blueprints or Bicep templates to deploy the policy pack

---

## 🧑‍💼 Authors

This process was developed by Warren du Toit, a Cloud Solution Architect @ Microsoft.
