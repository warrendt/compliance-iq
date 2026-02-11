// Azure Cosmos DB for NoSQL with serverless pricing
param name string
param location string = resourceGroup().location
param tags object = {}
param databaseName string = 'cctoolkit-db'

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
    publicNetworkAccess: 'Enabled'
    disableKeyBasedMetadataWriteAccess: false
    enableFreeTier: false
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

// Built-in Data Contributor role definition ID
var dataContributorRoleId = '00000000-0000-0000-0000-000000000002'

output id string = cosmosAccount.id
output name string = cosmosAccount.name
output endpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = database.name
output dataContributorRoleId string = '${cosmosAccount.id}/sqlRoleDefinitions/${dataContributorRoleId}'
