"""
Microsoft Purview Configuration Service.
Maps compliance controls to Microsoft Purview configurations including
sensitivity labels, DLP policies, retention labels, and data governance settings.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.models.control import ExternalControl
from app.models.purview import (
    PurviewConfigType,
    SensitivityLabelScope,
    SensitivityLabel,
    SensitivityLabelAction,
    RetentionLabel,
    PurviewDLPPolicy,
    PurviewControlMapping,
    PurviewConfigPackage,
    PurviewGenerationRequest,
)
from app.services.graph_client import get_graph_client

logger = logging.getLogger(__name__)

# Domain-to-Purview configuration type mapping
DOMAIN_TO_PURVIEW_CONFIG: Dict[str, List[PurviewConfigType]] = {
    "data protection": [PurviewConfigType.SENSITIVITY_LABEL, PurviewConfigType.DLP_POLICY],
    "data security": [PurviewConfigType.SENSITIVITY_LABEL, PurviewConfigType.DLP_POLICY],
    "data classification": [PurviewConfigType.SENSITIVITY_LABEL],
    "data retention": [PurviewConfigType.RETENTION_LABEL, PurviewConfigType.RETENTION_POLICY],
    "records management": [PurviewConfigType.RECORDS_MANAGEMENT, PurviewConfigType.RETENTION_LABEL],
    "information protection": [PurviewConfigType.SENSITIVITY_LABEL, PurviewConfigType.DLP_POLICY],
    "privacy": [PurviewConfigType.SENSITIVITY_LABEL, PurviewConfigType.DLP_POLICY],
    "ediscovery": [PurviewConfigType.EDISCOVERY],
    "legal hold": [PurviewConfigType.EDISCOVERY],
    "insider threat": [PurviewConfigType.INFORMATION_BARRIER],
    "communication": [PurviewConfigType.INFORMATION_BARRIER],
    "governance": [PurviewConfigType.RETENTION_POLICY, PurviewConfigType.SENSITIVITY_LABEL],
    "risk management": [PurviewConfigType.DLP_POLICY, PurviewConfigType.SENSITIVITY_LABEL],
    "identity": [PurviewConfigType.DLP_POLICY],
    "network security": [PurviewConfigType.DLP_POLICY],
    "logging": [PurviewConfigType.RETENTION_POLICY],
    "monitoring": [PurviewConfigType.DLP_POLICY],
    "vulnerability management": [PurviewConfigType.DLP_POLICY],
    "asset management": [PurviewConfigType.SENSITIVITY_LABEL],
}

# Default sensitivity label hierarchy
DEFAULT_SENSITIVITY_LABELS: List[Dict[str, Any]] = [
    {
        "name": "public",
        "display_name": "Public",
        "description": "Data approved for public access",
        "color": "#00AA00",
        "priority": 0,
        "actions": [],
    },
    {
        "name": "general",
        "display_name": "General",
        "description": "Business data not intended for public consumption",
        "color": "#0078D4",
        "priority": 1,
        "actions": [],
    },
    {
        "name": "confidential",
        "display_name": "Confidential",
        "description": "Sensitive business data that could cause damage if shared",
        "color": "#FF8C00",
        "priority": 2,
        "actions": [
            {"action_type": "header", "settings": {"text": "CONFIDENTIAL", "enabled": True}},
            {"action_type": "footer", "settings": {"text": "This document is classified as Confidential", "enabled": True}},
        ],
    },
    {
        "name": "highly-confidential",
        "display_name": "Highly Confidential",
        "description": "Highly sensitive data requiring encryption and access control",
        "color": "#FF0000",
        "priority": 3,
        "actions": [
            {"action_type": "encryption", "settings": {"encryptionEnabled": True}},
            {"action_type": "header", "settings": {"text": "HIGHLY CONFIDENTIAL", "enabled": True}},
            {"action_type": "watermark", "settings": {"text": "HIGHLY CONFIDENTIAL", "enabled": True}},
        ],
    },
]

# Default retention label templates
DEFAULT_RETENTION_LABELS: List[Dict[str, Any]] = [
    {
        "name": "retain-1y",
        "display_name": "Retain 1 Year",
        "description": "Retain content for 1 year then delete",
        "retention_days": 365,
        "retention_action": "keepAndDelete",
    },
    {
        "name": "retain-3y",
        "display_name": "Retain 3 Years",
        "description": "Retain content for 3 years then delete",
        "retention_days": 1095,
        "retention_action": "keepAndDelete",
    },
    {
        "name": "retain-7y-regulatory",
        "display_name": "Regulatory Records - 7 Years",
        "description": "Retain regulatory records for 7 years",
        "retention_days": 2555,
        "retention_action": "keepAndDelete",
        "is_record": True,
    },
    {
        "name": "retain-10y-financial",
        "display_name": "Financial Records - 10 Years",
        "description": "Retain financial records for 10 years per regulatory requirements",
        "retention_days": 3650,
        "retention_action": "keepAndDelete",
        "is_record": True,
        "regulatory_record": True,
    },
]

# DLP policy templates for Purview
PURVIEW_DLP_TEMPLATES: List[Dict[str, Any]] = [
    {
        "name": "purview-dlp-pii",
        "display_name": "PII Protection (Purview)",
        "description": "Detect and protect personally identifiable information across all M365 locations",
        "locations": ["Exchange", "SharePoint", "OneDrive", "Teams", "Endpoints"],
        "sensitive_info_types": [
            {"name": "Credit Card Number", "id": "50842eb7-edc8-4019-85dd-5a5c1f2bb085"},
            {"name": "Social Security Number", "id": "a44669fe-0d48-453d-a9b1-2cc83f2cba77"},
        ],
    },
    {
        "name": "purview-dlp-financial",
        "display_name": "Financial Data Protection (Purview)",
        "description": "Detect and protect financial data per regulatory requirements",
        "locations": ["Exchange", "SharePoint", "OneDrive"],
        "sensitive_info_types": [
            {"name": "Credit Card Number", "id": "50842eb7-edc8-4019-85dd-5a5c1f2bb085"},
            {"name": "International Banking Account Number", "id": "2c91b460-f3b7-4f4b-8e2c-0f18d7d4e577"},
        ],
    },
    {
        "name": "purview-dlp-health",
        "display_name": "Health Data Protection (Purview)",
        "description": "Detect and protect health information",
        "locations": ["Exchange", "SharePoint", "OneDrive", "Teams"],
        "sensitive_info_types": [
            {"name": "Health Insurance Claim Number", "id": ""},
        ],
    },
]


class PurviewConfigService:
    """Service for generating Microsoft Purview configurations from control mappings."""

    def map_control_to_purview(
        self,
        control: ExternalControl,
        config_types: Optional[List[PurviewConfigType]] = None,
    ) -> PurviewControlMapping:
        """
        Map a single compliance control to Purview configurations.

        Args:
            control: External compliance control
            config_types: Optional filter for specific Purview config types

        Returns:
            PurviewControlMapping with recommended configurations
        """
        domain = (control.domain or "").lower()
        description = (control.description or "").lower()

        # Determine relevant Purview config type based on domain and description
        matched_types: List[PurviewConfigType] = []
        for domain_key, types in DOMAIN_TO_PURVIEW_CONFIG.items():
            if domain_key in domain or domain_key in description:
                matched_types.extend(types)

        # Deduplicate while preserving order
        matched_types = list(dict.fromkeys(matched_types))

        # Apply filter if specified
        if config_types:
            matched_types = [t for t in matched_types if t in config_types]

        # Default to sensitivity label if no match
        if not matched_types:
            matched_types = [PurviewConfigType.SENSITIVITY_LABEL]

        primary_type = matched_types[0]

        # Build recommendations based on type
        sensitivity_labels: List[str] = []
        retention_labels: List[str] = []
        dlp_policies: List[str] = []

        if PurviewConfigType.SENSITIVITY_LABEL in matched_types:
            # Only recommend Confidential and above (skip Public and General)
            sensitivity_labels = [l["display_name"] for l in DEFAULT_SENSITIVITY_LABELS[2:]]

        if PurviewConfigType.RETENTION_LABEL in matched_types or PurviewConfigType.RETENTION_POLICY in matched_types:
            retention_labels = [l["display_name"] for l in DEFAULT_RETENTION_LABELS]

        if PurviewConfigType.DLP_POLICY in matched_types:
            dlp_policies = [t["display_name"] for t in PURVIEW_DLP_TEMPLATES]

        # Determine confidence
        confidence = 0.85 if domain else 0.65

        # Build reasoning
        reasoning = self._build_reasoning(control, primary_type, matched_types)

        return PurviewControlMapping(
            external_control_id=control.control_id,
            external_control_name=control.control_name,
            purview_config_type=primary_type,
            sensitivity_labels=sensitivity_labels,
            retention_labels=retention_labels,
            dlp_policies=dlp_policies,
            graph_api_endpoint=self._get_graph_endpoint(primary_type),
            confidence_score=confidence,
            reasoning=reasoning,
            implementation_guide=self._build_implementation_guide(primary_type),
        )

    def generate_purview_package(
        self,
        controls: List[ExternalControl],
        request: PurviewGenerationRequest,
    ) -> PurviewConfigPackage:
        """
        Generate a complete Purview configuration package for a set of controls.

        Args:
            controls: List of compliance controls
            request: Generation request with configuration

        Returns:
            PurviewConfigPackage with labels, policies, and mappings
        """
        logger.info(
            f"Generating Purview config package for {request.framework_name} "
            f"({len(controls)} controls)"
        )

        mappings: List[PurviewControlMapping] = []

        for control in controls:
            mapping = self.map_control_to_purview(
                control, config_types=request.config_types
            )
            mappings.append(mapping)

        # Generate sensitivity labels
        sensitivity_labels = self._generate_sensitivity_labels(request)

        # Generate retention labels
        retention_labels = self._generate_retention_labels(request)

        # Generate DLP policies
        dlp_policies = self._generate_dlp_policies(request)

        # Generate deployment script
        deployment_script = self._generate_deployment_script(
            sensitivity_labels, retention_labels, dlp_policies, request.framework_name
        )

        mapped_count = len([m for m in mappings if m.confidence_score > 0.5])

        package = PurviewConfigPackage(
            framework_name=request.framework_name,
            framework_version=request.framework_version,
            sensitivity_labels=sensitivity_labels,
            retention_labels=retention_labels,
            dlp_policies=dlp_policies,
            mappings=mappings,
            total_controls=len(controls),
            mapped_controls=mapped_count,
            deployment_script=deployment_script,
            generated_at=datetime.now(timezone.utc),
        )

        logger.info(
            f"Generated Purview package: {len(sensitivity_labels)} labels, "
            f"{len(dlp_policies)} DLP policies, "
            f"{mapped_count}/{len(controls)} controls mapped"
        )

        return package

    def export_as_json(self, package: PurviewConfigPackage, pretty: bool = True) -> str:
        """Export Purview config package as JSON."""
        data = package.model_dump(mode="json")
        return json.dumps(data, indent=2 if pretty else None, default=str)

    def _generate_sensitivity_labels(
        self,
        request: PurviewGenerationRequest,
    ) -> List[SensitivityLabel]:
        """Generate sensitivity labels for the framework."""
        if PurviewConfigType.SENSITIVITY_LABEL not in request.config_types:
            return []

        labels: List[SensitivityLabel] = []
        for template in DEFAULT_SENSITIVITY_LABELS:
            actions = [
                SensitivityLabelAction(**a) for a in template.get("actions", [])
            ]
            label = SensitivityLabel(
                name=f"{request.framework_name.lower().replace(' ', '-')}-{template['name']}",
                display_name=f"{request.framework_name} - {template['display_name']}",
                description=template["description"],
                color=template.get("color", ""),
                priority=template.get("priority", 0),
                scope=[SensitivityLabelScope.FILES_EMAILS],
                actions=actions,
            )
            labels.append(label)

        return labels

    def _generate_retention_labels(
        self,
        request: PurviewGenerationRequest,
    ) -> List[RetentionLabel]:
        """Generate retention labels for the framework."""
        if PurviewConfigType.RETENTION_LABEL not in request.config_types:
            return []

        labels: List[RetentionLabel] = []
        for template in DEFAULT_RETENTION_LABELS:
            label = RetentionLabel(
                name=f"{request.framework_name.lower().replace(' ', '-')}-{template['name']}",
                display_name=f"{request.framework_name} - {template['display_name']}",
                description=template["description"],
                retention_days=template["retention_days"],
                retention_action=template["retention_action"],
                is_record=template.get("is_record", False),
                regulatory_record=template.get("regulatory_record", False),
            )
            labels.append(label)

        return labels

    def _generate_dlp_policies(
        self,
        request: PurviewGenerationRequest,
    ) -> List[PurviewDLPPolicy]:
        """Generate DLP policies for the framework."""
        if PurviewConfigType.DLP_POLICY not in request.config_types:
            return []

        policies: List[PurviewDLPPolicy] = []
        for template in PURVIEW_DLP_TEMPLATES:
            policy = PurviewDLPPolicy(
                name=f"{request.framework_name.lower().replace(' ', '-')}-{template['name']}",
                display_name=f"{request.framework_name} - {template['display_name']}",
                description=template["description"],
                locations=template.get("locations", []),
                sensitive_info_types=template.get("sensitive_info_types", []),
                mode=request.enforcement_mode,
            )
            policies.append(policy)

        return policies

    def _generate_deployment_script(
        self,
        sensitivity_labels: List[SensitivityLabel],
        retention_labels: List[RetentionLabel],
        dlp_policies: List[PurviewDLPPolicy],
        framework_name: str,
    ) -> str:
        """Generate PowerShell deployment script for Purview configurations."""
        lines = [
            "# Microsoft Purview Configuration Deployment Script",
            f"# Framework: {framework_name}",
            "# Generated by ComplianceIQ",
            f"# Generated at: {datetime.now(timezone.utc).isoformat()}Z",
            "",
            "# Prerequisites:",
            "#   Install-Module Microsoft.Graph -Scope CurrentUser",
            "#   Install-Module ExchangeOnlineManagement -Scope CurrentUser",
            "",
            "# Connect to Microsoft Graph with required permissions",
            "$scopes = @(",
            '    "InformationProtectionPolicy.ReadWrite.All",',
            '    "RecordsManagement.ReadWrite.All",',
            '    "DlpPolicies.ReadWrite.All"',
            ")",
            "Connect-MgGraph -Scopes $scopes",
            "",
        ]

        # Sensitivity Labels
        if sensitivity_labels:
            lines.append(f"# --- Sensitivity Labels ({len(sensitivity_labels)}) ---")
            lines.append("")
            for label in sensitivity_labels:
                lines.append(f'Write-Host "Creating sensitivity label: {label.display_name}"')
                lines.append(f"$labelBody = @{{")
                lines.append(f'    displayName = "{label.display_name}"')
                lines.append(f'    description = "{label.description}"')
                lines.append(f'    color = "{label.color}"')
                lines.append(f'    priority = {label.priority}')
                lines.append("}")
                lines.append(
                    "Invoke-MgGraphRequest -Method POST "
                    "-Uri 'https://graph.microsoft.com/beta/security/informationProtection/sensitivityLabels' "
                    "-Body ($labelBody | ConvertTo-Json -Depth 10)"
                )
                lines.append(f'Write-Host "  ✓ Created: {label.display_name}"')
                lines.append("")

        # Retention Labels
        if retention_labels:
            lines.append(f"# --- Retention Labels ({len(retention_labels)}) ---")
            lines.append("")
            for label in retention_labels:
                lines.append(f'Write-Host "Creating retention label: {label.display_name}"')
                lines.append(f"$retentionBody = @{{")
                lines.append(f'    displayName = "{label.display_name}"')
                lines.append(f'    description = "{label.description}"')
                lines.append(f'    retentionDuration = @{{ days = {label.retention_days} }}')
                lines.append(f'    retentionAction = "{label.retention_action}"')
                lines.append(f'    isRecord = ${str(label.is_record).lower()}')
                lines.append("}")
                lines.append(
                    "Invoke-MgGraphRequest -Method POST "
                    "-Uri 'https://graph.microsoft.com/beta/security/labels/retentionLabels' "
                    "-Body ($retentionBody | ConvertTo-Json -Depth 10)"
                )
                lines.append(f'Write-Host "  ✓ Created: {label.display_name}"')
                lines.append("")

        # DLP Policies
        if dlp_policies:
            lines.append(f"# --- DLP Policies ({len(dlp_policies)}) ---")
            lines.append("")
            for policy in dlp_policies:
                lines.append(f'Write-Host "Creating DLP policy: {policy.display_name}"')
                lines.append(f"$dlpBody = @{{")
                lines.append(f'    displayName = "{policy.display_name}"')
                lines.append(f'    description = "{policy.description}"')
                lines.append(f'    mode = "{policy.mode}"')
                lines.append("}")
                lines.append(
                    "Invoke-MgGraphRequest -Method POST "
                    "-Uri 'https://graph.microsoft.com/beta/security/dataLossPreventionPolicies' "
                    "-Body ($dlpBody | ConvertTo-Json -Depth 10)"
                )
                lines.append(f'Write-Host "  ✓ Created: {policy.display_name}"')
                lines.append("")

        lines.append(f'Write-Host "✅ {framework_name} Purview configuration deployment complete."')
        lines.append("Disconnect-MgGraph")

        return "\n".join(lines)

    def _get_graph_endpoint(self, config_type: PurviewConfigType) -> str:
        """Get the Microsoft Graph API endpoint for a Purview config type."""
        endpoints = {
            PurviewConfigType.SENSITIVITY_LABEL: "/security/informationProtection/sensitivityLabels",
            PurviewConfigType.DLP_POLICY: "/security/dataLossPreventionPolicies",
            PurviewConfigType.RETENTION_LABEL: "/security/labels/retentionLabels",
            PurviewConfigType.RETENTION_POLICY: "/security/labels/retentionLabels",
            PurviewConfigType.EDISCOVERY: "/security/cases/ediscoveryCases",
            PurviewConfigType.INFORMATION_BARRIER: "/informationProtection/policy/labels",
            PurviewConfigType.RECORDS_MANAGEMENT: "/security/labels/retentionLabels",
        }
        return endpoints.get(config_type, "")

    def _build_reasoning(
        self,
        control: ExternalControl,
        primary_type: PurviewConfigType,
        all_types: List[PurviewConfigType],
    ) -> str:
        """Build a reasoning string for a control mapping."""
        type_names = {
            PurviewConfigType.SENSITIVITY_LABEL: "Sensitivity Labels",
            PurviewConfigType.DLP_POLICY: "DLP Policies",
            PurviewConfigType.RETENTION_LABEL: "Retention Labels",
            PurviewConfigType.RETENTION_POLICY: "Retention Policies",
            PurviewConfigType.EDISCOVERY: "eDiscovery",
            PurviewConfigType.INFORMATION_BARRIER: "Information Barriers",
            PurviewConfigType.RECORDS_MANAGEMENT: "Records Management",
        }

        primary_name = type_names.get(primary_type, str(primary_type))
        reasoning = (
            f"Control '{control.control_name}' in domain "
            f"'{control.domain or 'General'}' maps to Microsoft Purview "
            f"{primary_name} configuration."
        )

        if len(all_types) > 1:
            other_names = [type_names.get(t, str(t)) for t in all_types[1:]]
            reasoning += f" Also relevant to: {', '.join(other_names)}."

        return reasoning

    def _build_implementation_guide(self, config_type: PurviewConfigType) -> str:
        """Build implementation guidance for a Purview config type."""
        guides = {
            PurviewConfigType.SENSITIVITY_LABEL: (
                "1. Navigate to Microsoft Purview compliance portal > Information Protection\n"
                "2. Create sensitivity labels matching your classification taxonomy\n"
                "3. Configure protection settings (encryption, watermarks, headers)\n"
                "4. Create label policies to publish labels to users\n"
                "5. Configure auto-labeling policies for automatic classification\n"
                "6. Deploy via Microsoft Graph API for automation"
            ),
            PurviewConfigType.DLP_POLICY: (
                "1. Navigate to Microsoft Purview > Data Loss Prevention\n"
                "2. Create DLP policies targeting sensitive information types\n"
                "3. Configure policy rules (conditions, actions, notifications)\n"
                "4. Set policy scope across M365 services and endpoints\n"
                "5. Start in Test mode and review DLP reports\n"
                "6. Deploy via Microsoft Graph API for automation"
            ),
            PurviewConfigType.RETENTION_LABEL: (
                "1. Navigate to Microsoft Purview > Data Lifecycle Management\n"
                "2. Create retention labels with appropriate retention periods\n"
                "3. Configure retention actions (keep, delete, keep and delete)\n"
                "4. Mark as records or regulatory records if required\n"
                "5. Create label policies or auto-apply rules\n"
                "6. Deploy via Microsoft Graph API for automation"
            ),
            PurviewConfigType.EDISCOVERY: (
                "1. Navigate to Microsoft Purview > eDiscovery\n"
                "2. Create an eDiscovery case for the investigation\n"
                "3. Add custodians and data sources\n"
                "4. Create holds to preserve relevant content\n"
                "5. Run searches and review results\n"
                "6. Export content for review"
            ),
        }
        return guides.get(
            config_type,
            "Refer to Microsoft Purview documentation for implementation guidance.",
        )


def get_purview_config_service() -> PurviewConfigService:
    """Get Purview configuration service instance."""
    return PurviewConfigService()
