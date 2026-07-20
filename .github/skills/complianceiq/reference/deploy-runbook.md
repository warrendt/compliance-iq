# ComplianceIQ skill — deploy / enable runbook

Enables the skill against the **deployed** app. Run these once (they are the only
infra steps the skill needs). Nothing here uses `azd provision` / `azd up`, which
are blocked by the landing-zone policy `Deny-Subnet-Without-Nsg`.

> Sanitised: resolve subscription / RG / app names / FQDNs at runtime with `az`.
> Do not paste real identifiers into this repo.

## Prerequisites
- `az login` done; correct subscription selected (`az account set -s <sub>`).
- An `azd` environment bound to the existing resources (this repo ships no
  `.azure/`). If `azd env list` is empty, create/refresh one to point at the
  already-provisioned resources **without** re-provisioning:
  ```
  azd env new <env-name>
  azd env set AZURE_SUBSCRIPTION_ID <sub-id>
  azd env set AZURE_LOCATION <region>
  azd env set AZURE_RESOURCE_GROUP <rg>
  azd env refresh          # reads existing resources; does NOT provision
  ```
  `<env-name>` / `<region>` / `<rg>` must match the original deployment. If you
  are unsure of these, stop and confirm — do not guess against shared infra.

## 1. Deploy the frontend (activates the /api proxy)
The frontend already has `BACKEND_URL=https://<backend-internal-fqdn>` (set in
`app/infra/main.bicep`), so the new `start.sh` renders the `/api` proxy block on
boot. Code-only redeploy:
```
azd deploy frontend --no-prompt
```

## 1a. Let Easy Auth pass `/api` through to nginx (REQUIRED)
The frontend runs Container Apps **Easy Auth** with
`globalValidation.unauthenticatedClientAction = RedirectToLoginPage`. Left alone,
Easy Auth 302-redirects the skill's `/api` bearer requests to the login page
**before** they reach nginx, so the CLI never talks to the backend. Add the
`/api` paths to `globalValidation.excludedPaths` so Easy Auth bypasses them (the
backend still validates the ARM bearer itself on protected routes).

The token store uses a **user-assigned managed identity**
(`tokenStore.azureBlobStorage.blobContainerUri` + `managedIdentityResourceId`),
so you **must** use api-version `2025-10-02-preview`; the stable `2024-03-01`
rejects the managed-identity token store (`SasUrlSettingName ... must be set`).
GET the current config, add the excluded paths, PUT it back — preserving the
existing `tokenStore` block:
```
AUTHCFG=/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.App/containerApps/<frontend-app>/authConfigs/current
API=2025-10-02-preview

az rest --method GET --url "https://management.azure.com${AUTHCFG}?api-version=${API}" > /tmp/authcfg.json
# add "excludedPaths": ["/api","/api/","/api/*"] under properties.globalValidation, keep tokenStore intact
az rest --method PUT --url "https://management.azure.com${AUTHCFG}?api-version=${API}" \
  --headers "Content-Type=application/json" --body @/tmp/authcfg.json
```
Verify:
```
az rest --method GET --url "https://management.azure.com${AUTHCFG}?api-version=${API}" \
  --query "properties.globalValidation.{action:unauthenticatedClientAction,excluded:excludedPaths}"
```
Re-check after every `azd deploy frontend` — a deploy can drop the excludedPaths
or flip `unauthenticatedClientAction` back to `AllowAnonymous`.

## 2. Allow ARM-audience tokens on the backend
Add the accepted-audiences env var (creates a new revision). Bicep would be
ideal but changing infra env requires provision (blocked), so set it directly:
```
az containerapp update -n <backend-app> -g <rg> \
  --set-env-vars \
    AZURE_AD_ACCEPTED_AUDIENCES="https://management.azure.com,https://management.azure.com/"
```
Then redeploy the backend image (contains the multi-audience validation change):
```
azd deploy backend --no-prompt
```
(Order does not matter; both a new env var and a new image each roll a revision.)

## 3. Smoke test end-to-end
```
export CIQ_FRONTEND_APP=<frontend-app>
export CIQ_RESOURCE_GROUP=<rg>

python .github/skills/complianceiq/scripts/ciq.py health          # 200 + status
python .github/skills/complianceiq/scripts/ciq.py run --pdf <tiny.pdf>
python .github/skills/complianceiq/scripts/ciq.py artifacts --job-id <id> --out ./out
python .github/skills/complianceiq/scripts/ciq.py scopes           # 200 => bearer accepted
```
- `health` proves the proxy path (`https://<fqdn>/api/v1/health`).
- `scopes` returning 200 proves the ARM bearer is accepted on an **authenticated**
  route (i.e. step 2 worked and Easy Auth passed the header through).

## Rollback
- Remove the env var: `az containerapp update -n <backend-app> -g <rg> --remove-env-vars AZURE_AD_ACCEPTED_AUDIENCES` (reverts backend to app-audience-only; empty set = skip aud check).
- Remove the `/api` excludedPaths from the frontend authConfig (PUT the config back with `excludedPaths` cleared, api-version `2025-10-02-preview`) to re-lock `/api` behind Easy Auth.
- Redeploy the previous frontend image, or unset `BACKEND_URL` to strip the /api
  proxy (start.sh removes the block when `BACKEND_URL` is empty).

## Verify freshness first
Always `git fetch` and confirm the worktree is level with `origin/main` before
deploying — never ship stale code.
