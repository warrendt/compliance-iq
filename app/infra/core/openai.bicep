// Azure OpenAI with GPT model deployment and region validation
param name string
param location string = resourceGroup().location
param tags object = {}
// Defaults mirror the live dev environment. When they drifted (gpt-5.2 here vs
// gpt-5.6-luna live), `azd provision` would silently have repointed the backend
// to a different model; app/tests/test_openai_iac_matches_live.py locks this.
param modelName string = 'gpt-5.6-luna'
param modelVersion string = '2026-07-09'
param fallbackModel string = 'gpt-4.1'
param fallbackVersion string = '2025-04-14'
@description('Embedding model backing semantic Azure Policy retrieval')
param embeddingModel string = 'text-embedding-3-large'
param embeddingVersion string = '1'
@description('Capacity for the embedding deployment (queries are small and infrequent)')
param embeddingCapacity int = 50
param apiVersion string = '2024-12-01-preview'
param sku string = 'S0'
@description('SKU used for model deployments (e.g., GlobalStandard for GPT-5 family)')
param deploymentSku string = 'GlobalStandard'
// Live deployments run at 412 (thousands of tokens per minute). The old default
// of 10 meant a re-provision would have cut production throughput by ~97%
// without any error. A fresh subscription lacking this quota fails loudly at
// provision time instead, which is the safer failure; lower it via
// AZURE_OPENAI_DEPLOYMENT_CAPACITY.
@description('Capacity for each model deployment (thousands of tokens per minute)')
param deploymentCapacity int = 412
@description('Content filter for the primary model and embeddings. Newer models run on DefaultV2.')
param raiPolicyName string = 'Microsoft.DefaultV2'
@description('Content filter for the fallback model')
param fallbackRaiPolicyName string = 'Microsoft.Default'
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
    // Entra ID only, matching the live account. Omitting this let a
    // re-provision silently re-enable API-key auth; nothing uses keys (the app
    // authenticates with its managed identity).
    disableLocalAuth: true
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
    raiPolicyName: raiPolicyName
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
    raiPolicyName: fallbackRaiPolicyName
  }
  dependsOn: [
    modelDeployment
  ]
}

// Embedding deployment backing semantic policy retrieval. Regulatory control
// text and Azure Policy display names share almost no vocabulary, so lexical
// search alone misses most of the correct definitions; see
// app/backend/app/services/policy_catalog_service.py.
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = if (!existingAccount) {
  parent: openai
  name: embeddingModel
  sku: {
    name: 'Standard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModel
      version: embeddingVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: raiPolicyName
  }
  dependsOn: [
    fallbackDeployment
  ]
}

resource openAiPrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-08-01' = {
  name: '${name}-pe'
  location: location
  tags: tags
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
    embeddingDeployment
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
output embeddingDeploymentName string = embeddingModel
output apiVersion string = apiVersion
output openAiUserRoleId string = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
