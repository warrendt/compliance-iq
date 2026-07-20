---
name: complianceiq
description: >-
  Drive the deployed ComplianceIQ application end-to-end from chat: find or
  ingest a regulation PDF, run it through the backend extraction + Azure Policy
  mapping pipeline, review the generated initiative, and deploy it to Azure /
  Microsoft Defender for Cloud with guided enforcement and refresh questions.
  Also the reference for how ComplianceIQ's API, auth, infra, backend and
  frontend fit together. WHEN: "use compliance iq", "run this regulation
  through compliance iq", "extract controls from this PDF", "map controls to
  azure policy", "generate a policy initiative", "deploy initiative to azure",
  "onboard a standard to defender for cloud", "find regulations for <country /
  industry>", "how does compliance iq api / auth / infra work".
---

# ComplianceIQ skill

Turn a regulation PDF into a deployed Azure Policy initiative — the same flow the
ComplianceIQ web app performs (extract controls → map to Azure Policy → build an
initiative → deploy / assign / onboard to Defender for Cloud), driven from chat
against the **deployed** app. Authentication uses the caller's own `az login`
token.

> Read `reference/architecture.md`, `reference/api.md`, `reference/auth.md`,
> `reference/infra.md`, `reference/frameworks.md`, and
> `reference/troubleshooting.md` before troubleshooting anything. Do not guess
> ComplianceIQ internals — they are documented there.

## How it talks to the app

The backend Container App is **internal-only**. The skill reaches it through the
**frontend's `/api` reverse proxy** (`https://<frontend-fqdn>/api/v1/...`) and
sends the user's ARM token as `Authorization: Bearer`. The backend is configured
to accept the ARM audience (`https://management.azure.com`) so one token both
authenticates the caller and is reused for the ARM deploy calls. See
`reference/auth.md`.

All work goes through one stdlib-only CLI: `scripts/ciq.py` (no `pip install`;
needs only Python 3 and `az`). Never call the backend a different way.

### Base URL and token resolution
`ciq.py` resolves the base URL from, in order: `--base-url`, `$CIQ_BASE_URL`,
or an `az containerapp show` lookup via `--frontend-app`/`--resource-group`
(or `$CIQ_FRONTEND_APP`/`$CIQ_RESOURCE_GROUP`). The token comes from
`az account get-access-token --resource https://management.azure.com`. Confirm
`az login` and the right subscription (`az account show`) before starting.

## Guided workflow

Work one step at a time. Show the user what each step returned before moving on.

### a) Find or obtain the regulation PDF
- If the user already has a PDF, use its path.
- If they name a country / industry / framework, first check whether it is one
  of ComplianceIQ's 7 built-in regional frameworks (see
  `reference/frameworks.md`); if so, tell them the app already ships it and they
  may not need extraction.
- Otherwise help them locate the official source (use `web_search` / official
  regulator sites) and get the PDF into the session. Never fabricate regulation
  text — only process a real document the user supplies or an official source.

### b) + c) Extract controls and map to Azure Policy (one pipeline call)
```
python scripts/ciq.py health                      # confirm the proxy + backend
python scripts/ciq.py run --pdf <file.pdf> \
    [--min-confidence 0.5] [--allowed-locations eastus,westeurope]
```
`run` submits the PDF to `POST /pipeline/run`, prints the `job_id`, then polls
`GET /pipeline/status/{job_id}` to completion, streaming progress
(stage / controls extracted / controls mapped) to stderr. This performs the full
ComplianceIQ pipeline: PDF extraction → control intelligence → Azure Policy
mapping → initiative build.

Then fetch the artifacts (the Azure initiative JSON) and save them:
```
python scripts/ciq.py artifacts --job-id <id> --out ./ciq-out
```
Summarise for the user: how many controls were extracted, how many mapped, and
the initiative's policy count. Offer to show unmapped controls.

### d) Operational knowledge
When the user hits an error or asks how something works, answer from the
`reference/` docs (API surface, auth flow, infra topology, front/back-end split,
troubleshooting) rather than improvising. Common gotchas live in
`reference/troubleshooting.md` (e.g. the in-memory job store means status /
artifacts must hit the same replica; ARM-token audience must be accepted on the
backend; Easy Auth must pass the bearer header through).

### e) Deploy to Azure / Defender for Cloud — ask before acting
Never deploy without walking the user through these questions (they map exactly
to the app's `DeployRequest` — see `reference/api.md`). Default to the **safe**
option and make the destructive one explicit.

```
python scripts/ciq.py scopes                       # list subs / mgmt groups
python scripts/ciq.py validate --job-id <id> --scope <arm-scope>   # dry run
python scripts/ciq.py deploy   --job-id <id> --scope <arm-scope> \
    [--assign] [--enforce] [--location eastus]
```

Ask, in order:
1. **Scope** — which subscription or management group? (from `scopes`). Confirm
   `az account show` matches the intended subscription.
2. **Validate first?** — yes (recommended). Run `validate` and resolve any
   structural errors before deploying.
3. **Definition-only or assign now?** — `--assign` also creates a policy
   assignment. Without it, only the initiative/policy definitions are created.
4. **Enforcement** — **audit-only / DoNotEnforce is the default and the
   recommendation.** Only pass `--enforce` when the user explicitly wants active
   enforcement (DeployIfNotExists/Modify effects will remediate/deny). State
   this trade-off in one line before they choose.
5. **Identity location** — required whenever the initiative contains
   DeployIfNotExists or Modify policies (a managed identity is created even
   under DoNotEnforce). Ask for the region (`--location`, default `eastus`).
6. **Refresh / Defender** — after assignment, Azure Policy compliance
   evaluation is asynchronous (can take ~30 min); tell the user results are not
   instant and offer to trigger a re-evaluation. The exported initiative is
   already stamped with the `ASC` metadata that surfaces it under Defender for
   Cloud → Regulatory compliance, so no extra onboarding call is needed. If the
   token has expired mid-session, re-run `az login` (or let `ciq.py` fetch a
   fresh token on the next call).

### f) Token
Everything uses the caller's `az` login token (ARM audience). If a call returns
401, the token likely lacks the accepted audience or has expired — see
`reference/troubleshooting.md`.

## Safety rules
- Only `validate`, `deploy --assign`, and `--enforce` change Azure state.
  `health`, `run`, `status`, `artifacts`, and `scopes` are read-only /
  non-destructive (extraction produces artifacts only).
- Always `validate` before `deploy`, and default deployments to audit-only.
- Never invent regulation content, scope IDs, or initiative policies. If the
  pipeline returns nothing mapped, report that honestly.
- Do not print full bearer tokens; never commit tokens or environment-specific
  identifiers.

## Files
- `scripts/ciq.py` — the CLI the skill runs (stdlib + `az`).
- `scripts/ciq_core.py` — pure request/response helpers (unit-tested).
- `tests/test_ciq_client.py` — tests for the client.
- `reference/*.md` — ComplianceIQ operational knowledge.
