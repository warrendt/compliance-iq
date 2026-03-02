// Azure Cosmos DB for NoSQL with serverless pricing
param name string
param location string = resourceGroup().location
param tags object = {}
param databaseName string = 'cctoolkit-db'
param privateEndpointSubnetId string
param privateDnsZoneId string
@description('Also create regional Cosmos private DNS A record (host-suffix)')
param addRegionalDnsRecord bool = true
@description('IP addresses to use for the regional Cosmos private DNS record (optional)')
param regionalDnsIpAddresses array = []
@description('Developer public IP address for firewall rule (empty to keep fully private)')
param devPublicIpAddress string = ''

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: name
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    publicNetworkAccess: !empty(devPublicIpAddress) ? 'Enabled' : 'Disabled'
    ipRules: !empty(devPublicIpAddress) ? [
      {
        ipAddressOrRange: devPublicIpAddress
      }
    ] : []
    disableKeyBasedMetadataWriteAccess: false
    enableFreeTier: false
  }
}

resource cosmosPrivateEndpoint 'Microsoft.Network/privateEndpoints@2021-08-01' = {
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
          privateLinkServiceId: cosmosAccount.id
          groupIds: [
            'Sql'
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
              name: 'cosmosdb'
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
    cosmosAccount
  ]
}

// Private DNS record for regional endpoint (e.g., cosmos-<token>-swedencentral.privatelink.documents.azure.com)
var regionalRecordName = '${name}-${toLower(replace(location, ' ', ''))}'

resource cosmosPrivateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: 'privatelink.documents.azure.com'
  scope: resourceGroup()
}

resource regionalARecord 'Microsoft.Network/privateDnsZones/A@2020-06-01' = if (addRegionalDnsRecord && length(regionalDnsIpAddresses) > 0) {
  parent: cosmosPrivateDnsZone
  name: regionalRecordName
  properties: {
    ttl: 3600
    aRecords: [for ip in regionalDnsIpAddresses: {
      ipv4Address: ip
    }]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
  }
}

// Container for mapping results
resource mappingResultsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'mapping-results'
  properties: {
    resource: {
      id: 'mapping-results'
      partitionKey: {
        paths: [
          '/userId'
          '/date'
        ]
        kind: 'MultiHash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
      defaultTtl: 2592000 // 30 days in seconds
    }
  }
}

// Container for audit logs
resource auditLogsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'audit-logs'
  properties: {
    resource: {
      id: 'audit-logs'
      partitionKey: {
        paths: [
          '/userId'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
      }
      defaultTtl: 7776000 // 90 days in seconds
    }
  }
}

// Container for user uploads
resource userUploadsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'user-uploads'
  properties: {
    resource: {
      id: 'user-uploads'
      partitionKey: {
        paths: [
          '/userId'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
      }
      defaultTtl: 2592000 // 30 days in seconds
    }
  }
}

// Container for generated artifacts
resource generatedArtifactsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'generated-artifacts'
  properties: {
    resource: {
      id: 'generated-artifacts'
      partitionKey: {
        paths: [
          '/session_id'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
      }
      defaultTtl: 2592000 // 30 days in seconds
    }
  }
}

// Container for mapping jobs (background mapping status/results)
resource mappingJobsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'mapping-jobs'
  properties: {
    resource: {
      id: 'mapping-jobs'
      partitionKey: {
        paths: [
          '/job_id'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
      }
      defaultTtl: 2592000 // 30 days in seconds
    }
  }
}

// Container for policy cache (Azure Policy artifacts)
resource policyCacheContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: database
  name: 'policy-cache'
  properties: {
    resource: {
      id: 'policy-cache'
      partitionKey: {
        paths: [
          '/policy_id'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
      }
      defaultTtl: 1209600 // 14 days in seconds
    }
  }
}

// Built-in Data Contributor role definition ID
var dataContributorRoleId = '00000000-0000-0000-0000-000000000002'

output id string = cosmosAccount.id
output name string = cosmosAccount.name
output endpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = database.name
output dataContributorRoleId string = '${cosmosAccount.id}/sqlRoleDefinitions/${dataContributorRoleId}'
