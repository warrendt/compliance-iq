#!/bin/bash
# Post-deployment script

set -e

echo ""
echo "======================================"
echo "📦 Deployment Complete!"
echo "======================================"
echo ""

# Display environment info
ENV_NAME=${AZURE_ENV_NAME:-"unknown"}
RESOURCE_GROUP=${AZURE_RESOURCE_GROUP:-"unknown"}
LOCATION=${AZURE_LOCATION:-"unknown"}

echo "Environment Details:"
echo "-------------------"
echo "Environment Name: $ENV_NAME"
echo "Resource Group:   $RESOURCE_GROUP"
echo "Location:         $LOCATION"
echo ""

# Display application URLs
FRONTEND_URI=${FRONTEND_URI:-"Not available"}
BACKEND_URI=${BACKEND_URI:-"Not available"}

echo "Application URLs:"
echo "-----------------"
echo "Frontend (Public):  $FRONTEND_URI"
echo "Backend  (Internal): $BACKEND_URI"
echo ""

# Display OpenAI info
OPENAI_MODEL=${AZURE_OPENAI_DEPLOYMENT_NAME:-"unknown"}
OPENAI_VERSION=${AZURE_OPENAI_API_VERSION:-"unknown"}

echo "Azure OpenAI Configuration:"
echo "---------------------------"
echo "Model:       $OPENAI_MODEL"
echo "API Version: $OPENAI_VERSION"
echo ""

# Display Cosmos DB info
COSMOS_DB=${COSMOS_DB_DATABASE_NAME:-"unknown"}

echo "Cosmos DB Configuration:"
echo "------------------------"
echo "Database: $COSMOS_DB"
echo ""

echo "======================================"
echo "🚀 Next Steps"
echo "======================================"
echo ""
echo "1. Test the application:"
echo "   Open: $FRONTEND_URI"
echo ""
echo "2. View logs:"
echo "   Backend:  azd logs --service backend --follow"
echo "   Frontend: azd logs --service frontend --follow"
echo ""
echo "3. Monitor in Azure Portal:"
echo "   Application Insights: https://portal.azure.com/#blade/HubsExtension/BrowseResource/resourceType/microsoft.insights%2Fcomponents"
echo "   Resource Group: https://portal.azure.com/#@/resource/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}"
echo ""
echo "4. (Optional) Configure Azure AD authentication:"
echo "   See: DEPLOYMENT.md for Azure AD setup instructions"
echo ""
echo "======================================"
echo "✨ Happy mapping!"
echo "======================================"
echo ""

exit 0
