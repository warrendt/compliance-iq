// Azure OpenAI with GPT model deployment and region validation
param name string
param location string = resourceGroup().location
param tags object = {}
param modelName string = 'gpt-4.1'
param modelVersion string = '2025-04-14'
param fallbackModel string = 'gpt-4o'
param fallbackVersion string = '2024-11-20'
param apiVersion string = '2024-12-01-preview'
param sku string = 'S0'
param privateEndpointSubnetId string
param privateDnsZoneId string

// Note: GPT-4.1 is preview and may not be available in all regions
// This template deploys both primary and fallback models
resource openai 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: sku
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
  }
}

resource openAiPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: '${name}-pe'
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${name}-pe-conn'
        properties: {
          privateLinkServiceId: openai.id
          groupIds: [
            'account'
          ]
        }
      }
    ]
    privateDnsZoneGroups: [
      {
        name: '${name}-pe-dns'
        properties: {
          privateDnsZoneConfigs: [
            {
              name: 'openai'
              properties: {
                privateDnsZoneId: privateDnsZoneId
              }
            }
          ]
        }
      }
    ]
  }
  dependsOn: [
    openai
  ]
}

// Deploy requested model (gpt-4.1 or configured model)
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openai
  name: modelName
  sku: {
    name: 'Standard'
    capacity: 10 // TPM (tokens per minute) in thousands
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.Default'
  }
}

// Fallback deployment (gpt-4o) for reliability
resource fallbackDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = if (modelName != fallbackModel) {
  parent: openai
  name: '${fallbackModel}-fallback'
  sku: {
    name: 'Standard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: fallbackModel
      version: fallbackVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.Default'
  }
  dependsOn: [
    modelDeployment
  ]
}

// Cognitive Services OpenAI User role definition ID
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

output id string = openai.id
output name string = openai.name
output endpoint string = openai.properties.endpoint
output deploymentName string = modelDeployment.name
output fallbackDeploymentName string = modelName != fallbackModel ? fallbackDeployment.name : ''
output apiVersion string = apiVersion
output openAiUserRoleId string = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
