"""
Platform Selection Service.
Provides information about available compliance platforms and manages
platform selection for the compliance mapping workflow.
"""

import logging
from typing import List, Dict

from app.models.platform import (
    CompliancePlatform,
    PlatformCapability,
    PlatformInfo,
    PlatformSelectionRequest,
    PlatformSelectionResponse,
)

logger = logging.getLogger(__name__)

# Platform definitions with capabilities
PLATFORM_REGISTRY: Dict[CompliancePlatform, PlatformInfo] = {
    CompliancePlatform.AZURE_DEFENDER: PlatformInfo(
        platform=CompliancePlatform.AZURE_DEFENDER,
        display_name="Microsoft Defender for Cloud",
        description=(
            "Map compliance controls to Azure Policy definitions and deploy as "
            "policy initiatives in Microsoft Defender for Cloud. Includes Sovereign "
            "Landing Zone (SLZ) support for data residency and sovereignty requirements."
        ),
        icon="🛡️",
        capabilities=[
            PlatformCapability(
                id="azure_policy",
                name="Azure Policy Initiatives",
                description="Generate Azure Policy set definitions with MCSB control mappings",
                api_endpoint="/providers/Microsoft.Authorization/policySetDefinitions",
            ),
            PlatformCapability(
                id="defender_recommendations",
                name="Defender Recommendations",
                description="Map to Microsoft Defender for Cloud security recommendations",
            ),
            PlatformCapability(
                id="slz_policies",
                name="Sovereign Landing Zone Policies",
                description="Generate SLZ-specific policies for data sovereignty (L1-L3)",
            ),
            PlatformCapability(
                id="mcsb_mapping",
                name="MCSB Control Mapping",
                description="Map controls to Microsoft Cloud Security Benchmark",
            ),
        ],
        api_base="https://management.azure.com",
        documentation_url="https://learn.microsoft.com/en-us/azure/defender-for-cloud/",
    ),
    CompliancePlatform.MICROSOFT_365: PlatformInfo(
        platform=CompliancePlatform.MICROSOFT_365,
        display_name="Microsoft 365 Compliance",
        description=(
            "Map compliance controls to Microsoft 365 policies including Data Loss "
            "Prevention (DLP), Conditional Access, Device Compliance (Intune), and "
            "Information Protection policies. Managed via Microsoft Graph API."
        ),
        icon="📧",
        capabilities=[
            PlatformCapability(
                id="dlp",
                name="Data Loss Prevention",
                description="Create and manage DLP policies across Exchange, SharePoint, Teams, OneDrive",
                api_endpoint="/security/dataLossPreventionPolicies",
                requires_license="Microsoft 365 E5 Compliance",
            ),
            PlatformCapability(
                id="conditional_access",
                name="Conditional Access",
                description="Create Conditional Access policies for identity protection",
                api_endpoint="/identity/conditionalAccess/policies",
                requires_license="Microsoft Entra ID P1",
            ),
            PlatformCapability(
                id="device_compliance",
                name="Device Compliance (Intune)",
                description="Create device compliance policies for Windows, iOS, Android",
                api_endpoint="/deviceManagement/deviceCompliancePolicies",
                requires_license="Microsoft Intune Plan 1",
            ),
            PlatformCapability(
                id="information_protection",
                name="Information Protection",
                description="Configure information barriers and sharing policies",
                api_endpoint="/informationProtection/policy/labels",
                requires_license="Microsoft 365 E5",
            ),
        ],
        api_base="https://graph.microsoft.com/v1.0",
        documentation_url="https://learn.microsoft.com/en-us/microsoft-365/compliance/",
    ),
    CompliancePlatform.MICROSOFT_PURVIEW: PlatformInfo(
        platform=CompliancePlatform.MICROSOFT_PURVIEW,
        display_name="Microsoft Purview",
        description=(
            "Map compliance controls to Microsoft Purview data governance configurations "
            "including sensitivity labels, DLP policies, retention labels, eDiscovery, "
            "and records management. Provides unified data security and governance."
        ),
        icon="🔍",
        capabilities=[
            PlatformCapability(
                id="sensitivity_labels",
                name="Sensitivity Labels",
                description="Create sensitivity labels with encryption, watermarks, and auto-labeling",
                api_endpoint="/security/informationProtection/sensitivityLabels",
                requires_license="Microsoft 365 E5 Information Protection",
            ),
            PlatformCapability(
                id="purview_dlp",
                name="Purview DLP Policies",
                description="Create DLP policies with endpoint protection and Copilot integration",
                api_endpoint="/security/dataLossPreventionPolicies",
                requires_license="Microsoft 365 E5 Compliance",
            ),
            PlatformCapability(
                id="retention",
                name="Retention Labels & Policies",
                description="Create retention labels and policies for data lifecycle management",
                api_endpoint="/security/labels/retentionLabels",
                requires_license="Microsoft 365 E5 Compliance",
            ),
            PlatformCapability(
                id="ediscovery",
                name="eDiscovery",
                description="Configure eDiscovery cases, holds, and searches",
                api_endpoint="/security/cases/ediscoveryCases",
                requires_license="Microsoft 365 E5 eDiscovery",
            ),
            PlatformCapability(
                id="records_management",
                name="Records Management",
                description="Configure records management with regulatory record support",
                api_endpoint="/security/labels/retentionLabels",
                requires_license="Microsoft 365 E5 Compliance",
            ),
        ],
        api_base="https://graph.microsoft.com/beta",
        documentation_url="https://learn.microsoft.com/en-us/purview/",
    ),
}


class PlatformService:
    """Service for managing compliance platform selection."""

    def get_all_platforms(self) -> List[PlatformInfo]:
        """Get information about all available compliance platforms."""
        return list(PLATFORM_REGISTRY.values())

    def get_platform_info(self, platform: CompliancePlatform) -> PlatformInfo:
        """Get detailed information about a specific platform."""
        return PLATFORM_REGISTRY[platform]

    def select_platform(
        self,
        request: PlatformSelectionRequest,
    ) -> PlatformSelectionResponse:
        """
        Process a platform selection request.

        Args:
            request: Platform selection request with optional capability filters

        Returns:
            PlatformSelectionResponse with platform details and next steps
        """
        platform_info = PLATFORM_REGISTRY[request.platform]

        # Filter capabilities if specified
        if request.capabilities:
            selected_caps = [
                cap for cap in platform_info.capabilities
                if cap.id in request.capabilities
            ]
        else:
            selected_caps = list(platform_info.capabilities)

        # Build next steps based on platform
        next_steps = self._get_next_steps(request.platform)

        return PlatformSelectionResponse(
            platform=request.platform,
            platform_info=platform_info,
            selected_capabilities=selected_caps,
            next_steps=next_steps,
        )

    def _get_next_steps(self, platform: CompliancePlatform) -> List[str]:
        """Get recommended next steps for a platform."""
        common_steps = [
            "Upload your compliance framework controls (CSV or Excel)",
            "Run AI-powered control mapping",
            "Review and adjust the generated mappings",
        ]

        platform_steps = {
            CompliancePlatform.AZURE_DEFENDER: [
                *common_steps,
                "Generate Azure Policy initiative (JSON, Bicep, deployment scripts)",
                "Deploy initiative to Azure subscription via CLI or Portal",
                "Monitor compliance in Microsoft Defender for Cloud dashboard",
            ],
            CompliancePlatform.MICROSOFT_365: [
                *common_steps,
                "Generate Microsoft 365 compliance policies (DLP, Conditional Access)",
                "Deploy policies via Microsoft Graph API or PowerShell",
                "Monitor compliance in Microsoft 365 compliance center",
            ],
            CompliancePlatform.MICROSOFT_PURVIEW: [
                *common_steps,
                "Generate Purview configurations (sensitivity labels, DLP, retention)",
                "Deploy configurations via Microsoft Graph API or PowerShell",
                "Monitor data governance in Microsoft Purview compliance portal",
            ],
        }

        return platform_steps.get(platform, common_steps)


def get_platform_service() -> PlatformService:
    """Get platform service instance."""
    return PlatformService()
