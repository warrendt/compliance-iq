"""
Microsoft Graph API client for Microsoft 365 and Purview operations.
Provides authenticated access to Graph API endpoints for compliance policy
management, sensitivity labels, DLP policies, and related configurations.
"""

import logging
from typing import Dict, Any, Optional, List
from functools import lru_cache

import httpx

logger = logging.getLogger(__name__)

# Microsoft Graph API base URL
GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_API_BETA = "https://graph.microsoft.com/beta"

# Well-known Graph API endpoints for compliance
GRAPH_ENDPOINTS = {
    # Microsoft 365 DLP
    "dlp_policies": "/security/dataLossPreventionPolicies",
    # Sensitivity labels
    "sensitivity_labels": "/security/informationProtection/sensitivityLabels",
    # Retention labels
    "retention_labels": "/security/labels/retentionLabels",
    # Conditional Access
    "conditional_access": "/identity/conditionalAccess/policies",
    # Device compliance
    "device_compliance": "/deviceManagement/deviceCompliancePolicies",
    # Information protection
    "information_protection": "/informationProtection/policy/labels",
    # Security alerts
    "security_alerts": "/security/alerts_v2",
    # Compliance settings
    "compliance_settings": "/security/informationProtection",
}

# Required Graph API permissions for each capability
REQUIRED_PERMISSIONS = {
    "dlp": [
        "DlpPolicies.ReadWrite.All",
        "InformationProtectionPolicy.Read.All",
    ],
    "sensitivity_labels": [
        "InformationProtectionPolicy.ReadWrite.All",
    ],
    "retention": [
        "RecordsManagement.ReadWrite.All",
    ],
    "conditional_access": [
        "Policy.ReadWrite.ConditionalAccess",
        "Application.Read.All",
    ],
    "device_compliance": [
        "DeviceManagementConfiguration.ReadWrite.All",
        "DeviceManagementManagedDevices.Read.All",
    ],
}


class GraphClient:
    """
    Microsoft Graph API client for M365 and Purview compliance operations.

    This client provides methods to interact with Microsoft Graph API endpoints
    for managing compliance policies, sensitivity labels, and DLP configurations.
    It supports both delegated and application authentication flows.
    """

    def __init__(self):
        """Initialize the Graph API client."""
        self._http_client: Optional[httpx.AsyncClient] = None
        self._access_token: Optional[str] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                headers={"Content-Type": "application/json"},
            )
        return self._http_client

    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    async def set_access_token(self, token: str) -> None:
        """Set the access token for Graph API authentication."""
        self._access_token = token

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()

    # --- Discovery Methods ---

    def get_available_endpoints(self) -> Dict[str, str]:
        """Get all available Graph API compliance endpoints."""
        return dict(GRAPH_ENDPOINTS)

    def get_required_permissions(self, capability: str) -> List[str]:
        """Get required Graph API permissions for a capability."""
        return REQUIRED_PERMISSIONS.get(capability, [])

    def get_all_required_permissions(self) -> List[str]:
        """Get all required permissions across all capabilities."""
        all_perms: set[str] = set()
        for perms in REQUIRED_PERMISSIONS.values():
            all_perms.update(perms)
        return sorted(all_perms)

    # --- DLP Policy Operations ---

    async def list_dlp_policies(self) -> List[Dict[str, Any]]:
        """
        List existing DLP policies from Microsoft Graph.

        Returns:
            List of DLP policy objects from Graph API.
            Returns empty list if not authenticated or request fails.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{GRAPH_API_BETA}{GRAPH_ENDPOINTS['dlp_policies']}",
                headers=self._get_headers(),
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("value", [])
            logger.warning(f"Graph API DLP list returned {response.status_code}")
            return []
        except Exception as e:
            logger.warning(f"Failed to list DLP policies from Graph API: {e}")
            return []

    # --- Sensitivity Label Operations ---

    async def list_sensitivity_labels(self) -> List[Dict[str, Any]]:
        """
        List existing sensitivity labels from Microsoft Graph.

        Returns:
            List of sensitivity label objects from Graph API.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{GRAPH_API_BETA}{GRAPH_ENDPOINTS['sensitivity_labels']}",
                headers=self._get_headers(),
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("value", [])
            logger.warning(f"Graph API sensitivity labels returned {response.status_code}")
            return []
        except Exception as e:
            logger.warning(f"Failed to list sensitivity labels from Graph API: {e}")
            return []

    # --- Conditional Access Operations ---

    async def list_conditional_access_policies(self) -> List[Dict[str, Any]]:
        """
        List existing Conditional Access policies from Microsoft Graph.

        Returns:
            List of Conditional Access policy objects from Graph API.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{GRAPH_API_BASE}{GRAPH_ENDPOINTS['conditional_access']}",
                headers=self._get_headers(),
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("value", [])
            logger.warning(f"Graph API conditional access returned {response.status_code}")
            return []
        except Exception as e:
            logger.warning(f"Failed to list conditional access policies from Graph API: {e}")
            return []

    # --- Device Compliance Operations ---

    async def list_device_compliance_policies(self) -> List[Dict[str, Any]]:
        """
        List existing device compliance policies from Microsoft Graph.

        Returns:
            List of device compliance policy objects from Graph API.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{GRAPH_API_BASE}{GRAPH_ENDPOINTS['device_compliance']}",
                headers=self._get_headers(),
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("value", [])
            logger.warning(f"Graph API device compliance returned {response.status_code}")
            return []
        except Exception as e:
            logger.warning(f"Failed to list device compliance policies from Graph API: {e}")
            return []

    # --- Deployment Script Generation ---

    def generate_graph_deployment_script(
        self,
        policies: List[Dict[str, Any]],
        policy_type: str,
    ) -> str:
        """
        Generate a PowerShell deployment script for Microsoft Graph API.

        Args:
            policies: List of policy definitions to deploy.
            policy_type: Type of policy (dlp, sensitivity_label, etc.).

        Returns:
            PowerShell script content as string.
        """
        endpoint = GRAPH_ENDPOINTS.get(
            f"{policy_type}_policies",
            GRAPH_ENDPOINTS.get(policy_type, "/unknown"),
        )

        lines = [
            "# Microsoft Graph API Compliance Policy Deployment Script",
            "# Generated by ComplianceIQ",
            f"# Policy Type: {policy_type}",
            f"# Total Policies: {len(policies)}",
            "",
            "# Prerequisites:",
            "#   Install-Module Microsoft.Graph -Scope CurrentUser",
            "#   Connect-MgGraph -Scopes 'Policy.ReadWrite.All'",
            "",
            "# Connect to Microsoft Graph",
            "$requiredScopes = @(",
        ]

        perms = self.get_required_permissions(policy_type)
        for perm in perms:
            lines.append(f'    "{perm}",')
        lines.append(")")
        lines.append("Connect-MgGraph -Scopes $requiredScopes")
        lines.append("")
        lines.append(f'Write-Host "Deploying {len(policies)} {policy_type} policies..."')
        lines.append("")

        for i, policy in enumerate(policies, 1):
            name = policy.get("name", f"policy-{i}")
            lines.append(f"# Policy {i}: {name}")
            lines.append(f"$policy{i} = @{{")
            for key, value in policy.items():
                if isinstance(value, str):
                    lines.append(f'    "{key}" = "{value}"')
                elif isinstance(value, bool):
                    lines.append(f'    "{key}" = ${str(value).lower()}')
                elif isinstance(value, (int, float)):
                    lines.append(f'    "{key}" = {value}')
            lines.append("}")
            lines.append(
                f"Invoke-MgGraphRequest -Method POST "
                f"-Uri 'https://graph.microsoft.com/beta{endpoint}' "
                f"-Body ($policy{i} | ConvertTo-Json -Depth 10)"
            )
            lines.append(f'Write-Host "  ✓ Created: {name}"')
            lines.append("")

        lines.append(f'Write-Host "✅ All {len(policies)} {policy_type} policies deployed."')
        lines.append("Disconnect-MgGraph")

        return "\n".join(lines)


@lru_cache
def get_graph_client() -> GraphClient:
    """Get cached Graph API client instance."""
    return GraphClient()
