"""
Azure authentication module using DefaultAzureCredential.
Supports both local development (Azure CLI) and Azure deployment (Managed Identity).
"""

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from functools import lru_cache
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@lru_cache
def get_azure_credential() -> DefaultAzureCredential:
    """
    Get DefaultAzureCredential instance.

    This credential automatically detects:
    - Managed Identity (in Azure deployment)
    - Azure CLI credentials (local development)
    - Environment variables
    - Interactive browser login

    Returns:
        DefaultAzureCredential: Configured credential instance
    """
    logger.info("Initializing DefaultAzureCredential")

    credential_kwargs = {}

    # If user-assigned managed identity is configured
    if settings.azure_client_id:
        credential_kwargs["managed_identity_client_id"] = settings.azure_client_id
        logger.info(f"Using user-assigned managed identity: {settings.azure_client_id}")

    credential = DefaultAzureCredential(**credential_kwargs)
    logger.info("DefaultAzureCredential initialized successfully")

    return credential


@lru_cache
def get_azure_openai_client() -> AzureOpenAI:
    """
    Get Azure OpenAI client with token-based authentication.

    Returns:
        AzureOpenAI: Configured Azure OpenAI client

    Example:
        ```python
        client = get_azure_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}]
        )
        ```
    """
    logger.info("Initializing Azure OpenAI client")

    credential = get_azure_credential()

    # Get bearer token provider for Cognitive Services
    token_provider = get_bearer_token_provider(
        credential,
        "https://cognitiveservices.azure.com/.default"
    )

    client = AzureOpenAI(
        api_version=settings.azure_openai_api_version,
        azure_endpoint=settings.azure_openai_endpoint,
        azure_ad_token_provider=token_provider,
        timeout=120.0  # 2 minutes timeout for API calls
    )

    logger.info(f"Azure OpenAI client initialized for endpoint: {settings.azure_openai_endpoint}")

    return client


def test_azure_openai_connection() -> bool:
    """
    Test Azure OpenAI connection with a simple API call.

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        logger.info("Testing Azure OpenAI connection...")
        client = get_azure_openai_client()

        response = client.chat.completions.create(
            model=settings.azure_openai_deployment_name,
            messages=[{"role": "user", "content": "Hello, Azure OpenAI!"}],
            max_completion_tokens=10
        )

        logger.info("Azure OpenAI connection test successful")
        logger.debug(f"Test response: {response.choices[0].message.content}")

        return True

    except Exception as e:
        logger.error(f"Azure OpenAI connection test failed: {e}")
        return False
