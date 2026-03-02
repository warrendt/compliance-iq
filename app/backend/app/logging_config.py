"""
Structured logging configuration using structlog and Application Insights
"""
import logging
import sys
from typing import Any
import structlog
from pythonjsonlogger import jsonlogger
import os

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
        record.service_name = "cctoolkit-backend"
        return True


# Configure JSON formatter for standard logging
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields"""
    
    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record['service_name'] = 'cctoolkit-backend'
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
