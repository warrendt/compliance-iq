# ComplianceIQ — Deploy PR #30 + live E2E sweep (2026-07-21)

**Scope:** (1) deploy the latest merged code from **PR #30** ("Enforce
sovereignty-aware SLZ exports") to the dev environment, avoiding the
stale-worktree trap; (2) run a full live end-to-end sweep through the deployed
app with a real regulation PDF, with focus on verifying the PR #30 Sovereign
Landing Zone (SLZ) export path.

**Environment (placeholders — repo is public):**
- Frontend (public, Easy Auth): `https://<frontend-domain>/`
- Backend (internal ingress only): `<backend-container-app>`
- Resource group / subscription / tenant: withheld from this doc by policy.

**Test artifact:** `National Cloud Security Policy_V2.1.pdf` (from operator's
Microsoft Scout Regulations PDFs folder; copied into an MCP-allowed root for
upload).

> Honesty note: items are tagged **VERIFIED** (evidence captured this run) or
> **[UNVERIFIED]**. Nothing here is claimed as passing without evidence.

---

## Executive summary

| Area | Result |
| --- | --- |
| Deploy from merged `main` (PR #30, merge `dcc8d34`) — not stale worktree | ✅ VERIFIED |
| Backend deploy (dev, `azd deploy backend --no-prompt`) | ✅ VERIFIED — SUCCESS |
| Frontend deploy (dev, `azd deploy frontend --no-prompt`) | ✅ VERIFIED — SUCCESS |
| Easy Auth intact after deploy (RedirectToLoginPage) | ✅ VERIFIED |
| PDF extraction — 147 controls, framework auto-detected | ✅ VERIFIED |
| AI batch mapping — 147/147 mapped, 0 failures | ✅ VERIFIED |
| Review page — 147 mappings, 62% avg confidence | ✅ VERIFIED |
| **PR #30 SLZ export — jurisdiction auto-detect + guardrail + tiering** | ✅ VERIFIED |
| SLZ initiatives generated + saved (Version 3.0.0) | ✅ VERIFIED |
| MCSB initiative — UAE-consistent displayName after regen | ✅ VERIFIED |
| Full page sweep (Explorer, Gap, Version History, Workspace) | ✅ VERIFIED — 0 Python exceptions |
| Workspace activity recording populated (upload/map/export) | ✅ VERIFIED |
| Console errors across all pages | ✅ 0 errors (8 benign Vega-Lite warnings) |

---

## 1. The stale-worktree trap (avoided)

PR #30 (`warrendt-auditing-policy-mapping`, "Enforce sovereignty-aware SLZ
exports") merged into `main` at merge commit `dcc8d34`. The main worktree
(`/Users/wdt/Repos/compliance-iq`) was confirmed in sync with `origin/main` at
`dcc8d34`.

**Trap:** the azd `dev` environment was checked into a *different* worktree
(`warrendt-fictional-chainsaw`) sitting on a **stale** branch
(`warrendt-complianceiq-copilot-skill` @ `91033c1`) — **1,678 insertions behind
`main`** in `app/`. Deploying from there would have shipped old code, the exact
risk the operator flagged.

**Resolution:** brought the azd env (`.azure/`) into the main worktree at the
merge commit, then deployed. `.azure/` is **not** gitignored in this repo, so it
was added to `.git/info/exclude` locally to keep deployment-specific IDs out of
the public repo.

## 2. Deploy (VERIFIED)

- `azd deploy backend --no-prompt` → **SUCCESS** (remoteBuild in ACR).
- `azd deploy frontend --no-prompt` → **SUCCESS**.
- `azd provision` / `azd up` **not** used (blocked by landing-zone policy
  `Deny-Subnet-Without-Nsg`).
- Frontend Easy Auth re-checked: already `RedirectToLoginPage` (no drift this
  run). Frontend returned 401 to anonymous probe = Easy Auth enforcing = healthy.

## 3. Live E2E pipeline (VERIFIED)

Authenticated via SSO. Pipeline driven through the deployed UI:

1. **Upload / extract** — `National Cloud Security Policy_V2.1.pdf` →
   **147 controls**, framework **auto-detected** as *UAE National Cloud Security
   Policy v2.0*.
2. **AI mapping** — batch run: **147/147 mapped, 0 failures**, avg confidence
   **62%**, 17 high-confidence (≥80%). On-brand success effect (balloons
   replacement) fired.
3. **Review & Edit** — Total Mappings 147, Avg Confidence 62%, 0 console errors.

## 4. PR #30 — Sovereign Landing Zone export (VERIFIED)

The feature under test worked end-to-end:

- **Jurisdiction auto-detection** from the framework profile → **UAE**.
- **Allowed Azure locations** pre-filled: `uaenorth` (with `uaecentral` flagged
  restricted).
- **Sovereignty tiering:** L1 Global = 69, L2 CMK = 10, L3 Confidential = 0;
  **79 sovereignty-mapped controls**.
- **Residency guardrail** confirmation gate present and honoured.
- **Generate SLZ Initiatives** → ✅ generated, saved as **Version 3.0.0**.
  Archetypes: `sovereign_root`, `confidential_corp`, `confidential_online`, with
  an enforceable `listOfAllowedLocations` policy parameter
  (allowedValues: `uaenorth`, `uaecentral`).
- **MCSB initiative** regenerated to clear a stale cached "Dubai" preview →
  fresh output `displayName: "UAE National Cloud Security Policy Compliance
  Initiative"`. GUID/parameterized-builtin filters active (4 invalid GUIDs,
  14 parameterized built-ins excluded — expected).

## 5. Page sweep (VERIFIED — 0 Python exceptions)

| Page | Result |
| --- | --- |
| Policy Explorer (BETA) | Loads clean; "No definitions at this scope" (expected for tenant-scope BETA) |
| Gap Analysis (Diff_Compare) | Loads clean; framework dropdown + upload present |
| Version History | 29 versions; newest MCSB *UAE … v9.0.0*, newest SLZ *UAE … SLZ v3.0.0* |
| My Workspace (Profile) | Populated: Control sets 1, Mappings 420, Exports 7; recent activity shows this run's upload/map/export |

All pages: **0 console errors**, 8 benign Vega-Lite charting warnings (bundled
noise, not app defects).

## 6. Workspace activity recording (VERIFIED)

Both halves of the workspace pipeline populated correctly — Recent Activity feed
captured this run's events:
- 📄 Uploaded `National_Cloud_Security_Policy_V2.1.pdf` (v1) — 147 rows (20:02)
- 🤖 AI mapping (20:06)
- 📦 Exported `mcsb_initiative` for *UAE National Cloud Security Policy*
  (79 controls) (20:09)

---

## Notes / non-defects

- **Stale-preview quirk:** the top "Generated Policy Initiative" (MCSB) preview
  initially showed a cached "Dubai" displayName from a restored prior workflow;
  the config description and SLZ output correctly said UAE. Regenerating cleared
  it. "Start a new session" did not fully clear the sidebar session-status
  cache — the new PDF upload/load is what replaced the working set.
- **Version churn:** MCSB version reached v9.0.0 because the initiative was
  regenerated several times during verification (each generate is an immutable
  version — by design).

## Sanitisation

- No subscription / tenant / resource-group GUIDs, private hostnames, or emails
  in this doc (placeholders used per public-repo policy).
- Deployment env (`.azure/`) kept git-excluded locally; not committed.
