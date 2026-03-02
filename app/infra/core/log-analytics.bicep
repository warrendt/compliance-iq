// Log Analytics Workspace for centralized logging
param name string
param location string = resourceGroup().location
param tags object = {}
param sku string = 'PerGB2018'
param retentionInDays int = 90

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      name: sku
    }
    retentionInDays: retentionInDays
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    workspaceCapping: {
      dailyQuotaGb: 5 // Limit daily ingestion to 5GB to control costs
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

output id string = logAnalytics.id
output customerId string = logAnalytics.properties.customerId
output name string = logAnalytics.name
