"""
AI Mapping Service using Azure OpenAI with structured outputs.
Maps external framework controls to MCSB controls.
Enhanced with Microsoft Learn MCP server for Azure Policy discovery.
"""

import logging
import json
import inspect
from typing import List, Optional
from pydantic import ValidationError

from app.models import ExternalControl, MCSBControl, ControlMapping, MappingBatch
from app.models.sovereignty import SovereigntyMapping
from app.services.mcsb_service import get_mcsb_service
from app.services.microsoft_learn_client import get_microsoft_learn_client
from app.services.sovereignty_service import get_sovereignty_service
from app.auth import get_azure_openai_client
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# System prompt for AI mapping
SYSTEM_PROMPT = """You are an expert cybersecurity compliance analyst specializing in mapping compliance framework controls to the Microsoft Cloud Security Benchmark (MCSB) and the Microsoft Sovereign Landing Zone (SLZ).

Your task is to analyze external compliance framework controls and:
1. Map them to the most appropriate MCSB controls
2. Recommend the appropriate Sovereign Landing Zone (SLZ) sovereignty level and policies

## MCSB Mapping Guidelines

For each external control, you should:
1. Understand the primary security objective and intent
2. Identify the security domain (Identity, Network, Data Protection, etc.)
3. Analyze technical requirements and implementation guidance
4. Match to the most appropriate MCSB control(s)
5. Provide a confidence score (0.0 to 1.0) based on alignment
6. Explain your reasoning clearly

Confidence Score Guidelines:
- 0.9-1.0: Exact match - controls have identical or nearly identical objectives
- 0.7-0.8: Strong match - controls address the same security goal with similar requirements
- 0.5-0.6: Partial match - controls share some common objectives but differ in scope
- 0.3-0.4: Conceptual match - controls are related but address different aspects
- 0.0-0.2: Weak or no match - controls are fundamentally different

Mapping Type Guidelines:
- "exact": Controls have identical security objectives and requirements
- "partial": Controls share primary objectives but differ in implementation details
- "conceptual": Controls are related conceptually but address different scopes
- "none": No appropriate MCSB control exists for this requirement

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

Always be conservative with confidence scores - it's better to flag uncertain mappings for human review."""


class AIMappingService:
    """Service for AI-powered control mapping using Azure OpenAI."""

    def __init__(self):
        """Initialize AI mapping service."""
        self.client = get_azure_openai_client()
        self.learn_client = get_microsoft_learn_client()
        self.mcsb_service = get_mcsb_service()
        self.sovereignty_service = get_sovereignty_service()
        self.model = settings.azure_openai_deployment_name

    async def map_control(
        self,
        external_control: ExternalControl,
        mcsb_controls: Optional[List[MCSBControl]] = None
    ) -> ControlMapping:
        """
        Map a single external control to MCSB using AI.

        Args:
            external_control: External framework control to map
            mcsb_controls: Optional list of MCSB controls to consider
                          (if None, uses all controls)

        Returns:
            ControlMapping with AI-generated mapping

        Raises:
            Exception: If AI mapping fails
        """
        logger.info(f"Mapping control: {external_control.control_id}")

        # Get relevant MCSB controls
        if mcsb_controls is None:
            mcsb_controls = self.mcsb_service.get_controls_for_external_control(
                external_control.description,
                external_control.domain
            )

        # Search for relevant Azure Policies using Microsoft Learn
        logger.debug(f"Starting Azure Policy search for {external_control.control_id}")
        policy_context = await self._search_azure_policies(external_control)
        logger.debug(f"Policy search complete, context length: {len(policy_context)} chars")

        # Get relevant SLZ sovereignty policies
        logger.debug(f"Searching SLZ policies for {external_control.control_id}")
        sovereignty_context = self._get_sovereignty_context(external_control)
        logger.debug(f"Sovereignty context ready, length: {len(sovereignty_context)} chars")

        # Create user prompt with policy context
        logger.debug(f"Creating AI mapping prompt with {len(mcsb_controls)} MCSB controls")
        user_prompt = self._create_mapping_prompt(external_control, mcsb_controls, policy_context, sovereignty_context)
        logger.info(f"Generated prompt for AI ({len(user_prompt)} chars) with {len(mcsb_controls)} MCSB controls and policy context")
        logger.debug(f"Prompt preview: {user_prompt[:300]}...")

        try:
            # Call Azure OpenAI with structured output
            # Note: GPT-5 doesn't support temperature parameter (always 1.0)
            # and uses max_completion_tokens instead of max_tokens
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=ControlMapping,
                max_completion_tokens=settings.ai_max_tokens
            )

            # Extract parsed response
            mapping = completion.choices[0].message.parsed
            
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

            logger.info(
                f"Mapped {external_control.control_id} -> {mapping.mcsb_control_id} "
                f"(confidence: {mapping.confidence_score:.2f})"
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

    async def map_controls_batch(
        self,
        external_controls: List[ExternalControl],
        progress_callback: Optional[callable] = None
    ) -> MappingBatch:
        """Map multiple controls in batch (async-safe).

        Runs map_control with awaits to avoid nesting asyncio.run inside a running
        loop (which was causing failures in background tasks).
        """
        logger.info(f"Starting batch mapping for {len(external_controls)} controls")

        mappings: List[ControlMapping] = []
        unmapped_controls: List[str] = []
        total_controls = len(external_controls)

        for idx, control in enumerate(external_controls):
            try:
                mapping = await self.map_control(control)
                mappings.append(mapping)
            except Exception as e:
                logger.error(f"Failed to map {control.control_id}: {e}")
                unmapped_controls.append(control.control_id)

            if progress_callback:
                if inspect.iscoroutinefunction(progress_callback):
                    await progress_callback(idx + 1, total_controls)
                else:
                    progress_callback(idx + 1, total_controls)

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

    async def _search_azure_policies(self, external_control: ExternalControl) -> str:
        """
        Search Microsoft Learn for relevant Azure Policies.

        Args:
            external_control: External control to find policies for

        Returns:
            Context string with relevant policy information
        """
        try:
            logger.info(f"Searching Azure policies for: {external_control.control_id}")
            
            # Search Microsoft Learn for relevant policies
            policies = await self.learn_client.search_azure_policies(
                control_name=external_control.control_name,
                description=external_control.description,
                domain=external_control.domain
            )
            
            if policies:
                # Format policy information for the prompt
                policy_list = []
                logger.info(f"Formatting {len(policies)} policies for AI prompt context")
                for i, policy in enumerate(policies, 1):
                    policy_info = f"""
  - Policy: {policy['policy_name']}
    ID: {policy['policy_id']}
    Description: {policy['description']}
    Learn More: {policy['learn_url']}
"""
                    policy_list.append(policy_info)
                    logger.debug(f"  Added policy {i}/{len(policies)}: {policy['policy_name'][:60]}")
                
                policy_context = f"""
Relevant Azure Policies from Microsoft Learn:
{len(policies)} policies found that may implement this control:
{''.join(policy_list)}

Use these policy IDs in the azure_policy_ids field if they match the control requirements.
"""
                logger.info(f"✓ Generated policy context ({len(policy_context)} chars) with {len(policies)} policies for {external_control.control_id}")
                logger.debug(f"Policy context preview: {policy_context[:200]}...")
                return policy_context
            else:
                return """
Azure Policy Context:
No specific policies found in Microsoft Learn for this control.
Consider general security policies or provide custom policy recommendations based on the control requirements.
"""
            
        except Exception as e:
            logger.warning(f"Failed to search Azure policies: {e}")
            return "Azure Policy search unavailable - provide policy recommendations based on best practices"

    def _create_mapping_prompt(
        self,
        external_control: ExternalControl,
        mcsb_controls: List[MCSBControl],
        policy_context: str = "",
        sovereignty_context: str = ""
    ) -> str:
        """
        Create prompt for AI mapping.

        Args:
            external_control: External control to map
            mcsb_controls: Available MCSB controls
            policy_context: Azure Policy search results from Microsoft Learn
            sovereignty_context: SLZ sovereignty policy context

        Returns:
            Formatted prompt string
        """
        # Prepare MCSB controls context
        mcsb_context = []
        for ctrl in mcsb_controls:
            mcsb_context.append({
                "control_id": ctrl.control_id,
                "domain": ctrl.domain,
                "control_name": ctrl.control_name,
                "description": ctrl.description[:200],  # Truncate for token efficiency
                "azure_policy_ids": ctrl.azure_policy_ids
            })

        prompt = f"""
External Control to Map:
-----------------------
Control ID: {external_control.control_id}
Control Name: {external_control.control_name}
Description: {external_control.description}
Domain: {external_control.domain or 'Not specified'}
Control Type: {external_control.control_type or 'Not specified'}

Available MCSB Controls:
-----------------------
{json.dumps(mcsb_context, indent=2)}

Azure Policy Context:
--------------------
{policy_context}

{sovereignty_context}

Task:
-----
1. MCSB Mapping: Analyze the external control and identify the best matching MCSB control.
   Use the Azure Policy context to help identify relevant policy IDs that implement this control.
   Provide a confidence score, mapping type, and detailed reasoning.
   Include specific Azure Policy definition IDs (GUIDs or built-in policy names) that enforce this control.

2. Sovereignty Mapping: Determine the appropriate SLZ sovereignty level (L1/L2/L3),
   relevant sovereignty control objectives (SO-1 through SO-5), and matching SLZ policies.
   Provide the sovereignty mapping in the 'sovereignty' field with:
   - sovereignty_level: "L1", "L2", or "L3"
   - sovereignty_objectives: list of applicable SO-* IDs
   - slz_policy_names: list of specific SLZ policy names from the context above
   - target_archetype: "sovereign_root", "confidential_corp", or "confidential_online"
   - reasoning: brief explanation of why this sovereignty level was chosen

Important: The azure_policy_ids field should contain actual Azure Policy definition IDs found in the Azure Policy Context above.
The sovereignty field should reference specific SLZ policies from the Sovereignty Context above.
"""
        return prompt

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
        """
        Create a fallback mapping when AI fails.
        
        Args:
            external_control: The control that failed to map
            error_msg: Error message from the failure
            
        Returns:
            A default ControlMapping with minimal information
        """
        logger.warning(f"Creating fallback mapping for {external_control.control_id}: {error_msg}")
        
        return ControlMapping(
            external_control_id=external_control.control_id,
            external_control_name=external_control.control_name,
            mcsb_control_id="N/A",
            mcsb_control_name="Mapping failed - manual review required",
            mcsb_domain="Unknown",
            confidence_score=0.0,
            reasoning=f"Automated mapping failed: {error_msg}. This control requires manual review and mapping.",
            azure_policy_ids=[],
            mapping_type="none",
            defender_recommendations=[]
        )


def get_ai_mapping_service() -> AIMappingService:
    """Get AI mapping service instance."""
    return AIMappingService()
