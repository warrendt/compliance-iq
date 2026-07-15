"""
Unit tests for temperature handling in AIMappingService.

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_ai_temperature.py -q -p no:cacheprovider --noconftest
"""

from unittest.mock import MagicMock

import httpx
import openai
import pytest

from app.config import get_settings
from app.services.ai_mapping_service import AIMappingService, _is_temperature_error

settings = get_settings()


def _temperature_error() -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "https://dummy/"))
    body = {
        "message": "Unsupported value: 'temperature' does not support 0.3 with this model.",
        "type": "invalid_request_error",
        "param": "temperature",
        "code": "unsupported_value",
    }
    return openai.BadRequestError(body["message"], response=response, body=body)


def _unrelated_error() -> openai.BadRequestError:
    response = httpx.Response(400, request=httpx.Request("POST", "https://dummy/"))
    body = {"message": "Invalid content", "param": "messages", "code": "invalid"}
    return openai.BadRequestError(body["message"], response=response, body=body)


def _service_with_mock_client() -> AIMappingService:
    """Build a service without touching Azure clients (bypass __init__)."""
    svc = AIMappingService.__new__(AIMappingService)
    svc.model = "gpt-4.1"
    svc._temperature_supported = True
    svc.client = MagicMock()
    return svc


class TestIsTemperatureError:
    def test_detects_param(self):
        assert _is_temperature_error(_temperature_error()) is True

    def test_detects_message_without_param(self):
        response = httpx.Response(400, request=httpx.Request("POST", "https://dummy/"))
        err = openai.BadRequestError(
            "temperature is not supported", response=response, body=None)
        assert _is_temperature_error(err) is True

    def test_ignores_unrelated(self):
        assert _is_temperature_error(_unrelated_error()) is False


class TestParseMappingCompletion:
    def test_forwards_temperature_on_happy_path(self):
        svc = _service_with_mock_client()
        parse = svc.client.beta.chat.completions.parse
        parse.return_value = "ok"

        result = svc._parse_mapping_completion([{"role": "user", "content": "x"}])

        assert result == "ok"
        parse.assert_called_once()
        assert parse.call_args.kwargs["temperature"] == settings.ai_temperature
        assert svc._temperature_supported is True

    def test_retries_without_temperature_on_rejection(self):
        svc = _service_with_mock_client()
        parse = svc.client.beta.chat.completions.parse
        parse.side_effect = [_temperature_error(), "ok"]

        result = svc._parse_mapping_completion([{"role": "user", "content": "x"}])

        assert result == "ok"
        assert parse.call_count == 2
        assert "temperature" in parse.call_args_list[0].kwargs  # first tried with it
        assert "temperature" not in parse.call_args_list[1].kwargs  # retry dropped it
        assert svc._temperature_supported is False

    def test_suppresses_temperature_after_first_rejection(self):
        svc = _service_with_mock_client()
        svc._temperature_supported = False  # already learned it's unsupported
        parse = svc.client.beta.chat.completions.parse
        parse.return_value = "ok"

        svc._parse_mapping_completion([{"role": "user", "content": "x"}])

        parse.assert_called_once()
        assert "temperature" not in parse.call_args.kwargs

    def test_reraises_non_temperature_bad_request(self):
        svc = _service_with_mock_client()
        parse = svc.client.beta.chat.completions.parse
        parse.side_effect = _unrelated_error()

        with pytest.raises(openai.BadRequestError):
            svc._parse_mapping_completion([{"role": "user", "content": "x"}])
        assert svc._temperature_supported is True  # unchanged
