"""
Unit tests for platform selection, Microsoft 365 policy, and Purview configuration
services and models.
"""

import pytest
from app.models.platform import (
    CompliancePlatform,
    PlatformCapability,
    PlatformInfo,
    PlatformSelectionRequest,
    PlatformSelectionResponse,
)
from app.models.m365_policy import (
    M365PolicyType,
    M365ServiceScope,
    M365PolicyRule,
    M365PolicyDefinition,
    M365ControlMapping,
    M365PolicyPackage,
    M365GenerationRequest,
)
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
from app.models.control import ExternalControl
from app.services.platform_service import PlatformService, get_platform_service
from app.services.m365_policy_service import M365PolicyService, get_m365_policy_service
from app.services.purview_service import PurviewConfigService, get_purview_config_service
from app.services.graph_client import GraphClient, get_graph_client


# --- Platform Model Tests ---

class TestPlatformModels:
    """Tests for platform selection models."""

    def test_compliance_platform_enum_values(self):
        """Verify all compliance platform enum values exist."""
        assert CompliancePlatform.AZURE_DEFENDER == "azure_defender"
        assert CompliancePlatform.MICROSOFT_365 == "microsoft_365"
        assert CompliancePlatform.MICROSOFT_PURVIEW == "microsoft_purview"

    def test_platform_capability_creation(self):
        """Test PlatformCapability model creation."""
        cap = PlatformCapability(
            id="dlp",
            name="Data Loss Prevention",
            description="Create and manage DLP policies",
            api_endpoint="/security/dataLossPreventionPolicies",
            requires_license="Microsoft 365 E5",
        )
        assert cap.id == "dlp"
        assert cap.name == "Data Loss Prevention"
        assert cap.requires_license == "Microsoft 365 E5"

    def test_platform_info_creation(self):
        """Test PlatformInfo model creation."""
        info = PlatformInfo(
            platform=CompliancePlatform.MICROSOFT_365,
            display_name="Microsoft 365",
            description="M365 compliance",
            icon="📧",
            capabilities=[],
        )
        assert info.platform == CompliancePlatform.MICROSOFT_365
        assert info.icon == "📧"

    def test_platform_selection_request(self):
        """Test PlatformSelectionRequest model."""
        req = PlatformSelectionRequest(
            platform=CompliancePlatform.MICROSOFT_PURVIEW,
            capabilities=["sensitivity_labels", "dlp"],
        )
        assert req.platform == CompliancePlatform.MICROSOFT_PURVIEW
        assert len(req.capabilities) == 2

    def test_platform_selection_response(self):
        """Test PlatformSelectionResponse model."""
        resp = PlatformSelectionResponse(
            platform=CompliancePlatform.AZURE_DEFENDER,
            platform_info=PlatformInfo(
                platform=CompliancePlatform.AZURE_DEFENDER,
                display_name="Defender",
                description="Azure Defender",
            ),
            selected_capabilities=[],
            next_steps=["Upload controls", "Run mapping"],
        )
        assert resp.platform == CompliancePlatform.AZURE_DEFENDER
        assert len(resp.next_steps) == 2


# --- M365 Model Tests ---

class TestM365Models:
    """Tests for Microsoft 365 policy models."""

    def test_m365_policy_type_enum(self):
        """Verify M365 policy type enum values."""
        assert M365PolicyType.DLP == "dlp"
        assert M365PolicyType.CONDITIONAL_ACCESS == "conditional_access"
        assert M365PolicyType.DEVICE_COMPLIANCE == "device_compliance"

    def test_m365_policy_rule_creation(self):
        """Test M365PolicyRule model."""
        rule = M365PolicyRule(
            name="Block PII sharing",
            description="Prevent external PII sharing",
            conditions={"sensitiveInfoTypes": ["credit_card"]},
            actions={"blockAccess": True},
            priority=0,
        )
        assert rule.name == "Block PII sharing"
        assert rule.conditions["sensitiveInfoTypes"] == ["credit_card"]

    def test_m365_policy_definition_creation(self):
        """Test M365PolicyDefinition model."""
        policy = M365PolicyDefinition(
            name="test-dlp",
            display_name="Test DLP Policy",
            policy_type=M365PolicyType.DLP,
            service_scopes=[M365ServiceScope.EXCHANGE, M365ServiceScope.TEAMS],
            mode="TestWithNotifications",
        )
        assert policy.name == "test-dlp"
        assert M365ServiceScope.EXCHANGE in policy.service_scopes

    def test_m365_control_mapping(self):
        """Test M365ControlMapping model."""
        mapping = M365ControlMapping(
            external_control_id="SAMA-DP-01",
            external_control_name="Data Classification",
            m365_policy_type=M365PolicyType.DLP,
            m365_policies=["PII Protection"],
            confidence_score=0.88,
            reasoning="Data classification maps to DLP",
        )
        assert mapping.confidence_score == 0.88
        assert mapping.m365_policy_type == M365PolicyType.DLP

    def test_m365_generation_request(self):
        """Test M365GenerationRequest model."""
        req = M365GenerationRequest(
            framework_name="SAMA",
            policy_types=[M365PolicyType.DLP, M365PolicyType.CONDITIONAL_ACCESS],
            enforcement_mode="TestWithNotifications",
        )
        assert req.framework_name == "SAMA"
        assert len(req.policy_types) == 2


# --- Purview Model Tests ---

class TestPurviewModels:
    """Tests for Microsoft Purview configuration models."""

    def test_purview_config_type_enum(self):
        """Verify Purview config type enum values."""
        assert PurviewConfigType.SENSITIVITY_LABEL == "sensitivity_label"
        assert PurviewConfigType.DLP_POLICY == "dlp_policy"
        assert PurviewConfigType.RETENTION_LABEL == "retention_label"

    def test_sensitivity_label_creation(self):
        """Test SensitivityLabel model."""
        label = SensitivityLabel(
            name="confidential",
            display_name="Confidential",
            description="Sensitive business data",
            color="#FF8C00",
            priority=2,
            scope=[SensitivityLabelScope.FILES_EMAILS],
            actions=[
                SensitivityLabelAction(
                    action_type="encryption",
                    settings={"encryptionEnabled": True},
                )
            ],
        )
        assert label.name == "confidential"
        assert label.priority == 2
        assert len(label.actions) == 1

    def test_retention_label_creation(self):
        """Test RetentionLabel model."""
        label = RetentionLabel(
            name="retain-7y",
            display_name="Retain 7 Years",
            retention_days=2555,
            retention_action="keepAndDelete",
            is_record=True,
        )
        assert label.retention_days == 2555
        assert label.is_record is True

    def test_purview_dlp_policy_creation(self):
        """Test PurviewDLPPolicy model."""
        policy = PurviewDLPPolicy(
            name="purview-dlp-pii",
            display_name="PII Protection",
            locations=["Exchange", "SharePoint"],
            mode="TestWithNotifications",
        )
        assert len(policy.locations) == 2
        assert policy.mode == "TestWithNotifications"

    def test_purview_control_mapping(self):
        """Test PurviewControlMapping model."""
        mapping = PurviewControlMapping(
            external_control_id="SAMA-DP-02",
            external_control_name="Data Retention",
            purview_config_type=PurviewConfigType.RETENTION_LABEL,
            retention_labels=["Financial Records - 7 Years"],
            confidence_score=0.90,
        )
        assert mapping.purview_config_type == PurviewConfigType.RETENTION_LABEL
        assert len(mapping.retention_labels) == 1


# --- Platform Service Tests ---

class TestPlatformService:
    """Tests for platform selection service."""

    def test_get_all_platforms(self):
        """Test listing all available platforms."""
        service = PlatformService()
        platforms = service.get_all_platforms()
        assert len(platforms) == 3
        platform_ids = [p.platform for p in platforms]
        assert CompliancePlatform.AZURE_DEFENDER in platform_ids
        assert CompliancePlatform.MICROSOFT_365 in platform_ids
        assert CompliancePlatform.MICROSOFT_PURVIEW in platform_ids

    def test_get_platform_info_azure(self):
        """Test getting Azure Defender platform info."""
        service = PlatformService()
        info = service.get_platform_info(CompliancePlatform.AZURE_DEFENDER)
        assert info.display_name == "Microsoft Defender for Cloud"
        assert len(info.capabilities) > 0
        cap_ids = [c.id for c in info.capabilities]
        assert "azure_policy" in cap_ids
        assert "mcsb_mapping" in cap_ids

    def test_get_platform_info_m365(self):
        """Test getting Microsoft 365 platform info."""
        service = PlatformService()
        info = service.get_platform_info(CompliancePlatform.MICROSOFT_365)
        assert info.display_name == "Microsoft 365 Compliance"
        cap_ids = [c.id for c in info.capabilities]
        assert "dlp" in cap_ids
        assert "conditional_access" in cap_ids

    def test_get_platform_info_purview(self):
        """Test getting Microsoft Purview platform info."""
        service = PlatformService()
        info = service.get_platform_info(CompliancePlatform.MICROSOFT_PURVIEW)
        assert info.display_name == "Microsoft Purview"
        cap_ids = [c.id for c in info.capabilities]
        assert "sensitivity_labels" in cap_ids
        assert "retention" in cap_ids

    def test_select_platform_all_capabilities(self):
        """Test platform selection with all capabilities."""
        service = PlatformService()
        req = PlatformSelectionRequest(platform=CompliancePlatform.MICROSOFT_365)
        resp = service.select_platform(req)
        assert resp.platform == CompliancePlatform.MICROSOFT_365
        assert len(resp.selected_capabilities) > 0
        assert len(resp.next_steps) > 0

    def test_select_platform_filtered_capabilities(self):
        """Test platform selection with specific capabilities."""
        service = PlatformService()
        req = PlatformSelectionRequest(
            platform=CompliancePlatform.MICROSOFT_365,
            capabilities=["dlp"],
        )
        resp = service.select_platform(req)
        assert len(resp.selected_capabilities) == 1
        assert resp.selected_capabilities[0].id == "dlp"

    def test_get_platform_service_singleton(self):
        """Test that get_platform_service returns instance."""
        service = get_platform_service()
        assert isinstance(service, PlatformService)


# --- M365 Policy Service Tests ---

class TestM365PolicyService:
    """Tests for Microsoft 365 policy generation service."""

    def _make_control(self, control_id, name, domain, description="Test control"):
        return ExternalControl(
            control_id=control_id,
            control_name=name,
            description=description,
            domain=domain,
        )

    def test_map_identity_control(self):
        """Test mapping identity control to Conditional Access."""
        service = M365PolicyService()
        control = self._make_control(
            "TEST-AC-01", "MFA Requirement",
            "Identity & Access Control",
            "Enforce MFA for all users"
        )
        mapping = service.map_control_to_m365(control)
        assert mapping.m365_policy_type == M365PolicyType.CONDITIONAL_ACCESS
        assert mapping.confidence_score > 0
        assert len(mapping.m365_policies) > 0

    def test_map_data_protection_control(self):
        """Test mapping data protection control to DLP."""
        service = M365PolicyService()
        control = self._make_control(
            "TEST-DP-01", "Data Loss Prevention",
            "Data Protection",
            "Prevent unauthorized data sharing"
        )
        mapping = service.map_control_to_m365(control)
        assert mapping.m365_policy_type == M365PolicyType.DLP
        assert mapping.confidence_score > 0

    def test_map_endpoint_control(self):
        """Test mapping endpoint control to Device Compliance."""
        service = M365PolicyService()
        control = self._make_control(
            "TEST-EP-01", "Endpoint Protection",
            "Endpoint Security",
            "Deploy endpoint protection"
        )
        mapping = service.map_control_to_m365(control)
        assert mapping.m365_policy_type == M365PolicyType.DEVICE_COMPLIANCE

    def test_map_control_with_type_filter(self):
        """Test mapping with policy type filter."""
        service = M365PolicyService()
        control = self._make_control(
            "TEST-01", "General Control",
            "Identity & Access",
            "General security control"
        )
        mapping = service.map_control_to_m365(
            control, policy_types=[M365PolicyType.DLP]
        )
        # With filter, only DLP types should be returned if they matched
        assert mapping.m365_policy_type in [M365PolicyType.DLP, M365PolicyType.CONDITIONAL_ACCESS]

    def test_generate_m365_package(self):
        """Test generating a full M365 policy package."""
        service = M365PolicyService()
        controls = [
            self._make_control("AC-01", "MFA", "Identity & Access Control", "Enforce MFA"),
            self._make_control("DP-01", "DLP", "Data Protection", "Prevent data loss"),
            self._make_control("EP-01", "Endpoint", "Endpoint Security", "Secure endpoints"),
        ]
        request = M365GenerationRequest(
            framework_name="Test Framework",
            policy_types=[M365PolicyType.DLP, M365PolicyType.CONDITIONAL_ACCESS, M365PolicyType.DEVICE_COMPLIANCE],
        )
        package = service.generate_m365_package(controls, request)

        assert package.framework_name == "Test Framework"
        assert package.total_controls == 3
        assert package.mapped_controls > 0
        assert len(package.mappings) == 3
        assert len(package.policies) > 0
        assert len(package.deployment_script) > 0

    def test_export_as_json(self):
        """Test JSON export of M365 package."""
        service = M365PolicyService()
        controls = [
            self._make_control("AC-01", "MFA", "Identity & Access Control", "Enforce MFA"),
        ]
        request = M365GenerationRequest(framework_name="Test")
        package = service.generate_m365_package(controls, request)
        json_str = service.export_as_json(package)
        assert '"framework_name"' in json_str
        assert '"Test"' in json_str

    def test_get_m365_policy_service(self):
        """Test service factory function."""
        service = get_m365_policy_service()
        assert isinstance(service, M365PolicyService)


# --- Purview Config Service Tests ---

class TestPurviewConfigService:
    """Tests for Microsoft Purview configuration service."""

    def _make_control(self, control_id, name, domain, description="Test control"):
        return ExternalControl(
            control_id=control_id,
            control_name=name,
            description=description,
            domain=domain,
        )

    def test_map_data_classification_control(self):
        """Test mapping data classification to sensitivity labels."""
        service = PurviewConfigService()
        control = self._make_control(
            "TEST-DC-01", "Data Classification",
            "Data Classification",
            "Classify data based on sensitivity"
        )
        mapping = service.map_control_to_purview(control)
        assert mapping.purview_config_type == PurviewConfigType.SENSITIVITY_LABEL
        assert len(mapping.sensitivity_labels) > 0

    def test_map_data_retention_control(self):
        """Test mapping data retention to retention labels."""
        service = PurviewConfigService()
        control = self._make_control(
            "TEST-DR-01", "Data Retention",
            "Data Retention",
            "Retain records per regulatory mandate"
        )
        mapping = service.map_control_to_purview(control)
        assert mapping.purview_config_type == PurviewConfigType.RETENTION_LABEL
        assert len(mapping.retention_labels) > 0

    def test_map_data_protection_control(self):
        """Test mapping data protection to DLP + sensitivity labels."""
        service = PurviewConfigService()
        control = self._make_control(
            "TEST-DP-01", "Data Protection",
            "Data Protection",
            "Protect sensitive data from unauthorized sharing"
        )
        mapping = service.map_control_to_purview(control)
        assert mapping.purview_config_type in [
            PurviewConfigType.SENSITIVITY_LABEL,
            PurviewConfigType.DLP_POLICY,
        ]

    def test_map_ediscovery_control(self):
        """Test mapping eDiscovery control."""
        service = PurviewConfigService()
        control = self._make_control(
            "TEST-ED-01", "Legal Hold",
            "eDiscovery",
            "Place legal holds for investigations"
        )
        mapping = service.map_control_to_purview(control)
        assert mapping.purview_config_type == PurviewConfigType.EDISCOVERY

    def test_generate_purview_package(self):
        """Test generating a full Purview configuration package."""
        service = PurviewConfigService()
        controls = [
            self._make_control("DC-01", "Classification", "Data Classification", "Classify data"),
            self._make_control("DP-01", "DLP", "Data Protection", "Prevent data loss"),
            self._make_control("DR-01", "Retention", "Data Retention", "Retain records"),
        ]
        request = PurviewGenerationRequest(
            framework_name="Test Framework",
            config_types=[
                PurviewConfigType.SENSITIVITY_LABEL,
                PurviewConfigType.DLP_POLICY,
                PurviewConfigType.RETENTION_LABEL,
            ],
        )
        package = service.generate_purview_package(controls, request)

        assert package.framework_name == "Test Framework"
        assert package.total_controls == 3
        assert package.mapped_controls > 0
        assert len(package.mappings) == 3
        assert len(package.sensitivity_labels) > 0
        assert len(package.dlp_policies) > 0
        assert len(package.retention_labels) > 0
        assert len(package.deployment_script) > 0

    def test_deployment_script_contains_graph_commands(self):
        """Test that deployment script contains Graph API commands."""
        service = PurviewConfigService()
        controls = [
            self._make_control("DC-01", "Classification", "Data Classification", "Classify"),
        ]
        request = PurviewGenerationRequest(
            framework_name="Test",
            config_types=[PurviewConfigType.SENSITIVITY_LABEL, PurviewConfigType.DLP_POLICY, PurviewConfigType.RETENTION_LABEL],
        )
        package = service.generate_purview_package(controls, request)
        script = package.deployment_script

        assert "Connect-MgGraph" in script
        assert "Invoke-MgGraphRequest" in script
        assert "graph.microsoft.com" in script

    def test_export_as_json(self):
        """Test JSON export of Purview package."""
        service = PurviewConfigService()
        controls = [
            self._make_control("DC-01", "Classification", "Data Classification", "Classify"),
        ]
        request = PurviewGenerationRequest(framework_name="Test")
        package = service.generate_purview_package(controls, request)
        json_str = service.export_as_json(package)
        assert '"framework_name"' in json_str
        assert '"Test"' in json_str

    def test_get_purview_config_service(self):
        """Test service factory function."""
        service = get_purview_config_service()
        assert isinstance(service, PurviewConfigService)


# --- Graph Client Tests ---

class TestGraphClient:
    """Tests for Microsoft Graph API client."""

    def test_get_available_endpoints(self):
        """Test getting available Graph endpoints."""
        client = GraphClient()
        endpoints = client.get_available_endpoints()
        assert "dlp_policies" in endpoints
        assert "sensitivity_labels" in endpoints
        assert "conditional_access" in endpoints

    def test_get_required_permissions(self):
        """Test getting required permissions for a capability."""
        client = GraphClient()
        perms = client.get_required_permissions("dlp")
        assert len(perms) > 0
        assert any("DlpPolicies" in p for p in perms)

    def test_get_all_required_permissions(self):
        """Test getting all permissions across capabilities."""
        client = GraphClient()
        all_perms = client.get_all_required_permissions()
        assert len(all_perms) > 0

    def test_generate_deployment_script(self):
        """Test generating Graph API deployment script."""
        client = GraphClient()
        policies = [
            {"name": "test-policy", "displayName": "Test Policy"},
        ]
        script = client.generate_graph_deployment_script(policies, "dlp")
        assert "Connect-MgGraph" in script
        assert "test-policy" in script
        assert "Invoke-MgGraphRequest" in script

    def test_get_graph_client_singleton(self):
        """Test that get_graph_client returns instance."""
        client = get_graph_client()
        assert isinstance(client, GraphClient)
