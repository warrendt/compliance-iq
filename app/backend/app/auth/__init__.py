"""
Azure authentication module.
"""

from app.auth.azure_auth import (
    get_azure_credential,
    get_azure_openai_client,
    test_azure_openai_connection
)

__all__ = [
    "get_azure_credential",
    "get_azure_openai_client",
    "test_azure_openai_connection",
]
