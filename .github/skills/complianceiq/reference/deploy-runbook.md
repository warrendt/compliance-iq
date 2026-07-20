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
After deploy, re-assert Easy Auth (a deploy can reset it). Current design is
AllowAnonymous with app-level `require_login()`, so confirm it is still
`AllowAnonymous` (or the intended value):
```
az containerapp auth show -n <frontend-app> -g <rg> \
  --query "globalValidation.unauthenticatedClientAction"
```

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
- Redeploy the previous frontend image, or unset `BACKEND_URL` to strip the /api
  proxy (start.sh removes the block when `BACKEND_URL` is empty).

## Verify freshness first
Always `git fetch` and confirm the worktree is level with `origin/main` before
deploying — never ship stale code.
