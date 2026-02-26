"""
LLM-based Control Extraction Engine.
Uses Azure OpenAI with structured outputs to extract compliance controls from raw PDF text.
"""

import logging
from typing import Optional

from .models import ControlExtractionResult, ExtractedControl
from .config import PipelineConfig
from .pdf_extractor import chunk_text

logger = logging.getLogger(__name__)

# ── System prompt for control extraction ──────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are an expert compliance analyst specializing in cybersecurity, data protection, and cloud governance frameworks from the Middle East, Africa, and global regulatory bodies.

Your task is to analyze the raw text extracted from a compliance control document (PDF) and produce a structured extraction of ALL controls found in the document.

## Extraction Rules

1. **Identify every control** in the document. Controls may be numbered (e.g., TR-01, POL-03, Section 4.1) or listed as requirements, objectives, or mandates.

2. **Assign a control ID** using the document's own numbering. If the document uses IDs like "TR-01", "POL-03", etc., preserve them exactly. If the document uses section numbers (e.g., 4.1, 4.2), use those. If no numbering exists, create sequential IDs like "CTRL-001", "CTRL-002", etc.

3. **Classify each control's domain** into one of these categories:
   - Network Security
   - Identity & Access Management
   - Data Protection & Encryption
   - Logging & Monitoring
   - Endpoint Security
   - Vulnerability Management
   - Backup & Recovery
   - Incident Response
   - Risk Management
   - Governance & Policy
   - Physical Security
   - Cloud Security
   - AI & Emerging Technology
   - Privacy & Data Sovereignty
   - Compliance & Audit
   - Supply Chain / Third Party
   - Business Continuity

4. **Classify each control's type** as one of:
   - Technical: Can be enforced or audited via technical means (Azure Policy, Defender)
   - Policy: Requires organizational policy or procedure
   - Contractual: Relates to contracts with cloud providers
   - Management: Management oversight and governance
   - Operational: Day-to-day operational procedures
   - Governance: Overarching governance and frameworks

5. **Capture the full description** of each control — not just the title but the complete requirement text.

6. **Identify sub-controls** if a control has multiple sub-requirements (e.g., a, b, c).

7. **Identify the framework metadata**: name, version, issuing authority, and country/region.

8. **Be thorough** — it is critical to extract ALL controls, not just the first few. Scan the entire document.

9. **Do NOT invent controls** that are not in the document. Only extract what is explicitly stated.

10. **Provide a summary** of the framework's purpose and scope."""


def get_openai_client(config: PipelineConfig):
    """Create Azure OpenAI client using either API key or DefaultAzureCredential."""
    from openai import AzureOpenAI

    if config.azure_openai_api_key:
        return AzureOpenAI(
            azure_endpoint=config.azure_openai_endpoint,
            api_key=config.azure_openai_api_key,
            api_version=config.azure_openai_api_version,
        )
    else:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        return AzureOpenAI(
            azure_endpoint=config.azure_openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version=config.azure_openai_api_version,
        )


def extract_controls_from_text(
    pdf_text: str,
    config: PipelineConfig,
    pdf_metadata: Optional[dict] = None,
) -> ControlExtractionResult:
    """
    Use Azure OpenAI to extract structured controls from raw PDF text.

    If the text is too large for a single call, it is chunked and results are merged.

    Args:
        pdf_text: Raw text extracted from PDF.
        config: Pipeline configuration.
        pdf_metadata: Optional PDF metadata (title, author, etc.).

    Returns:
        ControlExtractionResult with all extracted controls.
    """
    client = get_openai_client(config)

    # Build context from metadata
    metadata_context = ""
    if pdf_metadata:
        metadata_context = (
            f"\nPDF Metadata:\n"
            f"  Title: {pdf_metadata.get('title', 'Unknown')}\n"
            f"  Author: {pdf_metadata.get('author', 'Unknown')}\n"
            f"  Pages: {pdf_metadata.get('pages', 'Unknown')}\n"
        )

    # Chunk if necessary (gpt-4.1 has ~128k context but we stay conservative)
    chunks = chunk_text(pdf_text, max_chars=100000)

    if len(chunks) == 1:
        return _extract_single(client, config, chunks[0], metadata_context)
    else:
        logger.info(f"Document split into {len(chunks)} chunks for extraction")
        return _extract_multi_chunk(client, config, chunks, metadata_context)


def _extract_single(
    client,
    config: PipelineConfig,
    text: str,
    metadata_context: str,
) -> ControlExtractionResult:
    """Extract controls from a single text chunk."""

    user_prompt = f"""{metadata_context}

## Document Text

{text}

---

Extract ALL compliance controls from this document. Be thorough — capture every control, requirement, and sub-requirement.
Return the structured result with framework metadata and a complete list of controls."""

    logger.info(f"Sending {len(user_prompt):,} chars to Azure OpenAI for control extraction...")

    completion = client.beta.chat.completions.parse(
        model=config.azure_openai_deployment,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format=ControlExtractionResult,
        max_completion_tokens=config.max_tokens,
    )

    result = completion.choices[0].message.parsed

    if not result:
        raise ValueError("LLM returned empty extraction result")

    logger.info(
        f"Extracted {len(result.controls)} controls from '{result.framework_name}'"
    )
    return result


def _extract_multi_chunk(
    client,
    config: PipelineConfig,
    chunks: list[str],
    metadata_context: str,
) -> ControlExtractionResult:
    """Extract controls from multiple chunks and merge results."""

    all_controls: list[ExtractedControl] = []
    seen_ids: set[str] = set()
    framework_name = ""
    framework_version = None
    issuing_authority = None
    country_or_region = None
    summary = ""

    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i + 1}/{len(chunks)} ({len(chunk):,} chars)")

        user_prompt = f"""{metadata_context}

## Document Text (Part {i + 1} of {len(chunks)})

{chunk}

---

Extract ALL compliance controls found in this portion of the document.
This is part {i + 1} of {len(chunks)} parts of the same document.
Be thorough — capture every control, requirement, and sub-requirement found in this section."""

        completion = client.beta.chat.completions.parse(
            model=config.azure_openai_deployment,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ControlExtractionResult,
            max_completion_tokens=config.max_tokens,
        )

        result = completion.choices[0].message.parsed
        if not result:
            logger.warning(f"Chunk {i + 1} returned empty result")
            continue

        # Take metadata from first chunk
        if i == 0:
            framework_name = result.framework_name
            framework_version = result.framework_version
            issuing_authority = result.issuing_authority
            country_or_region = result.country_or_region
            summary = result.summary

        # Deduplicate controls by ID
        for ctrl in result.controls:
            if ctrl.control_id not in seen_ids:
                all_controls.append(ctrl)
                seen_ids.add(ctrl.control_id)
            else:
                logger.debug(f"Skipping duplicate control: {ctrl.control_id}")

        logger.info(f"Chunk {i + 1}: found {len(result.controls)} controls ({len(all_controls)} total unique)")

    return ControlExtractionResult(
        framework_name=framework_name,
        framework_version=framework_version,
        issuing_authority=issuing_authority,
        country_or_region=country_or_region,
        controls=all_controls,
        summary=summary,
    )
