"""
Microsoft 365 Policy Generation Service.
Maps compliance controls to Microsoft 365 policies (DLP, Conditional Access,
Device Compliance, Information Protection) and generates deployable configurations.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.models.control import ExternalControl
from app.models.m365_policy import (
    M365PolicyType,
    M365ServiceScope,
    M365PolicyRule,
    M365PolicyDefinition,
    M365ControlMapping,
    M365PolicyPackage,
    M365GenerationRequest,
)
from app.services.graph_client import get_graph_client

logger = logging.getLogger(__name__)

# Domain-to-M365 policy type mapping
# Maps compliance control domains to relevant Microsoft 365 policy types
DOMAIN_TO_M365_POLICY: Dict[str, List[M365PolicyType]] = {
    "identity": [M365PolicyType.CONDITIONAL_ACCESS],
    "access control": [M365PolicyType.CONDITIONAL_ACCESS],
    "identity & access": [M365PolicyType.CONDITIONAL_ACCESS],
    "identity & access control": [M365PolicyType.CONDITIONAL_ACCESS],
    "identity management": [M365PolicyType.CONDITIONAL_ACCESS],
    "data protection": [M365PolicyType.DLP, M365PolicyType.INFORMATION_PROTECTION],
    "data security": [M365PolicyType.DLP, M365PolicyType.INFORMATION_PROTECTION],
    "data classification": [M365PolicyType.DLP, M365PolicyType.INFORMATION_PROTECTION],
    "network security": [M365PolicyType.CONDITIONAL_ACCESS],
    "endpoint security": [M365PolicyType.DEVICE_COMPLIANCE],
    "device management": [M365PolicyType.DEVICE_COMPLIANCE],
    "asset management": [M365PolicyType.DEVICE_COMPLIANCE],
    "communication": [M365PolicyType.COMMUNICATION_COMPLIANCE],
    "insider threat": [M365PolicyType.INSIDER_RISK],
    "logging": [M365PolicyType.DLP],
    "monitoring": [M365PolicyType.DLP],
    "vulnerability management": [M365PolicyType.DEVICE_COMPLIANCE],
    "governance": [M365PolicyType.DLP, M365PolicyType.CONDITIONAL_ACCESS],
    "risk management": [M365PolicyType.DLP, M365PolicyType.INSIDER_RISK],
}

# M365 policy templates for each policy type
M365_POLICY_TEMPLATES: Dict[M365PolicyType, List[Dict[str, Any]]] = {
    M365PolicyType.DLP: [
        {
            "name": "dlp-pii-protection",
            "display_name": "PII Data Loss Prevention",
            "description": "Prevents sharing of personally identifiable information outside the organization",
            "service_scopes": ["exchange", "sharepoint", "onedrive", "teams"],
            "sensitive_info_types": [
                "Credit Card Number", "Social Security Number",
                "National ID", "Passport Number",
            ],
        },
        {
            "name": "dlp-financial-data",
            "display_name": "Financial Data Protection",
            "description": "Protects financial information from unauthorized sharing",
            "service_scopes": ["exchange", "sharepoint", "onedrive"],
            "sensitive_info_types": [
                "Credit Card Number", "Bank Account Number",
                "SWIFT Code", "IBAN",
            ],
        },
        {
            "name": "dlp-health-data",
            "display_name": "Health Data Protection",
            "description": "Protects health information per HIPAA and regional requirements",
            "service_scopes": ["exchange", "sharepoint", "onedrive", "teams"],
            "sensitive_info_types": [
                "Health Insurance Claim Number", "Medical Record Number",
            ],
        },
    ],
    M365PolicyType.CONDITIONAL_ACCESS: [
        {
            "name": "ca-require-mfa-admins",
            "display_name": "Require MFA for Administrators",
            "description": "Enforce multi-factor authentication for all admin roles",
            "conditions": {
                "userRiskLevels": [],
                "signInRiskLevels": [],
                "includeRoles": ["Global Administrator", "Security Administrator"],
            },
            "grant_controls": {"builtInControls": ["mfa"]},
        },
        {
            "name": "ca-require-mfa-all-users",
            "display_name": "Require MFA for All Users",
            "description": "Enforce multi-factor authentication for all users",
            "conditions": {"includeUsers": ["All"]},
            "grant_controls": {"builtInControls": ["mfa"]},
        },
        {
            "name": "ca-block-legacy-auth",
            "display_name": "Block Legacy Authentication",
            "description": "Block legacy authentication protocols",
            "conditions": {"clientAppTypes": ["exchangeActiveSync", "other"]},
            "grant_controls": {"builtInControls": ["block"]},
        },
        {
            "name": "ca-require-compliant-device",
            "display_name": "Require Compliant Device",
            "description": "Require device compliance for access",
            "conditions": {"includeUsers": ["All"]},
            "grant_controls": {"builtInControls": ["compliantDevice"]},
        },
    ],
    M365PolicyType.DEVICE_COMPLIANCE: [
        {
            "name": "dc-windows-baseline",
            "display_name": "Windows Device Compliance Baseline",
            "description": "Baseline compliance policy for Windows devices",
            "settings": {
                "osMinimumVersion": "10.0.19041",
                "bitLockerEnabled": True,
                "passwordRequired": True,
                "secureBootEnabled": True,
                "antivirusRequired": True,
            },
        },
        {
            "name": "dc-mobile-baseline",
            "display_name": "Mobile Device Compliance Baseline",
            "description": "Baseline compliance policy for iOS and Android devices",
            "settings": {
                "passwordRequired": True,
                "passwordMinLength": 8,
                "storageEncryption": True,
                "jailbrokenDevicesBlocked": True,
            },
        },
    ],
    M365PolicyType.INFORMATION_PROTECTION: [
        {
            "name": "ip-external-sharing-restriction",
            "display_name": "External Sharing Restriction",
            "description": "Restrict external sharing of sensitive content",
            "settings": {
                "blockExternalSharing": True,
                "requireApproval": True,
            },
        },
    ],
}

# Microsoft Graph API endpoints per policy type
GRAPH_API_ENDPOINTS: Dict[M365PolicyType, str] = {
    M365PolicyType.DLP: "/security/dataLossPreventionPolicies",
    M365PolicyType.CONDITIONAL_ACCESS: "/identity/conditionalAccess/policies",
    M365PolicyType.DEVICE_COMPLIANCE: "/deviceManagement/deviceCompliancePolicies",
    M365PolicyType.INFORMATION_PROTECTION: "/informationProtection/policy/labels",
    M365PolicyType.COMMUNICATION_COMPLIANCE: "/security/cases/ediscoveryCases",
    M365PolicyType.INSIDER_RISK: "/security/cases/ediscoveryCases",
}


class M365PolicyService:
    """Service for generating Microsoft 365 compliance policies from control mappings."""

    def map_control_to_m365(
        self,
        control: ExternalControl,
        policy_types: Optional[List[M365PolicyType]] = None,
    ) -> M365ControlMapping:
        """
        Map a single compliance control to Microsoft 365 policies.

        Args:
            control: External compliance control
            policy_types: Optional filter for specific M365 policy types

        Returns:
            M365ControlMapping with recommended policies
        """
        domain = (control.domain or "").lower()
        description = (control.description or "").lower()

        # Determine relevant M365 policy type based on domain
        matched_types: List[M365PolicyType] = []
        for domain_key, types in DOMAIN_TO_M365_POLICY.items():
            if domain_key in domain or domain_key in description:
                matched_types.extend(types)

        # Deduplicate
        matched_types = list(dict.fromkeys(matched_types))

        # Apply filter if specified
        if policy_types:
            matched_types = [t for t in matched_types if t in policy_types]

        # Default to DLP if no match
        if not matched_types:
            matched_types = [M365PolicyType.DLP]

        primary_type = matched_types[0]

        # Find relevant policy templates
        recommended_policies: List[str] = []
        templates = M365_POLICY_TEMPLATES.get(primary_type, [])
        for template in templates:
            recommended_policies.append(template["display_name"])

        # Determine confidence based on match quality
        confidence = 0.85 if domain else 0.65

        # Build reasoning
        reasoning = self._build_reasoning(control, primary_type, matched_types)

        return M365ControlMapping(
            external_control_id=control.control_id,
            external_control_name=control.control_name,
            m365_policy_type=primary_type,
            m365_policies=recommended_policies,
            graph_api_endpoint=GRAPH_API_ENDPOINTS.get(primary_type, ""),
            confidence_score=confidence,
            reasoning=reasoning,
            implementation_guide=self._build_implementation_guide(primary_type),
        )

    def generate_m365_package(
        self,
        controls: List[ExternalControl],
        request: M365GenerationRequest,
    ) -> M365PolicyPackage:
        """
        Generate a complete Microsoft 365 policy package for a set of controls.

        Args:
            controls: List of compliance controls
            request: Generation request with configuration

        Returns:
            M365PolicyPackage with policies and mappings
        """
        logger.info(
            f"Generating M365 policy package for {request.framework_name} "
            f"({len(controls)} controls)"
        )

        mappings: List[M365ControlMapping] = []
        policies: List[M365PolicyDefinition] = []
        policy_names_seen: set[str] = set()

        for control in controls:
            mapping = self.map_control_to_m365(
                control, policy_types=request.policy_types
            )
            mappings.append(mapping)

            # Generate policies from templates for the mapped type
            templates = M365_POLICY_TEMPLATES.get(mapping.m365_policy_type, [])
            for template in templates:
                if template["name"] not in policy_names_seen:
                    policy_names_seen.add(template["name"])

                    scopes = [
                        M365ServiceScope(s) for s in template.get("service_scopes", ["all"])
                        if s in [e.value for e in M365ServiceScope]
                    ] or [M365ServiceScope.ALL]

                    policy = M365PolicyDefinition(
                        name=template["name"],
                        display_name=template["display_name"],
                        description=template.get("description", ""),
                        policy_type=mapping.m365_policy_type,
                        service_scopes=scopes,
                        mode=request.enforcement_mode,
                    )
                    policies.append(policy)

        # Generate deployment script
        graph_client = get_graph_client()
        policy_dicts = [p.model_dump() for p in policies]
        deployment_script = graph_client.generate_graph_deployment_script(
            policy_dicts, "dlp"
        )

        mapped_count = len([m for m in mappings if m.confidence_score > 0.5])

        package = M365PolicyPackage(
            framework_name=request.framework_name,
            framework_version=request.framework_version,
            policies=policies,
            mappings=mappings,
            total_controls=len(controls),
            mapped_controls=mapped_count,
            deployment_script=deployment_script,
            generated_at=datetime.utcnow(),
        )

        logger.info(
            f"Generated M365 package: {len(policies)} policies, "
            f"{mapped_count}/{len(controls)} controls mapped"
        )

        return package

    def export_as_json(self, package: M365PolicyPackage, pretty: bool = True) -> str:
        """Export M365 policy package as JSON."""
        data = package.model_dump(mode="json")
        return json.dumps(data, indent=2 if pretty else None, default=str)

    def _build_reasoning(
        self,
        control: ExternalControl,
        primary_type: M365PolicyType,
        all_types: List[M365PolicyType],
    ) -> str:
        """Build a reasoning string for a control mapping."""
        type_names = {
            M365PolicyType.DLP: "Data Loss Prevention",
            M365PolicyType.CONDITIONAL_ACCESS: "Conditional Access",
            M365PolicyType.DEVICE_COMPLIANCE: "Device Compliance",
            M365PolicyType.INFORMATION_PROTECTION: "Information Protection",
            M365PolicyType.COMMUNICATION_COMPLIANCE: "Communication Compliance",
            M365PolicyType.INSIDER_RISK: "Insider Risk Management",
        }

        primary_name = type_names.get(primary_type, str(primary_type))
        reasoning = (
            f"Control '{control.control_name}' in domain "
            f"'{control.domain or 'General'}' maps to Microsoft 365 "
            f"{primary_name} policy."
        )

        if len(all_types) > 1:
            other_names = [type_names.get(t, str(t)) for t in all_types[1:]]
            reasoning += f" Also relevant to: {', '.join(other_names)}."

        return reasoning

    def _build_implementation_guide(self, policy_type: M365PolicyType) -> str:
        """Build implementation guidance for a policy type."""
        guides = {
            M365PolicyType.DLP: (
                "1. Navigate to Microsoft Purview compliance portal > Data Loss Prevention\n"
                "2. Create a new DLP policy or deploy via Microsoft Graph API\n"
                "3. Select the sensitive information types to monitor\n"
                "4. Configure policy rules (block, notify, override)\n"
                "5. Set policy scope (Exchange, SharePoint, OneDrive, Teams)\n"
                "6. Start in Test mode before enabling enforcement"
            ),
            M365PolicyType.CONDITIONAL_ACCESS: (
                "1. Navigate to Microsoft Entra admin center > Conditional Access\n"
                "2. Create a new policy or deploy via Microsoft Graph API\n"
                "3. Configure users/groups and cloud apps\n"
                "4. Set conditions (sign-in risk, device, location)\n"
                "5. Configure grant/session controls (MFA, compliant device)\n"
                "6. Enable in Report-only mode first"
            ),
            M365PolicyType.DEVICE_COMPLIANCE: (
                "1. Navigate to Microsoft Intune admin center > Device compliance\n"
                "2. Create a new compliance policy or deploy via Graph API\n"
                "3. Select platform (Windows, iOS, Android)\n"
                "4. Configure compliance settings (encryption, password, OS version)\n"
                "5. Set non-compliance actions (notify, block access)\n"
                "6. Assign to user/device groups"
            ),
            M365PolicyType.INFORMATION_PROTECTION: (
                "1. Navigate to Microsoft Purview > Information Protection\n"
                "2. Configure sensitivity labels and auto-labeling rules\n"
                "3. Create information barrier policies if needed\n"
                "4. Deploy via Microsoft Graph API for automation\n"
                "5. Monitor label adoption via Activity Explorer"
            ),
        }
        return guides.get(
            policy_type,
            "Refer to Microsoft 365 documentation for implementation guidance.",
        )


def get_m365_policy_service() -> M365PolicyService:
    """Get M365 policy service instance."""
    return M365PolicyService()
