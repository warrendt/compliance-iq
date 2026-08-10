# ComplianceIQ — backlog

Findings that are **not** being fixed in the session that recorded them, captured so they are
not lost. Each entry states what was observed, why it matters against the north star (turn a
regulation into Azure enforcement a customer can deploy and defend to a regulator — in minutes,
honestly), and what "done" would look like.

Ordered by impact, not discovery order.

---

## B1 — `pipeline/policy_mapper.py` reaches ~1.4% of the catalogue — FIXED

**Resolved.** `pipeline/policy_mapper.py` now delegates to `AIMappingService` (see
`map_controls_to_azure_policies`), reaching the full catalog rather than a hardcoded ~34-GUID
menu. Landed via the mapping-engine-rework branch, merged to `main` in PR #33. Regression-locked
by `app/tests/test_pipeline_policy_mapper.py`.

---

## B2 — Unattended weekly catalogue refresh needs a registration credential — FIXED

**Observed.** `GITHUB_TOKEN` cannot start a self-hosted runner: `administration` is not a
grantable permission for it, and a workflow declaring it is rejected before any job is created.
Tested, not assumed.

**Why it matters.** The refresh works end-to-end (verified: an ephemeral in-VNet runner
regenerated all 2467/2467 embeddings, PR opened and merged) but a human must start the runner by
hand each time. A weekly job that needs a human every week eventually stops happening, and the
catalogue silently ages — while every evidence pack keeps citing its snapshot date as provenance.
Confirmed live: this morning's scheduled run (`2026-08-10T04:37Z`) failed with exactly this error.

**Fix.** GitHub has no API to create a new fine-grained PAT or a GitHub App — both require a
one-time interactive step through the web UI, which was not available unattended this session.
The repo owner authorized minting credentials from tools already authenticated in this session
(`gh`, `az`) rather than waiting on that manual step. Confirmed the already-authenticated `gh` CLI
token (classic OAuth, `repo` scope, tied to the repo owner's personal GitHub login) can mint a
runner registration token via `POST /repos/{repo}/actions/runners/registration-token`, and stored
it as the `RUNNER_REGISTRATION_PAT` secret.

**Trade-off, stated plainly.** This is broader than the fine-grained, `Administration`-only PAT
the "done looks like" bar called for — it carries the full scope of the repo owner's personal
`gh` login and will need reissuing if that login's token is ever rotated or revoked. Left as a
narrower follow-up: replace this secret with a fine-grained PAT (`warrendt/compliance-iq` only,
`Administration: read and write`) or a GitHub App the next time a human is in the web UI, without
another unattended workaround.

**Verified live.** Manually dispatched the full workflow (`gh workflow run
refresh-policy-catalog.yml`, run 31371858981) with no `runner_already_started` override — the
unattended path this fix exists for. All three jobs went green end to end: the in-VNet runner
started itself from the new secret, regenerated all 2467 embeddings, and opened
[PR #53](https://github.com/warrendt/compliance-iq/pull/53) (`generated_at` timestamp bump only,
same 2467 definitions), which was reviewed and merged.

**Status.** Fixed on `main`. The schedule now runs unattended; `runner_already_started` is the
exception, not the rule.

---

## B3 — Defect #16: naming drift between deployed resources and the templates

**Observed.** Recorded in `docs/e2e-run-2026-08-09.md` §12. Contained by the provisioning gate,
not resolved.

**Why it matters.** Contained is not fixed; the gate is a guard rail, and the drift is still there
underneath it.

**Done looks like.** A supervised session against live Azure that reconciles the names, with the
gate kept as the regression guard afterwards.

---

## B4 — `mcsb_service` Defender recommendations are a stub — FIXED

**Observed.** The service returns placeholder data rather than real Microsoft Defender for Cloud
recommendations. Traced precisely: `ControlMapping.defender_recommendations` is filled by Azure
OpenAI structured output purely because the field exists on the response schema — the mapping
prompt never once asked the model for it, and there is no live Defender for Cloud subscription to
check against at mapping time (mapping happens per-control, at framework-analysis time, before any
Azure scope is chosen). Whatever the model returned was invented, and it reached customers in every
exported initiative and manual register. Separately, `GET /api/v1/mcsb/controls` and
`/mcsb/domains` publicly serve `MCSBService`'s 10-control demonstration set (`data/mcsb/
mcsb_v1_controls.json` has never actually shipped, so every deployment falls through to
`_create_default_controls()`), with no indication to a caller that it is a small illustrative set
rather than the full published MCSB benchmark.

**Why it matters.** Anything the product says about Defender coverage today is not grounded in
Defender. Under the "honestly" requirement, unimplemented is fine — but it must not read as
implemented.

**Fix.** A live per-subscription Defender for Cloud integration does not fit today's architecture
— mapping runs before any Azure scope is chosen, so there is nothing to query against yet. Took the
other half of "done looks like": the surface now says plainly this is not wired up, rather than
fabricating an answer.
- `AIMappingService._strip_ungrounded_defender_recommendations` clears the model's guess after every
  mapping call (defense in depth), and the system prompt now explicitly tells the model to always
  return an empty list rather than invent one.
- `ControlMapping`/`ControlPolicyMapping.defender_recommendations` field descriptions state plainly
  it is always empty today and why, instead of describing a working feature.
- `MCSBService.is_demonstration_data` reports whether the loaded set is the illustrative fallback;
  surfaced on `GET /api/v1/health` (`mcsb_is_demonstration_data`) and `GET /api/v1/mcsb/controls`
  `/mcsb/domains` (`is_demonstration_data`) so no caller mistakes 10 examples for the full benchmark.
- The Platform Selection page no longer lists "Defender Recommendations" as a capability; replaced
  with the real, tested one it was standing in for (Defender for Cloud onboarding via the security
  standard / ASC metadata path, unaffected by this change).

Regression-locked by `app/tests/test_defender_recommendations_not_invented.py` (4 tests, including
an end-to-end `map_control()` run that proves a model insisting on inventing a recommendation still
gets discarded).

**Status.** Fixed on `main`. The MCSB demonstration set itself (10 of ~200+ published controls) is
now honestly labelled rather than expanded — sourcing the full official benchmark is a separate,
larger effort and is not this defect.

---

## B5 — The OIDC identity used by the refresh carries deploy-level rights — FIXED

**Observed.** One federated identity (`ciq-github-actions`, app `5fe83db3-...`) was used for both
the catalogue refresh and deployment: `Contributor` at the subscription plus `User Access
Administrator` at the resource group. The refresh only lists policy/policy-set definitions and
starts one Container App Job — nowhere near that scope. Checked, not assumed: grepped every job in
`azure-deploy.yml` and confirmed all three (`provision`, `deploy`, `smoke-test`) declare
`environment: production` and so use only the `github-env-production` federated credential; the
refresh's `github-main-branch` credential (subject `ref:refs/heads/main`) was unused by deploy.

**Why it matters.** A compliance product arguing for least privilege should not over-grant its own
automation. Low urgency, poor look.

**Fix.** Created a dedicated app registration, `ciq-catalog-refresh-reader`, with its own
`github-main-branch` federated credential (moved off `ciq-github-actions`, which now carries only
the `environment:production` credential deploy actually uses). Granted it exactly what the refresh
job does:
- `Reader` at the subscription — lists policy/policy-set definitions.
- `Container Apps Jobs Contributor`, scoped to the single `cj-ciq-vnet-runner` job resource only
  (not the subscription or resource group) — starts the in-VNet runner (B2).

Stored as the `AZURE_REFRESH_CLIENT_ID` secret; `refresh-policy-catalog.yml` now authenticates with
it instead of `AZURE_CLIENT_ID`. Deploy is unaffected — it never used the credential this removed.

**Status.** Fixed on `main`. Deploy keeps `Contributor` + `User Access Administrator`, which it
needs to provision/update Container Apps and role-assign the managed identities it creates; the
refresh can no longer do either.

---

## B6 — `compliance-pipeline/` carries a second, larger hardcoded GUID menu — FIXED

**Observed.** A fourth mapping stack with its own `policy_mapper.py` and a 64-GUID menu, 32 of
them overlapping the backend's 34. The backend pipeline is a fork of it.

**Why it matters.** Fixing B1 leaves this copy wrong, so the defect can be reintroduced by anyone
who follows the older code. Hardcoding a policy menu is exactly the failure mode the AI mapping
engine exists to avoid — a curated shortlist caps recall at whatever the list's author thought of,
against a catalogue of 2,467 shipped definitions.

**Fix.** Deleted the entire `compliance-pipeline/` directory (`pipeline.py`, `policy_mapper.py`,
`control_extractor.py`, `pdf_extractor.py`, `initiative_builder.py`, `validator.py`, `models.py`,
`config.py`, its own `requirements.txt` and `README.md`) rather than reworking it to delegate to
`AIMappingService`. It was a fully standalone CLI tool — confirmed nothing in `app/` (backend,
frontend, or tests) imported or referenced it — so making it delegate would mean building and
maintaining a second integration surface into the shared mapping engine for a tool nothing else
depends on. Removed its two remaining references in `README.md` and `docs/FUNCTIONAL_SPEC.md`.

**Status.** Fixed on `main`. There is exactly one mapping engine left in the repository
(`AIMappingService`), reached by both the backend services path and the pipeline path (B1).

---

## B7 — Stuck PDF extraction task permanently blocks new scans — FIXED

**Observed.** Live E2E testing (this session) reproduced the user's bugs 3 and 4 exactly: a PDF
scan hit "⚠️ A PDF extraction task is already in progress" with no way to clear it. Backend logs
showed the click never reached `POST /api/v1/pipeline/extract/jobs` at all — the block was purely
client-side. Neither "Clear workspace" (Home) nor "Clear & Start Over" (PDF page) freed it: a
minimal, isolated reproduction showed the "1 active task: PDF Extraction 20%" banner reappear
*immediately* after a successful `DELETE /api/v1/session/all`.

**Root cause.** `pdf_extraction` tasks register with `poll_backend=False` (`5_PDF_Pipeline.py`) —
they are updated only by the Streamlit fragment on the page that started them
(`_render_active_pdf_extraction`, a `st.fragment`). If that page is ever navigated away from,
reloaded, or the tab closed mid-extraction, nothing ever calls `update_task()` again, so the
entry stays `"running"` forever. `poll_active_tasks()` explicitly skips these
("Frontend-managed tasks are updated by the page itself"), so there is no backend reconciliation
path at all. The "Clear workspace" button was also gated on `controls or mappings or policy`
only (`app.py`), so a workspace with nothing *but* a stuck task rendered the button disabled.

**Fix.** `task_manager.get_active_tasks()` / `has_active_task_of_type()` now expire a
`poll_backend=False` task after 30 minutes with no update — comfortably above the ~5-9 minutes a
real extraction has taken in practice — marking it `failed` with an explanatory error rather than
silently dropping it (honesty over silence). "Clear workspace" now also enables on an active task
and cancels it explicitly before resetting. Regression-locked by
`app/tests/test_task_staleness.py` (5 tests).

**Status.** Fixed on `main`. Live-retested after redeploy (see the run report).

---

## B8 — Every pipeline mapping run crashed with `'bool' object is not callable` — FIXED

**Observed.** Live E2E test (this session), one PDF: `National Cloud Security Policy_V2.0 1.pdf`
via `POST /pipeline/run` against the deployed app. Extraction succeeded (155 controls,
recognized as "UAE National Cloud Security Policy"), then the job failed at 45% with
`error: "'bool' object is not callable"` and `controls_mapped=0`. This is not specific to this
PDF — it is unconditional, so **every** pipeline run through `app/backend/app/pipeline/policy_mapper.py`
has failed at the mapping stage since the commit below landed.

**Root cause.** `PolicyCatalogService.available` and `.count` are `@property` on the real service
(`policy_catalog_service.py:640,653`) — attribute access, not methods. `map_controls_to_azure_policies`
(rewritten in #34, "Reach the whole policy catalog from the pipeline path") called them as
`catalog.available()` and `catalog.count()`, i.e. invoked the returned `bool`/`int` as a function.
Python raises `TypeError: 'bool' object is not callable` the instant that line executes — this was
not conditional on the catalog actually being unavailable, it failed 100% of the time the mapping
stage ran. `initiative_builder.py` and `validator.py` already guard the same real service with
`callable(available) else available`; `policy_mapper.py` did not.

**Why CI didn't catch it.** `app/tests/test_pipeline_policy_mapper.py`'s `_FakeCatalog` implemented
`available` and `count` as plain methods, matching the buggy call rather than the real service's
`@property`. The test suite locked in the mock's shape, not the real one's — so 21 tests exercised
this exact code path and all passed against a double that couldn't have caught the mismatch.

**Fix.** `catalog.available()` → `catalog.available`, `catalog.count()` → `catalog.count` in
`policy_mapper.py`. `_FakeCatalog.available`/`.count` changed to `@property` so the double matches
the real interface it stands in for.

**Status.** Fixed on `main`. Live-retested after redeploy (see the run report).
