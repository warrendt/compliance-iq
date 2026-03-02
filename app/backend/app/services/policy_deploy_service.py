"""
Deploy Azure Policy definitions, initiatives, and assignments using the
caller's delegated Entra ID access token (on-behalf-of flow).

The service proxies ARM REST calls so the frontend never talks to ARM directly.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_ARM_BASE = "https://management.azure.com"
_API_VERSION_POLICY = "2023-04-01"
_TIMEOUT = 30.0


class PolicyDeployService:
    """Thin wrapper around Azure Resource Manager policy APIs."""

    def __init__(self, access_token: str):
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Scope helpers
    # ------------------------------------------------------------------

    async def list_subscriptions(self) -> list[dict[str, Any]]:
        """Return subscriptions visible to the caller."""
        url = f"{_ARM_BASE}/subscriptions?api-version=2022-12-01"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json().get("value", [])

    async def list_management_groups(self) -> list[dict[str, Any]]:
        """Return management groups visible to the caller."""
        url = f"{_ARM_BASE}/providers/Microsoft.Management/managementGroups?api-version=2021-04-01"
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json().get("value", [])

    # ------------------------------------------------------------------
    # Validate (dry-run)
    # ------------------------------------------------------------------

    async def validate_initiative(
        self, scope: str, initiative_name: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        """PUT the initiative definition and return ARM response.

        Uses the same PUT endpoint but we limit to returning the result
        without an assignment (pure definition creation is idempotent).
        """
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policySetDefinitions/{initiative_name}?api-version={_API_VERSION_POLICY}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.put(url, headers=self._headers, json=body)
            data = resp.json() if resp.status_code != 204 else {}
            return {"status_code": resp.status_code, "body": data}

    # ------------------------------------------------------------------
    # Deploy initiative (definition + optional assignment)
    # ------------------------------------------------------------------

    async def deploy_initiative(
        self,
        scope: str,
        initiative_name: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or update a policy set definition at *scope*."""
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policySetDefinitions/{initiative_name}?api-version={_API_VERSION_POLICY}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.put(url, headers=self._headers, json=body)
            resp.raise_for_status()
            return resp.json()

    async def create_assignment(
        self,
        scope: str,
        assignment_name: str,
        policy_set_definition_id: str,
        display_name: str,
        description: str = "",
    ) -> dict[str, Any]:
        """Assign a policy set definition at *scope*."""
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policyAssignments/{assignment_name}?api-version={_API_VERSION_POLICY}"
        )
        body = {
            "properties": {
                "policyDefinitionId": policy_set_definition_id,
                "displayName": display_name,
                "description": description,
            }
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.put(url, headers=self._headers, json=body)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Read existing policies (for explorer)
    # ------------------------------------------------------------------

    async def list_policy_definitions(
        self, scope: str, *, custom_only: bool = True
    ) -> list[dict[str, Any]]:
        """List policy definitions at *scope*."""
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policyDefinitions?api-version={_API_VERSION_POLICY}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            items = resp.json().get("value", [])
        if custom_only:
            items = [
                d for d in items
                if d.get("properties", {}).get("policyType") == "Custom"
            ]
        return items

    async def list_policy_set_definitions(
        self, scope: str, *, custom_only: bool = True
    ) -> list[dict[str, Any]]:
        """List policy set (initiative) definitions at *scope*."""
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policySetDefinitions?api-version={_API_VERSION_POLICY}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            items = resp.json().get("value", [])
        if custom_only:
            items = [
                d for d in items
                if d.get("properties", {}).get("policyType") == "Custom"
            ]
        return items

    async def list_policy_assignments(
        self, scope: str
    ) -> list[dict[str, Any]]:
        """List policy assignments at *scope*."""
        url = (
            f"{_ARM_BASE}/{scope.lstrip('/')}/providers/Microsoft.Authorization"
            f"/policyAssignments?api-version={_API_VERSION_POLICY}"
        )
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            resp = await c.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json().get("value", [])
