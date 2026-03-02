# Troubleshooting Guide

Common issues and solutions for deploying and running the ComplianceIQ AI Mapping Agent.

## Quick Diagnostics

```bash
# Check all service health
azd show

# View recent logs
azd logs --tail 100

# Check Azure resources
az resource list --resource-group rg-compliance-iq-dev -o table

# Validate Bicep templates
az deployment sub validate \
  --location swedencentral \
  --template-file infra/main.bicep
```

---

## Common Issues

### 1. Authentication Errors

#### "Not logged in to Azure"

**Symptom:** `azd up` fails with authentication error

**Solution:**
```bash
# Login to Azure CLI
az login

# Login to azd
azd auth login

# Verify
az account show
azd auth login --check-status
```

#### "Insufficient permissions"

**Symptom:** Role assignment fails during deployment

**Solution:**
- Ensure you have **Owner** role (or Contributor + User Access Administrator)
- Check permissions: `az role assignment list --assignee $(az account show --query user.name -o tsv)`
- Contact Azure admin if needed

---

### 2. OpenAI Deployment Issues

#### "GPT-4.1 model not available in region"

**Symptom:** OpenAI deployment fails during provisioning

**Solution:**
```bash
# Check available models in region
az cognitiveservices model list \
  --location swedencentral \
  --query "[?name=='gpt-4.1']"

# Use fallback model
azd env set AZURE_OPENAI_MODEL_NAME gpt-4o
azd provision
```

**Regions with GPT-4.1 availability (as of Feb 2026):**
- East US
- West Europe
- Sweden Central (check availability)

#### "Quota exceeded for model deployment"

**Symptom:** `QuotaExceeded` error during OpenAI deployment

**Solution:**
1. Check quota: Azure Portal → Azure OpenAI → Quotas
2. Request quota increase: Azure Portal → Support → New support request
3. Or use different region with available quota

---

### 3. Container App Issues

#### "Container app not starting"

**Symptom:** Container app shows "Provisioning failed" status

**Solution:**
```bash
# Check logs for specific error
azd logs --service backend --tail 50

# Common causes:
# 1. Image pull failure - check Container Registry permissions
# 2. Application startup error - check environment variables
# 3. Health probe failure - check health endpoints

# Verify environment variables
az containerapp show \
  --name ca-backend-<token> \
  --resource-group rg-compliance-iq-dev \
  --query properties.template.containers[0].env -o table
```

#### "Health check failing"

**Symptom:** App shows as unhealthy in Azure Portal

**Solution:**
```bash
# Check health endpoint locally
curl https://your-backend-url.azurecontainerapps.io/api/v1/health/health

# Check Container App logs
azd logs --service backend --follow

# Common issues:
# - Cosmos DB connection failure (check managed identity)
# - OpenAI connection failure (check endpoint/model)
# - Missing environment variables
```

---

### 4. Cosmos DB Issues

#### "Cosmos DB authentication failed"

**Symptom:** Backend logs show 401 Unauthorized from Cosmos DB

**Solution:**
```bash
# Verify managed identity role assignment
az cosmosdb sql role assignment list \
  --account-name cosmos-<token> \
  --resource-group rg-compliance-iq-dev

# Recreate role assignment if missing
azd provision
```

#### "Cosmos DB throttling (429 errors)"

**Symptom:** Intermittent 429 errors in logs

**Solution:**
- Serverless Cosmos DB has RU/s limits
- Reduce concurrent operations in application
- Consider switching to provisioned throughput if sustained high load
- Check metrics: Azure Portal → Cosmos DB → Insights

---

### 5. Networking Issues

#### "Cannot access frontend URL"

**Symptom:** Frontend URL returns connection error

**Solution:**
```bash
# Get actual URL
azd env get-values | grep FRONTEND_URI

# Check Container App status
az containerapp show \
  --name ca-frontend-<token> \
  --resource-group rg-compliance-iq-dev \
  --query properties.managementState

# Check if ingress is enabled
az containerapp show \
  --name ca-frontend-<token> \
  --resource-group rg-compliance-iq-dev \
  --query properties.configuration.ingress
```

#### "CORS errors in browser"

**Symptom:** Browser console shows CORS policy error

**Solution:**
- Update `CORS_ORIGINS` in backend config
- Add frontend URL to allowed origins
- Redeploy backend: `azd deploy backend`

---

### 6. Deployment Failures

#### "Bicep deployment failed"

**Symptom:** `azd provision` fails with ARM deployment error

**Solution:**
```bash
# Get detailed error
az deployment sub show \
  --name <deployment-name> \
  --query properties.error

# Validate template locally
az deployment sub validate \
  --location swedencentral \
  --template-file infra/main.bicep \
  --parameters infra/main.parameters.json

# Common fixes:
# - Resource name conflicts (use unique environment names)
# - Region doesn't support service (try different region)
# - Quota exceeded (request increase or change region)
```

#### "Docker build failed"

**Symptom:** `azd deploy` fails during image build

**Solution:**
```bash
# Test build locally
cd backend
docker build -t test-backend .

cd ../frontend
docker build -t test-frontend .

# Check Dockerfile syntax
# Check requirements.txt dependencies
# Ensure all required files exist
```

---

### 7. Application Errors

#### "OpenAI rate limit errors"

**Symptom:** Logs show 429 errors from OpenAI

**Solution:**
- Azure OpenAI has TPM (tokens per minute) limits
- Check quota: Azure Portal → Azure OpenAI → Quotas
- Implement retry logic (already included)
- Request TPM increase if sustained high usage

#### "Mapping results not saving"

**Symptom:** Data doesn't persist in Cosmos DB

**Solution:**
```bash
# Check if Cosmos DB is configured
azd env get-values | grep COSMOS_DB_ENDPOINT

# Check backend logs for Cosmos errors
azd logs --service backend | grep cosmos

# Verify Cosmos DB containers exist
az cosmosdb sql database show \
  --account-name cosmos-<token> \
  --resource-group rg-compliance-iq-dev \
  --name compliance-iq-db
```

---

## Finding Correlation IDs

Every request has a unique correlation ID for tracing.

### From Response Headers

```bash
# In HTTP response headers
X-Correlation-ID: abc-123-def-456
```

### From Application Logs

```bash
# Search logs by correlation ID
azd logs --service backend | grep "abc-123-def-456"
```

### From Application Insights

```kusto
// Kusto query in Log Analytics
traces
| where customDimensions.correlation_id == "abc-123-def-456"
| order by timestamp desc
```

---

## Useful KQL Queries

Access in Azure Portal → Log Analytics workspace → Logs

### Find All Errors

```kusto
traces
| where severityLevel >= 3  // Error or Critical
| where timestamp > ago(1h)
| project timestamp, message, severityLevel, customDimensions
| order by timestamp desc
| take 50
```

### Find Slow Requests

```kusto
requests
| where duration > 3000  // > 3 seconds
| where timestamp > ago(24h)
| project timestamp, name, duration, resultCode
| order by duration desc
| take 20
```

### Track Specific Request

```kusto
union requests, dependencies, traces
| where operation_Id == "<operation-id>"
| order by timestamp asc
| project timestamp, itemType, name, message, duration
```

### OpenAI Usage

```kusto
traces
| where message contains "openai"
| where timestamp > ago(24h)
| extend model = tostring(customDimensions.model)
| extend tokens = todouble(customDimensions.total_tokens)
| summarize TotalTokens = sum(tokens), RequestCount = count() by model
```

### Cosmos DB Metrics

```kusto
traces
| where message contains "cosmosdb"
| where timestamp > ago(1h)
| extend ru = todouble(customDimensions.ru_consumed)
| summarize TotalRU = sum(ru), AvgRU = avg(ru), RequestCount = count() by bin(timestamp, 5m)
| render timechart
```

---

## Getting Help

### 1. Check Azure Service Health

```bash
# Check for Azure outages
az servicehealth incident list
```

### 2. Enable Debug Logging

```bash
# Set log level to DEBUG
azd env set LOG_LEVEL DEBUG
azd deploy backend

# View detailed logs
azd logs --service backend --follow
```

### 3. Access Azure Portal

```bash
# Open Portal
az portal

# Navigate to:
# - Resource Group: rg-compliance-iq-dev
# - Application Insights: Live Metrics
# - Container Apps: Logs and Monitoring
# - Cosmos DB: Data Explorer and Metrics
```

### 4. Contact Support

- **GitHub Issues:** [Create issue](../issues/new)
- **Azure Support:** Azure Portal → Support → New support request
- **Community:** Azure Container Apps Q&A on Microsoft Learn

---

## Preventive Measures

### Health Monitoring

```bash
# Set up health check endpoint monitoring
az monitor app-insights web-test create \
  --name backend-health-check \
  --resource-group rg-compliance-iq-dev \
  --location swedencentral \
  --web-test-kind ping \
  --frequency 300 \
  --timeout 30 \
  --enabled true \
  --locations "[{\"Id\": \"emea-nl-ams-azr\"}]"
```

### Cost Alerts

```bash
# Set budget alert
az consumption budget create \
  --budget-name compliance-iq-budget \
  --amount 50 \
  --category Cost \
  --time-grain Monthly \
  --start-date 2026-02-01 \
  --end-date 2026-12-31
```

### Regular Updates

```bash
# Update azd to latest version
azd version --check

# Update Azure CLI
az upgrade
```

---

## Still Stuck?

1. **Collect information:**
   - Error messages
   - Correlation IDs
   - Logs from `azd logs`
   - Screenshots if UI issue

2. **Check documentation:**
   - [DEPLOYMENT.md](DEPLOYMENT.md)
   - [Azure Container Apps docs](https://learn.microsoft.com/azure/container-apps/)

3. **Create detailed issue:**
   - Include error messages
   - Steps to reproduce
   - Environment details (`azd env get-values`)

---

**Remember:** Most issues are related to permissions, region availability, or configuration. Double-check environment variables and Azure resources first!
