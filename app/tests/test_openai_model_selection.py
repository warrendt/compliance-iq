"""Regression coverage for Azure OpenAI primary and fallback deployment wiring."""

import json
from pathlib import Path

from app.config import Settings
from app.pipeline.config import PipelineConfig


APP_ROOT = Path(__file__).resolve().parents[1]


def test_default_pipeline_deployments_prefer_sol_with_a_distinct_fallback():
    config = PipelineConfig()

    assert config.azure_openai_deployment == "gpt-5.6-sol"
    assert config.azure_openai_fallback_model == "gpt-4.1-fallback"
    assert config.azure_openai_deployment != config.azure_openai_fallback_model


def test_application_settings_use_the_same_deployment_defaults():
    settings = Settings(azure_openai_endpoint="https://example.openai.azure.com")

    assert settings.azure_openai_deployment_name == "gpt-5.6-sol"
    assert settings.azure_openai_fallback_model == "gpt-4.1-fallback"


def test_environment_can_override_both_deployment_names(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT_NAME", "primary-deployment")
    monkeypatch.setenv("AZURE_OPENAI_FALLBACK_MODEL", "fallback-deployment")

    config = PipelineConfig.from_env()

    assert config.azure_openai_deployment == "primary-deployment"
    assert config.azure_openai_fallback_model == "fallback-deployment"


def test_bicep_parameters_keep_primary_and_fallback_deployment_names_explicit():
    parameters = json.loads((APP_ROOT / "infra" / "main.parameters.json").read_text())
    values = parameters["parameters"]

    assert values["openAiModelName"]["value"] == "${AZURE_OPENAI_MODEL_NAME=gpt-5.6-sol}"
    assert values["openAiModelVersion"]["value"] == "${AZURE_OPENAI_MODEL_VERSION=2026-07-09}"
    assert values["openAiFallbackModel"]["value"] == "${AZURE_OPENAI_FALLBACK_MODEL=gpt-4.1}"
    assert values["openAiFallbackVersion"]["value"] == "${AZURE_OPENAI_FALLBACK_VERSION=2025-04-14}"
    assert values["openAiPrimaryDeploymentName"]["value"] == "${AZURE_OPENAI_PRIMARY_DEPLOYMENT_NAME=gpt-5.6-sol}"
    assert values["openAiFallbackDeploymentName"]["value"] == "${AZURE_OPENAI_FALLBACK_DEPLOYMENT_NAME=gpt-4.1-fallback}"
