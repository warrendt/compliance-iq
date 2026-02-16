// Azure Container Registry for storing Docker images
param name string
param location string = resourceGroup().location
param tags object = {}
param sku string = 'Premium'
param privateEndpointSubnetId string
param privateDnsZoneId string

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: true
    publicNetworkAccess: 'Disabled'
    zoneRedundancy: 'Disabled'
  }
}

resource acrPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-09-01' = {
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
          privateLinkServiceId: containerRegistry.id
          groupIds: [
            'registry'
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
              name: 'acr'
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
    containerRegistry
  ]
}

output id string = containerRegistry.id
output name string = containerRegistry.name
output loginServer string = containerRegistry.properties.loginServer
