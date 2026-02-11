#!/bin/bash
# Pre-provision checks before Azure deployment

set -e

echo "======================================"
echo "Pre-Provisioning Checks"
echo "======================================"

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo "❌ Error: Azure CLI is not installed"
    echo "   Install from: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi
echo "✅ Azure CLI found: $(az version --query '"azure-cli"' -o tsv)"

# Check Azure login
if ! az account show &> /dev/null; then
    echo "❌ Error: Not logged in to Azure"
    echo "   Run: az login"
    exit 1
fi
echo "✅ Azure authentication verified"

# Display current subscription
SUBSCRIPTION_NAME=$(az account show --query name -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo "✅ Current subscription: $SUBSCRIPTION_NAME ($SUBSCRIPTION_ID)"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "⚠️  Warning: Docker is not installed"
    echo "   azd will handle container builds, but local testing won't be available"
else
    echo "✅ Docker found: $(docker --version)"
fi

echo ""
echo "======================================"
echo "All checks passed!"
echo "======================================"

exit 0
