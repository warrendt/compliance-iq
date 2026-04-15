"""
LLM-based Control Extraction Engine.
Uses Azure OpenAI with structured outputs to extract compliance controls from raw PDF text.
"""

import logging
import time
from typing import Callable, Optional

import openai

from .models import ControlExtractionResult, ExtractedControl
from .config import PipelineConfig
from .pdf_extractor import chunk_text

logger = logging.getLogger(__name__)

# ── System prompt for control extraction ──────────────────────────────────────

EXTRACTION_SYSTEM_PROMPT = """You are an expert compliance analyst specializing in multi-domain regulatory and control frameworks, including cybersecurity, privacy, financial services, legal/statutory obligations, operational risk, and industry-specific governance.

Your task is to analyze the raw text extracted from a compliance control document (PDF) and produce a structured extraction of ALL controls found in the document.

## Extraction Rules

1. **Identify every control** in the document. Controls may be numbered (e.g., TR-01, POL-03, Section 4.1) or listed as requirements, objectives, or mandates.

2. **Assign a control ID** using the document's own numbering. If the document uses IDs like "TR-01", "POL-03", etc., preserve them exactly. If the document uses section numbers (e.g., 4.1, 4.2), use those. If no numbering exists, create sequential IDs like "CTRL-001", "CTRL-002", etc.

3. **Classify each control's domain** using the best-fit domain label.
    Prefer one of these standard domains when applicable:
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
    - Financial Controls & Reporting
    - AML / KYC & Financial Crime
    - Legal & Statutory Obligations
    - Records Management & Retention
    - Consumer Protection & Conduct
    - Operational Resilience

    If none of the above fits well, use a concise domain name taken from the document's own terminology.

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

10. **Provide a summary** of the framework's purpose and scope.

11. **Do not rely on external databases** for control discovery. Extract controls from the uploaded document text only. If the document cites external laws/standards, include those citations in descriptions or sub-controls when present in the text."""


def get_openai_client(config: PipelineConfig):
    """Get Azure OpenAI client — delegates to the central auth module."""
    from app.auth.azure_auth import get_azure_openai_client
    return get_azure_openai_client()


def extract_controls_from_text(
    pdf_text: str,
    config: PipelineConfig,
    pdf_metadata: Optional[dict] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    legal_enrichment: bool = False,
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

    # Chunk conservatively to reduce structured-output truncation on long documents.
    chunks = chunk_text(pdf_text, max_chars=max(8000, config.extract_chunk_chars))

    if len(chunks) == 1:
        if progress_callback:
            progress_callback(1, 1)
        try:
            return _extract_single(
                client,
                config,
                chunks[0],
                metadata_context,
                legal_enrichment=legal_enrichment,
            )
        except openai.LengthFinishReasonError:
            # If a single-call extraction is truncated by output length, retry in multi-chunk mode.
            fallback_chunk_chars = max(8000, config.extract_chunk_chars // 2)
            retry_chunks = chunk_text(pdf_text, max_chars=fallback_chunk_chars)
            if len(retry_chunks) <= 1:
                raise
            logger.warning(
                "Single-chunk extraction hit output length limit. "
                f"Retrying with {len(retry_chunks)} chunks (max_chars={fallback_chunk_chars})."
            )
            return _extract_multi_chunk(
                client,
                config,
                retry_chunks,
                metadata_context,
                progress_callback=progress_callback,
                legal_enrichment=legal_enrichment,
            )
    else:
        logger.info(f"Document split into {len(chunks)} chunks for extraction")
        return _extract_multi_chunk(
            client,
            config,
            chunks,
            metadata_context,
            progress_callback=progress_callback,
            legal_enrichment=legal_enrichment,
        )


def _get_retry_after(exc: openai.RateLimitError, default: float) -> float:
    """Extract retry-after seconds from a 429 response, with a floor of default."""
    # Try the response header first
    try:
        if exc.response and exc.response.headers:
            val = exc.response.headers.get("retry-after")
            if val:
                return max(float(val), default)
    except Exception:
        pass
    return default


def _parse_with_retry(
    client,
    config: PipelineConfig,
    messages: list[dict],
    response_format,
    max_retries: int = 3,
):
    """Call client.beta.chat.completions.parse with retry + model fallback on 429."""
    models = [config.azure_openai_deployment]
    if config.azure_openai_fallback_model and config.azure_openai_fallback_model != config.azure_openai_deployment:
        models.append(config.azure_openai_fallback_model)

    for model in models:
        for attempt in range(1, max_retries + 1):
            try:
                return client.beta.chat.completions.parse(
                    model=model,
                    messages=messages,
                    response_format=response_format,
                    max_completion_tokens=config.max_tokens,
                )
            except openai.RateLimitError as e:
                retry_after = _get_retry_after(e, default=30.0 * attempt)
                if attempt < max_retries:
                    logger.warning(
                        f"Rate limited on {model} (attempt {attempt}/{max_retries}). "
                        f"Retrying in {retry_after}s..."
                    )
                    time.sleep(retry_after)
                else:
                    logger.warning(
                        f"Rate limited on {model} after {max_retries} attempts. "
                        f"{'Falling back to next model...' if model != models[-1] else 'No more models to try.'}"
                    )
    raise openai.RateLimitError(
        message="All models exhausted after retries",
        response=None,
        body=None,
    )


def _extract_single(
    client,
    config: PipelineConfig,
    text: str,
    metadata_context: str,
    legal_enrichment: bool = False,
) -> ControlExtractionResult:
    """Extract controls from a single text chunk."""

    enrichment_block = """
## Additional Legal/Statutory Focus

When extracting controls, prioritize explicit legal/statutory obligations and citations in the text, including:
- Acts, laws, decrees, directives, circulars, and regulations
- Clauses, articles, sections, schedules, and appendices
- Mandatory retention, reporting, disclosure, and record-keeping obligations

Capture cited references exactly as written when they appear in the document.
""" if legal_enrichment else ""

    user_prompt = f"""{metadata_context}

## Document Text

{text}

---

{enrichment_block}

Extract ALL compliance controls from this document. Be thorough — capture every control, requirement, and sub-requirement.
Return the structured result with framework metadata and a complete list of controls."""

    logger.info(f"Sending {len(user_prompt):,} chars to Azure OpenAI for control extraction...")

    completion = _parse_with_retry(
        client,
        config,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format=ControlExtractionResult,
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
    progress_callback: Optional[Callable[[int, int], None]] = None,
    legal_enrichment: bool = False,
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
        if progress_callback:
            progress_callback(i + 1, len(chunks))
        logger.info(f"Processing chunk {i + 1}/{len(chunks)} ({len(chunk):,} chars)")

        enrichment_block = """
    ## Additional Legal/Statutory Focus

    Within this chunk, prioritize extraction of legal/statutory obligations and cited references exactly as written.
    """ if legal_enrichment else ""

        user_prompt = f"""{metadata_context}

## Document Text (Part {i + 1} of {len(chunks)})

{chunk}

---

    {enrichment_block}

Extract ALL compliance controls found in this portion of the document.
This is part {i + 1} of {len(chunks)} parts of the same document.
Be thorough — capture every control, requirement, and sub-requirement found in this section."""

        completion = _parse_with_retry(
            client,
            config,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ControlExtractionResult,
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
