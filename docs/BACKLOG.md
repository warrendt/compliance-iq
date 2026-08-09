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

## B2 — Unattended weekly catalogue refresh needs a registration credential

**Observed.** `GITHUB_TOKEN` cannot start a self-hosted runner: `administration` is not a
grantable permission for it, and a workflow declaring it is rejected before any job is created.
Tested, not assumed.

**Why it matters.** The refresh works end-to-end (verified: an ephemeral in-VNet runner
regenerated all 2467/2467 embeddings, PR opened and merged) but a human must start the runner by
hand each time. A weekly job that needs a human every week eventually stops happening, and the
catalogue silently ages — while every evidence pack keeps citing its snapshot date as provenance.

**Done looks like.** A fine-grained PAT (`warrendt/compliance-iq` only, `Administration: read and
write`) stored as `RUNNER_REGISTRATION_PAT`, or a GitHub App. Then the schedule runs unattended
and `runner_already_started` becomes the exception rather than the rule.

**Mitigation today.** The workflow fails with instructions rather than shipping a catalogue
without its embeddings, and `test_catalog_snapshot_is_not_stale` fires if the loop stops.

**Status.** Infrastructure and CI are done; only the credential decision remains, and it needs the
repo owner (creating a PAT is not something to do unilaterally).

---

## B3 — Defect #16: naming drift between deployed resources and the templates

**Observed.** Recorded in `docs/e2e-run-2026-08-09.md` §12. Contained by the provisioning gate,
not resolved.

**Why it matters.** Contained is not fixed; the gate is a guard rail, and the drift is still there
underneath it.

**Done looks like.** A supervised session against live Azure that reconciles the names, with the
gate kept as the regression guard afterwards.

---

## B4 — `mcsb_service` Defender recommendations are a stub

**Observed.** The service returns placeholder data rather than real Microsoft Defender for Cloud
recommendations.

**Why it matters.** Anything the product says about Defender coverage today is not grounded in
Defender. Under the "honestly" requirement, unimplemented is fine — but it must not read as
implemented.

**Done looks like.** Either it queries Defender for real, or the surface says plainly that this
is not yet wired up.

---

## B5 — The OIDC identity used by the refresh carries deploy-level rights

**Observed.** One federated identity is used for both the catalogue refresh and deployment. The
refresh only reads policy definitions.

**Why it matters.** A compliance product arguing for least privilege should not over-grant its own
automation. Low urgency, poor look.

**Done looks like.** The refresh authenticates with a Reader-scoped identity; deploy keeps the
rights it needs.

---

## B6 — `compliance-pipeline/` carries a second, larger hardcoded GUID menu

**Observed.** A fourth mapping stack with its own `policy_mapper.py` and a 64-GUID menu, 32 of
them overlapping the backend's 34. The backend pipeline is a fork of it.

**Why it matters.** Fixing B1 leaves this copy wrong, so the defect can be reintroduced by anyone
who follows the older code.

**Done looks like.** Either it is deleted, or it delegates to the same engine. A decision, not an
oversight.

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
