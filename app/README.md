# 🛡️ AI-Powered Control Mapping Agent

Automatically map compliance framework controls to Microsoft Cloud Security Benchmark (MCSB) and generate Azure Policy initiatives using AI.

## 🎯 Overview

This AI agent automates the manual process of mapping external compliance framework controls to the Microsoft Cloud Security Benchmark and generates deployable Azure Policy custom initiatives.

### Key Features

- **🤖 Intelligent Control Mapping**: Uses Azure OpenAI GPT-4.1 to analyze and map controls
- **📊 Structured Outputs**: Enforces JSON schema for consistent, validated mappings
- **🔐 Secure Authentication**: DefaultAzureCredential (Managed Identity + Azure CLI)
- **✏️ Interactive Review**: Web-based UI to review and adjust AI mappings
- **📦 Policy Generation**: Creates valid Azure Policy initiative JSON
- **🏛️ Sovereign Landing Zone (SLZ)**: AI-recommended sovereignty levels (L1/L2/L3) with per-archetype policy exports
- **⚡ End-to-End Pipeline**: Upload → Map → Review → Export (MCSB + SLZ)

## 🏗️ Architecture

```
┌──────────────────────────────────────────┐
│    Streamlit Web Interface (8501)        │
│  Upload │ Map │ Review │ Export (SLZ)    │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│    FastAPI Backend (8000)                │
│  • MCSB Loader                           │
│  • AI Mapping Service (MCSB + SLZ)       │
│  • Sovereignty Service                   │
│  • Policy Generator (Generic + SLZ)      │
│  • Microsoft Learn Client                │
└────────────────┬─────────────────────────┘
                 │
          ┌──────┴──────┐
          ▼             ▼
┌──────────────┐ ┌─────────────────────────┐
│ Azure OpenAI │ │ Azure Landing Zones Lib  │
│  GPT-4.1    │ │  SLZ Policy Definitions  │
│  Structured  │ │  Initiatives & Assign.   │
│  Outputs     │ │  Sovereignty Objectives  │
└──────────────┘ └─────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Azure OpenAI resource with GPT-4.1 deployment
- Azure CLI (for local development)

### 1. Clone and Setup

```bash
# Navigate to project directory
cd app

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Install frontend dependencies
cd ../frontend
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy environment template
cd backend
cp .env.template .env

# Edit .env with your Azure OpenAI details
nano .env
```

**Required settings**:
```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1
```

### 3. Authenticate with Azure

```bash
# Login to Azure (for local development)
az login

# Verify you can access Azure OpenAI
az account show
```

### 4. Start Backend Server

```bash
cd backend
uvicorn app.main:app --reload --host localhost --port 8000
```

Backend will be available at: http://localhost:8000

API docs: http://localhost:8000/docs

### 5. Start Frontend (New Terminal)

```bash
cd frontend
streamlit run app.py
```

Frontend will open in your browser at: http://localhost:8501

## 📖 Usage

### Step 1: Upload Framework Controls

1. Navigate to "📁 Upload Controls" page
2. Upload your CSV/Excel file with columns:
   - `Control ID`
   - `Control Name`
   - `Description`
   - `Domain` (optional)
3. Preview and validate the upload

**Example CSV**:
```csv
Control ID,Control Name,Description,Domain
SAMA-AC-01,Strong Authentication,Enforce MFA for all access,Identity & Access Control
SAMA-NS-01,Network Segmentation,Implement network segmentation,Network Security
```

### Step 2: AI Mapping

1. Navigate to "🤖 AI Mapping" page
2. Click "Start AI Mapping"
3. Monitor progress as AI maps each control to MCSB
4. View confidence scores and reasoning

### Step 3: Review & Edit

1. Navigate to "✏️ Review & Edit" page
2. Review mappings in interactive table
3. Edit MCSB assignments if needed
4. Filter by confidence score
5. Flag low-confidence mappings for manual review

### Step 4: Export Policy Initiative

1. Navigate to "📦 Export Policy" page
2. Enter framework name
3. Click "Generate Policy Initiative"
4. Download JSON for Azure Portal import

### Step 5: PDF Pipeline (end-to-end)

1. Open **🚀 PDF Pipeline** page
2. Upload a compliance PDF, set min confidence and optional allowed locations
3. Wait for completion (extract → map → validate → generate)
4. Use **Review & Edit Mappings** to adjust control-to-policy mappings inline
5. Edit mappings inline and either:
  - Download the edited mappings CSV, or
  - Repack and download a new initiative ZIP with your edits applied
6. Deploy with the provided PowerShell/CLI scripts

## 🔧 Project Structure

```
app/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── auth/              # Azure authentication
│   │   ├── models/            # Pydantic models
│   │   │   ├── control.py     # Control models
│   │   │   ├── mapping.py     # Mapping models (+ sovereignty field)
│   │   │   ├── policy.py      # Policy initiative models
│   │   │   └── sovereignty.py # SLZ / sovereignty models (NEW)
│   │   ├── services/          # Business logic
│   │   │   ├── ai_mapping_service.py   # AI mapping (MCSB + SLZ)
│   │   │   ├── mcsb_service.py         # MCSB control loader
│   │   │   ├── microsoft_learn_client.py # MS Learn policy search
│   │   │   ├── policy_service.py       # Policy gen (+ SLZ initiatives)
│   │   │   └── sovereignty_service.py  # SLZ data service (NEW)
│   │   ├── api/routes/        # API endpoints
│   │   │   ├── health.py      # Health checks (+ SLZ status)
│   │   │   ├── mapping.py     # Control mapping
│   │   │   ├── policy.py      # Policy gen (+ SLZ endpoint)
│   │   │   └── sovereignty.py # Sovereignty API (NEW)
│   │   ├── data/              # Pre-bundled SLZ data
│   │   │   ├── slz_policies.json
│   │   │   └── slz_archetypes.json
│   │   ├── config.py          # Configuration
│   │   └── main.py            # FastAPI app
│   ├── scripts/
│   │   └── sync_slz_policies.py  # SLZ data sync script
│   ├── requirements.txt
│   └── .env.template
│
├── frontend/                   # Streamlit frontend
│   ├── pages/                 # Multi-page app
│   │   ├── 1_📁_Upload_Controls.py
│   │   ├── 2_🤖_AI_Mapping.py    # Shows SLZ level badges
│   │   ├── 3_✏️_Review_Edit.py    # Sovereignty filter + panels
│   │   └── 4_📦_Export_Policy.py  # MCSB + SLZ export tabs
│   ├── utils/                 # API client (+ SLZ methods)
│   ├── app.py                 # Main app (SLZ status in sidebar)
│   └── requirements.txt
│
├── data/                      # Reference data
│   ├── mcsb/                  # MCSB controls
│   └── examples/              # Sample files
│
├── tests/                     # Test suite
├── docs/                      # Documentation
└── README.md
```

## 🧪 Testing

### Backend Tests

```bash
cd backend
pytest tests/ -v --cov=app
```

### Test Azure OpenAI Connection

```python
from app.auth import test_azure_openai_connection

if test_azure_openai_connection():
    print("✅ Azure OpenAI connection successful")
else:
    print("❌ Connection failed")
```

## 🔐 Authentication

This application uses **DefaultAzureCredential** which automatically detects:

1. **Local Development**: Azure CLI credentials (`az login`)
2. **Azure Deployment**: Managed Identity (system or user-assigned)
3. **Environment Variables**: Service principal credentials

**No API keys required** - authentication is handled via Azure AD tokens.

### RBAC Requirements

Your identity (user or managed identity) needs:
- **Cognitive Services OpenAI User** role on Azure OpenAI resource

```bash
# Grant role to current user
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --scope /subscriptions/{subscription-id}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{openai-resource}
```

## 📊 Example Workflow

**Input** (SAMA Framework CSV):
```csv
Control ID,Control Name,Description
SAMA-AC-01,Strong Authentication,Enforce MFA and disable legacy protocols
```

**AI Mapping Output**:
```json
{
  "external_control_id": "SAMA-AC-01",
  "mcsb_control_id": "IM-6",
  "confidence_score": 0.92,
  "reasoning": "Both controls focus on enforcing MFA...",
  "azure_policy_ids": ["4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"]
}
```

**Generated Policy Initiative**:
```json
{
  "properties": {
    "displayName": "SAMA Compliance Initiative",
    "policyDefinitions": [
      {
        "policyDefinitionId": "/providers/Microsoft.Authorization/policyDefinitions/4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b",
        "policyDefinitionReferenceId": "SAMA-AC-01"
      }
    ]
  }
}
```

## 🏛️ Sovereign Landing Zone (SLZ) Integration

The agent also maps controls to Microsoft's Sovereign Landing Zone policies, assigning:

### Sovereignty Levels
| Level | Name | Description |
|-------|------|-------------|
| **L1** | Global | Data residency + Trusted Launch |
| **L2** | CMK | Customer-Managed Keys (includes L1) |
| **L3** | Confidential | Confidential Computing (includes L1+L2) |

### Sovereignty Objectives
| ID | Objective | Type |
|----|-----------|------|
| SO-1 | Data Residency | Policy-enforced |
| SO-2 | Customer Lockbox | Procedural only |
| SO-3 | Customer-Managed Keys | Policy-enforced |
| SO-4 | Confidential Computing | Policy-enforced |
| SO-5 | Trusted Launch | Policy-enforced |

### SLZ Archetypes
- **sovereign_root** — Foundation policies for all SLZ deployments
- **confidential_corp** — Corporate workloads requiring confidential computing
- **confidential_online** — Internet-facing workloads with sovereignty
- **public** — Standard Azure workloads with baseline sovereignty

### SLZ Data Sync

```bash
# Sync from Azure Landing Zones Library (requires git)
cd backend
python3 scripts/sync_slz_policies.py --output-dir app/data

# Or generate fallback data (no git/network required)
python3 scripts/sync_slz_policies.py --fallback --output-dir app/data
```

### SLZ Export

The Export page generates per-archetype packages:
- **JSON** — Policy initiative definition
- **Bicep** — Management-group-scoped template
- **Azure CLI** — Deployment shell script
- **PowerShell** — Deployment PS1 script

## 🚢 Deployment

### Local Development

Already covered in Quick Start above.

### Azure Container Apps (Recommended)

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment guide.

Quick deploy:
```bash
cd deployment/azure/bicep
az deployment group create \
  --resource-group rg-compliance-iq \
  --template-file main.bicep
```

## 📚 API Documentation

Once backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

**Mapping:**
- `POST /api/v1/mapping/map-single` - Map a single control (MCSB + SLZ)
- `POST /api/v1/mapping/analyze` - Batch-map controls
- `GET /api/v1/mapping/status/{job_id}` - Check mapping progress

**Policy Generation:**
- `POST /api/v1/policy/generate` - Generate MCSB policy initiative
- `POST /api/v1/policy/generate/slz` - Generate SLZ per-archetype initiatives
- `POST /api/v1/policy/generate/bicep` - Download Bicep template
- `POST /api/v1/policy/generate/scripts` - Get deployment scripts

**Sovereignty (SLZ):**
- `GET /api/v1/sovereignty/summary` - SLZ data summary
- `GET /api/v1/sovereignty/policies` - Query SLZ policies (level, service, objective, search)
- `GET /api/v1/sovereignty/objectives` - List sovereignty objectives (SO-1 to SO-5)
- `GET /api/v1/sovereignty/archetypes` - List SLZ archetypes
- `POST /api/v1/sovereignty/admin/sync-slz` - Sync SLZ data from Azure repo

**Health:**
- `GET /api/v1/health` - Health check (MCSB + SLZ + Azure OpenAI status)

## 🤝 Contributing

This is part of the Cloud Compliance Toolkit (ComplianceIQ) project.

See existing frameworks in `/catalogues` for reference mappings.

## 📝 License

MIT License - Same as parent ComplianceIQ repository

## 🙏 Acknowledgments

- Microsoft Cloud Security Benchmark team
- Azure OpenAI service
- Existing ComplianceIQ framework mappings (SAMA, CCC, ADHICS, SITA)

## 🔗 Related Resources

- [Microsoft Cloud Security Benchmark](https://learn.microsoft.com/en-us/security/benchmark/azure/introduction)
- [Azure Policy Documentation](https://learn.microsoft.com/en-us/azure/governance/policy/)
- [Azure OpenAI Structured Outputs](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs)
- [ComplianceIQ Repository](../README.md)

---

**Built with ❤️ by the Cloud Compliance Toolkit team**
