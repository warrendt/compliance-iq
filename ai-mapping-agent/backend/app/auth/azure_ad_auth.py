"""
Simplified Azure AD authentication (placeholder for full implementation)
Note: Full Azure AD integration requires app registration configuration
"""
import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import structlog

logger = structlog.get_logger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


class User:
    """User model from Azure AD token"""
    
    def __init__(self, oid: str, email: str, name: str):
        self.oid = oid  # Object ID (unique user identifier)
        self.email = email
        self.name = name
        
    def __str__(self):
        return f"User(oid={self.oid}, email={self.email})"


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> User:
    """
    Dependency to get current authenticated user.
    
    For now, this is a simplified implementation.
    In production, this should validate JWT tokens from Azure AD.
    
    Args:
        credentials: Bearer token from Authorization header
        
    Returns:
        User object
        
    Raises:
        HTTPException: If authentication fails
    """
    # Check if authentication is enabled
    auth_enabled = os.getenv("ENABLE_AUTH", "false").lower() == "true"
    
    if not auth_enabled:
        # Development mode: return mock user
        logger.debug("Authentication disabled - using mock user")
        return User(
            oid="dev-user-123",
            email="dev@example.com",
            name="Development User"
        )
    
    if not credentials:
        logger.warning("authentication_failed", reason="missing_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials"
        )
    
    # TODO: Implement full Azure AD JWT validation
    # 1. Decode JWT token
    # 2. Validate signature using Azure AD public keys
    # 3. Verify token claims (issuer, audience, expiration)
    # 4. Extract user info from token
    
    try:
        token = credentials.credentials
        
        # Placeholder validation
        # In production, use fastapi-azure-auth or similar library
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Mock user extraction (replace with real JWT decoding)
        user = User(
            oid="user-" + token[:8],
            email="user@example.com",
            name="Authenticated User"
        )
        
        logger.info("authentication_success", user_id=user.oid)
        return user
        
    except Exception as e:
        logger.error("authentication_error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Optional authentication - returns None if not authenticated.
    
    Args:
        credentials: Bearer token from Authorization header
        
    Returns:
        User object or None
    """
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
