"""
Configuration module for AI Control Mapping Agent.
Loads environment variables and provides application configuration.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


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
    azure_openai_deployment_name: str = "gpt-4o"
    azure_openai_api_version: str = "2024-10-21"

    # Optional: For user-assigned managed identity
    azure_client_id: Optional[str] = None
    azure_tenant_id: Optional[str] = None

    # CORS Settings
    cors_origins: list[str] = ["http://localhost:8501", "http://localhost:3000"]

    # Data paths
    mcsb_data_path: str = "data/mcsb/mcsb_v1_controls.json"
    policy_mappings_path: str = "data/mcsb/azure_policy_mappings.json"

    # AI Mapping Settings
    ai_temperature: float = 0.3  # Lower for consistency
    ai_max_tokens: int = 2000
    ai_batch_size: int = 5  # Process controls in batches

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
