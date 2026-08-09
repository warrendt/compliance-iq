# E2E run — pipeline mapping crash (B8), one PDF, one full cycle

Continuation of the test → fix → deploy → re-test backlog. Scope for this session: one PDF
(`National Cloud Security Policy_V2.0 1.pdf`), one full walkthrough, fix only what a full
walkthrough actually surfaced.

---

## 1. Live UI walkthrough — blocked by tooling, not the app

Attempted a Playwright/computer-use walkthrough against the deployed frontend, authenticated via
Easy Auth (SSO succeeded silently using the signed-in Windows account — no prompt). Two blockers:

- The isolated Playwright MCP browser could not launch (`Chromium distribution 'chrome' is not
  found`), even after installing Chrome to work around what looks like an enterprise policy
  blocking the standard installer.
- The only remaining automation surface (computer-use) drives the operator's real, live desktop
  in the background, never bringing the window to the foreground. Edge's memory-saver marked the
  tab **"Sleeping"** after it sat unfocused, freezing its JS before the Streamlit app finished
  mounting — a blank page on every load/reload. Confirmed this is a tooling artifact, not an app
  defect, by observing the tab's title change to "... - Sleeping - Memory usage - 113 MB".

**Not claimed as a product bug.** Given the live desktop was under continuous real use (Edge kept
reporting "user input detected"), further UI automation was deliberately not forced. Pivoted to
API/CLI-level testing against the same deployed backend, which is a genuine test of the same
pipeline the UI drives (extraction → mapping → initiative), just not of Streamlit's own rendering.

## 2. `ciq.py` itself was broken on Windows — found first, fixed to unblock everything else

`_az()` called `subprocess.run(["az", ...])` with `shell=False`. On Windows `az` is `az.cmd`;
`CreateProcess` does not resolve `PATHEXT` for a bare command name without a shell, so every `az`
call raised `FileNotFoundError` — including `ciq.py health`. Fixed by resolving the executable
via `shutil.which("az")` first. Added 2 regression tests (`test_az_resolves_executable_via_which`,
`test_az_raises_when_not_on_path`) mocking `shutil.which`/`subprocess.run` so this can't regress
silently on a non-Windows CI runner.

## 3. Full pipeline run, one PDF — VERIFIED, and it failed exactly where B7's fix said it wouldn't

```
ciq.py run --pdf "National Cloud Security Policy_V2.0 1.pdf"
```

Extraction succeeded: 155 controls, framework recognized as "UAE National Cloud Security Policy".
The job then failed at 45% progress, in the mapping stage:

```json
{
  "status": "failed",
  "stage": "Mapping controls to Azure Policies",
  "controls_extracted": 155,
  "controls_mapped": 0,
  "error": "'bool' object is not callable"
}
```

**Root cause.** `PolicyCatalogService.available` and `.count` are `@property` on the real service
(`policy_catalog_service.py:640,653`). `map_controls_to_azure_policies` (`policy_mapper.py`,
rewritten in #34 "Reach the whole policy catalog from the pipeline path") called them as
`catalog.available()` and `catalog.count()` — invoking the returned `bool`/`int` as a function.
This is **unconditional**: it fails 100% of the time this line executes, regardless of whether the
catalog is actually loaded. Every pipeline run through this path has failed at the mapping stage
since #34 landed. `initiative_builder.py` and `validator.py` already guard the same real service
defensively (`callable(available) else available`); `policy_mapper.py` did not.

**Why CI didn't catch it.** `test_pipeline_policy_mapper.py`'s `_FakeCatalog` implemented
`available`/`count` as plain methods — matching the bug's call shape, not the real service's
`@property` interface. 21 tests exercised this exact code path against a double shaped like the
bug and all passed. The test suite was testing the mock, not the contract.

**Fix.** `catalog.available()` → `catalog.available`, `catalog.count()` → `catalog.count`.
`_FakeCatalog.available`/`.count` changed to `@property` so the double can't silently drift from
the real interface again.

## 4. Shipped the loop

Committed → [PR #50](https://github.com/warrendt/compliance-iq/pull/50) → CI green (unit tests) →
merged to `main` (`296fc6e`) → deploy workflow:

- **Deploy containers**: green on retry (first attempt hit a transient ACR build network failure
  reaching `deb.debian.org`, unrelated to this change — re-run succeeded).
- **Smoke test**: green on retry (first attempt hit a transient ARM `InternalServerError` on
  `az containerapp show`, unrelated to this change — re-run succeeded). Backend revision
  `ca-backend-ciq-dev-kz2jze--0000028` confirmed running image `backend:296fc6e`, `Healthy`.

## 5. Re-tested live — VERIFIED, fixed

Same PDF, same command, against the redeployed backend:

```json
{
  "status": "completed",
  "stage": "Complete",
  "controls_extracted": 163,
  "controls_mapped": 163,
  "error": null
}
```

Fetched the artifacts: initiative `"UAE National Cloud Security Policy Compliance Controls"` with
**138 real Azure Policy definitions** (sampled GUIDs resolve against the catalog, not a
hardcoded list). Extraction count differs run-to-run (155 vs 163) — the same non-determinism
already recorded in `docs/e2e-run-2026-08-09.md` §"NEW FINDING — extraction is non-deterministic";
not a new finding here.

## Backlog status

- **B8 (this fix) — fixed, deployed, verified.** Added to `docs/BACKLOG.md`.
- B1, B7 — previously fixed, unaffected by this cycle.
- B2 (runner credential) — still needs the repo owner's PAT decision.
- B3 (naming drift), B5 (over-privileged OIDC), B6 (duplicate pipeline copy) — untouched;
  all three need either a supervised live-Azure session or a standalone code/infra decision, not
  a PDF-driven E2E walkthrough. Not attempted this cycle.
- B4 (MCSB stub) — untouched. Candidate for the next cycle: it's a code-only gap (no infra/live-Azure
  session required), unlike B3/B5/B6.

## Not done

- Did not re-run the 11/14-PDF reference sweep or the CSV/clear-workspace regression suite —
  only the mapping path this fix touched.
- Live Streamlit UI walkthrough remains unverified in *this* session for the reasons in §1. B7's
  fix (stuck task / Clear workspace) was already live-verified in the prior cycle and is
  unaffected by this change.
- Only one test → fix → deploy → retest cycle completed this session.
