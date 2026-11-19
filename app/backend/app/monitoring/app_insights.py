"""
Application Insights telemetry via the Microsoft OpenTelemetry Distro.

Replaces the retired opencensus integration, which built a tracer that was
never attached to any request and so exported nothing.

Telemetry is a no-op unless ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set,
so local runs and tests never export. Only stdlib log records from the
``app`` logger hierarchy are exported, which keeps third-party SDK chatter out
of App Insights. Request and response bodies are never recorded.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional

# Container Apps health probes hit this path constantly; tracing it would
# drown real requests and cost ingestion for no diagnostic value.
EXCLUDED_URLS = "api/v1/health/ping"
APP_LOGGER_NAME = "app"
SAMPLER = "microsoft.fixed_percentage"

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TelemetrySettings:
    connection_string: Optional[str]
    environment: str
    sampling_ratio: float

    @property
    def enabled(self) -> bool:
        return bool(self.connection_string)


def resolve_settings(env: Mapping[str, str]) -> TelemetrySettings:
    """Derive telemetry settings from an environment mapping (pure)."""
    environment = env.get("ENVIRONMENT", "development")
    return TelemetrySettings(
        connection_string=env.get("APPLICATIONINSIGHTS_CONNECTION_STRING") or None,
        environment=environment,
        # Keep every trace while developing; sample 10% everywhere else.
        sampling_ratio=1.0 if environment == "development" else 0.1,
    )


def sampler_env(settings: TelemetrySettings, env: Mapping[str, str]) -> dict[str, str]:
    """Sampler variables to apply, leaving any operator override in place (pure)."""
    if "OTEL_TRACES_SAMPLER" in env:
        return {}
    return {
        "OTEL_TRACES_SAMPLER": SAMPLER,
        "OTEL_TRACES_SAMPLER_ARG": str(settings.sampling_ratio),
    }


class AppInsights:
    """Configures the distro once and instruments the FastAPI app."""

    def __init__(self) -> None:
        self.enabled = False

    def initialize(self, app: Any = None) -> bool:
        settings = resolve_settings(os.environ)
        if not settings.enabled:
            _logger.info("Application Insights connection string not set; telemetry disabled")
            return False
        if self.enabled:
            return True

        os.environ.update(sampler_env(settings, os.environ))

        from microsoft.opentelemetry import use_microsoft_opentelemetry

        use_microsoft_opentelemetry(
            enable_azure_monitor=True,
            azure_monitor_connection_string=settings.connection_string,
            logger_name=APP_LOGGER_NAME,
            # The app object already exists by the time this runs, so the
            # import-time FastAPI patch would miss it; instrument it directly.
            instrumentation_options={"fastapi": {"enabled": False}},
        )
        if app is not None:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app, excluded_urls=EXCLUDED_URLS)

        self.enabled = True
        _logger.info(
            "Application Insights telemetry enabled (env=%s, sampling=%s)",
            settings.environment,
            settings.sampling_ratio,
        )
        return True


app_insights = AppInsights()
