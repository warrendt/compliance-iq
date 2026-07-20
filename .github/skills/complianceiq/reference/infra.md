# ComplianceIQ infrastructure

Deployed with **Azure Developer CLI (azd)** to **Azure Container Apps**. Infra
is Bicep under `app/infra/`.

> This repo is public — do not hardcode subscription IDs, tenant IDs, resource
> group names, or FQDNs here or in commits. Resolve them at runtime with `az`.

## Resources
- **Container Apps environment** hosting two apps:
  - `ca-frontend-*` — Streamlit + **nginx**, **external** ingress (port 8501).
    The public entry point and the `/api` reverse proxy to the backend.
  - `ca-backend-*` — FastAPI, **internal** ingress only (port 8000).
- **Azure OpenAI** — control intelligence + mapping.
- **Cosmos DB** — job status + user workspace data.
- **Container Registry** — images (deploys use ACR **remoteBuild**).
- **User-assigned managed identities** — backend→ARM/AOAI/Cosmos, and the
  frontend Easy Auth token store→blob storage.

## The `/api` reverse proxy (how the skill reaches the internal backend)
`app/frontend/nginx.conf` has a `location ^~ /api/` block (between
`# __API_PROXY_START__` / `# __API_PROXY_END__`) that proxies to the backend's
internal FQDN. `app/frontend/start.sh` `render_nginx_conf()` substitutes
placeholders from the `BACKEND_URL` env var at container start
(`__BACKEND_URL__`, `__BACKEND_HOST__`, `__DNS_RESOLVER__`), writes
`/tmp/nginx.conf`, and runs `nginx -c /tmp/nginx.conf`. If `BACKEND_URL` is
unset the whole `/api` block is stripped (proxy disabled).

Key nginx settings: a runtime `resolver` (from `/etc/resolv.conf`, fallback
`168.63.129.16`) with `proxy_pass $var$request_uri` to force runtime DNS of the
internal FQDN; `proxy_ssl_server_name on`; `Authorization` header passthrough;
long timeouts (600s) and `proxy_request_buffering off` for large PDF uploads.
`location ^~ /api/` takes precedence over the Streamlit regex locations.

## Deploy commands (verified constraints)
- Redeploy code only: `azd deploy backend --no-prompt` /
  `azd deploy frontend --no-prompt` (remoteBuild in ACR).
- **Never** `azd provision` / `azd up` — blocked by landing-zone policy
  `Deny-Subnet-Without-Nsg`.
- After `azd deploy frontend`, re-check frontend Easy Auth
  (`unauthenticatedClientAction`) **and** that `globalValidation.excludedPaths`
  still contains `/api`, `/api/`, `/api/*` — a deploy can drop either. Patch with
  api-version `2025-10-02-preview` (see `deploy-runbook.md` §1a).
- To enable ARM-token auth on the backend, set
  `AZURE_AD_ACCEPTED_AUDIENCES=https://management.azure.com,https://management.azure.com/`
  on `ca-backend-*` (env var or Bicep), then redeploy/restart the revision.

## Runtime discovery (no hardcoding)
```
az containerapp show -n <frontend-app> -g <rg> \
  --query properties.configuration.ingress.fqdn -o tsv
```
`ciq.py` does this automatically when given `--frontend-app`/`--resource-group`
(or `$CIQ_FRONTEND_APP`/`$CIQ_RESOURCE_GROUP`).
