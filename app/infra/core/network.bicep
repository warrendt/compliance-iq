// Virtual network for Container Apps and private endpoints
param name string
param location string = resourceGroup().location
param tags object = {}
param addressPrefix string = '10.20.0.0/21'

// Subnet plan sized for Container Apps requirements
var infraPrefix = '10.20.0.0/23'
var workloadPrefix = '10.20.2.0/24'
var privateEndpointPrefix = '10.20.3.0/24'

// NSG for private endpoint subnet (allow 443 from vnet)
resource peNsg 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: '${name}-pe-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'Allow-HTTPS-From-VNet'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '443'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [addressPrefix]
    }
    subnets: [
      {
        name: 'aca-infra'
        properties: {
          addressPrefix: infraPrefix
          delegations: [
            {
              name: 'Microsoft.App/environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: 'aca-workload'
        properties: {
          addressPrefix: workloadPrefix
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: privateEndpointPrefix
          networkSecurityGroup: {
            id: peNsg.id
          }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output infraSubnetId string = resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'aca-infra')
output workloadSubnetId string = resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'aca-workload')
output privateEndpointSubnetId string = resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, 'private-endpoints')
output nsgId string = peNsg.id
