param principalId string
param roleDefinitionId string
param principalType string = 'ServicePrincipal'
@description('ACR name to scope the role assignment')
param registryName string

// Existing ACR resource to scope the assignment
resource acr 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = {
  name: registryName
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(principalId, roleDefinitionId, registryName)
  scope: acr
  properties: {
    roleDefinitionId: roleDefinitionId
    principalId: principalId
    principalType: principalType
  }
}

output id string = roleAssignment.id
