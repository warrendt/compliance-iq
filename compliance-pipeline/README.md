# CCToolkit Compliance Pipeline

**PDF → Controls → Azure Policy → Defender for Cloud — in one command.**

This pipeline automates the entire journey from a compliance control PDF document to a deployable Azure Policy initiative for Microsoft Defender for Cloud regulatory compliance.

## What It Does

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌────────────┐     ┌─────────────────┐
│  Compliance  │     │   AI Control     │     │  Azure Policy    │     │  Validate  │     │  Initiative     │
│  PDF Input   │────▶│   Extraction     │────▶│  Mapping (LLM)   │────▶│  Mappings  │────▶│  Artifacts      │
│              │     │  (Azure OpenAI)  │     │                  │     │            │     │  (JSON + PS1)   │
└─────────────┘     └──────────────────┘     └──────────────────┘     └────────────┘     └─────────────────┘
      PDF                Stage 1                   Stage 2              Stage 3              Stage 4
```

### Stage 1: PDF Text Extraction
- Extracts all text from the PDF using `pypdf`
- Handles multi-page documents (up to 200 pages)
- Chunks large documents for LLM processing

### Stage 2: AI Control Extraction
- Sends PDF text to Azure OpenAI (GPT-5/GPT-4o)
- Uses **structured outputs** to extract every control with:
  - Control ID, title, description, domain, type
  - Sub-controls and requirements
  - Framework metadata (name, version, authority, region)

### Stage 3: Azure Policy Mapping
- Maps each control to:
  - **MCSB controls** (Microsoft Cloud Security Benchmark)
  - **Azure Policy definitions** (real built-in policy GUIDs)
  - **Defender for Cloud recommendations**
- Identifies automatable vs manual controls
- Provides confidence scores and rationale

### Stage 4: Validation
- Validates all policy GUIDs are proper format
- Checks MCSB control ID formats
- Flags low-confidence mappings for review
- Ensures all controls have mappings

### Stage 5: Generate Initiative Artifacts
Produces the exact file format expected by Azure:

| File | Purpose |
|------|---------|
| `<Framework>_Initiative.json` | Main initiative definition (Policy Set Definition) |
| `policies.json` | Policy definition references with group assignments |
| `groups.json` | Policy definition groups (one per control) |
| `params.json` | Parameters (e.g., allowed locations) |
| `Deploy-Initiative.ps1` | PowerShell script for Azure deployment |
| `deploy-initiative.sh` | Azure CLI script for deployment |
| `<Framework>_Mappings.csv` | Complete mapping report |
| `validation_report.json` | Validation results |

## Quick Start

### 1. Prerequisites

```bash
# Python 3.10+
pip install -r requirements.txt

# Azure authentication (choose one)
az login                              # Azure CLI (recommended)
# OR set AZURE_OPENAI_API_KEY in .env
```

### 2. Configure

```bash
cp .env.template .env
# Edit .env with your Azure OpenAI endpoint
```

### 3. Run

```bash
# Basic — process a compliance PDF
python pipeline.py ./my-framework.pdf

# With custom output directory
python pipeline.py ./my-framework.pdf --output ./frameworks/my-framework

# With Azure region restrictions
python pipeline.py ./my-framework.pdf --locations uaenorth,uaecentral

# Higher confidence threshold
python pipeline.py ./my-framework.pdf --min-confidence 0.7

# Verbose for debugging
python pipeline.py ./my-framework.pdf --verbose
```

### 4. Deploy to Azure

```powershell
# PowerShell
cd output/my-framework
.\Deploy-Initiative.ps1

# With management group scope
.\Deploy-Initiative.ps1 -ManagementGroupId "mg-compliance"

# Create and assign in one step
.\Deploy-Initiative.ps1 -AssignAfterCreation
```

```bash
# Azure CLI
cd output/my-framework
bash deploy-initiative.sh

# With management group scope
bash deploy-initiative.sh --management-group mg-compliance
```

## Example Output

Running against an Oman CDC document:

```
╔══════════════════════════════════════════════════════════════╗
║   CCToolkit Compliance Pipeline                            ║
║   PDF → Controls → Azure Policy → Defender for Cloud       ║
╚══════════════════════════════════════════════════════════════╝

──────────────────────────────────────────────────────────────
  Stage 1: PDF Text Extraction
──────────────────────────────────────────────────────────────

  ✓ Extracted 45,230 characters from 28 pages

──────────────────────────────────────────────────────────────
  Stage 2: AI Control Extraction (Azure OpenAI)
──────────────────────────────────────────────────────────────

  ✓ Framework:  Oman CDC Cloud Security Controls
  ✓ Authority:  Cyber Defense Centre (CDC)
  ✓ Region:     Oman
  ✓ Controls:   28 extracted

  Domain Breakdown:
    Network Security: 4
    Identity & Access Management: 3
    Data Protection & Encryption: 5
    ...

──────────────────────────────────────────────────────────────
  Stage 3: Azure Policy Mapping (Azure OpenAI)
──────────────────────────────────────────────────────────────

  ✓ Mapped:      28 controls
  ✓ Automatable: 19 (via Azure Policy)
  ✓ Manual:       9 (require attestation)
  ✓ Policies:    37 unique Azure Policy definitions
  ✓ Confidence:  0.82 average

──────════════════════════════════════════════════════════════
  Pipeline Complete — 47.3s
══════════════════════════════════════════════════════════════
```

## Architecture

```
compliance-pipeline/
├── pipeline.py            # CLI orchestrator (main entry point)
├── config.py              # Configuration loader
├── models.py              # Pydantic models (structured outputs)
├── pdf_extractor.py       # PDF → raw text
├── control_extractor.py   # Raw text → structured controls (LLM)
├── policy_mapper.py       # Controls → Azure Policy mappings (LLM)
├── validator.py           # Mapping validation
├── initiative_builder.py  # Generate JSON + PS1 + CSV artifacts
├── requirements.txt       # Python dependencies
├── .env.template          # Environment variable template
└── README.md              # This file
```

## How It Works with Defender for Cloud

The generated initiative follows the exact format used by built-in regulatory standards in Defender for Cloud:

1. **Policy Definition Groups** = your compliance controls
2. **Policy Definitions** = Azure Policy rules mapped to each control
3. Each policy is assigned to one or more groups (controls)
4. Non-automatable controls appear as "Manual attestation required"

Once deployed and assigned:
- Defender for Cloud evaluates all resources against the initiative
- Compliance dashboard shows per-control status
- Non-compliant resources are flagged with remediation guidance
- Manual controls require evidence upload in the portal

## Supported PDF Formats

- ✅ Text-based PDFs (most modern compliance documents)
- ✅ Multi-language documents (Arabic, English, etc.)
- ✅ Documents up to 200 pages
- ❌ Scanned/image-only PDFs (OCR not yet supported)
- ❌ Password-protected PDFs

## Integration with Existing CCToolkit

This pipeline generates the same artifact format as the existing frameworks in `../framework/`:
- `framework/Oman CDC/` — CDC_Initiative.json, cdc_policies.json, cdc_groups.json
- `framework/SAMA/` — SAMA_Cybersecurity_Framework.json, policies.json
- `framework/SITA Cloud Compliance Framework/` — similar structure

The generated `Deploy-Initiative.ps1` follows the same pattern as `CreateCDCInitiative.ps1`.
