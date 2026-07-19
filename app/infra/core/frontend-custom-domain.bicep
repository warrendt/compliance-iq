// Free managed TLS certificate for a Container Apps custom domain.
//
// Issued at the managed-environment scope and bound to the app via the
// container app's ingress.customDomains (SniEnabled). Issuance validates
// domain ownership over the public internet, so the CNAME and the
// `asuid.<subdomain>` TXT verification record MUST already exist in DNS
// before this resource is deployed. DNS for compliance-iq.net is hosted on
// Cloudflare (external), so those records are created there, not in Bicep.
param environmentName string
param location string = resourceGroup().location
param tags object = {}

@description('Fully-qualified custom domain to secure, e.g. app.compliance-iq.net')
param customDomain string

resource environment 'Microsoft.App/managedEnvironments@2023-05-01' existing = {
  name: environmentName
}

resource managedCertificate 'Microsoft.App/managedEnvironments/managedCertificates@2023-05-01' = {
  parent: environment
  name: 'mc-${replace(customDomain, '.', '-')}'
  location: location
  tags: tags
  properties: {
    subjectName: customDomain
    domainControlValidation: 'CNAME'
  }
}

output certificateId string = managedCertificate.id
output certificateName string = managedCertificate.name
