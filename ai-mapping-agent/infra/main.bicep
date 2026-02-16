targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (e.g., dev, staging, prod)')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Azure OpenAI model name to deploy')
param openAiModelName string = 'gpt-4.1'

@description('Azure OpenAI model version')
param openAiModelVersion string = '2025-04-14'

@description('Fallback Azure OpenAI model if primary is not available')
param openAiFallbackModel string = 'gpt-4o'

@description('Fallback model version')
param openAiFallbackVersion string = '2024-11-20'

@description('Azure OpenAI API version')
param openAiApiVersion string = '2024-12-01-preview'

@description('Cosmos DB database name')
param cosmosDatabaseName string = 'cctoolkit-db'

// Generate resource names
var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
  Environment: environmentName
  ManagedBy: 'azd'
  Project: 'cctoolkit-ai-agent'
}

// Resource Group
resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: '${abbrs.resourcesResourceGroups}${environmentName}'
  location: location
  tags: tags
}

// Networking (VNet, subnets, NSG)
module network './core/network.bicep' = {
  name: 'network'
  scope: resourceGroup
  params: {
    name: '${abbrs.networkVirtualNetworks}${resourceToken}'
    location: location
    tags: tags
  }
}

// Private DNS zones linked to the VNet
module privateDns './core/private-dns.bicep' = {
  name: 'private-dns'
  scope: resourceGroup
  params: {
    vnetId: network.outputs.vnetId
    environmentName: environmentName
    location: location
    tags: tags
  }
}

// Log Analytics Workspace
module logAnalytics './core/log-analytics.bicep' = {
  name: 'log-analytics'
  scope: resourceGroup
  params: {
    name: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    location: location
    tags: tags
    retentionInDays: 90
  }
}

// Application Insights
module appInsights './core/app-insights.bicep' = {
  name: 'app-insights'
  scope: resourceGroup
  params: {
    name: '${abbrs.insightsComponents}${resourceToken}'
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.id
  }
}

// Container Registry
module containerRegistry './core/container-registry.bicep' = {
  name: 'container-registry'
  scope: resourceGroup
  params: {
    name: '${abbrs.containerRegistryRegistries}${resourceToken}'
    location: location
    tags: tags
    sku: 'Premium'
    privateEndpointSubnetId: network.outputs.privateEndpointSubnetId
    privateDnsZoneId: privateDns.outputs.acrZoneId
  }
}

// Azure OpenAI
module openai './core/openai.bicep' = {
  name: 'openai'
  scope: resourceGroup
  params: {
    name: '${abbrs.cognitiveServicesAccounts}${resourceToken}'
    location: location
    tags: tags
    modelName: openAiModelName
    modelVersion: openAiModelVersion
    fallbackModel: openAiFallbackModel
    fallbackVersion: openAiFallbackVersion
    apiVersion: openAiApiVersion
    privateEndpointSubnetId: network.outputs.privateEndpointSubnetId
    privateDnsZoneId: privateDns.outputs.openaiZoneId
    existingAccount: true
  }
}

// Cosmos DB
module cosmos './core/cosmosdb.bicep' = {
  name: 'cosmosdb'
  scope: resourceGroup
  params: {
    name: '${abbrs.documentDBDatabaseAccounts}${resourceToken}'
    location: location
    tags: tags
    databaseName: cosmosDatabaseName
    privateEndpointSubnetId: network.outputs.privateEndpointSubnetId
    privateDnsZoneId: privateDns.outputs.cosmosZoneId
  }
}

// Container Apps Environment
module containerAppsEnvironment './core/container-apps-environment.bicep' = {
  name: 'container-apps-environment'
  scope: resourceGroup
  params: {
    name: '${abbrs.appManagedEnvironments}${resourceToken}'
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.id
    infrastructureSubnetId: network.outputs.infraSubnetId
    workloadSubnetId: network.outputs.workloadSubnetId
  }
}

// Backend Container App
module backendApp './core/container-app.bicep' = {
  name: 'backend-app'
  scope: resourceGroup
  params: {
    name: '${abbrs.appContainerApps}backend-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'backend' })
    containerAppsEnvironmentId: containerAppsEnvironment.outputs.id
    containerImage: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest' // Placeholder, replaced by azd
    containerPort: 8000
    isExternalIngress: false
    minReplicas: 0
    maxReplicas: 10
    cpu: '0.5'
    memory: '1Gi'
    containerRegistryName: containerRegistry.outputs.name
    environmentVariables: [
      {
        name: 'AZURE_OPENAI_ENDPOINT'
        value: openai.outputs.endpoint
      }
      {
        name: 'AZURE_OPENAI_DEPLOYMENT_NAME'
        value: openai.outputs.deploymentName
      }
      {
        name: 'AZURE_OPENAI_API_VERSION'
        value: openai.outputs.apiVersion
      }
      {
        name: 'COSMOS_DB_ENDPOINT'
        value: cosmos.outputs.endpoint
      }
      {
        name: 'COSMOS_DB_DATABASE_NAME'
        value: cosmos.outputs.databaseName
      }
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        value: appInsights.outputs.connectionString
      }
      {
        name: 'LOG_LEVEL'
        value: 'INFO'
      }
      {
        name: 'ENVIRONMENT'
        value: environmentName
      }
    ]
  }
}

// Frontend Container App
module frontendApp './core/container-app.bicep' = {
  name: 'frontend-app'
  scope: resourceGroup
  params: {
    name: '${abbrs.appContainerApps}frontend-${resourceToken}'
    location: location
    tags: union(tags, { 'azd-service-name': 'frontend' })
    containerAppsEnvironmentId: containerAppsEnvironment.outputs.id
    containerImage: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest' // Placeholder, replaced by azd
    containerPort: 8501
    isExternalIngress: true
    minReplicas: 0
    maxReplicas: 5
    cpu: '0.25'
    memory: '0.5Gi'
    containerRegistryName: containerRegistry.outputs.name
    environmentVariables: [
      {
        name: 'BACKEND_URL'
        value: 'https://${backendApp.outputs.fqdn}'
      }
      {
        name: 'ENVIRONMENT'
        value: environmentName
      }
    ]
  }
}

// RBAC: Backend identity -> OpenAI (Cognitive Services OpenAI User)
module backendOpenAiRoleAssignment './core/role-assignment.bicep' = {
  name: 'backend-openai-role'
  scope: resourceGroup
  params: {
    principalId: backendApp.outputs.identityPrincipalId
    roleDefinitionId: openai.outputs.openAiUserRoleId
    principalType: 'ServicePrincipal'
  }
}

// RBAC: Backend identity -> Cosmos DB (Built-in Data Contributor)
module backendCosmosRoleAssignment './core/cosmosdb-role-assignment.bicep' = {
  name: 'backend-cosmos-role'
  scope: resourceGroup
  params: {
    cosmosAccountName: cosmos.outputs.name
    principalId: backendApp.outputs.identityPrincipalId
    roleDefinitionId: cosmos.outputs.dataContributorRoleId
  }
}

// Monitoring Alerts (disabled for initial deployment - can be enabled later)
// module alerts './core/alerts.bicep' = {
//   name: 'alerts'
//   scope: resourceGroup
//   params: {
//     name: resourceToken
//     location: 'global'
//     tags: tags
//     appInsightsId: appInsights.outputs.id
//     actionGroupId: ''
//     enabled: false
//   }
// }

// Outputs for azd
output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output AZURE_RESOURCE_GROUP string = resourceGroup.name

output APPLICATIONINSIGHTS_CONNECTION_STRING string = appInsights.outputs.connectionString
output APPLICATIONINSIGHTS_NAME string = appInsights.outputs.name

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.loginServer
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.name

output AZURE_OPENAI_ENDPOINT string = openai.outputs.endpoint
output AZURE_OPENAI_DEPLOYMENT_NAME string = openai.outputs.deploymentName
output AZURE_OPENAI_API_VERSION string = openai.outputs.apiVersion

output COSMOS_DB_ENDPOINT string = cosmos.outputs.endpoint
output COSMOS_DB_DATABASE_NAME string = cosmos.outputs.databaseName

output BACKEND_URI string = backendApp.outputs.uri
output FRONTEND_URI string = frontendApp.outputs.uri

output SERVICE_BACKEND_NAME string = backendApp.outputs.name
output SERVICE_FRONTEND_NAME string = frontendApp.outputs.name
