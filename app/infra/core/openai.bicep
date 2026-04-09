// Azure OpenAI with GPT model deployment and region validation
param name string
param location string = resourceGroup().location
param tags object = {}
param modelName string = 'gpt-5.2'
param modelVersion string = '2025-12-11'
param fallbackModel string = 'gpt-5.4-mini'
param fallbackVersion string = '2026-03-17'
param apiVersion string = '2024-12-01-preview'
param sku string = 'S0'
@description('SKU used for model deployments (e.g., GlobalStandard for GPT-5 family)')
param deploymentSku string = 'GlobalStandard'
@description('Capacity for each model deployment')
param deploymentCapacity int = 10
param privateEndpointSubnetId string
param privateDnsZoneId string
param existingAccount bool = false
@description('Developer public IP address for firewall rule (empty to keep fully private)')
param devPublicIpAddress string = ''

// This template deploys both primary and fallback models
resource openai 'Microsoft.CognitiveServices/accounts@2023-05-01' = if (!existingAccount) {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: sku
  }
  properties: {
    customSubDomainName: name
    publicNetworkAccess: !empty(devPublicIpAddress) ? 'Enabled' : 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      ipRules: !empty(devPublicIpAddress) ? [
        {
          value: devPublicIpAddress
        }
      ] : []
      virtualNetworkRules: []
    }
  }
}

resource existingOpenai 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = if (existingAccount) {
  name: name
}

var openaiId = existingAccount ? existingOpenai.id : openai.id
var openaiEndpoint = existingAccount ? existingOpenai.properties.endpoint : openai.properties.endpoint

// Deploy requested model
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = if (!existingAccount) {
  parent: openai
  name: modelName
  sku: {
    name: deploymentSku
    capacity: deploymentCapacity
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

// Fallback deployment for reliability
resource fallbackDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = if (!existingAccount && modelName != fallbackModel) {
  parent: openai
  name: '${fallbackModel}-fallback'
  sku: {
    name: deploymentSku
    capacity: deploymentCapacity
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

resource openAiPrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-08-01' = {
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
          privateLinkServiceId: openaiId
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
  dependsOn: existingAccount ? [] : [
    modelDeployment
    fallbackDeployment
  ]
}

resource openAiPeDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2021-08-01' = {
  parent: openAiPrivateEndpoint
  name: 'default'
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

// Cognitive Services OpenAI User role definition ID
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

output id string = openaiId
output name string = name
output endpoint string = openaiEndpoint
output deploymentName string = existingAccount ? modelName : modelDeployment.name
output fallbackDeploymentName string = existingAccount ? '${fallbackModel}-fallback' : (modelName != fallbackModel ? fallbackDeployment.name : '')
output apiVersion string = apiVersion
output openAiUserRoleId string = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
