"""
Configuration module for AI Control Mapping Agent.
Loads environment variables and provides application configuration.
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import Optional, Union


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "AI Control Mapping Agent"
    app_version: str = "1.0.0"
    debug: bool = False

    # API Settings
    backend_host: str = "localhost"
    backend_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    # Azure Open AI Settings
    azure_openai_endpoint: str
    azure_openai_deployment_name: str = "gpt-4.1"  # Primary model
    azure_openai_fallback_model: str = "gpt-4o-fallback"  # Fallback if gpt-4.1 unavailable
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_api_key: Optional[str] = None  # If set, uses API key; else DefaultAzureCredential

    # Optional: For user-assigned managed identity
    azure_client_id: Optional[str] = None
    azure_tenant_id: Optional[str] = None

    # Cosmos DB Settings
    cosmos_db_endpoint: Optional[str] = None
    cosmos_db_database_name: str = "compliance-iq-db"

    # Application Insights
    applicationinsights_connection_string: Optional[str] = None

    # Authentication
    enable_auth: bool = False  # Enable Azure AD authentication
    azure_ad_tenant_id: Optional[str] = None
    azure_ad_client_id: Optional[str] = None
    azure_ad_audience: Optional[str] = None  # Defaults to client_id if not set

    # Environment
    environment: str = "development"  # development, staging, production
    log_level: str = "INFO"

    # CORS Settings (can be comma-separated string or list)
    cors_origins: Union[list[str], str] = "http://localhost:8501,http://localhost:3000"
    
    @field_validator('cors_origins', mode='before')
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(',') if origin.strip()]
        return v

    # Data paths
    mcsb_data_path: str = "data/mcsb/mcsb_v1_controls.json"
    policy_mappings_path: str = "data/mcsb/azure_policy_mappings.json"

    # AI Mapping Settings
    ai_temperature: float = 0.3  # Lower for consistency
    ai_max_tokens: int = 16000
    ai_batch_size: int = 5  # Process controls in batches

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
