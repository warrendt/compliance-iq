# ComplianceIQ authentication

## Two ways the backend resolves a user
`get_current_user` (`app/backend/app/auth/azure_ad_auth.py`) resolves identity
in this order:
1. **Easy Auth headers** — `X-MS-CLIENT-PRINCIPAL-*` and
   `X-MS-TOKEN-AAD-ACCESS-TOKEN`, forwarded by the frontend Container App's
   Easy Auth. This is how the **Streamlit UI** authenticates its users.
2. **`Authorization: Bearer <jwt>`** — the token is validated (signature +
   issuer via the tenant JWKS) and the audience is checked against an accepted
   set. This is how **this skill** authenticates.
3. **Mock user** — only when `ENABLE_AUTH=false` (non-prod/testing).

Deploy routes reuse `user.access_token` (the bearer, or the Easy Auth ARM token)
for ARM calls. So the same token authenticates the caller **and** performs the
deployment.

## Why an ARM token works (the audience change)
A token from `az account get-access-token --resource https://management.azure.com`
has:
- `aud = https://management.azure.com` (no trailing slash)
- `iss = https://sts.windows.net/<tenant>/` (v1)
- `appid` = Azure CLI

`_validate_token` verifies signature + issuer with `python-jose`, then checks the
audience **manually** against `_get_accepted_audiences()`:
- app audience: `AZURE_AD_AUDIENCE` or `AZURE_AD_CLIENT_ID`, **plus**
- extras from `AZURE_AD_ACCEPTED_AUDIENCES` (comma-separated).

For the skill, the backend must have:
```
AZURE_AD_ACCEPTED_AUDIENCES = https://management.azure.com,https://management.azure.com/
```
An **empty** accepted set means "don't check audience" (legacy loose behaviour;
signature + issuer are still verified). The backend already lists the v1 issuer
in `_get_issuer_urls()`, so v1 ARM tokens pass issuer validation.

> Security note: accepting the ARM audience means any valid tenant ARM token is
> accepted on `/api` — parity with "any authenticated frontend user today". This
> was an explicit, approved decision.

## Frontend Easy Auth state
Frontend Easy Auth runs with
`globalValidation.unauthenticatedClientAction = RedirectToLoginPage`. Left alone,
Easy Auth **302-redirects** any unauthenticated request — including the skill's
`/api` bearer calls (the ARM audience does not match the frontend app) — to the
login page **before** it reaches nginx. To let the skill through, the `/api`
paths are added to `globalValidation.excludedPaths`
(`["/api","/api/","/api/*"]`), so Easy Auth bypasses them and forwards the
`Authorization` header to nginx → backend, which then validates the ARM bearer
itself. The app still gates its own Streamlit UI via `require_login()`.

Patch the excludedPaths with api-version `2025-10-02-preview` — the token store
uses a **user-assigned managed identity** against blob storage (shared-key
access is denied by policy), and the stable `2024-03-01` api-version rejects that
token store. After every `azd deploy frontend`, re-check the frontend auth
config: a deploy can drop the excludedPaths or reset
`unauthenticatedClientAction`. See `deploy-runbook.md` §1a for the exact commands.

## What the caller needs
- `az login` completed, correct subscription selected (`az account show`).
- Rights at the target scope to create policy set definitions / assignments
  (e.g. Resource Policy Contributor / Owner).
