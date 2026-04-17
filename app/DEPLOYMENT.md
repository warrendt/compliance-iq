# Deployment Guide - Azure Cloud Deployment

Complete guide for deploying the ComplianceIQ AI Mapping Agent to Azure using Azure Developer CLI (azd).

## Overview

This deployment uses:
- **Azure Container Apps** (Consumption plan) - Serverless containers that scale to zero
- **Azure Cosmos DB** (Serverless) - NoSQL database for mapping results and audit logs  
- **Azure OpenAI** (configurable model) - AI model for control mapping
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
cd app
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
azd env new compliance-iq-dev

# Or use existing environment
azd env select compliance-iq-dev
```

### 4. Deploy Everything

```bash
# One command to deploy all infrastructure and applications
azd up
```

**What happens:**
1. Prompts for Azure region (defaults to Sweden Central)
2. Creates resource group `rg-<environment>` by default, or uses `AZURE_RESOURCE_GROUP` when set
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
- Model: configurable (you will be prompted to choose during `azd up`)
- Region: Sweden Central
- Authentication: Disabled

### Option B: Customize Deployment

```bash
# Set custom region
azd env set AZURE_LOCATION eastus

# Use an explicit resource group name
azd env set AZURE_RESOURCE_GROUP wdt-ciq-dev

# Prefix resource names (the template appends a short unique suffix)
azd env set AZURE_NAME_PREFIX ciqdev

# Override model selection (skips the interactive prompt)
azd env set AZURE_OPENAI_MODEL_NAME <model-name>

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

### 3. (Optional) Enable Entra ID Authentication

Authentication is **disabled by default** for easier testing.  When enabled,
the frontend Container App uses **Easy Auth v2** (built-in Entra ID) and the
backend validates tokens via `fastapi-azure-auth`.

To enable it, set the `AUTH_CLIENT_ID` (and optionally `AUTH_TENANT_ID`)
environment variables **before** running `azd up`.  If these are left empty,
authentication is skipped entirely.

#### A. Create an Entra ID App Registration

```bash
# Create a single app registration for both frontend Easy Auth and backend API
az ad app create \
  --display-name "ComplianceIQ" \
  --sign-in-audience AzureADMyOrg \
  --enable-id-token-issuance true \
  --enable-access-token-issuance true \
  --web-redirect-uris "https://<your-frontend-url>/.auth/login/aad/callback"

# Note the Application (client) ID from the output
# You can also find it in the Azure Portal → App registrations
```

#### B. Wire it into the `azd` Environment

```bash
# Set the app registration client ID (this enables auth)
azd env set AUTH_CLIENT_ID <your-app-registration-client-id>

# Required for Easy Auth to return delegated access tokens to the frontend/backed flow
azd env set AUTH_CLIENT_SECRET <your-app-registration-client-secret>

# (Optional) Override the tenant — defaults to the deployment tenant
azd env set AUTH_TENANT_ID <your-tenant-id>

# Deploy (or redeploy)
azd up
```

> The Entra app registration also needs delegated permission for
> `https://management.azure.com/user_impersonation` with tenant consent if you
> want the authenticated `/api/v1/deploy` flow to work in production.

The `preprovision` hook will confirm whether auth is enabled or disabled.
The `postprovision` hook will show the auth status in the deployment summary.

#### C. How It Works

| Component | Auth Mechanism |
|-----------|---------------|
| **Frontend Container App** | Easy Auth v2 (Container Apps built-in) redirects unauthenticated users to the Entra ID login page |
| **Backend Container App** | Internal-only ingress — accepts trusted Easy Auth headers forwarded by the frontend, or bearer tokens for local MSAL development |
| **Bicep** | `container-app.bicep` deploys an `authConfig` resource **only** when `authClientId` is non-empty |

#### D. Disable Authentication

Simply leave `AUTH_CLIENT_ID` unset (or empty) and redeploy:

```bash
azd env set AUTH_CLIENT_ID ""
azd up
```

---

## Environment Variables Reference

### Required
- `AZURE_ENV_NAME` - Environment name (e.g., dev, prod)
- `AZURE_LOCATION` - Azure region (default: swedencentral)
- `AZURE_SUBSCRIPTION_ID` - Azure subscription ID

### Optional
- `AZURE_RESOURCE_GROUP` - Explicit resource group name override (defaults to `rg-<environment>`)
- `AZURE_NAME_PREFIX` - Optional resource naming prefix; separators are stripped and a short unique suffix is appended
- `AZURE_OPENAI_MODEL_NAME` - Model to deploy (prompted during `azd up` if not set)
- `AZURE_OPENAI_FALLBACK_MODEL` - Fallback model if primary is unavailable
- `AUTH_CLIENT_ID` - Entra ID App Registration client ID (enables Easy Auth on frontend; leave empty to disable)
- `AUTH_CLIENT_SECRET` - Entra ID App Registration client secret (required for Easy Auth token store and delegated ARM tokens)
- `AUTH_TENANT_ID` - Entra ID tenant ID (defaults to deployment tenant when empty)
- `DEV_PUBLIC_IP` - Developer public IP for resource firewall rules

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
az group show --name <your-resource-group>

# View Container Apps
az containerapp list --resource-group <your-resource-group> -o table
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
azd env delete compliance-iq-dev
```

---

## Multiple Environments

### Development

```bash
azd env new compliance-iq-dev
azd env set AZURE_LOCATION swedencentral
azd up
```

### Production

```bash
azd env new compliance-iq-prod
azd env set AZURE_LOCATION eastus
azd env set ENABLE_AUTH true
azd up
```

### Switch Environments

```bash
# List environments
azd env list

# Switch
azd env select compliance-iq-prod

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
docker build -t compliance-iq-backend ./backend
docker build -t compliance-iq-frontend ./frontend
```

---

## Cost Management

### Estimated Monthly Costs

| Service | Configuration | Est. Cost |
|---------|--------------|-----------|
| Container Apps (2) | Consumption, scale-to-zero | $0-5 |
| Cosmos DB | Serverless, 1GB storage | $1-5 |
| Azure OpenAI | Pay-per-token | Variable* |
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
