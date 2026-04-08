# Azure Deployment - Quick Reference

## 🚀 Deploy in 3 Commands

```bash
# 1. Login
azd auth login

# 2. Create environment
azd env new compliance-iq-dev

# 3. Deploy everything
azd up
```

**That's it!** Your application will be live in ~10 minutes.

---

## 📋 What Gets Deployed

- ✅ 2 Container Apps (backend + frontend)
- ✅ Azure Cosmos DB (serverless)
- ✅ Azure OpenAI (model selected during setup)
- ✅ Container Registry
- ✅ Application Insights + Log Analytics
- ✅ Managed Identity with RBAC

**All in one resource group, all with managed identity (no secrets!).**

---

## 🔧 Useful Commands

```bash
# View application URL
azd env get-values | grep FRONTEND_URI

# View logs
azd logs --service backend --follow

# Redeploy after code changes
azd deploy

# Update infrastructure
azd provision

# Delete everything
azd down --purge
```

---

## 📚 Full Documentation

- **Complete Guide:** [DEPLOYMENT.md](DEPLOYMENT.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Application Guide:** [README.md](README.md)

---

## 💰 Cost

~$5-15/month + OpenAI usage (scales to zero when idle)

---

## 🆘 Need Help?

```bash
# Check deployment status
azd show

# Validate templates
az deployment sub validate --location swedencentral --template-file infra/main.bicep

# Get detailed logs
azd logs --tail 100
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for solutions to common issues.
