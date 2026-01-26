"""
AI Mapping Service using Azure OpenAI with structured outputs.
Maps external framework controls to MCSB controls.
Enhanced with Microsoft Learn MCP server for Azure Policy discovery.
"""

import logging
import json
from typing import List, Optional
from pydantic import ValidationError

from app.models import ExternalControl, MCSBControl, ControlMapping, MappingBatch
from app.services.mcsb_service import get_mcsb_service
from app.services.microsoft_learn_client import get_microsoft_learn_client
from app.auth import get_azure_openai_client
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# System prompt for AI mapping
SYSTEM_PROMPT = """You are an expert cybersecurity compliance analyst specializing in mapping compliance framework controls to the Microsoft Cloud Security Benchmark (MCSB).

Your task is to analyze external compliance framework controls and map them to the most appropriate MCSB controls.

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

Always be conservative with confidence scores - it's better to flag uncertain mappings for human review."""


class AIMappingService:
    """Service for AI-powered control mapping using Azure OpenAI."""

    def __init__(self):
        """Initialize AI mapping service."""
        self.client = get_azure_openai_client()
        self.learn_client = get_microsoft_learn_client()
        self.mcsb_service = get_mcsb_service()
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

        # Create user prompt with policy context
        logger.debug(f"Creating AI mapping prompt with {len(mcsb_controls)} MCSB controls")
        user_prompt = self._create_mapping_prompt(external_control, mcsb_controls, policy_context)
        logger.info(f"Generated prompt for AI ({len(user_prompt)} chars) with {len(mcsb_controls)} MCSB controls and policy context")
        logger.debug(f"Prompt preview: {user_prompt[:300]}...")

        try:
            # Call Azure OpenAI with structured output
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=ControlMapping,
                temperature=settings.ai_temperature,
                max_tokens=settings.ai_max_tokens
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

    def map_controls_batch(
        self,
        external_controls: List[ExternalControl],
        progress_callback: Optional[callable] = None
    ) -> MappingBatch:
        """
        Map multiple controls in batch.

        Args:
            external_controls: List of external controls to map
            progress_callback: Optional callback(current, total) for progress updates

        Returns:
            MappingBatch with all mappings and summary

        Example:
            ```python
            service = AIMappingService()
            controls = [ExternalControl(...), ...]
            batch = service.map_controls_batch(controls)
            print(f"Mapped {batch.mapped_count}/{batch.total_controls}")
            ```
        """
        import asyncio
        logger.info(f"Starting batch mapping for {len(external_controls)} controls")

        mappings: List[ControlMapping] = []
        unmapped_controls: List[str] = []

        for idx, control in enumerate(external_controls):
            try:
                # Run async map_control in sync context
                mapping = asyncio.run(self.map_control(control))
                mappings.append(mapping)

                # Call progress callback
                if progress_callback:
                    progress_callback(idx + 1, len(external_controls))

            except Exception as e:
                logger.error(f"Failed to map {control.control_id}: {e}")
                unmapped_controls.append(control.control_id)

        # Calculate statistics
        total_controls = len(external_controls)
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
        policy_context: str = ""
    ) -> str:
        """
        Create prompt for AI mapping.

        Args:
            external_control: External control to map
            mcsb_controls: Available MCSB controls
            policy_context: Azure Policy search results from Microsoft Learn

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

Task:
-----
Analyze the external control and identify the best matching MCSB control.
Use the Azure Policy context to help identify relevant policy IDs that implement this control.
Provide a confidence score, mapping type, and detailed reasoning.
Include specific Azure Policy definition IDs (GUIDs or built-in policy names) that enforce this control.

Important: The azure_policy_ids field should contain actual Azure Policy definition IDs found in the Azure Policy Context above
Analyze the external control and identify the best matching MCSB control.
Provide a confidence score, mapping type, and detailed reasoning.
Include any relevant Azure Policy IDs from the matched MCSB control.
"""
        return prompt

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
