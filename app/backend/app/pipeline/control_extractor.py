"""
LLM-based Control Extraction Engine.
Uses Azure OpenAI with structured outputs to extract compliance controls from raw PDF text.
"""

import logging
import time
from copy import deepcopy
from typing import Callable, Optional

import openai
from pydantic import BaseModel, ValidationError

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
    """Get the Azure OpenAI Responses API client used by GPT-5.6 deployments."""
    from app.auth.azure_auth import get_azure_openai_responses_client

    return get_azure_openai_responses_client()


def extract_controls_from_text(
    pdf_text: str,
    config: PipelineConfig,
    pdf_metadata: Optional[dict] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
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
        try:
            return _extract_single(client, config, chunks[0], metadata_context)
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
                client, config, retry_chunks, metadata_context, progress_callback
            )
    else:
        logger.info(f"Document split into {len(chunks)} chunks for extraction")
        return _extract_multi_chunk(
            client, config, chunks, metadata_context, progress_callback
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


def _strict_response_schema(response_format: type[BaseModel]) -> dict:
    """Adapt Pydantic JSON Schema to Azure OpenAI strict structured-output rules."""
    schema = deepcopy(response_format.model_json_schema())

    def make_objects_strict(value: object) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if isinstance(properties, dict):
                value["additionalProperties"] = False
                value["required"] = list(properties)
            for child in value.values():
                make_objects_strict(child)
        elif isinstance(value, list):
            for child in value:
                make_objects_strict(child)

    make_objects_strict(schema)

    # Strip server-only fields the model must never populate (honest accounting
    # values set by the pipeline itself, not by the LLM).
    server_only = {"failed_sections"}
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name in server_only:
            properties.pop(name, None)
    if isinstance(schema.get("required"), list):
        schema["required"] = [r for r in schema["required"] if r not in server_only]

    return schema


def _parse_with_retry(
    client,
    config: PipelineConfig,
    messages: list[dict],
    response_format: type[BaseModel],
    max_retries: int = 3,
) -> BaseModel:
    """Use Responses API JSON schema output with bounded retries and fallback."""
    models = [config.azure_openai_deployment]
    if config.azure_openai_fallback_model and config.azure_openai_fallback_model != config.azure_openai_deployment:
        models.append(config.azure_openai_fallback_model)

    for model in models:
        for attempt in range(1, max_retries + 1):
            try:
                response = client.responses.create(
                    model=model,
                    input=messages,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "control_extraction",
                            "schema": _strict_response_schema(response_format),
                            "strict": True,
                        }
                    },
                    max_output_tokens=config.max_tokens,
                )
                return response_format.model_validate_json(response.output_text)
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
            except (openai.APITimeoutError, openai.APIConnectionError) as exc:
                logger.warning(
                    "%s did not respond on attempt %s/%s: %s. "
                    "%s",
                    model,
                    attempt,
                    max_retries,
                    exc,
                    "Retrying..." if attempt < max_retries else "Falling back to next model...",
                )
            except (openai.AuthenticationError, openai.PermissionDeniedError):
                raise
            except openai.APIStatusError as exc:
                logger.warning(
                    "%s is unavailable for extraction: %s. Falling back to next model...",
                    model,
                    exc,
                )
                break
            except ValidationError as exc:
                logger.warning(
                    "%s returned an invalid extraction result on attempt %s/%s: %s. %s",
                    model,
                    attempt,
                    max_retries,
                    exc,
                    "Retrying..." if attempt < max_retries else "Falling back to next model...",
                )
    raise RuntimeError(
        "Azure OpenAI extraction failed after exhausting the configured primary and fallback models"
    )


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

    completion = _parse_with_retry(
        client,
        config,
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format=ControlExtractionResult,
    )

    logger.info(
        f"Extracted {len(completion.controls)} controls from '{completion.framework_name}'"
    )
    return completion


def _extract_multi_chunk(
    client,
    config: PipelineConfig,
    chunks: list[str],
    metadata_context: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> ControlExtractionResult:
    """Extract controls from multiple chunks and merge results."""

    all_controls: list[ExtractedControl] = []
    seen_ids: set[str] = set()
    framework_name = ""
    framework_version = None
    issuing_authority = None
    country_or_region = None
    summary = ""
    metadata_captured = False
    failed_sections = 0

    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i + 1}/{len(chunks)} ({len(chunk):,} chars)")

        user_prompt = f"""{metadata_context}

## Document Text (Part {i + 1} of {len(chunks)})

{chunk}

---

Extract ALL compliance controls found in this portion of the document.
This is part {i + 1} of {len(chunks)} parts of the same document.
Be thorough — capture every control, requirement, and sub-requirement found in this section."""

        try:
            completion = _parse_with_retry(
                client,
                config,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=ControlExtractionResult,
            )
        except RuntimeError as exc:
            # One section exhausting all models must not discard the sections that
            # did succeed. Record the failure honestly and keep going.
            failed_sections += 1
            logger.warning(
                "Chunk %s/%s failed extraction after all models were exhausted: %s. "
                "Continuing with the remaining sections.",
                i + 1,
                len(chunks),
                exc,
            )
            if progress_callback:
                progress_callback(i + 1, len(chunks))
            continue

        result = completion

        # Take metadata from the first section that extracts successfully.
        if not metadata_captured:
            framework_name = result.framework_name
            framework_version = result.framework_version
            issuing_authority = result.issuing_authority
            country_or_region = result.country_or_region
            summary = result.summary
            metadata_captured = True

        # Deduplicate controls by ID
        for ctrl in result.controls:
            if ctrl.control_id not in seen_ids:
                all_controls.append(ctrl)
                seen_ids.add(ctrl.control_id)
            else:
                logger.debug(f"Skipping duplicate control: {ctrl.control_id}")

        logger.info(f"Chunk {i + 1}: found {len(result.controls)} controls ({len(all_controls)} total unique)")
        if progress_callback:
            progress_callback(i + 1, len(chunks))

    if failed_sections == len(chunks):
        raise RuntimeError(
            "Azure OpenAI extraction failed for every document section after "
            "exhausting the configured primary and fallback models"
        )

    if failed_sections:
        logger.warning(
            "Extraction completed with partial coverage: %s of %s sections failed.",
            failed_sections,
            len(chunks),
        )

    return ControlExtractionResult(
        framework_name=framework_name,
        framework_version=framework_version,
        issuing_authority=issuing_authority,
        country_or_region=country_or_region,
        controls=all_controls,
        summary=summary,
        failed_sections=failed_sections,
    )
