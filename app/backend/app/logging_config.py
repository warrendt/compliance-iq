"""
Structured logging configuration using structlog and Application Insights.

Includes a ``MemoryLogHandler`` that keeps the last *N* log entries in an
in-memory ring buffer so they can be served to the frontend via
``GET /api/v1/health/logs``.
"""
import logging
import sys
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List
import structlog
from pythonjsonlogger import jsonlogger
import os


# ── In-memory log buffer ──────────────────────────────────────────────────

_MAX_LOG_BUFFER = 500
_log_buffer: deque[Dict[str, Any]] = deque(maxlen=_MAX_LOG_BUFFER)
_log_lock = Lock()
_log_cursor: int = 0  # monotonically increasing sequence number


class MemoryLogHandler(logging.Handler):
    """Handler that stores log records in a bounded in-memory deque."""

    def emit(self, record: logging.LogRecord) -> None:
        global _log_cursor
        try:
            entry: Dict[str, Any] = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            }
            with _log_lock:
                _log_cursor += 1
                entry["seq"] = _log_cursor
                _log_buffer.append(entry)
        except Exception:
            pass  # never let logging crash the app


def get_log_entries(since: int = 0, level: str = "DEBUG", limit: int = 200) -> Dict[str, Any]:
    """Return buffered log entries with *seq* > *since*.

    Args:
        since: Only return entries whose ``seq`` is strictly greater.
        level: Minimum log level filter (DEBUG, INFO, WARNING, ERROR).
        limit: Max entries to return.

    Returns:
        Dict with ``logs`` list, ``next_cursor``, and ``total_buffered``.
    """
    min_level = getattr(logging, level.upper(), logging.DEBUG)
    with _log_lock:
        entries = [
            e for e in _log_buffer
            if e["seq"] > since and getattr(logging, e.get("level", "DEBUG"), 0) >= min_level
        ]
    # Apply limit (return newest entries)
    if len(entries) > limit:
        entries = entries[-limit:]

    next_cursor = entries[-1]["seq"] if entries else since
    return {
        "logs": entries,
        "next_cursor": next_cursor,
        "total_buffered": len(_log_buffer),
    }


def configure_logging(level: str = "INFO") -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        stream=sys.stdout
    )

    # Attach the in-memory handler to the root logger
    memory_handler = MemoryLogHandler()
    memory_handler.setLevel(log_level)
    memory_handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(memory_handler)
    
    # Configure structlog processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    
    # Use JSON formatting in production, human-readable in development
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "development":
        # Human-readable output for local development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer()
        ]
    else:
        # JSON output for Azure (parsable by Log Analytics)
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class ContextFilter(logging.Filter):
    """Filter to add context to log records"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Add service name
        record.service_name = "compliance-iq-backend"
        return True


# Configure JSON formatter for standard logging
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record['service_name'] = 'compliance-iq-backend'
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
