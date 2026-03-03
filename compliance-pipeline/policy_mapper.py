"""
Azure Policy Mapping Engine.
Uses Azure OpenAI to map extracted controls to Azure Policy definitions,
MCSB controls, and Defender for Cloud recommendations.
"""

import json
import logging
from typing import Optional

from models import (
    ExtractedControl,
    ControlExtractionResult,
    ControlPolicyMapping,
    AzurePolicyMapping,
    BatchPolicyMappingResult,
)
from config import PipelineConfig
from control_extractor import get_openai_client

logger = logging.getLogger(__name__)

# ── System prompt for Azure Policy mapping ────────────────────────────────────

MAPPING_SYSTEM_PROMPT = """You are an expert Azure cloud security architect specializing in Azure Policy, Microsoft Cloud Security Benchmark (MCSB), and Microsoft Defender for Cloud.

Your task is to map compliance framework controls to:
1. **Azure Policy definitions** — specific built-in policy GUIDs that enforce or audit the control
2. **MCSB controls** — the closest matching Microsoft Cloud Security Benchmark control
3. **Defender for Cloud recommendations** — relevant recommendations

## Azure Policy Mapping Guidelines

For EACH control, identify **3 to 8** Azure Policy definitions that enforce or audit the control requirement.
Do NOT map only 1 policy per control — always identify multiple policies that together provide broad coverage.
Cover different resource types: VMs, storage, databases, networking, identity, and container services where relevant.

### Policy ID Format
Use ONLY the GUIDs listed below. Do NOT invent or guess GUIDs.

**Identity & Access Management:**
- `4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b` — MFA should be enabled on accounts with owner permissions
- `9297c21d-2ed6-4474-b48f-163f75654ce3` — MFA should be enabled on accounts with write permissions
- `e3576e28-8b17-4677-84c3-db2990658d64` — MFA should be enabled on accounts with read permissions
- `a451c1ef-c6ca-483d-87ed-f49761e3ffb5` — Role-Based Access Control (RBAC) should be used on Kubernetes Services
- `34c877ad-507e-4c82-993e-3452a6e0ad3c` — Kubernetes Services should have Role-Based Access Control enabled
- `0b15565f-aa9e-48ba-8619-45960f2c314d` — There should be more than one owner assigned to your subscription
- `a8eff44e-8db1-4c48-82a2-64d4e30b56bc` — Deprecated accounts with owner permissions should be removed
- `94e1c2ac-cbbe-4cac-a2b5-2cb8b36ce676` — Deprecated accounts should be removed from your subscription
- `9bc48460-f641-4a27-9f38-efe33a4a3e9e` — An Azure Active Directory administrator should be provisioned for SQL servers
- `abfb7388-5bf4-4ad7-ba99-2cd2f41cebb9` — An Azure Active Directory administrator should be provisioned for SQL Managed Instance
- `0015ea4d-51ff-4ce3-8d8c-f3f8f0be26b8` — Audit usage of custom RBAC roles
- `1f314764-cb73-4fc9-b863-8eca98ac36e9` — RBAC should be used on Kubernetes Services
- `b0f33259-77d7-4c9e-aac6-3aabcfae693c` — Management ports of virtual machines should be protected with just-in-time network access control

**Network Security:**
- `e71308d3-144b-4262-b144-efdc3cc90517` — Subnets should be associated with a Network Security Group
- `2c89a2e5-7285-40fe-afe0-ae8654b92fb2` — All network ports should be restricted on network security groups associated to your VM
- `fc5e4038-4584-4632-8c85-c0448d374b2c` — All network ports should be restricted on NSGs associated to virtual machines
- `bb91dfba-c30d-4263-9add-9c2384e659a6` — Remote debugging should be turned off for Web Applications
- `cb510bfd-1cba-4d9f-a1ea-bed557ae0564` — Remote debugging should be turned off for Function Apps
- `f9d614c5-c173-4d56-95a7-b4437057d193` — Remote debugging should be turned off for API Apps
- `1e66c121-a66d-4b99-b523-e2cf4bf16934` — Azure Firewall should be enabled to protect your virtual network
- `83e0d761-c550-47de-b1b6-359f2a30b354` — Adaptive network hardening recommendations should be applied on internet facing virtual machines
- `9dfea752-cf9d-4745-b47b-81b8330bbb9f` — SQL Managed Instance should have public endpoint access disabled
- `ae89ebf1-3572-4ab1-b1bd-ec5f00bab3a6` — Private endpoint connections on Azure SQL Database should be enabled
- `1c06e275-d63d-4540-b761-71f364c2111d` — Private endpoint should be enabled for Key Vault

**Encryption & Data Protection:**
- `7595c971-233d-4bcf-bd18-596129188c49` — Transparent data encryption on SQL databases should be enabled
- `404c3081-a854-4457-ae30-26a93ef643f9` — Secure transfer to storage accounts should be enabled
- `4733ea7b-a883-42fe-8cac-97454c2a9e4a` — Storage accounts should restrict network access
- `a4af4a39-4135-4a60-8bf6-d34b2a1d4f2c` — Storage accounts should use customer-managed key for encryption
- `1f905d99-2622-4c13-100b-f7c8e2078bc5` — Azure Cosmos DB accounts should use customer-managed keys to encrypt data at rest
- `702dd420-7fcc-42c5-afe8-4026edd20fe0` — OS and data disks should be encrypted with a customer-managed key
- `18adea5e-f416-4d0f-8aa8-d24321e3e274` — PostgreSQL servers should use customer-managed keys to encrypt data at rest
- `0a370ff3-6cab-4e85-8995-295fd854c5b8` — SQL managed instances should use customer-managed keys to encrypt data at rest
- `0961003e-5a0a-4549-abde-af6a37f2724d` — Virtual machines should encrypt temp disks, caches, and data flows between Compute and Storage resources
- `67121cc7-ff16-4bfd-986d-b15f4c767a1b` — Cognitive Services accounts should enable data encryption with a customer-managed key
- `0725b4dd-7e76-479c-a735-68e7ee23d5ca` — Cognitive Services accounts should restrict network access

**Logging & Monitoring:**
- `818719e5-1338-4776-9a9d-3c31e4df5986` — Log Analytics agent should be installed on your virtual machine for Azure Security Center monitoring
- `428256e6-1fac-4f48-a757-df34c2b3336d` — Audit diagnostic setting for listed resource types
- `89099bee-89e0-4b26-a5f4-165451757743` — SQL servers should be configured with 90 days auditing retention or higher
- `b954148f-4c11-4c38-8221-be76711e194e` — Advanced data security should be enabled on SQL Managed Instance
- `b0d14bf4-f90c-4e66-9457-1346f80b5a44` — Email notification to subscription owner for high severity alerts should be enabled
- `6e2593d9-add6-4083-9c9b-4b7d2188c899` — Email notifications to admins should be enabled in Microsoft Defender for SQL

**Key Management:**
- `8e826246-c976-48f6-b03e-619bb92b3d82` — Key Vault keys should have an expiration date
- `5f0bc445-3935-4915-9981-011aa2b46147` — Key Vault secrets should have an expiration date
- `f4b53539-8df9-40e4-86c6-6b607703bd4e` — Keys should be backed by a hardware security module (HSM)
- `6a523b34-47f5-4a80-a97e-d3e2d8bca2d6` — Azure Key Vault Managed HSM should have purge protection enabled
- `c39ba22d-4428-4149-b981-98acef4f7277` — Azure Key Vault should have firewall enabled

**Endpoint Security & Vulnerability Management:**
- `e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f` — Vulnerability assessment should be enabled on your virtual machines
- `44e1ad92-5f90-4a45-83bb-81cd4695e9f4` — Machines should have vulnerability findings resolved
- `1b7aa243-0538-4a73-b824-0b3fc489d80c` — Vulnerability assessment should be enabled on SQL Managed Instance
- `013e242c-8828-4970-87b3-ab247555486d` — Endpoint protection should be installed on your machines
- `ac076320-ddcf-4066-b451-6154267e8ad2` — Monitor missing Endpoint Protection in Azure Security Center
- `86b3d65f-7626-441e-b690-81a8b71cff60` — System updates should be installed on your machines
- `bd876905-5b84-4f73-ab2d-2e7a7c4568d9` — A vulnerability assessment solution should be enabled on your virtual machines
- `9c276cf7-d6e0-4a09-a4b4-be5f06902a79` — VMSS system updates should be installed

**Backup & Recovery:**
- `09024ccc-0c5f-475e-9457-b7c0d9ed487b` — Azure Backup should be enabled for Virtual Machines
- `013e242c-8828-4970-87b3-ab247555486d` — Endpoint protection health issues should be resolved on your machines
- `22bee202-a82f-4305-9a2a-6d7f44d4dedb` — Geo-redundant backup should be enabled for Azure Database for MySQL
- `e96a9a5f-07ca-471b-9bc5-6a0f33cbd68f` — Vulnerability assessment should be enabled on your virtual machines

**Data Classification & Privacy:**
- `ca610c1d-041c-4332-9d88-7ed3094967c7` — Private endpoint connections on Azure SQL Database should be enabled
- `0b60c0b2-2dc2-4e1c-b5c9-abbed971de53` — Sensitive data in your SQL databases should be classified

**Location / Data Residency:**
- `e56962a6-4747-49cd-b67b-bf8b01975c4c` — Allowed locations
- `37bc2e11-1d3c-4e6e-a9fc-62ca7b58b6c2` — Allowed locations for resource groups

**Incident Response:**
- `2c89a2e5-7285-40fe-afe0-ae8654b92fb2` — Subscriptions should have a contact email address for security issues

### ⛔ NEVER USE THESE GUIDs (deployment failures / not available):
- `e1145ab1-eb4f-43d8-911b-36ddf771d13f` — DO NOT USE (Azure Update Manager — not available)
- `055f3b15-58a8-4d91-a4f6-8437a6c8f7e8` — DO NOT USE (DDoS Standard — not available)
- `b79fa14e-238a-4c2d-b376-442ce508fc84` — DO NOT USE (DINE activity log — causes parameter conflict)
- `55d1f543-d1b0-4811-9663-d6d0dbc6326d` — DO NOT USE (DINE Cognitive Services — causes parameter conflict)

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

### Critical Rules
- ONLY use GUIDs from the list above. Do NOT invent or guess GUIDs.
- Map **3 to 8 policies per control** for automatable controls — never just 1 or 2.
- A single control can map to MULTIPLE Azure Policies.
- A single Azure Policy can appear in MULTIPLE control groups.
- If no Azure Policy exists for a control, set `is_automatable: false` and explain.
- Be precise with confidence scores."""


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

    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = min(start + batch_size, len(controls))
        batch = controls[start:end]

        logger.info(
            f"Mapping batch {batch_idx + 1}/{total_batches} "
            f"(controls {start + 1}-{end} of {len(controls)})"
        )

        batch_mappings = _map_batch(
            client=client,
            config=config,
            controls=batch,
            framework_name=extraction.framework_name,
        )

        all_mappings.extend(batch_mappings)

        if progress_callback:
            progress_callback(end, len(controls))

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
