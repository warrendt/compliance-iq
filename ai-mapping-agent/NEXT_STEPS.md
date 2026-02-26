# Next Steps - Post-Implementation

## 🎯 Immediate Actions

### 1. Test Local Build (Optional)
```bash
cd ai-mapping-agent

# Test Docker builds
docker build -t cctoolkit-backend ./backend
docker build -t cctoolkit-frontend ./frontend

# Or test with docker-compose
docker-compose up --build
```

### 2. Deploy to Azure
```bash
cd ai-mapping-agent

# You already created the environment: cctoolkit-dev
# Now just deploy!
azd up
```

**Expected duration:** 8-12 minutes

### 3. Verify Deployment
```bash
# Get URLs
azd env get-values | grep URI

# View logs
azd logs --service backend --follow

# Check resources in portal
az portal
```

---

## 🐛 If Deployment Fails

### Common First-Time Issues

1. **"Region doesn't support gpt-4.1"**
   ```bash
   # Use GPT-4o instead
   azd env set AZURE_OPENAI_MODEL_NAME gpt-4o
   azd provision
   ```

2. **"Quota exceeded"**
   - Request quota increase in Azure Portal → Azure OpenAI → Quotas
   - Or try different region: `azd env set AZURE_LOCATION eastus`

3. **"Bicep validation failed"**
   ```bash
   # Validate manually
   az deployment sub validate \
     --location swedencentral \
     --template-file infra/main.bicep \
     --parameters infra/main.parameters.json
   ```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more solutions.

---

## 📊 After Successful Deployment

### 1. Test Application
- Open frontend URL
- Upload sample CSV (use one from `../../catalogues/`)
- Run single mapping
- Run batch mapping
- Download generated Bicep template

### 2. Check Monitoring
- Azure Portal → Application Insights → Live Metrics
- View real-time requests and performance
- Check for any errors

### 3. Verify Persistence
- Make a mapping
- Check Cosmos DB Data Explorer
- Container: `mapping-results`
- Should see documents with your mappings

### 4. Check Costs
- Azure Portal → Cost Management → Cost Analysis
- Filter by resource group: `rg-cctoolkit-dev`
- Verify costs are within expected range (~$0.50/day)

---

## 🔧 Configuration Tweaks

### Enable Authentication (Production)
```bash
# Create Azure AD app registrations (requires Azure AD admin)
az ad app create --display-name "CCToolkit Backend"
# Note the client ID

az ad app create --display-name "CCToolkit Frontend"
# Note the client ID

# Configure environment
azd env set ENABLE_AUTH true
azd env set AZURE_AD_TENANT_ID $(az account show --query tenantId -o tsv)
azd env set AZURE_AD_CLIENT_ID <backend-client-id>
azd env set AZURE_AD_FRONTEND_CLIENT_ID <frontend-client-id>

# Redeploy
azd deploy
```

### Increase OpenAI Quota
- Azure Portal → Azure OpenAI → Quotas
- Request increase for TPM (tokens per minute)
- Default: 10K TPM, can request up to 240K TPM

### Adjust Log Retention
Edit `infra/core/log-analytics.bicep`:
```bicep
retentionInDays: 90  // Change to 30, 60, 90, etc.
```

Then: `azd provision`

---

## 🚀 Production Readiness

### Before Going to Production

1. **Enable Authentication**
   - Set `ENABLE_AUTH=true`
   - Configure Azure AD app registrations
   - Update frontend redirect URIs

2. **Add Custom Domain**
   - Azure Portal → Container App → Custom domains
   - Add CNAME record in DNS
   - Configure managed certificate

3. **Enable VNet Integration**
   - Modify Bicep to add VNet
   - Set Container Apps to internal ingress only
   - Add Application Gateway for public access

4. **Set Up Alerts**
   - Configure action groups (email, Teams, SMS)
   - Set budget alerts
   - Enable health monitoring

5. **Review Security**
   - Disable public access to Container Registry
   - Add IP restrictions (if needed)
   - Enable diagnostic settings on all resources
   - Review Cosmos DB firewall rules

6. **Backup Strategy**
   - Enable Cosmos DB backup (automatic by default)
   - Export policy definitions regularly
   - Document disaster recovery procedure

---

## 🔄 Ongoing Maintenance

### Weekly
- Review cost dashboard
- Check error logs in Application Insights
- Verify no unusual token usage spikes

### Monthly
- Review and clean up old Cosmos DB data (TTL handles this automatically)
- Check for Azure service updates
- Review security recommendations in Azure Security Center
- Update dependencies in requirements.txt

### Quarterly
- Review OpenAI model availability (GPT-4.1 → newer models?)
- Optimize Cosmos DB indexing based on query patterns
- Review and update alert thresholds
- Audit role assignments

---

## 📈 Scaling Considerations

### Current Limits (Consumption Plan)
- Max 10 replicas per container app
- ~10-50 concurrent users
- Cosmos DB serverless: 1M RU/s

### If You Need More Scale

1. **Switch to Dedicated Container Apps Plan**
   ```bicep
   // In container-apps-environment.bicep
   sku: {
     name: 'Consumption'  // Change to 'Dedicated'
   }
   ```

2. **Upgrade Cosmos DB to Provisioned**
   ```bicep
   // In cosmosdb.bicep
   // Remove serverless capability
   // Add throughput settings
   ```

3. **Add Caching Layer**
   - Azure Cache for Redis
   - Cache MCSB control data
   - Cache Azure Policy definitions

4. **Load Balancer / CDN**
   - Azure Front Door for global distribution
   - CDN for static assets

---

## 🎓 Learning Resources

### Recommended Next Steps

1. **Learn Bicep**
   - [MS Learn: Bicep Fundamentals](https://learn.microsoft.com/training/paths/bicep-deploy/)
   - Customize infrastructure templates

2. **Master Container Apps**
   - [MS Learn: Container Apps](https://learn.microsoft.com/training/paths/deploy-manage-container-apps/)
   - Understand scaling, networking, revisions

3. **Deep Dive Application Insights**
   - [MS Learn: Monitor Apps](https://learn.microsoft.com/training/paths/monitor-app-performance-analytics/)
   - Create custom dashboards and workbooks

4. **Cosmos DB Optimization**
   - [MS Learn: Cosmos DB](https://learn.microsoft.com/training/paths/work-with-nosql-data-in-azure-cosmos-db/)
   - Learn query optimization and indexing

---

## 🤝 Contributing

If you improve the deployment:

1. Test changes in dev environment
2. Document changes in IMPLEMENTATION_SUMMARY.md
3. Update DEPLOYMENT.md if user-facing
4. Commit and push

---

## ✅ Implementation Checklist

- [x] Infrastructure-as-Code (Bicep)
- [x] Container configuration (Dockerfiles)
- [x] Logging and monitoring
- [x] Cosmos DB integration
- [x] Azure AD authentication (placeholder)
- [x] GPT-4.1 with fallback
- [x] Deployment documentation
- [x] Troubleshooting guide
- [ ] Deploy to Azure (you're about to do this!)
- [ ] Test application end-to-end
- [ ] Enable authentication (optional)
- [ ] Set up CI/CD (optional)
- [ ] Custom domain (optional)

---

## 📞 Support

- **Documentation:** See [DEPLOYMENT.md](DEPLOYMENT.md) and [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Azure Support:** Azure Portal → Support → New support request
- **Community:** Stack Overflow (tag: azure-container-apps)

---

**Ready to go live? Run `azd up`! 🚀**
