"""App Insights telemetry: off without a connection string, sampled when on."""
import os

import microsoft.opentelemetry as distro
import pytest
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.monitoring.app_insights import (
    APP_LOGGER_NAME,
    EXCLUDED_URLS,
    SAMPLER,
    AppInsights,
    resolve_settings,
    sampler_env,
)

CONN = "InstrumentationKey=00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize(
    ("environment", "ratio"),
    [("development", 1.0), ("dev", 0.1), ("production", 0.1)],
)
def test_sampling_ratio_follows_environment(environment, ratio):
    assert resolve_settings({"ENVIRONMENT": environment}).sampling_ratio == ratio


def test_missing_or_blank_connection_string_disables_telemetry():
    assert not resolve_settings({}).enabled
    assert not resolve_settings({"APPLICATIONINSIGHTS_CONNECTION_STRING": ""}).enabled


def test_operator_sampler_override_is_preserved():
    settings = resolve_settings({"ENVIRONMENT": "dev"})
    assert sampler_env(settings, {"OTEL_TRACES_SAMPLER": "always_on"}) == {}
    assert sampler_env(settings, {}) == {
        "OTEL_TRACES_SAMPLER": SAMPLER,
        "OTEL_TRACES_SAMPLER_ARG": "0.1",
    }


@pytest.fixture
def recorded(monkeypatch):
    calls = {"distro": [], "instrument": []}
    monkeypatch.setattr(distro, "use_microsoft_opentelemetry", lambda **kw: calls["distro"].append(kw))
    monkeypatch.setattr(
        FastAPIInstrumentor,
        "instrument_app",
        staticmethod(lambda app, **kw: calls["instrument"].append((app, kw))),
    )
    for name in ("APPLICATIONINSIGHTS_CONNECTION_STRING", "OTEL_TRACES_SAMPLER", "OTEL_TRACES_SAMPLER_ARG"):
        # setenv first so monkeypatch restores the variable initialize() writes.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    return calls


def test_initialize_is_noop_without_connection_string(recorded):
    telemetry = AppInsights()
    assert telemetry.initialize(FastAPI()) is False
    assert not telemetry.enabled
    assert recorded == {"distro": [], "instrument": []}


def test_initialize_configures_distro_and_instruments_app_once(recorded, monkeypatch):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", CONN)
    monkeypatch.setenv("ENVIRONMENT", "dev")
    app = FastAPI()
    telemetry = AppInsights()

    assert telemetry.initialize(app) is True
    assert telemetry.initialize(app) is True

    assert len(recorded["distro"]) == 1
    kwargs = recorded["distro"][0]
    assert kwargs["enable_azure_monitor"] is True
    assert kwargs["azure_monitor_connection_string"] == CONN
    assert kwargs["logger_name"] == APP_LOGGER_NAME
    assert recorded["instrument"] == [(app, {"excluded_urls": EXCLUDED_URLS})]
    assert os.environ["OTEL_TRACES_SAMPLER"] == SAMPLER
    assert os.environ["OTEL_TRACES_SAMPLER_ARG"] == "0.1"
