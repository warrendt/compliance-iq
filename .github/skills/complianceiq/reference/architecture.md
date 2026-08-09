# ComplianceIQ architecture

ComplianceIQ turns a compliance regulation (a PDF of controls) into a deployable
**Azure Policy initiative** and onboards it to **Microsoft Defender for Cloud**.
It is a two-tier app on Azure Container Apps.

```mermaid
flowchart LR
    U[User + az login token] -->|HTTPS /api/v1/*| FE
    subgraph ACA[Azure Container Apps env]
      FE[ca-frontend  Streamlit + nginx  external ingress]
      BE[ca-backend  FastAPI  internal ingress only]
    end
    FE -->|nginx /api reverse proxy  internal FQDN :8000| BE
    BE --> COS[(Cosmos DB  jobs / profiles)]
    BE --> AOAI[Azure OpenAI  control intelligence + mapping]
    BE --> CAT[Azure Policy catalog snapshot  ~2465 defs]
    BE -->|ARM w/ user token| ARM[Azure Resource Manager]
    ARM --> DFC[Defender for Cloud  Regulatory compliance]
```

## Tiers
- **Frontend** `ca-frontend-*` — Streamlit UI behind **nginx**, the only public
  entry point (external ingress, port 8501). nginx also serves an **`/api`
  reverse proxy** to the backend so external callers (this skill) can reach the
  internal API. See `infra.md`.
- **Backend** `ca-backend-*` — FastAPI, **internal ingress only** (port 8000).
  Not reachable from outside the Container Apps environment except via the
  frontend proxy.

## Pipeline (what happens inside `POST /pipeline/run`)
1. **PDF extraction** — text/controls pulled from the uploaded PDF. A scanned
   PDF with no text layer is **reported as unreadable**; there is no OCR.
2. **Control intelligence** — controls normalised/enriched (Azure OpenAI).
3. **Azure Policy mapping** — the pipeline path and the services path now run
   the **same engine** (`AIMappingService`) against the **whole catalog**
   snapshot (`app/backend/app/data/policy_catalog/azure_policy_catalog.json`,
   ~2465 defs), **not** MCSB. Retrieval is query expansion → wide sweep →
   LLM rerank → per-control selection. The pipeline previously carried its own
   hardcoded menu of 34 identifiers (~1.4% of the catalog, six of them not real).
4. **Coverage taxonomy** — each control is answered on two independent axes:
   how it is met (`A_AzurePolicy` / `B_AzureConfig` / `C_Process` /
   `D_MicrosoftAttestation`) and who owns it (`Customer` / `Microsoft` /
   `Shared`). A and B emit policy IDs; C and D never do and go to the manual
   register instead. Effects and enforcement plane are resolved from the
   catalog, positionally aligned with the policy IDs on the row.
5. **Initiative build** — mapped policies assembled into an Azure Policy
   Set (initiative) JSON, stamped with `ASC` metadata so it surfaces under
   Defender for Cloud → Regulatory compliance. Scoping keys off **effect**, not
   category, so an audit policy is never presented as a hard guardrail.

Measured 2026-08-09: ~325s for a 57-control framework at concurrency 4.

## Failure behaviour
When the engine fails on a control it emits a mapping that **says so** —
`coverage_gap=True`, a reason naming the engine failure, and no responsibility
it never determined — and the control still reaches the manual register. It is
never reported as "a process control Azure cannot enforce", because that reads
as a considered judgement and is indistinguishable from a real finding.

## Deploy
`POST /deploy/initiative` uses the **caller's ARM token** to create the policy
set definition (and optionally an assignment) at a subscription or management
group scope. `enforce_mode=false` (DoNotEnforce / audit-only) is the default.

## Data
- **Cosmos DB** — pipeline job status (fallback beyond the in-memory store) and
  user workspace data (uploads, mappings, exports, activity).
- Generated artifacts (`*_Initiative.json`, etc.) are written to the job's local
  `output_dir` on the backend replica that ran the job — see the replica caveat
  in `troubleshooting.md`.
