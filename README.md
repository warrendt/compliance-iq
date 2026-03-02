# ComplianceIQ

<div align="center">

**AI-Powered Compliance Control Mapping & Policy Generation for Azure**

*Accelerate regulatory compliance across Government, Healthcare, and Financial sectors*

[![Azure](https://img.shields.io/badge/Azure-0078D4?style=flat&logo=microsoft-azure&logoColor=white)](https://azure.microsoft.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Compliance](https://img.shields.io/badge/Frameworks-8%20Supported-green)](#supported-frameworks)

</div>

---

## Overview

**ComplianceIQ** is a toolkit for implementing security and compliance controls in Azure cloud environments. It combines pre-built compliance control catalogs with an AI-powered mapping agent that can automatically map any compliance framework to the Microsoft Cloud Security Benchmark (MCSB) and generate deployable Azure Policy initiatives.

### Key Capabilities

- **AI-Powered Mapping** — Upload a compliance PDF, and GPT-4.1 maps controls to Azure policies and Defender for Cloud recommendations
- **8 Pre-Built Catalogs** — Ready-to-use mappings for SAMA, ADHICS, CCC, SITA, Oman CDC, eGovernment, IGR, and POPIA
- **Azure Policy Generation** — Export compliant Azure Policy initiative JSON, including Sovereign Landing Zone (SLZ) archetypes
- **Interactive Review UI** — Streamlit-based web interface for reviewing, editing, and approving AI-generated mappings
- **End-to-End Pipeline** — Upload PDF → Extract Controls → AI Map → Review → Export Policy
- **One-Click Deployment** — Deploy to Azure Container Apps with `azd up`

---

## Repository Structure

```
compliance-iq/
├── README.md                  # This file
├── LICENSE                    # MIT License
├── CONTRIBUTING.md            # Contribution guidelines
├── azure.yaml                 # Azure Developer CLI config
│
├── app/                       # AI Mapping Agent (full-stack application)
│   ├── backend/               #   FastAPI + Azure OpenAI + Cosmos DB
│   ├── frontend/              #   Streamlit web UI
│   ├── infra/                 #   Bicep IaC (Container Apps, OpenAI, Cosmos DB)
│   ├── tests/                 #   Integration tests
│   ├── README.md              #   App documentation
│   ├── QUICKSTART.md          #   5-minute local setup
│   ├── DEPLOYMENT.md          #   Azure deployment guide
│   └── TROUBLESHOOTING.md     #   Common issues & fixes
│
├── catalogues/                # Pre-built compliance control mappings (CSV)
│   ├── SAMA_Catalog_Azure_Mappings.csv
│   ├── ADHICS_Framework_Azure_Mappings.csv
│   ├── CCC_Framework_Azure_Mappings.csv
│   ├── SITA_Architecture_Azure_Mappings.csv
│   ├── OmanCDC_Framework_Azure_Mappings.csv
│   ├── eGovernment_Framework_Azure_Mappings.csv
│   ├── IGR_Framework_Azure_Mappings.csv
│   ├── POPIA_Framework_Azure_Mappings.csv
│   └── CATALOG_SUMMARY.md
│
├── compliance-pipeline/       # Standalone CLI tool for batch processing
├── framework/                 # Azure Policy initiative JSON & deployment scripts
├── reference_documents/       # Source compliance framework PDFs
├── templates/                 # Simplified control templates for gap analysis
└── docs/                      # Supplementary guides & references
```

---

## Supported Frameworks

| Framework | Region | Sector | Controls | Catalog |
|-----------|--------|--------|----------|---------|
| **SAMA** | Saudi Arabia | Financial | 36 | [View](catalogues/SAMA_Catalog_Azure_Mappings.csv) |
| **ADHICS** | Abu Dhabi | Healthcare | 36 | [View](catalogues/ADHICS_Framework_Azure_Mappings.csv) |
| **CCC** | Saudi Arabia | Cloud Computing | 32 | [View](catalogues/CCC_Framework_Azure_Mappings.csv) |
| **SITA** | South Africa | Government | 38 | [View](catalogues/SITA_Architecture_Azure_Mappings.csv) |
| **Oman CDC** | Oman | Government | 47 | [View](catalogues/OmanCDC_Framework_Azure_Mappings.csv) |
| **eGovernment** | South Africa | Government | — | [View](catalogues/eGovernment_Framework_Azure_Mappings.csv) |
| **IGR** | South Africa | Government | — | [View](catalogues/IGR_Framework_Azure_Mappings.csv) |
| **POPIA** | South Africa | Privacy | — | [View](catalogues/POPIA_Framework_Azure_Mappings.csv) |

Each catalog maps controls to:
- Azure Policy names and definition IDs (GUIDs)
- Microsoft Defender for Cloud control categories
- Evidence examples and implementation guidance

---

## Quick Start

### Option 1: Use the Pre-Built Catalogs

```bash
git clone https://github.com/warrendt/compliance-iq.git
cd compliance-iq

# Browse catalogs for your sector
cat catalogues/SAMA_Catalog_Azure_Mappings.csv       # Financial
cat catalogues/ADHICS_Framework_Azure_Mappings.csv    # Healthcare
cat catalogues/SITA_Architecture_Azure_Mappings.csv   # Government
```

### Option 2: Run the AI Mapping Agent Locally

```bash
cd app

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env   # Edit with your Azure OpenAI endpoint
az login
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd ../frontend
pip install -r requirements.txt
streamlit run 1_🏠_Home.py --server.port 8501
```

See [app/QUICKSTART.md](app/QUICKSTART.md) for full setup instructions.

### Option 3: Deploy to Azure

```bash
# One-command deployment with Azure Developer CLI
azd auth login
azd init
azd up
```

This provisions: Azure Container Apps, Azure OpenAI (GPT-4.1), Azure Cosmos DB, Container Registry, and VNet with private endpoints.

See [app/DEPLOYMENT.md](app/DEPLOYMENT.md) for detailed deployment guide.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│             Streamlit Frontend (Port 8501)               │
│   Home │ AI Mapping │ Review │ Export │ PDF Pipeline     │
│                  │ Policy Explorer                       │
└─────────────────┬───────────────────────────────────────┘
                  │ REST API
┌─────────────────▼───────────────────────────────────────┐
│              FastAPI Backend (Port 8000)                 │
│  • MCSB Loader       • AI Mapping Service               │
│  • Sovereignty SLZ   • Policy Generator                 │
│  • PDF Extractor     • Cosmos DB Persistence             │
└────────┬──────────────────────────┬─────────────────────┘
         │                          │
┌────────▼────────┐     ┌──────────▼──────────────────────┐
│  Azure OpenAI   │     │  Azure Cosmos DB                │
│  GPT-4.1        │     │  Mapping history & persistence  │
│  Structured Out │     │                                 │
└─────────────────┘     └─────────────────────────────────┘
```

**Azure Infrastructure** (deployed via Bicep):
- Azure Container Apps (frontend + backend)
- Azure OpenAI (GPT-4.1 with structured outputs)
- Azure Cosmos DB (NoSQL — session & mapping storage)
- Azure Container Registry
- VNet with private endpoints
- Entra ID authentication

---

## Use Cases

### Security Architects
Use the pre-built catalogs to identify Azure Policy definitions and Defender for Cloud controls for your regulatory framework. Extract policy GUIDs and deploy directly via CLI, Bicep, or Terraform.

### Compliance Teams
Upload new compliance framework PDFs to the AI agent for automated mapping. Review and adjust AI-generated mappings through the web UI, then export audit-ready evidence documentation.

### DevOps / Platform Engineers
Deploy Azure Policy initiatives generated by the toolkit. Use the `framework/` directory for ready-made policy initiative JSON and PowerShell deployment scripts.

---

## Documentation

| Document | Description |
|----------|-------------|
| [app/QUICKSTART.md](app/QUICKSTART.md) | 5-minute local setup guide |
| [app/DEPLOYMENT.md](app/DEPLOYMENT.md) | Azure deployment with `azd` |
| [app/TROUBLESHOOTING.md](app/TROUBLESHOOTING.md) | Common issues & fixes |
| [catalogues/CATALOG_SUMMARY.md](catalogues/CATALOG_SUMMARY.md) | Detailed catalog documentation |
| [templates/CONTROL_TEMPLATES_README.md](templates/CONTROL_TEMPLATES_README.md) | Simplified template usage |
| [docs/PROCESS_DOCUMENTATION.md](docs/PROCESS_DOCUMENTATION.md) | End-to-end process guide |

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Author

**Warren du Toit**
Cloud Solution Architect @ Microsoft

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

[Report Bug](https://github.com/warrendt/compliance-iq/issues) · [Request Feature](https://github.com/warrendt/compliance-iq/issues) · [Documentation](docs/PROCESS_DOCUMENTATION.md)

</div>
