"""
Azure AD / Entra ID authentication module.

Supports two operational modes:
  1. **Production** (ENABLE_AUTH=true): Validates JWT bearer tokens from
     Container Apps Easy Auth or direct MSAL client flows.
  2. **Development** (ENABLE_AUTH=false): Returns a deterministic mock user
     so local workflows run without Azure AD configuration.
"""

import os
import time
from typing import Optional

import httpx
import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Security scheme (auto_error=False so we can handle missing tokens ourselves)
# ---------------------------------------------------------------------------
security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# JWKS caching (module-level singleton)
# ---------------------------------------------------------------------------
_jwks_cache: dict | None = None
_jwks_cache_ts: float = 0.0
_JWKS_TTL_SECONDS = 3600  # refresh signing keys once per hour


class User:
    """Thin user principal extracted from an Azure AD JWT."""

    def __init__(
        self,
        oid: str,
        email: str,
        name: str,
        roles: list[str] | None = None,
        access_token: str | None = None,
    ):
        self.oid = oid
        self.email = email
        self.name = name
        self.roles = roles or []
        self.access_token = access_token  # original bearer token for ARM calls

    def __str__(self) -> str:
        return f"User(oid={self.oid}, email={self.email})"


# ---------------------------------------------------------------------------
# JWKS helpers
# ---------------------------------------------------------------------------

def _get_tenant_id() -> str:
    return os.getenv("AZURE_AD_TENANT_ID", "common")


def _get_jwks_url() -> str:
    tenant = _get_tenant_id()
    return f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"


def _get_issuer_urls() -> list[str]:
    """Return accepted issuer URLs (v1 + v2 endpoints)."""
    tenant = _get_tenant_id()
    return [
        f"https://login.microsoftonline.com/{tenant}/v2.0",
        f"https://sts.windows.net/{tenant}/",
    ]


async def _fetch_jwks() -> dict:
    """Retrieve JSON Web Key Set, with in-memory caching."""
    global _jwks_cache, _jwks_cache_ts

    now = time.monotonic()
    if _jwks_cache and (now - _jwks_cache_ts) < _JWKS_TTL_SECONDS:
        return _jwks_cache

    url = _get_jwks_url()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_ts = now
        logger.info("jwks_refreshed", url=url)
        return _jwks_cache


def _find_signing_key(jwks: dict, kid: str) -> dict | None:
    """Find the key in the JWKS that matches the given Key ID."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

async def _validate_token(token: str) -> dict:
    """Validate a JWT issued by Entra ID and return its claims."""
    global _jwks_cache_ts

    audience = os.getenv(
        "AZURE_AD_AUDIENCE",
        os.getenv("AZURE_AD_CLIENT_ID", ""),
    )

    # Decode header to get the key id
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token header: {exc}")

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token header missing 'kid'")

    jwks = await _fetch_jwks()
    signing_key = _find_signing_key(jwks, kid)
    if not signing_key:
        # JWKS may have rotated — force refresh once
        _jwks_cache_ts = 0
        jwks = await _fetch_jwks()
        signing_key = _find_signing_key(jwks, kid)
        if not signing_key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Signing key not found in JWKS")

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=_get_issuer_urls(),
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        logger.warning("jwt_validation_failed", error=str(exc))
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Token validation failed: {exc}")

    return claims


# ---------------------------------------------------------------------------
# Easy Auth header helpers
# ---------------------------------------------------------------------------

def _user_from_easy_auth(request: Request) -> User | None:
    """Extract user identity from Container Apps Easy Auth headers."""
    principal_name = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    if not principal_name:
        return None

    access_token = request.headers.get("X-MS-TOKEN-AAD-ACCESS-TOKEN")
    principal_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "")

    return User(
        oid=principal_id,
        email=principal_name,
        name=principal_name.split("@")[0] if "@" in principal_name else principal_name,
        access_token=access_token,
    )


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """FastAPI dependency that resolves the current authenticated user.

    Resolution order:
      1. Easy Auth headers (X-MS-CLIENT-PRINCIPAL-NAME)
      2. Authorization: Bearer <JWT>
      3. Mock user when ENABLE_AUTH=false (dev mode)
    """
    auth_enabled = os.getenv("ENABLE_AUTH", "false").lower() == "true"

    # 1. Easy Auth headers (set by Container Apps authentication)
    easy_user = _user_from_easy_auth(request)
    if easy_user:
        logger.info("auth_easy_auth", user=easy_user.email)
        return easy_user

    # 2. Bearer token
    if credentials and credentials.credentials:
        token = credentials.credentials
        claims = await _validate_token(token)
        user = User(
            oid=claims.get("oid", claims.get("sub", "")),
            email=claims.get("preferred_username", claims.get("email", claims.get("upn", ""))),
            name=claims.get("name", ""),
            roles=claims.get("roles", []),
            access_token=token,
        )
        logger.info("auth_jwt", user=user.email)
        return user

    # 3. Dev mode fallback
    if not auth_enabled:
        logger.debug("auth_disabled_mock_user")
        return User(oid="dev-user-123", email="dev@example.com", name="Development User")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Optional: dependency that returns None instead of 401 when no auth
async def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User | None:
    """Same as get_current_user but returns None instead of raising 401."""
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


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
