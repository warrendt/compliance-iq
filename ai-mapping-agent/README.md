# 🛡️ AI-Powered Control Mapping Agent

Automatically map compliance framework controls to Microsoft Cloud Security Benchmark (MCSB) and generate Azure Policy initiatives using AI.

## 🎯 Overview

This AI agent automates the manual process of mapping external compliance framework controls to the Microsoft Cloud Security Benchmark and generates deployable Azure Policy custom initiatives.

### Key Features

- **🤖 Intelligent Control Mapping**: Uses Azure OpenAI GPT-4o to analyze and map controls
- **📊 Structured Outputs**: Enforces JSON schema for consistent, validated mappings
- **🔐 Secure Authentication**: DefaultAzureCredential (Managed Identity + Azure CLI)
- **✏️ Interactive Review**: Web-based UI to review and adjust AI mappings
- **📦 Policy Generation**: Creates valid Azure Policy initiative JSON
- **⚡ End-to-End Pipeline**: Upload → Map → Review → Export

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│   Streamlit Web Interface (8501)   │
│  Upload │ Map │ Review │ Export     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   FastAPI Backend (8000)            │
│  • MCSB Loader                      │
│  • AI Mapping Service               │
│  • Policy Generator                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Azure OpenAI (GPT-4o)             │
│  • Structured outputs                │
│  • Control analysis                  │
│  • Confidence scoring                │
└─────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Azure OpenAI resource with GPT-4o deployment
- Azure CLI (for local development)

### 1. Clone and Setup

```bash
# Navigate to project directory
cd ai-mapping-agent

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
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
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

## 🔧 Project Structure

```
ai-mapping-agent/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── auth/              # Azure authentication
│   │   ├── models/            # Pydantic models
│   │   ├── services/          # Business logic
│   │   ├── api/routes/        # API endpoints
│   │   ├── config.py          # Configuration
│   │   └── main.py            # FastAPI app
│   ├── requirements.txt
│   └── .env.template
│
├── frontend/                   # Streamlit frontend
│   ├── pages/                 # Multi-page app
│   ├── components/            # Reusable UI components
│   ├── utils/                 # API client
│   ├── app.py                 # Main app
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

## 🚢 Deployment

### Local Development

Already covered in Quick Start above.

### Azure Container Apps (Recommended)

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment guide.

Quick deploy:
```bash
cd deployment/azure/bicep
az deployment group create \
  --resource-group rg-cctoolkit \
  --template-file main.bicep
```

## 📚 API Documentation

Once backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

- `POST /api/v1/mapping/analyze` - Upload and map controls
- `GET /api/v1/mapping/status/{job_id}` - Check mapping progress
- `POST /api/v1/policy/generate` - Generate policy initiative
- `GET /api/health` - Health check

## 🤝 Contributing

This is part of the Cloud Compliance Toolkit (CCToolkit) project.

See existing frameworks in `/catalogues` for reference mappings.

## 📝 License

MIT License - Same as parent CCToolkit repository

## 🙏 Acknowledgments

- Microsoft Cloud Security Benchmark team
- Azure OpenAI service
- Existing CCToolkit framework mappings (SAMA, CCC, ADHICS, SITA)

## 🔗 Related Resources

- [Microsoft Cloud Security Benchmark](https://learn.microsoft.com/en-us/security/benchmark/azure/introduction)
- [Azure Policy Documentation](https://learn.microsoft.com/en-us/azure/governance/policy/)
- [Azure OpenAI Structured Outputs](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/structured-outputs)
- [CCToolkit Repository](../README.md)

---

**Built with ❤️ by the Cloud Compliance Toolkit team**
