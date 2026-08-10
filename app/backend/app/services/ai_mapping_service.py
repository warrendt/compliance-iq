"""
AI Mapping Service using Azure OpenAI with structured outputs.
Maps external framework controls directly to Azure Policy definitions.
Enhanced with Microsoft Learn MCP server for Azure Policy discovery.
"""

import asyncio
import logging
import json
import inspect
from typing import List, Optional
import openai
from pydantic import ValidationError

from app.models import ExternalControl, ControlMapping, MappingBatch
from app.models.sovereignty import SovereigntyMapping
from app.services.microsoft_learn_client import get_microsoft_learn_client
from app.services.policy_catalog_service import get_policy_catalog_service
from app.services.control_intent_service import get_control_intent_service
from app.services.control_classification_service import (
    get_control_classification_service,
    unknown_classification,
)
from app.services.policy_rerank_service import get_policy_rerank_service
from app.services.sovereignty_service import get_sovereignty_service
from app.services import coverage
from app.auth import get_azure_openai_client
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# System prompt for AI mapping
SYSTEM_PROMPT = """You are an expert cybersecurity compliance analyst specializing in mapping compliance framework controls directly to Azure Policy (built-in policy definitions and the initiatives that bundle them, including Microsoft Defender for Cloud's own initiatives) and to the Microsoft Sovereign Landing Zone (SLZ).

Your task is to analyze external compliance framework controls and:
1. Map them to the Azure Policy definition(s) that genuinely enforce or evidence them
2. Recommend the appropriate Sovereign Landing Zone (SLZ) sovereignty level and policies

## Azure Policy Mapping Guidelines

There is no intermediate control taxonomy standing between the external control and
Azure Policy. Map directly against the real candidates:

1. Understand the primary security objective, intent, and literal wording of the
   external control - what it actually requires, not a paraphrase of it.
2. Review the "Azure Policy Context" section below: real built-in Azure Policy
   definitions retrieved for THIS control from the full built-in catalog (~2,467
   definitions), which also names the built-in initiatives that already bundle a
   candidate (e.g. "Microsoft cloud security benchmark", "ASC Default", or another
   Microsoft Defender for Cloud initiative) when one exists. There is no smaller
   pre-filtered subset behind these candidates - if a real Azure Policy or Defender
   for Cloud initiative enforces this control, it is reachable here.
3. Select every azure_policy_ids GUID whose own display name, description, and
   effect genuinely enforce or evidence the control's literal requirement. Azure
   Policy definitions that back Microsoft Defender for Cloud recommendations,
   configurations, and initiatives are valid, in-scope candidates like any other
   built-in. A candidate initiative name shown for context is not itself a
   selectable ID - only its GUIDs go in azure_policy_ids.
4. Provide a confidence score and mapping type based on how closely the TEXT of
   the control matches the TEXT of the Azure Policy definition(s) you selected -
   never on fit to any external taxonomy. If nothing in the candidate list truly
   enforces the control, say so honestly (empty azure_policy_ids, mapping_type
   "none") instead of forcing a weak match to look like a successful one.
5. Explain your reasoning clearly, citing what in the control's own wording the
   selected policy addresses.

Confidence Score Guidelines — grounded in real expert-verified mappings, not the
abstract categories they name:

- 0.9-1.0 ("exact"): the selected policy/policies enforce the control's literal
  subject and mechanism directly.
  Worked example: control text "...consumers shall implement it [HYOK] to retain
  exclusive control over encryption keys and mitigate the risk of unauthorized
  access to data" maps at ~0.95 to the built-in policies "OS and data disks should
  be encrypted with a customer-managed key", "Storage accounts should use
  customer-managed key for encryption", and "SQL servers should use
  customer-managed keys to encrypt data at rest" - the control's subject
  (customer-held encryption keys) and the policies' mechanism (CMK enforcement)
  are the same requirement, just phrased in regulatory vs. Azure vocabulary.

- 0.7-0.8 ("exact"/"partial"): the policy addresses the same security goal, but
  only part of the control's scope, or several policies must combine to
  approximate full coverage.
  Worked example: a control requiring encryption "at rest ... in use ... and in
  transmission" across "file servers, databases, and end-user devices" maps at
  ~0.75 to a list of resource-specific CMK policies (SQL, storage, managed disks,
  PostgreSQL, etc.) plus a transit-specific policy such as "Secure transfer to
  storage accounts should be enabled" - each candidate covers one resource type or
  one leg of the requirement, not the whole sentence, so no single policy is an
  exact match even though the combination is a strong one.

- 0.5-0.6 ("partial"/"conceptual"): the control's intent is achievable in Azure,
  but primarily through configuration Azure Policy itself cannot enforce or audit
  (Entra Conditional Access, Purview labelling, key management outside ARM).
  Score in this band, set coverage_category to "B_AzureConfig", describe the
  configuration step in outside_step, and only include azure_policy_ids for a
  definition that genuinely audits some part of it.
  Worked example: "Multi-factor authentication shall be implemented for accounts
  with elevated privileges" is delivered through an Entra Conditional Access
  policy, which Azure Policy (ARM) cannot itself configure or audit - score
  around 0.5-0.6 and classify "B_AzureConfig", not "A_AzurePolicy".

- 0.0-0.3 ("conceptual"/"none"): no candidate policy or initiative addresses the
  control, or the control is process/organisational and Azure has no technical
  means to enforce it at all.
  Worked example: "senior leadership shall mandate the establishment of a cloud
  security program with apparent oversight" is pure governance - score 0.0,
  coverage_category "C_Process", empty azure_policy_ids. Do NOT reach for a
  governance catch-all policy just to attach something.

Mapping Type Guidelines:
- "exact": the selected policy/policies enforce the control's literal subject and
  mechanism directly (confidence typically 0.8-1.0)
- "partial": the selected policy/policies address the same goal but cover only
  part of the control's scope, or require several policies combined
- "conceptual": related in intent but achieved mainly through configuration Azure
  Policy cannot itself enforce, or only loosely related
- "none": no Azure Policy definition or initiative can address this requirement

## Sovereign Landing Zone (SLZ) Mapping Guidelines

For EACH control, also determine the appropriate sovereignty dimensions:

### Sovereignty Level (REQUIRED):
- "L1" (Global): Data residency and in-transit encryption. For controls about data location, geographic restrictions, trusted launch, or basic sovereignty.
- "L2" (CMK): Customer-managed keys for encryption at rest. For controls requiring encryption with customer-controlled keys, BYOK, or key management.
- "L3" (Confidential): Confidential computing with encryption in-use. For controls requiring hardware-level isolation, TEEs, or strongest data protection.

### Sovereignty Control Objectives (select all that apply):
- SO-1: Data Residency — controls about data location, geographic restrictions, allowed regions
- SO-2: Customer Lockbox — controls about customer approval for Microsoft support access (procedural, no Azure Policy)
- SO-3: Customer-Managed Keys — controls about CMK, BYOK, encryption at rest with customer keys
- SO-4: Confidential Computing — controls about hardware-level isolation, TEEs, VM SKU restrictions
- SO-5: Trusted Launch — controls about secure boot, vTPM, boot integrity

### Target Archetype:
- "sovereign_root": Default for L1/L2 controls
- "confidential_corp": For L3 controls on connected (internal) workloads
- "confidential_online": For L3 controls on internet-facing workloads

If a control has NO sovereignty relevance (e.g., purely governance/procedural), set sovereignty_level to "L1" with an empty objectives list.

Always provide sovereignty reasoning explaining why you chose that level.

## Coverage Classification (REQUIRED)

Not every control can be enforced by Azure Policy. Many compliance frameworks
contain process, legal, HR, contractual, and organisational-governance controls
that Azure has no technical means to enforce. Attaching an Azure Policy to these
just to appear complete is a FALSE POSITIVE.

Classify every control into exactly one coverage_category:
- "A_AzurePolicy": technically enforceable or auditable by an Azure Policy
  definition (e.g. encryption, MFA, network rules, logging, backup). ONLY this
  category may carry azure_policy_ids.
- "B_AzureConfig": achieved through Azure configuration but NOT via an Azure
  Policy definition. Return an EMPTY azure_policy_ids list.
- "C_Process": process, legal, HR, contractual, jurisdiction, incident-contact,
  training, or organisational-governance controls Azure cannot enforce. Return an
  EMPTY azure_policy_ids list.
- "D_MicrosoftAttestation": satisfied by Microsoft-operated infrastructure the
  customer attests to (datacentre/physical security, hypervisor, ISO/SOC
  certifications). Return an EMPTY azure_policy_ids list.

Manual opt-out: if the control's nature (see "Control Type") is Policy,
Contractual, Management, Operational, or Governance, and it is not clearly a
technical safeguard, set coverage_category to "C_Process" (or "D_MicrosoftAttestation"
for Microsoft-operated items) and return an EMPTY azure_policy_ids list. Do NOT
reach for a governance catch-all policy just to attach something.

## Defender for Cloud

Microsoft Defender for Cloud's underlying built-in policies, configurations, and
initiatives (e.g. "Microsoft cloud security benchmark", "ASC Default") are
legitimate Azure Policy candidates and should be mapped and considered like any
other built-in when the "Azure Policy Context" shows one enforces the control.

This is distinct from Defender for Cloud RECOMMENDATIONS (free-text names such as
"Enable MFA for all users"): you have no access to a live Defender for Cloud
subscription and no data about actual recommendation state, so ALWAYS return an
EMPTY defender_recommendations list. Never invent or guess a recommendation name
- an invented one is indistinguishable from a real one to the reader and is worse
than reporting nothing.

Always be conservative with confidence scores - it's better to flag uncertain mappings for human review."""


class AIMappingService:
    """Service for AI-powered control mapping using Azure OpenAI."""

    def __init__(self):
        """Initialize AI mapping service."""
        self.client = get_azure_openai_client()
        self.learn_client = get_microsoft_learn_client()
        self.catalog = get_policy_catalog_service()
        self.control_intent = get_control_intent_service()
        self.control_classification = get_control_classification_service()
        self.policy_rerank = get_policy_rerank_service()
        self.sovereignty_service = get_sovereignty_service()
        self.model = settings.azure_openai_deployment_name

    async def map_control(
        self,
        external_control: ExternalControl,
    ) -> ControlMapping:
        """
        Map a single external control directly to Azure Policy using AI.

        Args:
            external_control: External framework control to map

        Returns:
            ControlMapping with AI-generated mapping

        Raises:
            Exception: If AI mapping fails
        """
        logger.info(f"Mapping control: {external_control.control_id}")

        # Stage 1 — classify BLIND, before any policy candidates exist. Showing a
        # ranked candidate list first anchors the model into attaching a policy to
        # a control Azure cannot enforce; on the NCSP gold mapping 113 of 137
        # controls are not policy-enforceable, so getting this wrong is the
        # default failure, not an edge case.
        classification = await self.control_classification.classify(
            external_control.control_name,
            external_control.description,
            external_control.domain or "",
            external_control.control_type,
        )
        if classification.is_valid:
            logger.info(
                "Classified %s as %s (%s)",
                external_control.control_id,
                classification.coverage_category,
                classification.responsibility,
            )

        # Search for relevant Azure Policies using Microsoft Learn
        logger.debug(f"Starting Azure Policy search for {external_control.control_id}")
        policy_context = await self._search_azure_policies(
            external_control, classification
        )
        logger.debug(f"Policy search complete, context length: {len(policy_context)} chars")

        # Get relevant SLZ sovereignty policies
        logger.debug(f"Searching SLZ policies for {external_control.control_id}")
        sovereignty_context = self._get_sovereignty_context(external_control)
        logger.debug(f"Sovereignty context ready, length: {len(sovereignty_context)} chars")

        # Create user prompt with policy context
        user_prompt = self._create_mapping_prompt(external_control, policy_context, sovereignty_context)
        logger.info(f"Generated prompt for AI ({len(user_prompt)} chars) with policy context")
        logger.debug(f"Prompt preview: {user_prompt[:300]}...")

        try:
            mapping = await asyncio.to_thread(
                self._request_mapping,
                external_control,
                user_prompt,
            )
            
            # Validate that mapping has required fields
            if not mapping:
                raise ValueError("AI returned empty mapping")
            
            # Ensure all required fields are present with defaults if needed
            if not hasattr(mapping, 'confidence_score') or mapping.confidence_score is None:
                logger.warning(f"Missing confidence_score for {external_control.control_id}, defaulting to 0.5")
                mapping.confidence_score = 0.5
            
            if not hasattr(mapping, 'external_control_id'):
                mapping.external_control_id = external_control.control_id
            
            if not hasattr(mapping, 'external_control_name'):
                mapping.external_control_name = external_control.control_name

            # Defender for Cloud recommendations are never grounded in
            # anything: there is no live subscription context at mapping
            # time to check against, the prompt never asks for this field,
            # and the model still fills it because it is present in the
            # ControlMapping schema (see B4). Whatever comes back here is
            # invented, so clear it rather than ship a plausible-looking
            # recommendation nobody verified.
            self._strip_ungrounded_defender_recommendations(mapping)

            # Deterministic coverage guarantee: the blind classification is the
            # primary signal, the extractor's control_type a fallback. Controls
            # that are not Azure-Policy enforceable have their azure_policy_ids
            # cleared here so they never reach the initiative, and carry the
            # classification's reason, responsibility and evidence pointer.
            coverage.apply_coverage(
                mapping,
                external_control.control_type,
                self.catalog,
                classification,
            )

            self._apply_procedural_sovereignty(mapping, external_control)

            # policy_category is a resolvable fact about the real catalog
            # entries selected, not a judgement call, so it is always computed
            # here rather than asked of the model - same rationale as
            # _strip_ungrounded_defender_recommendations above. This replaces
            # the old mcsb_domain fallback, which came from a 10-control demo
            # taxonomy rather than the actual policies chosen.
            self._set_policy_category(mapping, external_control)

            logger.info(
                f"Mapped {external_control.control_id} -> {len(mapping.azure_policy_ids or [])} "
                f"Azure Policy definition(s) "
                f"(confidence: {mapping.confidence_score:.2f}, "
                f"coverage: {mapping.coverage_category})"
            )

            return mapping

        except ValidationError as e:
            logger.error(f"Validation error in AI response: {e}")
            # Return a default mapping instead of failing
            return self._create_fallback_mapping(external_control, str(e))

        except Exception as e:
            logger.error(f"AI mapping failed for {external_control.control_id}: {e}")
            # Return a default mapping instead of failing
            return self._create_fallback_mapping(external_control, str(e))

    def _request_mapping(
        self,
        external_control: ExternalControl,
        user_prompt: str,
    ) -> ControlMapping:
        """Run the blocking model request without blocking other mapping workers."""
        models = [self.model]
        if (
            settings.azure_openai_fallback_model
            and settings.azure_openai_fallback_model != self.model
        ):
            models.append(settings.azure_openai_fallback_model)

        for model in models:
            try:
                completion = self.client.beta.chat.completions.parse(
                    model=model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format=ControlMapping,
                    max_completion_tokens=settings.ai_max_tokens,
                )
                mapping = completion.choices[0].message.parsed
                if not mapping:
                    raise ValueError("AI returned empty mapping")
                if model != self.model:
                    logger.warning(
                        "Mapped %s with fallback model %s after primary model failure",
                        external_control.control_id,
                        model,
                    )
                return mapping
            except (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError) as exc:
                logger.warning(
                    "Azure OpenAI %s failed for %s: %s. %s",
                    model,
                    external_control.control_id,
                    exc,
                    "Trying fallback model." if model != models[-1] else "No fallback remains.",
                )

        raise RuntimeError("Azure OpenAI did not return a mapping from any configured model")

    async def map_controls_batch(
        self,
        external_controls: List[ExternalControl],
        progress_callback: Optional[callable] = None,
        concurrency: int = 1,
    ) -> MappingBatch:
        """Map multiple controls in batch (async-safe).

        Runs map_control with awaits to avoid nesting asyncio.run inside a running
        loop (which was causing failures in background tasks).
        """
        logger.info(f"Starting batch mapping for {len(external_controls)} controls")

        total_controls = len(external_controls)
        semaphore = asyncio.Semaphore(max(1, concurrency))
        completed = 0

        async def map_one(control: ExternalControl) -> tuple[str, Optional[ControlMapping]]:
            nonlocal completed
            async with semaphore:
                try:
                    mapping = await self.map_control(control)
                except Exception as exc:
                    logger.error(f"Failed to map {control.control_id}: {exc}")
                    mapping = None
                completed += 1
                if progress_callback:
                    if inspect.iscoroutinefunction(progress_callback):
                        await progress_callback(completed, total_controls)
                    else:
                        progress_callback(completed, total_controls)
                return control.control_id, mapping

        results = await asyncio.gather(*(map_one(control) for control in external_controls))
        mappings = []
        unmapped_controls = []
        for control_id, mapping in results:
            if mapping is None:
                unmapped_controls.append(control_id)
            else:
                mappings.append(mapping)

        mapped_count = len(mappings)
        avg_confidence = (
            sum(m.confidence_score for m in mappings) / mapped_count
            if mapped_count > 0 else 0.0
        )

        summary = self._generate_summary(total_controls, mapped_count, avg_confidence)

        batch = MappingBatch(
            mappings=mappings,
            unmapped_controls=unmapped_controls,
            summary=summary,
            total_controls=total_controls,
            mapped_count=mapped_count,
            avg_confidence=avg_confidence
        )

        logger.info(f"Batch mapping complete: {summary}")
        return batch

    async def _search_azure_policies(
        self,
        external_control: ExternalControl,
        classification=None,
    ) -> str:
        """
        Retrieve candidate Azure built-in policy definitions for a control.

        Runs the three-stage retrieval pipeline over the *whole* shipped catalog
        (~2.5k built-in definitions) so the model chooses ``azure_policy_ids``
        from real Azure Policy GUIDs:

        1. **Expand** — restate the control in Azure vocabulary. Regulatory prose
           and Azure Policy display names barely share vocabulary, so this is the
           single largest recall lever (measured 15.6% -> 32.2% micro-recall@15
           on the NCSP gold mapping, lexical-only).
        2. **Retrieve wide** — hybrid lexical + semantic sweep to
           ``policy_catalog_retrieval_depth`` (84.4% recall@200 with expansion).
        3. **Rerank** — narrow that sweep to ``policy_catalog_candidate_count``
           so the selection prompt stays short without sacrificing the sweep.

        Every stage degrades independently: a failed expansion falls back to the
        raw control text, an absent embedding artifact falls back to lexical
        retrieval, and a failed rerank falls back to retrieval order.

        Args:
            external_control: External control to find policies for
            classification: The blind classification stage's verdict. When it says
                the control is process/organisational or Microsoft-attested,
                retrieval is skipped entirely.

        Returns:
            Context string with candidate policy definitions (name + GUID)
        """
        try:
            # Anchoring guard: for controls no Azure Policy can assert, do NOT
            # show the model a ranked candidate list — that biases it into picking
            # a policy anyway. The blind classification decides this, because it
            # judged the control on its own terms; the extractor's control_type
            # keyword test is the fallback for when classification is unavailable.
            # The deterministic coverage layer enforces the outcome regardless,
            # but suppressing candidates also improves the model's rationale.
            control_text = " ".join(
                p for p in (
                    external_control.control_name,
                    external_control.description,
                ) if p
            )
            if classification is not None and classification.is_valid:
                skip_retrieval = not classification.may_have_policies
                skip_because = f"classified {classification.coverage_category}"
            else:
                skip_retrieval = coverage.is_process_control(
                    external_control.control_type
                ) and not any(
                    kw in control_text.casefold()
                    for kw in coverage.TECHNICAL_KEYWORDS
                )
                skip_because = f"process control_type={external_control.control_type}"

            if skip_retrieval:
                logger.info(
                    "Skipping Azure Policy candidate retrieval for %s (%s) "
                    "to avoid anchoring",
                    external_control.control_id, skip_because,
                )
                return (
                    "Azure Policy Context:\n"
                    "This control's nature is process/organisational, not a "
                    "technical safeguard Azure Policy can enforce. Return an EMPTY "
                    "azure_policy_ids list and set coverage_category to 'C_Process' "
                    "(or 'D_MicrosoftAttestation' if it concerns Microsoft-operated "
                    "infrastructure)."
                )

            query = " ".join(
                p for p in (
                    external_control.control_name,
                    external_control.description,
                    external_control.domain or "",
                ) if p
            )

            intent = await self.control_intent.expand(
                external_control.control_name,
                external_control.description,
                external_control.domain or "",
            )
            if not intent.is_empty:
                logger.info(
                    "Expanded %s for retrieval: %s",
                    external_control.control_id, intent.azure_restatement,
                )

            retrieved = await asyncio.to_thread(
                self.catalog.search,
                intent.build_query(query),
                settings.policy_catalog_retrieval_depth,
                intent.policy_categories,
            )
            candidates = await self.policy_rerank.rerank(
                query, retrieved, settings.policy_catalog_candidate_count
            )

            if candidates:
                logger.info(
                    "Retrieved %d candidate Azure policies for %s from catalog (%s), "
                    "reranked from a depth-%d sweep",
                    len(candidates), external_control.control_id, self.catalog.source,
                    len(retrieved),
                )
                lines = []
                for c in candidates:
                    desc = (c.description or "").strip().replace("\n", " ")
                    if len(desc) > 220:
                        desc = desc[:217] + "..."
                    # Surface built-in initiatives (e.g. "Microsoft cloud security
                    # benchmark", "ASC Default", other Defender for Cloud
                    # initiatives) that already bundle this candidate, as context
                    # only - initiatives are not directly selectable, only the
                    # definition GUIDs inside azure_policy_ids are.
                    initiative_note = ""
                    try:
                        initiatives = self.catalog.initiatives_containing(c.name)
                    except Exception:
                        initiatives = []
                    if initiatives:
                        names = ", ".join(
                            i.get("display_name") or i.get("name", "")
                            for i in initiatives[:3]
                        )
                        initiative_note = f"\n    Bundled in built-in initiative(s): {names}"
                    lines.append(
                        f"  - {c.display_name} [{c.category}]\n"
                        f"    ID: {c.name}\n"
                        f"    {desc}"
                        f"{initiative_note}"
                    )
                return (
                    "Candidate Azure Policy definitions (retrieved from the Azure "
                    "built-in policy catalog, including Microsoft Defender for "
                    "Cloud's own policies where relevant):\n"
                    f"{len(candidates)} candidates ranked by relevance.\n"
                    + "\n".join(lines)
                    + "\n\nSelect azure_policy_ids ONLY from the ID (GUID) values "
                    "listed above that genuinely enforce this control. You may "
                    "select several. Do NOT invent GUIDs or use policy names or "
                    "initiative names as IDs - only a definition GUID belongs in "
                    "azure_policy_ids, never an initiative. "
                    "Prefer enforceable policies (Audit/Deny/DeployIfNotExists) over "
                    "'Regulatory Compliance' entries, which are manual-attestation "
                    "controls with no enforcement logic - only pick those if no "
                    "enforceable policy fits. If none are relevant, return an empty list."
                )

            logger.info(
                "No catalog candidates for %s (catalog source=%s)",
                external_control.control_id, self.catalog.source,
            )
            return (
                "Azure Policy Context:\n"
                "No candidate policy definitions were retrieved for this control. "
                "Return an empty azure_policy_ids list rather than inventing GUIDs."
            )

        except Exception as e:
            logger.warning(f"Failed to retrieve candidate Azure policies: {e}")
            return (
                "Azure Policy search unavailable - return an empty azure_policy_ids "
                "list rather than inventing GUIDs."
            )

    def _create_mapping_prompt(
        self,
        external_control: ExternalControl,
        policy_context: str = "",
        sovereignty_context: str = ""
    ) -> str:
        """
        Create prompt for AI mapping.

        Args:
            external_control: External control to map
            policy_context: Azure Policy search results from Microsoft Learn
            sovereignty_context: SLZ sovereignty policy context

        Returns:
            Formatted prompt string
        """
        prompt = f"""
External Control to Map:
-----------------------
Control ID: {external_control.control_id}
Control Name: {external_control.control_name}
Description: {external_control.description}
Domain: {external_control.domain or 'Not specified'}
Control Type: {external_control.control_type or 'Not specified'}

Azure Policy Context:
--------------------
{policy_context}

{sovereignty_context}

Task:
-----
1. Azure Policy selection: From the "Azure Policy Context" section above, select the
   Azure Policy definition GUIDs that genuinely enforce this control's literal
   requirement and put them in azure_policy_ids. Use ONLY the ID (GUID) values listed
   there. Select as many as truly apply (there may be several, and a genuine match
   may span several resource-specific definitions). Never invent GUIDs, and never put
   a policy name or initiative name in azure_policy_ids. If none of the candidates
   fit, return an empty list. Score confidence_score and mapping_type against how
   closely the selected definition(s) match the control's own wording (see the
   worked calibration examples above), and explain that match in reasoning.

2. Sovereignty Mapping: Determine the appropriate SLZ sovereignty level (L1/L2/L3),
   relevant sovereignty control objectives (SO-1 through SO-5), and matching SLZ policies.
   Provide the sovereignty mapping in the 'sovereignty' field with:
   - sovereignty_level: "L1", "L2", or "L3"
   - sovereignty_objectives: list of applicable SO-* IDs
   - slz_policy_names: list of specific SLZ policy names from the context above
   - target_archetype: "sovereign_root", "confidential_corp", or "confidential_online"
   - reasoning: brief explanation of why this sovereignty level was chosen

Important: azure_policy_ids MUST contain only GUIDs copied verbatim from the Azure Policy
Context above. The sovereignty field should reference specific SLZ policies from the
Sovereignty Context above.
"""
        return prompt

    @staticmethod
    def _strip_ungrounded_defender_recommendations(mapping) -> None:
        """Clear the model's ``defender_recommendations`` guess.

        Nothing in this engine queries Microsoft Defender for Cloud: mapping
        happens per-control, at framework-analysis time, before any Azure
        subscription is chosen, so there is no live tenant to check
        recommendations against. The mapping prompt never asks the model for
        this field either - it fills it only because ``ControlMapping``
        declares it. Whatever text comes back is invented, so it is cleared
        here rather than shipped as if it were a verified Defender for Cloud
        recommendation. See docs/BACKLOG.md B4.
        """
        if getattr(mapping, "defender_recommendations", None):
            mapping.defender_recommendations = []

    def _set_policy_category(self, mapping, external_control: ExternalControl) -> None:
        """Derive ``policy_category`` from the catalog, not from the model.

        Replaces the old ``mcsb_domain`` fallback. The category of a resolved
        Azure Policy definition is a fact recorded in the catalog snapshot -
        looking it up is strictly more accurate than asking the model to
        restate a taxonomy label, and it stays truthful even when the model's
        own domain guess would have been stale or invented. Falls back to the
        external control's own extracted domain when no policy was selected
        (process/organisational controls, or a coverage gap).
        """
        categories: list[str] = []
        for policy_id in (mapping.azure_policy_ids or []):
            entry = self.catalog.get(policy_id) if self.catalog else None
            category = (entry or {}).get("category")
            if category:
                categories.append(category)

        if categories:
            # Most common category among the selected definitions; ties break
            # on first-seen order, which is retrieval-rank order.
            mapping.policy_category = max(set(categories), key=categories.count)
        else:
            mapping.policy_category = external_control.domain or None

    def _apply_procedural_sovereignty(self, mapping, external_control) -> None:
        """Name the Azure feature that meets a sovereignty objective with no policy.

        SO-2 Operator Access is the case: no Azure Policy can assert it, and it
        is met by enabling Customer Lockbox. Because the policy search skips
        procedural objectives - correctly, they have no policies - such a
        control previously came back with no sovereignty linkage at all, which
        for a sovereign customer is close to the whole question.

        Reporting "no policy" is honest but incomplete; naming the feature is
        the difference between an apparent gap and a solved requirement. This is
        deterministic keyword matching against the objective definitions, never
        model output, for the same reason effects are read from the catalog.
        """
        try:
            objectives = self.sovereignty_service.procedural_objectives_for_control(
                control_description=external_control.description,
                control_domain=external_control.domain,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Procedural sovereignty lookup failed: %s", exc)
            return

        if not objectives:
            return

        features = [o.named_feature for o in objectives if o.named_feature]
        ids = [o.id for o in objectives]

        sovereignty = getattr(mapping, "sovereignty", None)
        if sovereignty is not None:
            existing = list(getattr(sovereignty, "sovereignty_objectives", None) or [])
            for obj_id in ids:
                if obj_id not in existing:
                    existing.append(obj_id)
            sovereignty.sovereignty_objectives = existing

        # Only fill outside_step when the classification did not already name a
        # step. The model saw the control text; this saw only keywords, so it
        # supplements rather than overrides.
        if features and not (getattr(mapping, "outside_step", None) or "").strip():
            mapping.outside_step = "; ".join(features)

    def _get_sovereignty_context(self, external_control: ExternalControl) -> str:
        """
        Build sovereignty context string for the AI prompt.

        Args:
            external_control: External control to find sovereignty policies for

        Returns:
            Formatted sovereignty context string
        """
        try:
            relevant_policies = self.sovereignty_service.get_relevant_policies_for_control(
                control_description=external_control.description,
                control_domain=external_control.domain,
            )

            if not relevant_policies:
                # Return all policies as general context (limited)
                relevant_policies = self.sovereignty_service.get_all_policies()[:15]

            if not relevant_policies:
                return ""

            # Format the policies for the prompt
            policy_lines = []
            for p in relevant_policies:
                policy_lines.append(
                    f"  - Name: {p.name}\n"
                    f"    Display Name: {p.display_name}\n"
                    f"    Level: {p.sovereignty_level} | Objectives: {', '.join(p.sovereignty_objectives)} | Service: {p.service_category}\n"
                    f"    Effect: {p.effect}"
                )

            # Include objectives reference
            objectives = self.sovereignty_service.get_all_objectives()
            obj_lines = []
            for obj_id, obj in objectives.items():
                if not obj.procedural_only:
                    obj_lines.append(f"  - {obj_id}: {obj.name} — {obj.description}")
                else:
                    obj_lines.append(f"  - {obj_id}: {obj.name} — {obj.description} [PROCEDURAL ONLY - no Azure Policy]")

            context = f"""Sovereign Landing Zone (SLZ) Context:
-------------------------------------
Sovereignty Control Objectives:
{chr(10).join(obj_lines)}

Available SLZ Policies (relevant to this control):
{chr(10).join(policy_lines)}

Use these SLZ policy names in the sovereignty.slz_policy_names field if they match the control requirements.
"""
            return context

        except Exception as e:
            logger.warning(f"Failed to build sovereignty context: {e}")
            return ""

    def _generate_summary(
        self,
        total: int,
        mapped: int,
        avg_confidence: float
    ) -> str:
        """Generate human-readable summary of mapping results."""
        unmapped = total - mapped

        summary = f"Successfully mapped {mapped} out of {total} controls"

        if avg_confidence > 0:
            summary += f" with average confidence {avg_confidence:.2f}"

        if unmapped > 0:
            summary += f". {unmapped} controls could not be mapped."

        return summary
    
    def _create_fallback_mapping(
        self,
        external_control: ExternalControl,
        error_msg: str
    ) -> ControlMapping:
        """Create a fallback mapping when AI fails.

        This must *say* it failed. It previously returned ``COVERAGE_C`` with
        ``coverage_gap`` left False, which reads downstream as a considered
        judgement - "this is a process control, Azure cannot enforce it" -
        when in fact no mapping was attempted successfully. A whole framework
        of engine failures was therefore indistinguishable from a whole
        framework of genuine process controls. That is the failure mode this
        product exists to avoid: a confident wrong answer instead of an
        admitted gap.

        The category stays ``COVERAGE_C`` only so the control still reaches the
        manual register - a control that silently disappears from the
        deliverable is worse than one flagged for review - but the gap flag and
        reason now make the failure explicit.
        """
        logger.warning(f"Creating fallback mapping for {external_control.control_id}: {error_msg}")

        return ControlMapping(
            external_control_id=external_control.control_id,
            external_control_name=external_control.control_name,
            confidence_score=0.0,
            reasoning=f"Automated mapping failed: {error_msg}. This control requires manual review and mapping.",
            azure_policy_ids=[],
            mapping_type="none",
            policy_category=external_control.domain or None,
            defender_recommendations=[],
            control_type=external_control.control_type,
            coverage_category=coverage.COVERAGE_C,
            azure_enforceable=False,
            coverage_gap=True,
            coverage_reason=(
                "The automated mapping engine failed for this control, so no "
                "Azure coverage judgement was reached. This is an engine "
                f"failure, not a finding that Azure cannot help: {error_msg}"
            ),
            responsibility=None,
        )


def get_ai_mapping_service() -> AIMappingService:
    """Get AI mapping service instance."""
    return AIMappingService()
