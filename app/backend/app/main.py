"""
FastAPI main application for AI Control Mapping Agent.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from app.config import get_settings
from app.api.routes import health, mapping, policy, sovereignty, pipeline, deploy, platform, m365, purview
from app.logging_config import configure_logging, get_logger
from app.monitoring import app_insights
from app.db import cosmos_client
from app.middleware import (
    LoggingMiddleware,
    global_exception_handler,
    http_exception_handler,
    validation_exception_handler
)

# Get settings
settings = get_settings()

# Configure structured logging
configure_logging(settings.log_level)
logger = get_logger(__name__)

# Suppress noisy library loggers
for noisy_logger in [
    "azure.identity", "azure.core", "httpcore", "httpx",
    "openai._base_client", "urllib3", "msal"
]:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered control mapping agent for Azure, Microsoft 365, and Purview compliance frameworks",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add custom middleware
app.add_middleware(LoggingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Include routers
app.include_router(health.router, prefix=f"{settings.api_v1_prefix}/health")
app.include_router(mapping.router, prefix=settings.api_v1_prefix)
app.include_router(policy.router, prefix=settings.api_v1_prefix)
app.include_router(sovereignty.router, prefix=settings.api_v1_prefix)
app.include_router(pipeline.router, prefix=settings.api_v1_prefix)
app.include_router(deploy.router, prefix=settings.api_v1_prefix)
app.include_router(platform.router, prefix=settings.api_v1_prefix)
app.include_router(m365.router, prefix=settings.api_v1_prefix)
app.include_router(purview.router, prefix=settings.api_v1_prefix)


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment
    )
    
    # Initialize Application Insights
    try:
        app_insights.initialize()
        logger.info("application_insights_initialized")
    except Exception as e:
        # opencensus is incompatible with Python 3.14 — skip gracefully
        print(f"[WARN] Application Insights init skipped: {e}")
    
    # Initialize Cosmos DB client
    if settings.cosmos_db_endpoint:
        try:
            await cosmos_client.initialize()
            logger.info("cosmos_db_initialized", endpoint=settings.cosmos_db_endpoint)
        except Exception as e:
            logger.error("cosmos_db_initialization_failed", error=str(e))
    else:
        logger.warning("cosmos_db_not_configured")
    
    logger.info(
        "application_started",
        api_prefix=settings.api_v1_prefix,
        openai_endpoint=settings.azure_openai_endpoint,
        openai_model=settings.azure_openai_deployment_name
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("application_shutting_down")
    
    # Close Cosmos DB client
    if cosmos_client.client:
        await cosmos_client.close()
        logger.info("cosmos_db_closed")
    
    logger.info("application_shutdown_complete")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AI Control Mapping Agent API",
        "version": settings.app_version,
        "docs": "/docs",
        "health": f"{settings.api_v1_prefix}/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=settings.debug
    )
