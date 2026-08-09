"""An empty extraction must not be reported as a finished analysis.

Found live, not by reading code. A commencement proclamation that had twice
yielded 2 controls returned 0 controls in 6.6 seconds on a later run. Every
check downstream passed — the sweep harness reported ``0 controls, 0
violations``, and the pipeline would have driven the job to ``completed`` with
``controls_extracted: 0`` and built an empty initiative.

The product would then have told a customer that the regulation they are legally
bound by contains no requirements, with nothing anywhere indicating a failure.
That is the single most damaging thing this system can say, and it was the
default behaviour on any run that came back empty.

The rule locked here: an empty result from a document with readable text is
raised as an error, exactly as an unreadable PDF already is. Both are "we could
not analyse this", and both must look like it.
"""

import pytest

from app.pipeline.control_extractor import (
    MIN_TEXT_CHARS_FOR_EXTRACTION,
    _reject_empty_extraction,
)
from app.pipeline.models import ControlExtractionResult, ExtractedControl


def _result(controls):
    return ControlExtractionResult(
        framework_name="Test Framework",
        summary="A framework used to exercise the empty-extraction guard.",
        controls=controls,
    )


def _control():
    return ExtractedControl(
        control_id="CTRL-001",
        control_title="Encrypt data at rest",
        control_description="All stored data must be encrypted at rest.",
        domain="Data Protection & Encryption",
        control_type="Technical",
    )


def test_an_empty_extraction_from_a_readable_document_is_an_error():
    readable = "x" * (MIN_TEXT_CHARS_FOR_EXTRACTION + 1)

    with pytest.raises(ValueError) as exc:
        _reject_empty_extraction(_result([]), readable)

    message = str(exc.value)
    # The message has to tell the operator two things they cannot otherwise know:
    # that text WAS read (so this is not a scanned-PDF problem), and that a retry
    # is worth attempting (because extraction is not deterministic).
    assert "no controls" in message.lower()
    assert "deterministic" in message.lower()


def test_a_document_with_almost_no_text_is_left_to_the_unreadable_pdf_error():
    """Two different failures deserve two different messages.

    A scanned image and a readable document that yielded nothing are not the
    same problem, and reporting them identically would send the operator looking
    for OCR when the real answer is "run it again".
    """
    _reject_empty_extraction(_result([]), "short")


def test_a_normal_extraction_passes_through_untouched():
    _reject_empty_extraction(_result([_control()]), "x" * 10_000)


def test_the_guard_is_wired_into_the_real_extraction_entry_point():
    """Testing the helper alone would not prove the pipeline ever calls it.

    All four callers in ``api/routes/pipeline.py`` go through
    ``extract_controls_from_text``, so the guard has to fire there rather than
    only in a unit that nothing reaches.
    """
    import app.pipeline.control_extractor as ce

    original_single = ce._extract_single
    original_client = ce.get_openai_client
    ce.get_openai_client = lambda config: object()
    ce._extract_single = lambda client, config, text, metadata: _result([])
    try:
        with pytest.raises(ValueError, match="No controls"):
            ce.extract_controls_from_text(
                "y" * (MIN_TEXT_CHARS_FOR_EXTRACTION + 1),
                _PipelineConfigStub(),
            )
    finally:
        ce._extract_single = original_single
        ce.get_openai_client = original_client


class _PipelineConfigStub:
    extract_chunk_chars = 100_000
    max_tokens = 1000
    azure_openai_deployment = "gpt"
    azure_openai_fallback_model = None
