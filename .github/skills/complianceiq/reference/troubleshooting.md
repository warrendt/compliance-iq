# ComplianceIQ troubleshooting (skill)

## 401 Unauthorized on `/api/v1/policy/*` or `/deploy/*`
- Token expired → re-run `az login`; `ciq.py` fetches a fresh token per call.
- Wrong audience → the backend must have
  `AZURE_AD_ACCEPTED_AUDIENCES` including `https://management.azure.com`
  (and the trailing-slash variant). See `auth.md` / `infra.md`.
- Token is for the wrong tenant/subscription → check `az account show`.
- Pipeline routes (`/pipeline/*`) are unauthenticated; a 401 there means the
  proxy/backend is rejecting the request for another reason, not auth.

## 404 / connection errors on `/api/...`
- The nginx `/api` proxy isn't deployed or `BACKEND_URL` is unset (the block is
  stripped when `BACKEND_URL` is empty). Redeploy the frontend and confirm
  `BACKEND_URL` is set on `ca-frontend-*`.
- `GET /api/v1/health` is the quickest end-to-end proxy check (`ciq.py health`).

## Bearer header not reaching the backend
Frontend Easy Auth runs `unauthenticatedClientAction = RedirectToLoginPage`, so
it 302-redirects `/api` bearer calls to the login page unless the `/api` paths
are in `globalValidation.excludedPaths`. If `ciq.py health` returns HTML or a
redirect, confirm `excludedPaths` still contains `/api`, `/api/`, `/api/*`
(a deploy can drop them). Patch it back with api-version `2025-10-02-preview`
(see `auth.md` / `deploy-runbook.md` §1a). Also confirm nginx passes
`Authorization` (it does in the committed config). Smoke test: `ciq.py health`
then a tiny PDF through `ciq.py run`.

## Status/artifacts 404 after a successful run (replica mismatch)
**Known caveat.** The pipeline job store `_jobs` is **in-memory per replica**,
and `/artifacts` and `/download` read the local `output_dir` of the replica that
ran the job. With `maxReplicas > 1`, a poll/artifacts request can land on a
different replica. `status` has a Cosmos fallback; **artifacts do not**.
Mitigations:
- Dev typically runs a single replica — usually fine.
- If artifacts 404 but status was `completed`, retry a few times (you may hit
  the right replica), or reduce backend `maxReplicas` to 1 for a run.

## Pipeline returns few/no mapped controls
- Lower `--min-confidence` (default 0.5) to surface more candidate mappings, but
  review them — lower confidence = noisier matches.
- Report honestly if extraction found no controls (bad/scanned PDF). The mapper
  uses the Azure built-in catalog snapshot (~2465 defs), not MCSB.

## Deploy validation fails
- `check_references` catches structural issues (missing policy defs, duplicate
  reference IDs, non-GUID policy IDs, missing groups). Fix the initiative JSON
  before deploying.
- Built-in policies with required parameters lacking defaults, or `System
  Policy`/`Static` policyType built-ins, cannot go into a custom policy set —
  strip or parameterize them.
- DeployIfNotExists/Modify policies require `location` (identity region) even
  under DoNotEnforce.

## Compliance results don't show up immediately
Azure Policy evaluation is asynchronous (can take ~30 min after assignment).
The initiative carries `ASC` metadata so it appears under Defender for Cloud →
Regulatory compliance once evaluated. Offer to trigger a re-evaluation rather
than assuming failure.
