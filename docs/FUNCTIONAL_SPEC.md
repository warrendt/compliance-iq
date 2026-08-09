# ComplianceIQ — functional specification

Written from behaviour verified against the deployed application on 2026-08-09, not from
intent. Anything not verified is marked **[UNVERIFIED]**.

---

## 1. What the product is for

Turn a regulation a customer is legally bound by into Azure enforcement they can deploy
and defend to a regulator — in minutes, honestly, without an expert.

`docs/PROCESS_DOCUMENTATION.md` prices the manual alternative at **25–35 hours** for the
shipped framework set: 3–4h research and 2–3h cataloguing per framework, plus 1–2h of
GUID validation — a step that exists only because humans mistype identifiers.

The customers are sovereign-cloud organisations in the Gulf and Africa (SAMA, ADHICS,
NCA CSCC and NDMO, KSA Government, South African Government/POPIA/SITA, Oman Government)
whose Azure adoption is gated on proving controls to a regulator. There, compliance is
not a report — it is the precondition for using the cloud at all.

The seven pre-built catalogues are proof of the method. The product is onboarding the
eighth, and the hundredth, without the expert.

**"Honestly" is load-bearing.** An auditor reads this output. A confident wrong answer is
worse than an admitted gap: a gap gets remediated, a wrong answer gets discovered by the
regulator. Every design decision below follows from that.

---

## 2. The coverage taxonomy — the product's central claim

Each control is answered on **two independent axes**.

### Axis 1 — how the control is met

| Code | Presented as | Emits Azure Policy IDs? |
|---|---|---|
| `A_AzurePolicy` | Azure Policy enforced | **Yes** |
| `B_AzureConfig` | Azure/Entra config — partial | **Yes** |
| `C_Process` | Process / organisational | No — manual register |
| `D_MicrosoftAttestation` | Microsoft attested | No — Microsoft attestation |

A and B are **identical for policy emission**. The nuance is carried by `policy_effects`
and `enforcement_plane`, which are resolved from the catalogue snapshot rather than
inferred, because whether a policy denies or merely audits is a fact about the
definition and asking a model to recall it invites confident errors.

"Partial" in B is not decoration: it means policy or Entra configuration covers a
substantial part and full coverage needs a named step outside Azure Policy (Conditional
Access, Customer Lockbox). The product names that step rather than reporting an
unexplained shortfall.

### Axis 2 — who owns the control

`responsibility` is `Customer` / `Microsoft` / `Shared`, assigned by the nature of the
control and **not derived from the category**. The gold workbook contains 30
process/organisational controls owned by Microsoft; a system that ties responsibility to
category cannot express them and misattributes all 30.

**Verified live** on a 57-control NCA CCC run: categories `{C_Process 23,
D_MicrosoftAttestation 17, B_AzureConfig 17}` alongside responsibility `{Customer 30,
Microsoft 23, Shared 4}` — the axes vary independently in real output.

### Category D must be cited, not asserted

D is where the auditor's answer is handed over, so it resolves to one of four honest
states:

1. a validated certification clause,
2. a validated audit-report criterion,
3. published Microsoft documentation,
4. an **explicit unattested gap**, with its reason.

Citations are checked against a curated attestation catalogue exactly as GUIDs are
checked against the policy catalogue. Clause numbers come from Azure's own built-in
compliance initiatives (the ISO/IEC 27002:2022 group identifiers), so they are grounded
in a Microsoft artefact rather than authored — and no standard body text is reproduced.
**Anything that cannot be grounded is reported as a gap, never printed as a guess.**

The gap case is the sovereign case. A regulator demanding UAE security clearance for
operations personnel is not satisfied by ISO 27001 screening. Labelling that
"Microsoft-attested" would hand the customer a false pass on precisely the requirement
their regulator cares most about.

---

## 3. Invariants the system must satisfy

These are rules, deliberately free of any number that could be gamed by tuning against a
fixture. They are asserted per framework by `ops/sweep_reference_pdfs.py`.

* No C or D control emits a policy ID, and each carries a substantive, control-specific
  reason and appears in the manual register.
* Every emitted identifier exists in the catalogue, on every path.
* Mappings are drawn from the whole catalogue — demonstrated by identifiers appearing
  from outside the historical hardcoded menu. Reintroducing a menu fails immediately.
* Nothing is silently dropped. Every identifier that fails validation, resolves to
  nothing, or is deprecated surfaces as a named finding on its control.
* Effects align one-to-one and positionally with the policy IDs on the row, so a reader
  can tell which policy denies and which only audits.
* Responsibility and coverage category are independent outputs.
* A control needing a custom definition says so; it is not reported as uncovered.
* Initiative-level coverage is representable, and deprecated definitions are reported as
  deprecated rather than as missing.
* Every mapping carries provenance — what verified it and when, plus the catalogue
  snapshot date.
* An engine failure is declared as an engine failure, never as a coverage judgement.
* `control_id` is the join key everywhere; nothing keys on `control_name`.

---

## 4. API surface — VERIFIED

**94 operations across 89 paths and 14 routers**, read from the deployed OpenAPI
document. (Earlier documentation said 92 endpoints / 13 routers; that was stale.)

| Router | Concern |
|---|---|
| `health` | liveness and dependency status |
| `platform` | platform/profile selection |
| `session` | workflow session state |
| `mapping` | control→policy mapping jobs |
| `policy` | catalogue, initiative generation, lookup |
| `pipeline` | PDF extract → map → build → export |
| `comparison` | Diff Compare and initiative build |
| `deploy` | ARM deployment (audit-only / what-if) |
| `sovereignty` | SLZ sovereignty objectives |
| `version` | initiative version history |
| `user`, `m365`, `purview`, `deploy` | identity and adjacent services |

### Catalogue lookup reports five distinct kinds

`GET /policy/catalog/lookup/{identifier}` returns `kind` ∈ {`definition`, `initiative`,
`microsoft_managed_control`, `deprecated`, `unknown`} plus `enforceable`,
`classification` and `explanation`.

This matters because the three-way collapse it replaces — reporting managed-control,
withdrawn and absent identifiers identically as `known=false` — is the same defect class
the product exists to eliminate: distinct facts flattened into one answer that reads as
"we checked and there is nothing".

The 327 initiative members that resolve to nothing are all `policyType: Static`
Microsoft Managed Controls. That is Category D's answer, not broken data.

---

## 5. User-facing pages

Ten Streamlit pages: Platform Selection, Upload Controls, AI Mapping, Review & Edit,
Export Policy, PDF Pipeline, Policy Explorer, Profile, Diff Compare, Version History.

Two paths reach the mapping engine: the **services path** (Pages 1–4) and the
**pipeline path** (Page 5 PDF Pipeline, Page 8 Diff Compare, and the skill CLI). Both
now run the same engine against the same catalogue. The pipeline path previously carried
a hardcoded menu of 34 identifiers — roughly 1.4% of the ~2,467 shipped definitions, six
of them not real.

**[UNVERIFIED]** The 10 pages were not driven end-to-end in this run: they sit behind
interactive Easy Auth and no user was present to sign in.

---

## 6. Deployment model

Initiatives deploy **`DoNotEnforce` (audit-only)** so they are safe to point at
production on day one. Trust precedes enforcement: a customer sees what would have been
blocked before anything is blocked.

Initiative scoping keys off **effect**, not category, so an audit/DINE policy is never
presented as a hard guardrail and a `Deny` is never softened because the control was
labelled B.

---

## 7. Operating constraints — VERIFIED

* Azure OpenAI and the storage account both have `publicNetworkAccess: Disabled`. **The
  mapping engine cannot execute outside the VNet**, so end-to-end verification runs as a
  Container Apps job in the same managed environment.
* Runtime is roughly **5–7 minutes per mid-size framework** (~325s for 57 controls at
  concurrency 4). **[UNVERIFIED]** token cost per framework.
* Structured-output calls must be budgeted for a **reasoning** model: it spends
  completion tokens on reasoning before emitting output, so a ceiling sized for a
  non-reasoning model is consumed entirely by reasoning and the call fails having
  produced nothing.
* Response models used as `response_format` must be **closed at every level**
  (`additionalProperties: false`). A single bare `dict` annotation anywhere in the tree
  causes Azure OpenAI to reject the whole request with a 400 before the model runs.

---

## 8. Known limitations

* `mcsb_service` is a stub — `data/mcsb/mcsb_v1_controls.json` does not exist, so MCSB
  control context is empty on every mapping and `mcsb_control_id` is weakly grounded.
* No OCR. A scanned regulation is **reported as unreadable** rather than silently
  returning zero controls, but it cannot be processed. One of the three Arabic reference
  documents is affected; the other two carry real text layers and process normally.
* ISO 27018, SOC 1 and SOC 3 have no Azure clause metadata, so citations against them
  can never reach `GROUNDED`.
* `comparison.py` `_run_build_job` has no cancellation check.
* `compliance-pipeline/` retains its own 64-identifier fork of the mapper. Out of scope,
  recorded as a decision rather than an oversight.
