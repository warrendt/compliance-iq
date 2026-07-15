"""Regression tests for Responses API model fallback."""

from types import SimpleNamespace

import openai
import pytest

from app.pipeline.config import PipelineConfig
from app.pipeline.control_extractor import (
    _extract_multi_chunk,
    _parse_with_retry,
    _strict_response_schema,
)
from app.pipeline.models import ControlExtractionResult


def _result_json() -> str:
    return """{
        "framework_name": "Example Framework",
        "framework_version": null,
        "issuing_authority": null,
        "country_or_region": null,
        "summary": "Example",
        "controls": []
    }"""


def test_responses_api_falls_back_after_primary_timeout():
    calls: list[str] = []

    class Responses:
        def create(self, *, model, **_kwargs):
            calls.append(model)
            if model == "gpt-5.6-sol":
                raise openai.APITimeoutError(request=SimpleNamespace())
            return SimpleNamespace(output_text=_result_json())

    config = PipelineConfig(
        azure_openai_deployment="gpt-5.6-sol",
        azure_openai_fallback_model="gpt-4.1-fallback",
    )
    result = _parse_with_retry(
        SimpleNamespace(responses=Responses()),
        config,
        [{"role": "user", "content": "Extract controls"}],
        response_format=ControlExtractionResult,
        max_retries=1,
    )

    assert calls == ["gpt-5.6-sol", "gpt-4.1-fallback"]
    assert result.framework_name == "Example Framework"


def test_responses_api_schema_rejects_extra_properties_for_all_objects():
    schema = _strict_response_schema(ControlExtractionResult)

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])

    extracted_control = schema["$defs"]["ExtractedControl"]
    assert extracted_control["additionalProperties"] is False
    assert set(extracted_control["required"]) == set(extracted_control["properties"])


def test_failed_sections_is_stripped_from_strict_schema():
    """The server-only failed_sections field must never be sent to the model."""
    schema = _strict_response_schema(ControlExtractionResult)

    assert "failed_sections" not in schema["properties"]
    assert "failed_sections" not in schema["required"]


def _control_json(control_id: str) -> str:
    return (
        '{"framework_name":"F","framework_version":null,"issuing_authority":null,'
        '"country_or_region":null,"summary":"s","controls":['
        f'{{"control_id":"{control_id}","control_title":"t","control_description":"d",'
        '"domain":"Network Security","control_type":"Technical","sub_controls":[]}]}'
    )


def test_multi_chunk_keeps_partial_results_when_a_section_fails():
    """One section exhausting all models must not discard the sections that worked."""

    class Responses:
        def create(self, *, model, input, **_kwargs):
            text = input[-1]["content"]
            if "FAILME" in text:
                raise openai.APITimeoutError(request=SimpleNamespace())
            control_id = "C1" if "Part 1" in text else "C2"
            return SimpleNamespace(output_text=_control_json(control_id))

    config = PipelineConfig(
        azure_openai_deployment="gpt-5.6-luna",
        azure_openai_fallback_model="gpt-4.1-fallback",
    )
    progress: list[tuple[int, int]] = []

    result = _extract_multi_chunk(
        SimpleNamespace(responses=Responses()),
        config,
        ["good section one", "FAILME section two"],
        metadata_context="",
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert result.failed_sections == 1
    assert [c.control_id for c in result.controls] == ["C1"]
    assert result.framework_name == "F"
    # Progress still advances for the failed section so the UI is not stuck.
    assert progress == [(1, 2), (2, 2)]


def test_multi_chunk_raises_only_when_every_section_fails():
    """If no section produces anything, extraction is a genuine failure."""

    class Responses:
        def create(self, *, model, **_kwargs):
            raise openai.APITimeoutError(request=SimpleNamespace())

    config = PipelineConfig(
        azure_openai_deployment="gpt-5.6-luna",
        azure_openai_fallback_model="gpt-4.1-fallback",
    )

    with pytest.raises(RuntimeError):
        _extract_multi_chunk(
            SimpleNamespace(responses=Responses()),
            config,
            ["section one", "section two"],
            metadata_context="",
        )
