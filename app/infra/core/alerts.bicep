// Azure Monitor Alerts
param name string
param location string = 'global'
param tags object = {}
param appInsightsId string
param actionGroupId string
param enabled bool = true

// High error rate alert
resource highErrorRateAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${name}-high-error-rate'
  location: location
  tags: tags
  properties: {
    description: 'Alert when error rate exceeds 10% for 5 minutes'
    severity: 2
    enabled: enabled
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'FailedRequestsPercentage'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'requests/failed'
          operator: 'GreaterThan'
          threshold: 10
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroupId
      }
    ]
  }
}

// High response time alert
resource highResponseTimeAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${name}-high-response-time'
  location: location
  tags: tags
  properties: {
    description: 'Alert when average response time exceeds 3 seconds for 10 minutes'
    severity: 3
    enabled: enabled
    scopes: [
      appInsightsId
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT10M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ResponseTime'
          metricNamespace: 'microsoft.insights/components'
          metricName: 'requests/duration'
          operator: 'GreaterThan'
          threshold: 3000
          timeAggregation: 'Average'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroupId
      }
    ]
  }
}

// Action Group for notifications
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${name}-action-group'
  location: location
  tags: tags
  properties: {
    groupShortName: substring(name, 0, min(length(name), 12))
    enabled: true
    emailReceivers: []
    smsReceivers: []
    webhookReceivers: []
  }
}

output actionGroupId string = actionGroup.id
output actionGroupName string = actionGroup.name
