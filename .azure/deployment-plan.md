# Deployment Plan: Azure OpenAI Model Deployment Update

**Status:** Validation Blocked

## 1. Scope

Update the existing Azure OpenAI Bicep deployment to use `gpt-5.6-sol` as its
primary deployment and `gpt-4.1` as its fallback. Keep application-facing
deployment names explicit and independent from model identifiers.

## 2. Constraints

- Do not provision or deploy resources.
- Preserve existing application deployment-name references.
- Treat the existing Cosmos DB `disableLocalAuth` preview change as an unrelated
  deployment risk.
- Subscription-specific catalog and quota checks are blocked by the current
  identity's `Microsoft.Resources/subscriptions/read` authorization failure.

## 3. Availability Evidence and Design

- Microsoft Foundry model catalog lookup on 2026-07-12 reports
  `gpt-5.6-sol` version `2026-07-09`, lifecycle `Generally Available`, Azure
  OpenAI deployment option `AOAI`, and `GlobalStandard` availability in
  `SWEDENCENTRAL`.
- Model catalog detail lookup reports `OpenAI` as the Azure OpenAI model
  provider and `GlobalStandard` as a supported SKU.
- The fallback is `gpt-4.1` version `2025-04-14`, with a deployment name of
  `gpt-4.1-fallback`. It remains separately deployed so the runtime retry
  path can select it after primary rate-limit exhaustion.
- Official deployment guidance requires the model name, format, version, and
  SKU to be verified with `az cognitiveservices account list-models` for the
  target account before deployment:
  <https://learn.microsoft.com/azure/foundry/foundry-models/how-to/create-model-deployments>.

## 4. Assumptions and Deployment Risks

- Regional availability does not establish subscription quota or entitlement.
  A privileged operator must run `az cognitiveservices account list-models`
  against the target account and confirm `gpt-5.6-sol`, version `2026-07-09`,
  format `OpenAI`, and `GlobalStandard` before provisioning.
- Do not apply `azd provision` until the existing unrelated Cosmos DB
  `disableLocalAuth: true => false` preview change is reviewed and approved.
- The Bicep resource API and existing OpenAI resource configuration are
  retained; this change updates model selection and deployment-name wiring.

## 5. Validation Proof

| Check | Result |
| --- | --- |
| Microsoft Foundry model catalog and detail lookup | Passed: `gpt-5.6-sol` version `2026-07-09` is GA, supports Azure OpenAI, and lists `SWEDENCENTRAL` for `GlobalStandard`. |
| `az bicep build --file app/infra/core/openai.bicep` | Passed. Existing nullability warnings remain for conditional Azure resource references. |
| `az bicep build --file app/infra/main.bicep` | Passed. Existing repository lint warnings remain in unrelated network, private DNS, registry, Cosmos DB, and Container App modules. |
| Focused regression tests | Passed: 74 tests, including `test_openai_model_selection.py`, `test_user_profile.py`, and `test_m365_purview.py`. |
| `az deployment sub validate` with resolved `cciq-01` parameters | Blocked by the existing landing-zone `Deny-Subnet-Without-Nsg` policy for the template VNet. |
| `azd provision --preview --no-prompt` using supplied subscription, resource group, and location | Blocked by the same subnet-NSG policy before a complete resource diff. No resources were provisioned. |

The model change is not validated for the target subscription until the
subscription policy blocker is resolved or an approved compliant network
configuration is supplied. Do not deploy while this status is blocked.
