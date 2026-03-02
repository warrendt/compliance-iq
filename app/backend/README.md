# Backend - AI Control Mapping Agent

FastAPI backend service for AI-powered compliance control mapping.

## 🚀 Quick Start

### Option 1: Automated Setup (Recommended)

Run the setup script that handles everything:

```bash
cd backend
./setup.sh
```

This script will:
- ✅ Activate the virtual environment
- ✅ Install all dependencies
- ✅ Create `.env` from template if needed
- ✅ Check Azure CLI authentication
- ✅ Optionally start the server

### Option 2: Manual Setup

**1. Activate Virtual Environment**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**2. Install Dependencies**

```bash
cd backend
pip install -r requirements.txt
```

**3. Configure Environment**

```bash
cp .env.template .env
```

Edit `.env` and set your Azure OpenAI details:

```env
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

**4. Authenticate with Azure**

```bash
az login
```

This allows the application to use your Azure CLI credentials for local development.

**5. Start Server**

```bash
uvicorn app.main:app --reload --host localhost --port 8000
```

Or use the quick-start script:

```bash
./start.sh
```

Server will start at: **http://localhost:8000**

## 📚 API Documentation

Once the server is running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/v1/health

## 🔑 API Endpoints

### Health & Status

- `GET /health` - Application health check
- `GET /ping` - Simple ping

### Control Mapping

- `POST /api/v1/mapping/map-single` - Map single control
- `POST /api/v1/mapping/analyze` - Batch mapping (async)
- `GET /api/v1/mapping/status/{job_id}` - Job status
- `GET /api/v1/mapping/mcsb/controls` - Get MCSB controls
- `GET /api/v1/mapping/mcsb/domains` - Get MCSB domains

### Policy Generation

- `POST /api/v1/policy/generate` - Generate initiative
- `POST /api/v1/policy/generate/json` - Download JSON
- `POST /api/v1/policy/generate/bicep` - Download Bicep
- `POST /api/v1/policy/generate/scripts` - Deployment scripts

## 🧪 Testing

### Test Health Check

```bash
curl http://localhost:8000/api/v1/health | jq
```

Expected output:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "azure_openai_connected": true,
  "mcsb_controls_loaded": true,
  "mcsb_control_count": 10
}
```

### Test Single Control Mapping

```bash
curl -X POST http://localhost:8000/api/v1/mapping/map-single \
  -H "Content-Type: application/json" \
  -d '{
    "control": {
      "control_id": "SAMA-AC-01",
      "control_name": "Strong Authentication",
      "description": "Enforce MFA for privileged and user access",
      "domain": "Identity & Access Control"
    }
  }' | jq
```

### Test MCSB Controls Retrieval

```bash
curl http://localhost:8000/api/v1/mapping/mcsb/controls | jq
```

## 🚀 Azure Container Apps Deployment Notes

- Container Apps pull images from ACR using the system-assigned managed identity (AcrPull granted in Bicep). No ACR admin credentials are needed at runtime.
- ACR stays private; a toggle `acrAllowPublicAccess` exists in `infra/main.bicep` to temporarily enable public network access for dev pushes.
- Private endpoints are provisioned for ACR/Cosmos/OpenAI with private DNS; keep client traffic inside the VNet when possible.

## 🏗️ Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── auth/                # Azure authentication
│   │   └── azure_auth.py
│   ├── models/              # Pydantic models
│   │   ├── control.py
│   │   ├── mapping.py
│   │   └── policy.py
│   ├── services/            # Business logic
│   │   ├── mcsb_service.py
│   │   ├── ai_mapping_service.py
│   │   └── policy_service.py
│   ├── api/routes/          # API endpoints
│   │   ├── health.py
│   │   ├── mapping.py
│   │   └── policy.py
│   └── utils/               # Utilities
│       └── parsers.py
├── requirements.txt
├── .env.template
└── README.md
```

## 🔐 Authentication

The backend uses **DefaultAzureCredential** which automatically tries:

1. **Managed Identity** (when deployed to Azure)
2. **Azure CLI** (`az login` - for local development)
3. **Environment Variables** (service principal)

No API keys required!

### Required Azure RBAC Role

Your identity needs the **Cognitive Services OpenAI User** role:

```bash
az role assignment create \
  --role "Cognitive Services OpenAI User" \
  --assignee $(az ad signed-in-user show --query id -o tsv) \
  --scope /subscriptions/{subscription-id}/resourceGroups/{rg}/providers/Microsoft.CognitiveServices/accounts/{openai-resource}
```

## 🎯 Core Features

### AI Mapping Service
- Azure OpenAI GPT-4o with structured outputs
- Confidence scoring (0.0 to 1.0)
- Detailed reasoning for each mapping
- Batch processing with progress tracking

### MCSB Service
- Load MCSB controls from JSON
- Search by keywords, domain, control ID
- Default controls for demonstration

### Policy Generation Service
- Generate Azure Policy initiative JSON
- Export as Bicep template
- Generate deployment scripts (CLI/PowerShell)
- Validate initiative structure

## 🐛 Troubleshooting

### Azure OpenAI Connection Failed

Check:
1. `az login` completed successfully
2. `AZURE_OPENAI_ENDPOINT` is correct in `.env`
3. `AZURE_OPENAI_DEPLOYMENT_NAME` matches your deployment
4. You have the required RBAC role

Test connection:
```python
from app.auth import test_azure_openai_connection
test_azure_openai_connection()  # Should return True
```

### MCSB Controls Not Loading

The service includes 10 default MCSB controls for demonstration. For full MCSB catalog:

1. Download from GitHub SecurityBenchmarks
2. Place JSON at `../data/mcsb/mcsb_v1_controls.json`
3. Restart server

## 📝 Development

### Run with Auto-reload

```bash
uvicorn app.main:app --reload --log-level debug
```

### Run Tests

```bash
pytest tests/ -v --cov=app
```

## 🚢 Deployment

See `/deployment/azure/` for:
- Bicep templates
- Docker configuration
- Azure Container Apps setup

## 📞 Support

For issues or questions:
- Check API docs: http://localhost:8000/docs
- View logs in console
- Review `IMPLEMENTATION_STATUS.md` for architecture details
