@description('Cosmos DB account name')
param cosmosAccountName string

@description('Principal ID to assign the role to')
param principalId string

@description('Role definition ID')
param roleDefinitionId string

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' existing = {
  name: cosmosAccountName
}

resource roleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-04-15' = {
  name: guid(cosmosAccount.id, principalId, roleDefinitionId)
  parent: cosmosAccount
  properties: {
    roleDefinitionId: roleDefinitionId
    principalId: principalId
    scope: cosmosAccount.id
  }
}

output roleAssignmentId string = roleAssignment.id
