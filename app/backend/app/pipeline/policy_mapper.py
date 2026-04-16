"""
Azure Policy Mapping Engine.
Uses Azure OpenAI to map extracted controls to Azure Policy definitions,
MCSB controls, and Defender for Cloud recommendations.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .models import (
    ExtractedControl,
    ControlExtractionResult,
    ControlPolicyMapping,
    AzurePolicyMapping,
    BatchPolicyMappingResult,
)
from .config import PipelineConfig
from .control_extractor import get_openai_client

logger = logging.getLogger(__name__)

# ── System prompt for Azure Policy mapping ────────────────────────────────────

MAPPING_SYSTEM_PROMPT = """You are an expert Azure cloud security architect specializing in Azure Policy, Microsoft Cloud Security Benchmark (MCSB), and Microsoft Defender for Cloud.

Your task is to map compliance framework controls to:
1. **Azure Policy definitions** — specific built-in policy GUIDs that enforce or audit the control
2. **MCSB controls** — the closest matching Microsoft Cloud Security Benchmark control
3. **Defender for Cloud recommendations** — relevant recommendations

## Azure Policy Mapping Guidelines

For EACH control, identify Azure Policy definitions that enforce or audit the control requirement.

### Policy ID Format
Use the actual Azure Policy definition GUID. Examples of well-known built-in policies:

**Identity & Access:**
- `4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b` — MFA should be enabled on accounts with owner permissions
- `34c877ad-507e-4c82-993e-3452a6e0ad3c` — Accounts with owner permissions should be MFA enabled
- `1f314764-cb73-4fc9-b863-8eca98ac36e9` — RBAC should be used on Kubernetes Services
- `0b15565f-aa9e-48ba-8619-45960f2c314d` — RBAC should be used for Azure subscriptions

**Network Security:**
- `e71308d3-144b-4262-b144-efdc3cc90517` — Subnets should be associated with a Network Security Group
- `fc5e4038-4584-4632-8c85-c0448d374b2c` — All network ports should be restricted on NSGs
- `055f3b15-58a8-4d91-a4f6-8437a6c8f7e8` — Azure DDoS Protection should be enabled
- `1e66c121-a66a-4b1f-9b83-0fd99bf0fc2d` — Azure Firewall should be deployed

**Encryption & Data Protection:**
- `7595c971-233d-4bcf-bd18-596129188c49` — TDE on SQL databases should be enabled
- `404c3081-a854-4457-ae30-26a93ef643f9` — Secure transfer to storage accounts should be enabled
- `4733ea7b-a883-42fe-8cac-97454c2a9e4a` — Storage accounts should use HTTPS
- `a4af4a39-4135-47fb-b175-47fbdf85311d` — Azure Cosmos DB accounts should use CMK
- `702dd420-7fcc-42c5-afe8-4026edd20fe0` — OS and data disks should be encrypted with CMK
- `18adea5e-f416-4d0f-8aa8-d24321e3e274` — PostgreSQL should use CMK
- `0a370ff3-6cab-4e85-8995-295fd854c5b8` — SQL managed instances should use CMK

**Logging & Monitoring:**
- `818719e5-1338-4776-9a9d-3c31e4df5986` — Log Analytics agent should be installed
- `428256e6-1fac-4f48-a757-df34c2b3336d` — Diagnostic logs should be enabled
- `b79fa14e-238a-4c2d-b376-442ce508fc84` — Activity log should be retained for at least 365 days

**Endpoint & Vulnerability:**
- `e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f` — Vulnerability assessment should be enabled on VMs
- `013e242c-8828-4970-87b3-ab247555486d` — Endpoint protection should be installed
- `ac076320-ddcf-4066-b451-6154267e8ad2` — Anti-malware extension should be deployed on VMs
- `e1145ab1-eb4f-43d8-911b-36ddf771d13f` — System updates should be installed

**Backup & Recovery:**
- `09024ccc-0c5f-475e-9457-b7c0d9ed487b` — Azure Backup should be enabled for VMs
- `22bee202-a82f-4305-9a2a-6d7f44d4dedb` — Geo-redundant backup should be enabled

**Privacy & Data Loss:**
- `ca610c1d-041c-4332-9d88-7ed3094967c7` — Private endpoints should be used
- `0b60c0b2-2dc2-4e1c-b5c9-abbed971de53` — Azure Purview / data classification

**Location/Data Residency:**
- `e56962a6-4747-49cd-b67b-bf8b01975c4c` — Allowed locations
- `37bc2e11-1d3c-4e6e-a9fc-62ca7b58b6c2` — Allowed locations for resource groups

**Key Management:**
- `0725b4dd-7e76-479c-a735-68e7ee23d5ca` — Key Vault should use RBAC
- `8e826246-c976-48f6-b03e-619bb92b3d82` — Key Vault keys should have expiration date
- `5f0bc445-3935-4915-9981-011aa2b46147` — Secrets should have expiration date
- `f4b53539-8df9-40e4-86c6-6b607703bd4e` — Keys should be backed by HSM

**Incident Response:**
- `2c89a2e5-7285-40fe-afe0-ae8654b92fb2` — Email notification for high-severity alerts

**AI governance:**
- `55d1f543-d1b0-4811-9663-d6d0dbc6326d` — Cognitive Services should restrict network access

### MCSB Control IDs
Map to the closest MCSB control using these domain prefixes:
- **NS** (Network Security): NS-1 through NS-10
- **IM** (Identity Management): IM-1 through IM-9
- **PA** (Privileged Access): PA-1 through PA-8
- **DP** (Data Protection): DP-1 through DP-8
- **AM** (Asset Management): AM-1 through AM-5
- **LT** (Logging and Threat Detection): LT-1 through LT-7
- **IR** (Incident Response): IR-1 through IR-6
- **PV** (Posture and Vulnerability Management): PV-1 through PV-6
- **ES** (Endpoint Security): ES-1 through ES-3
- **BR** (Backup and Recovery): BR-1 through BR-4
- **DS** (DevOps Security): DS-1 through DS-7
- **GS** (Governance and Strategy): GS-1 through GS-10

### Automatable vs Manual
- If a control can be enforced or audited via Azure Policy: `is_automatable: true`
- If a control requires human processes, contracts, or governance: `is_automatable: false`
  - Add a `manual_attestation_note` explaining what manual steps are needed

### Confidence Score
- 0.9-1.0: Exact match — Azure Policy directly enforces this control
- 0.7-0.8: Strong — Policy covers the core requirement with minor gaps
- 0.5-0.6: Partial — Policy partially addresses the control
- 0.3-0.4: Weak — Only tangentially related
- 0.0-0.2: No direct Azure Policy available

### Important
- Use REAL Azure Policy definition GUIDs, not made-up ones
- A single control can map to MULTIPLE Azure Policies
- A single Azure Policy can appear in MULTIPLE control groups
- If no Azure Policy exists for a control, set `is_automatable: false` and explain
- Be precise with confidence scores"""


def map_controls_to_azure_policies(
    extraction: ControlExtractionResult,
    config: PipelineConfig,
    progress_callback=None,
) -> list[ControlPolicyMapping]:
    """
    Map all extracted controls to Azure Policy definitions using Azure OpenAI.

    Controls are processed in batches to stay within token limits.

    Args:
        extraction: The extracted controls from the PDF.
        config: Pipeline configuration.
        progress_callback: Optional callable(current, total) for progress updates.

    Returns:
        List of ControlPolicyMapping objects.
    """
    client = get_openai_client(config)
    controls = extraction.controls
    batch_size = config.batch_size

    all_mappings: list[ControlPolicyMapping] = []

    # Process in batches
    total_batches = (len(controls) + batch_size - 1) // batch_size

    batch_specs: list[tuple[int, int, int, list[ExtractedControl]]] = []
    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(controls))
        batch_specs.append((batch_idx, start, end, controls[start:end]))

    batch_results: dict[int, list[ControlPolicyMapping]] = {}
    mapped_count = 0
    max_workers = min(max(1, config.mapping_parallelism), total_batches)

    def _map_batch_with_index(
        batch_idx: int,
        start: int,
        end: int,
        batch: list[ExtractedControl],
    ) -> tuple[int, int, list[ControlPolicyMapping]]:
        logger.info(
            f"Mapping batch {batch_idx + 1}/{total_batches} "
            f"(controls {start + 1}-{end} of {len(controls)})"
        )
        # Use a per-worker client to avoid any potential shared-client thread-safety issues.
        worker_client = get_openai_client(config)
        return (
            batch_idx,
            len(batch),
            _map_batch(
                client=worker_client,
                config=config,
                controls=batch,
                framework_name=extraction.framework_name,
            ),
        )

    if max_workers == 1:
        for batch_idx, start, end, batch in batch_specs:
            result_idx, batch_size_done, mappings = _map_batch_with_index(batch_idx, start, end, batch)
            batch_results[result_idx] = mappings
            mapped_count += batch_size_done
            if progress_callback:
                progress_callback(mapped_count, len(controls))
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_map_batch_with_index, batch_idx, start, end, batch): batch_idx
                for batch_idx, start, end, batch in batch_specs
            }
            for future in as_completed(futures):
                try:
                    result_idx, batch_size_done, mappings = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"Batch mapping failed: {exc}")
                    continue
                batch_results[result_idx] = mappings
                mapped_count += batch_size_done
                if progress_callback:
                    progress_callback(mapped_count, len(controls))

    if not batch_results and controls:
        raise ValueError("All mapping batches failed")

    for batch_idx in range(total_batches):
        all_mappings.extend(batch_results.get(batch_idx, []))

    logger.info(f"Completed mapping {len(all_mappings)} controls to Azure Policies")
    return all_mappings


def _map_batch(
    client,
    config: PipelineConfig,
    controls: list[ExtractedControl],
    framework_name: str,
) -> list[ControlPolicyMapping]:
    """Map a batch of controls via a single LLM call."""

    # Build the control descriptions for the prompt
    controls_text = ""
    for ctrl in controls:
        sub_text = ""
        if ctrl.sub_controls:
            sub_text = "\n    Sub-controls: " + "; ".join(ctrl.sub_controls)
        controls_text += f"""
  - ID: {ctrl.control_id}
    Title: {ctrl.control_title}
    Domain: {ctrl.domain}
    Type: {ctrl.control_type}
    Description: {ctrl.control_description}{sub_text}
"""

    user_prompt = f"""## Framework: {framework_name}

## Controls to Map ({len(controls)} controls)
{controls_text}

---

For EACH control above, provide:
1. The best-matching MCSB control ID and name
2. All relevant Azure Policy definition GUIDs that enforce or audit this control
3. Relevant Defender for Cloud recommendations
4. Whether the control is automatable via Azure Policy
5. A confidence score and rationale

Map ALL {len(controls)} controls. Do not skip any."""

    logger.info(f"Sending {len(user_prompt):,} chars for policy mapping...")

    completion = client.beta.chat.completions.parse(
        model=config.azure_openai_deployment,
        messages=[
            {"role": "system", "content": MAPPING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format=BatchPolicyMappingResult,
        max_completion_tokens=config.max_tokens,
    )

    result = completion.choices[0].message.parsed
    if not result:
        raise ValueError("LLM returned empty mapping result")

    logger.info(f"Mapped {len(result.mappings)} controls in this batch")
    return result.mappings
