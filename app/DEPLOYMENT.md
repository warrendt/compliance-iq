# Deployment Guide - Azure Cloud Deployment

Complete guide for deploying the CCToolkit AI Mapping Agent to Azure using Azure Developer CLI (azd).

## Overview

This deployment uses:
- **Azure Container Apps** (Consumption plan) - Serverless containers that scale to zero
- **Azure Cosmos DB** (Serverless) - NoSQL database for mapping results and audit logs  
- **Azure OpenAI** (GPT-4.1 with GPT-4o fallback) - AI model for control mapping
- **Application Insights** - Monitoring, logging, and telemetry
- **Managed Identity** - Secure, keyless authentication

**Cost:** ~$5-15/month + OpenAI usage (scales to zero when idle)

---

## Prerequisites

### Required Tools

1. **Azure CLI** - [Install](https://docs.microsoft.com/cli/azure/install-azure-cli)
   ```bash
   az --version
   ```

2. **Azure Developer CLI (azd)** - [Install](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
   ```bash
   azd version
   ```

3. **Docker** (optional for local testing) - [Install](https://docs.docker.com/get-docker/)
   ```bash
   docker --version
   ```

### Azure Permissions

- **Owner** role on Azure subscription (or Contributor + User Access Administrator)
- Ability to create Azure AD app registrations (optional, for authentication)

---

## Quick Start (5 Minutes)

### 1. Clone and Navigate

```bash
cd ai-mapping-agent
```

### 2. Login to Azure

```bash
# Login to Azure
az login

# Login to azd
azd auth login

# Set subscription (if you have multiple)
az account set --subscription "<subscription-id-or-name>"
```

### 3. Initialize Environment

```bash
# Create new environment
azd env new cctoolkit-dev

# Or use existing environment
azd env select cctoolkit-dev
```

### 4. Deploy Everything

```bash
# One command to deploy all infrastructure and applications
azd up
```

**What happens:**
1. Prompts for Azure region (defaults to Sweden Central)
2. Creates resource group: `rg-cctoolkit-dev`
3. Provisions infrastructure (Cosmos DB, OpenAI, Container Apps, etc.)
4. Builds Docker images
5. Pushes images to Azure Container Registry
6. Deploys containers to Azure Container Apps
7. Assigns managed identity roles
8. Displays frontend URL

**Duration:** ~8-12 minutes

### 5. Access Application

```bash
# Frontend URL is displayed after deployment
# Example: https://ca-frontend-abc123.swedencentral-01.azurecontainerapps.io
```

---

## Detailed Deployment Steps

### Option A: Deploy with Default Settings

```bash
azd up
```

Uses defaults:
- Model: gpt-4.1 (falls back to gpt-4o if unavailable)
- Region: Sweden Central
- Authentication: Disabled

### Option B: Customize Deployment

```bash
# Set custom region
azd env set AZURE_LOCATION eastus

# Use specific model
azd env set AZURE_OPENAI_MODEL_NAME gpt-4o

# View all environment variables
azd env get-values
```

### Option C: Deploy Infrastructure Only

```bash
# Provision infrastructure without deploying apps
azd provision

# Deploy apps later
azd deploy
```

---

## Post-Deployment Configuration

### 1. Verify Deployment

```bash
# Check deployment status
azd show

# View application logs
azd logs --service backend --follow
azd logs --service frontend --follow

# Open Azure Portal
az portal
```

### 2. Test Application

```bash
# Get frontend URL
azd env get-values | grep FRONTEND_URI

# Open in browser
open $(azd env get-values | grep FRONTEND_URI | cut -d '=' -f2)
```

### 3. (Optional) Enable Azure AD Authentication

**Currently, auth is disabled by default for easier testing.**

To enable:

#### A. Create Azure AD App Registrations

```bash
# Backend API app registration
az ad app create \
  --display-name "CCToolkit Backend API" \
  --sign-in-audience AzureADMyOrg \
  --enable-id-token-issuance true

# Note the Application (client) ID
BACKEND_CLIENT_ID="<client-id-from-output>"

# Frontend SPA app registration  
az ad app create \
  --display-name "CCToolkit Frontend" \
  --sign-in-audience AzureADMyOrg \
  --enable-id-token-issuance true \
  --enable-access-token-issuance true \
  --spa-redirect-uris "https://your-frontend-url.azurecontainerapps.io"

FRONTEND_CLIENT_ID="<client-id-from-output>"
```

#### B. Configure Application

```bash
# Set environment variables
azd env set ENABLE_AUTH true
azd env set AZURE_AD_TENANT_ID $(az account show --query tenantId -o tsv)
azd env set AZURE_AD_CLIENT_ID $BACKEND_CLIENT_ID
azd env set AZURE_AD_FRONTEND_CLIENT_ID $FRONTEND_CLIENT_ID

# Redeploy
azd deploy
```

---

## Environment Variables Reference

### Required
- `AZURE_ENV_NAME` - Environment name (e.g., dev, prod)
- `AZURE_LOCATION` - Azure region (default: swedencentral)
- `AZURE_SUBSCRIPTION_ID` - Azure subscription ID

### Optional
- `AZURE_OPENAI_MODEL_NAME` - Model to deploy (default: gpt-4.1)
- `AZURE_OPENAI_FALLBACK_MODEL` - Fallback model (default: gpt-4o)
- `ENABLE_AUTH` - Enable Azure AD auth (default: false)
- `AZURE_AD_TENANT_ID` - Azure AD tenant ID
- `AZURE_AD_CLIENT_ID` - Backend API client ID
- `AZURE_AD_FRONTEND_CLIENT_ID` - Frontend client ID

---

## Managing Deployments

### Update Application Code

```bash
# Rebuild and redeploy
azd deploy

# Deploy specific service
azd deploy backend
azd deploy frontend
```

### Update Infrastructure

```bash
# Edit infra/main.bicep or modules
# Then run:
azd provision

# Or full update:
azd up
```

### View Logs

```bash
# Real-time logs
azd logs --follow

# Specific service
azd logs --service backend --follow

# Last 100 lines
azd logs --tail 100
```

### Monitor Resources

```bash
# Open Azure Portal
az portal

# View resource group
az group show --name rg-cctoolkit-dev

# View Container Apps
az containerapp list --resource-group rg-cctoolkit-dev -o table
```

---

## Cleanup / Teardown

### Delete Everything

```bash
# Delete all Azure resources
azd down

# Also delete Azure AD app registrations
azd down --force --purge

# Or manually
az ad app delete --id $BACKEND_CLIENT_ID
az ad app delete --id $FRONTEND_CLIENT_ID
```

### Delete Just the Environment

```bash
# Keeps Azure resources, removes local environment
azd env delete cctoolkit-dev
```

---

## Multiple Environments

### Development

```bash
azd env new cctoolkit-dev
azd env set AZURE_LOCATION swedencentral
azd up
```

### Production

```bash
azd env new cctoolkit-prod
azd env set AZURE_LOCATION eastus
azd env set ENABLE_AUTH true
azd up
```

### Switch Environments

```bash
# List environments
azd env list

# Switch
azd env select cctoolkit-prod

# Auto-selects env for commands
azd logs --service backend
```

---

## Local Testing (Before Azure Deployment)

### 1. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.template .env

# Edit .env with your Azure OpenAI credentials
# (Use existing Azure OpenAI resource or create one)

# Run backend
uvicorn app.main:app --reload
```

### 2. Setup Frontend

```bash
cd frontend

# Create virtual environment  
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set backend URL
export BACKEND_URL=http://localhost:8000

# Run frontend
streamlit run app.py
```

### 3. Docker Compose Testing

```bash
# Build and run both services
docker-compose up --build

# Access
# Frontend: http://localhost:8501
# Backend:  http://localhost:8000/docs

# Stop
docker-compose down
```

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

### Quick Checks

```bash
# Check azd is logged in
azd auth login --check-status

# Validate Bicep templates
az deployment sub validate \
  --location swedencentral \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json

# Check Docker builds locally
docker build -t cctoolkit-backend ./backend
docker build -t cctoolkit-frontend ./frontend
```

---

## Cost Management

### Estimated Monthly Costs

| Service | Configuration | Est. Cost |
|---------|--------------|-----------|
| Container Apps (2) | Consumption, scale-to-zero | $0-5 |
| Cosmos DB | Serverless, 1GB storage | $1-5 |
| OpenAI GPT-4.1 | Pay-per-token | Variable* |
| Container Registry | Basic | $5 |
| Log Analytics | First 5GB free | $0-2 |
| Application Insights | Included with Log Analytics | $0 |
| **Total (excl. OpenAI)** | | **~$6-17/month** |

*OpenAI costs depend on usage. Example: 1M tokens ≈ $10-30 depending on model.

### Cost Optimization Tips

1. **Enable scale-to-zero** (default) - Containers stop when idle
2. **Set Cosmos DB TTL** (default: 30 days) - Auto-delete old data
3. **Monitor OpenAI usage** - Set budget alerts in Azure Portal
4. **Use dev/prod environments** - Delete dev when not actively developing
5. **Review costs daily** - Azure Cost Management

```bash
# View current costs
az consumption usage list --start-date 2026-02-01 --end-date 2026-02-28
```

---

## Support

- **Issues:** [GitHub Issues](../issues)
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Azure Docs:** [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- **azd Docs:** [Azure Developer CLI](https://learn.microsoft.com/azure/developer/azure-developer-cli/)

---

## Next Steps

1. ✅ Deploy to Azure with `azd up`
2. 📊 View Application Insights dashboards
3. 🔐 Configure Azure AD authentication (optional)
4. 🚀 Test AI mapping with sample controls
5. 📈 Monitor usage and costs
6. 🔄 Set up CI/CD pipeline (GitHub Actions)

---

**Deployed successfully? 🎉**

Access your application and start mapping controls to Azure policies!
