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

// NSGs for the Container Apps subnets.
//
// These are not decorative. A subscription-level Azure Policy requires every
// subnet to carry an NSG ("Subnets must have a Network Security Group"), and
// without them `azd provision` is rejected outright with
// RequestDisallowedByPolicy before any Container Apps resource is touched.
//
// They already exist in the deployed environment, created out-of-band with
// exactly these names and no custom rules -- so this template could no longer
// reproduce the environment it supposedly describes. Declaring them here
// closes that drift; the names match the live resources so provisioning
// adopts them rather than creating a second set.
//
// No security rules are defined, deliberately. An NSG with none applies only
// the platform defaults (intra-VNet traffic allowed, outbound allowed,
// inbound from the internet denied), which is what the running environment
// has today. Container Apps also requires specific traffic on its
// infrastructure subnet, so restrictive rules must not be invented here
// without testing them against a live environment.
resource acaInfraNsg 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: '${name}-aca-infra-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: []
  }
}

resource acaWorkloadNsg 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: '${name}-aca-workload-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: []
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
          networkSecurityGroup: {
            id: acaInfraNsg.id
          }
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
          networkSecurityGroup: {
            id: acaWorkloadNsg.id
          }
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
