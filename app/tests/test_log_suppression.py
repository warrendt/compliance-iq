"""Tests for noisy third-party logger suppression.

The Cosmos SDK routes HTTP logging through ``azure.cosmos`` (its own
``CosmosHttpLoggingPolicy``), which is *not* a child of ``azure.core``. A
regression here floods the backend logs with full HTTP header dumps, so this
locks in that ``azure.cosmos`` (and the other chatty SDKs) are quieted.
"""
from __future__ import annotations

import logging

from app.logging_config import NOISY_LOGGERS, quiet_noisy_loggers


def test_cosmos_logger_is_in_noisy_list() -> None:
    # Explicitly required: Cosmos header dumps live under azure.cosmos.
    assert "azure.cosmos" in NOISY_LOGGERS
    # Umbrella azure logger covers any azure.* SDK we didn't name.
    assert "azure" in NOISY_LOGGERS


def test_quiet_noisy_loggers_sets_warning_level() -> None:
    # Start noisy.
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.DEBUG)

    quiet_noisy_loggers()

    for name in NOISY_LOGGERS:
        assert logging.getLogger(name).level == logging.WARNING, name


def test_quiet_noisy_loggers_custom_level() -> None:
    quiet_noisy_loggers(logging.ERROR)
    assert logging.getLogger("azure.cosmos").level == logging.ERROR
    # Reset to the production default so ordering doesn't leak into other tests.
    quiet_noisy_loggers(logging.WARNING)
