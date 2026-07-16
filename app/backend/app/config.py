"""
Configuration module for AI Control Mapping Agent.
Loads environment variables and provides application configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
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
    azure_openai_deployment_name: str = "gpt-5.6-sol"
    azure_openai_fallback_model: str = "gpt-4.1-fallback"
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_api_key: Optional[str] = None  # If set, uses API key; else DefaultAzureCredential
    azure_openai_request_timeout_seconds: float = 120.0

    # Optional: For user-assigned managed identity
    azure_client_id: Optional[str] = None
    azure_tenant_id: Optional[str] = None

    # Microsoft Graph API Settings (for M365 and Purview)
    graph_api_base_url: str = "https://graph.microsoft.com/v1.0"
    graph_api_beta_url: str = "https://graph.microsoft.com/beta"
    graph_client_id: Optional[str] = None  # App registration for Graph API access
    graph_client_secret: Optional[str] = None  # Client secret (use managed identity in production)

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
    # Bundled external-framework catalogues (CSV). Relative paths are resolved
    # against the backend ``app/`` package dir; absolute paths are used as-is.
    catalogues_dir: str = "data/catalogues"

    # Azure Policy catalog (retrieval corpus for control -> policy mapping).
    # Relative paths are resolved against the backend ``app/`` package dir.
    policy_catalog_path: str = "data/policy_catalog/azure_policy_catalog.json"
    # Candidate policy definitions retrieved per control and offered to the LLM.
    policy_catalog_candidate_count: int = 15
    # Best-effort runtime refresh of the catalog from ARM using the backend's
    # managed identity. Off by default; the on-demand refresh endpoint works
    # regardless. Requires the identity to have Reader on a subscription.
    policy_catalog_runtime_refresh: bool = False
    # Subscription used for runtime/on-demand ARM catalog refresh (optional;
    # falls back to the first subscription visible to the identity).
    policy_catalog_refresh_subscription: Optional[str] = None

    # AI Mapping Settings
    ai_temperature: float = 0.3  # Lower for consistency
    ai_max_tokens: int = 16000
    ai_batch_size: int = 5  # Process controls in batches
    ai_mapping_max_concurrency: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
