"""
Logging middleware for request context and correlation IDs.

Uses raw ASGI (not BaseHTTPMiddleware) to avoid body-buffering issues
with streaming multipart file uploads on platforms like Azure Container Apps.
BaseHTTPMiddleware has a known Starlette limitation where it can interfere
with streaming request bodies, causing:
  "Attempted to access streaming request content, without having called read()"
"""
import time
import uuid
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
import structlog

logger = structlog.get_logger(__name__)


class LoggingMiddleware:
    """Pure ASGI middleware to add logging context and track requests."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = str(uuid.uuid4())

        # Set correlation ID on request.state without touching the body stream.
        # Creating Request(scope) here only reads scope metadata — no body buffering.
        req = Request(scope)
        req.state.correlation_id = correlation_id

        # Read metadata from scope directly (no body access)
        method = scope.get("method", "")
        path = scope.get("path", "")
        query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")
        client = scope.get("client")
        client_host = client[0] if client else None

        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            request_path=path,
            request_method=method,
        )

        start_time = time.time()
        logger.info(
            "request_started",
            method=method,
            path=path,
            query_params=query_string,
            client_host=client_host,
        )

        status_code = 500

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
                # Inject correlation ID into response headers
                headers = MutableHeaders(scope=message)
                headers.append("X-Correlation-ID", correlation_id)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                "request_completed",
                status_code=status_code,
                duration_ms=round(duration_ms, 2),
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "request_failed",
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration_ms, 2),
                exc_info=True,
            )
            raise
        finally:
            structlog.contextvars.clear_contextvars()
