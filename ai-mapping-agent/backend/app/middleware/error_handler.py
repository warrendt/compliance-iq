"""
Global error handler for FastAPI
"""
import traceback
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

logger = structlog.get_logger(__name__)


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for all unhandled exceptions.
    
    Args:
        request: FastAPI request
        exc: Exception raised
        
    Returns:
        JSON error response
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    # Log exception with full context
    logger.error(
        "unhandled_exception",
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        stack_trace=traceback.format_exc(),
        correlation_id=correlation_id,
        request_path=request.url.path,
        request_method=request.method,
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please contact support.",
            "correlation_id": correlation_id
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handler for HTTP exceptions.
    
    Args:
        request: FastAPI request
        exc: HTTP exception
        
    Returns:
        JSON error response
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.warning(
        "http_exception",
        status_code=exc.status_code,
        detail=exc.detail,
        correlation_id=correlation_id,
        request_path=request.url.path
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "correlation_id": correlation_id
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handler for request validation errors.
    
    Args:
        request: FastAPI request
        exc: Validation error
        
    Returns:
        JSON error response
    """
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.warning(
        "validation_error",
        errors=exc.errors(),
        correlation_id=correlation_id,
        request_path=request.url.path
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation error",
            "details": exc.errors(),
            "correlation_id": correlation_id
        }
    )
