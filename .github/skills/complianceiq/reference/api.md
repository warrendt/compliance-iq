# ComplianceIQ API reference (skill-relevant surface)

Base URL for the skill: `https://<frontend-fqdn>/api/v1` (through the nginx
`/api` proxy). All routers are mounted under `settings.api_v1_prefix` = `/api/v1`.
Send `Authorization: Bearer <ARM token>` on every call (harmless on the
unauthenticated pipeline routes; required on `policy/*` and `deploy/*`).

Routers: `health`, `mapping` (`/mapping`), `policy` (`/policy`),
`pipeline` (`/pipeline`), `deploy` (`/deploy`), plus `platform`, `m365`,
`purview`, `session`, `user`, `comparison`, `version`, `sovereignty`.

## Health
`GET /api/v1/health` → `{status, ...}` (also `/health/ping`, `/health/logs`).

## Pipeline (extraction + mapping + initiative) — **unauthenticated**
- `POST /pipeline/run` — **multipart/form-data**:
  - `pdf_file` (file, required)
  - `min_confidence` (float, 0–1, default `0.5`)
  - `allowed_locations` (string, comma-separated Azure regions, optional)
  Returns `PipelineJobStatus` incl. `job_id`. Runs as a background task.
- `GET /pipeline/status/{job_id}` → `PipelineJobStatus`
  (`status`, `progress`, `stage`, `controls_extracted`, `controls_mapped`,
  `error`). Terminal statuses: `completed`, `failed`, `cancelled`.
- `GET /pipeline/artifacts/{job_id}` → `PipelineArtifacts`. `files.initiative`
  holds the Azure initiative JSON (from the generated `*_Initiative.json`).
- `GET /pipeline/download/{job_id}` — zipped artifacts.
- Also: `POST /pipeline/extract` (sync extract-only), `/pipeline/extract/jobs`,
  `/pipeline/run/m365`, `/pipeline/run/purview`, `/pipeline/selftest`.

## Granular mapping (`/mapping`) — for advanced flows
`POST /mapping/analyze` (job) · `POST /mapping/map-batch` · `POST /mapping/map-single`
· `GET /mapping/status/{job_id}` · `GET /mapping/mcsb/{controls,domains}`.

## Policy generation (`/policy`) — **authenticated**
`POST /policy/generate` (+ `/generate/{json,bicep,scripts,slz}`) ·
`POST /policy/details` (policy_ids capped at 100 — chunk larger lists) ·
`GET /policy/catalog/status` · `POST /policy/catalog/refresh`.

## Deploy (`/deploy`) — **authenticated**, uses the caller's ARM token
- `GET /deploy/scopes` → `{scopes: [{id, display, type, scope}], warnings: []}`
  where `type` is `subscription` or `management_group` and `scope` is the ARM
  path. Subscriptions and management groups are fetched independently; a 403 on
  management groups still returns subscriptions.
- `POST /deploy/validate` — non-destructive dry run. Body (`ValidateRequest`):
  ```json
  { "scope": "...", "initiative_name": "...", "initiative_body": { }, "check_references": true }
  ```
- `POST /deploy/initiative` — create the policy set (and optionally assign).
  Body (`DeployRequest`):
  ```json
  {
    "scope": "/subscriptions/<sub>  or  /providers/Microsoft.Management/managementGroups/<mg>",
    "initiative_name": "framework_name_lowercased_with_underscores (<=128)",
    "initiative_body": { "properties": { } },
    "assign": false,
    "assignment_display_name": null,
    "assignment_description": "",
    "enforce_mode": false,
    "location": "eastus"
  }
  ```
  Field meaning (the guided deploy questions):
  - `scope` — subscription or management group to deploy to.
  - `assign` — also create a policy assignment (else definition-only).
  - `enforce_mode` — `false` = **DoNotEnforce / audit-only (safe default)**;
    `true` = enforce (DeployIfNotExists/Modify remediate or Deny).
  - `location` — identity region, **required** when the initiative contains
    DeployIfNotExists or Modify policies (an identity is created even under
    DoNotEnforce).
- `GET /deploy/{definitions,initiatives,assignments}?scope=...` — list existing.

## The skill CLI maps to these as
| CLI command | API call |
|---|---|
| `ciq.py health` | `GET /health` |
| `ciq.py run --pdf` | `POST /pipeline/run` then poll `GET /pipeline/status/{id}` |
| `ciq.py status --job-id` | `GET /pipeline/status/{id}` |
| `ciq.py artifacts --job-id` | `GET /pipeline/artifacts/{id}` |
| `ciq.py scopes` | `GET /deploy/scopes` |
| `ciq.py validate` | `POST /deploy/validate` |
| `ciq.py deploy` | `POST /deploy/initiative` |
