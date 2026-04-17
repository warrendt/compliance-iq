// Individual Container App
param name string
param location string = resourceGroup().location
param tags object = {}
param containerAppsEnvironmentId string
param containerImage string
param containerPort int
param isExternalIngress bool = false
param minReplicas int = 1
param maxReplicas int = 10
param environmentVariables array = []
param cpu string = '0.5'
param memory string = '1Gi'
param containerRegistryName string = ''

// Authentication (Easy Auth v2) – only applied when authClientId is set
param authClientId string = ''
param authTenantId string = ''
@secure()
param authClientSecret string = ''

var authEnabled = !empty(authClientId)
var containerSecrets = concat(
  !empty(containerRegistryName) ? [
    {
      name: 'acr-password'
      value: containerRegistry.listCredentials().passwords[0].value
    }
  ] : [],
  !empty(authClientSecret) ? [
    {
      name: 'auth-client-secret'
      value: authClientSecret
    }
  ] : []
)
var aadRegistration = union({
  clientId: authClientId
  openIdIssuer: 'https://sts.windows.net/${!empty(authTenantId) ? authTenantId : tenant().tenantId}/v2.0'
}, !empty(authClientSecret) ? {
  clientSecretSettingName: 'auth-client-secret'
} : {})
var aadLogin = !empty(authClientSecret) ? {
  loginParameters: [
    'response_type=code id_token'
    'scope=openid profile email offline_access https://management.azure.com/user_impersonation'
  ]
} : null

// Reference existing ACR to get admin credentials
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' existing = if (!empty(containerRegistryName)) {
  name: containerRegistryName
}

resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        external: isExternalIngress
        targetPort: containerPort
        transport: 'http'
        allowInsecure: false
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
      }
      registries: !empty(containerRegistryName) ? [
        {
          server: containerRegistry.properties.loginServer
          username: containerRegistry.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ] : []
      secrets: containerSecrets
    }
    template: {
      containers: [
        {
          name: name
          image: containerImage
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          env: environmentVariables
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

output id string = containerApp.id
output name string = containerApp.name
output fqdn string = containerApp.properties.configuration.ingress.fqdn
output uri string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output identityPrincipalId string = containerApp.identity.principalId

// Easy Auth v2 – conditionally deployed when authClientId is provided
resource authConfig 'Microsoft.App/containerApps/authConfigs@2023-05-01' = if (authEnabled) {
  parent: containerApp
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      unauthenticatedClientAction: 'RedirectToLoginPage'
      redirectToProvider: 'azureactivedirectory'
    }
    identityProviders: {
      azureActiveDirectory: {
        registration: {
          clientId: aadRegistration.clientId
          openIdIssuer: aadRegistration.openIdIssuer
          clientSecretSettingName: contains(aadRegistration, 'clientSecretSettingName') ? aadRegistration.clientSecretSettingName : null
        }
        login: aadLogin
        validation: {
          allowedAudiences: [
            'api://${authClientId}'
            authClientId
          ]
        }
      }
    }
  }
}
