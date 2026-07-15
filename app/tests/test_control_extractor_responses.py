"""Regression tests for Responses API model fallback."""

from types import SimpleNamespace

import openai

from app.pipeline.config import PipelineConfig
from app.pipeline.control_extractor import _parse_with_retry, _strict_response_schema
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
