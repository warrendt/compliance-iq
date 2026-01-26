"""
Azure Policy Initiative Generation Service.
Generates valid Azure Policy initiative definitions from control mappings.
"""

import logging
import json
from typing import List, Dict, Any
from datetime import datetime

from app.models import (
    ControlMapping,
    PolicyInitiative,
    PolicyInitiativeProperties,
    PolicyInitiativeMetadata,
    PolicyDefinitionReference,
    PolicyGenerationRequest,
    PolicyGenerationResponse
)

logger = logging.getLogger(__name__)


class PolicyGenerationService:
    """Service for generating Azure Policy initiatives."""

    def generate_initiative(
        self,
        request: PolicyGenerationRequest
    ) -> PolicyGenerationResponse:
        """
        Generate Azure Policy initiative from control mappings.

        Args:
            request: Policy generation request with mappings

        Returns:
            PolicyGenerationResponse with generated initiative

        Example:
            ```python
            service = PolicyGenerationService()
            response = service.generate_initiative(request)
            json_output = response.initiative.to_azure_json()
            ```
        """
        logger.info(f"Generating policy initiative for {request.framework_name}")

        # Filter mappings by confidence threshold
        filtered_mappings, warnings = self._filter_mappings(
            request.mappings,
            request.min_confidence_threshold,
            request.include_all_policies
        )

        # Generate policy definitions
        policy_definitions = self._create_policy_definitions(filtered_mappings)

        # Create metadata
        metadata = PolicyInitiativeMetadata(
            framework_name=request.framework_name,
            framework_version=request.framework_version,
            generated_date=datetime.utcnow()
        )

        # Create properties
        properties = PolicyInitiativeProperties(
            display_name=f"{request.framework_name} Compliance Initiative",
            description=f"AI-generated policy initiative for {request.framework_name} compliance framework",
            metadata=metadata,
            policy_definitions=policy_definitions
        )

        # Create initiative
        initiative = PolicyInitiative(properties=properties)

        # Create response
        response = PolicyGenerationResponse(
            initiative=initiative,
            total_controls=len(request.mappings),
            included_policies=len(policy_definitions),
            excluded_policies=len(request.mappings) - len(filtered_mappings),
            warnings=warnings
        )

        logger.info(
            f"Generated initiative with {response.included_policies} policies, "
            f"excluded {response.excluded_policies}"
        )

        return response

    def _filter_mappings(
        self,
        mappings: List[ControlMapping],
        min_confidence: float,
        include_all: bool
    ) -> tuple[List[ControlMapping], List[str]]:
        """
        Filter mappings based on confidence threshold.

        Args:
            mappings: List of control mappings
            min_confidence: Minimum confidence threshold
            include_all: Whether to include all policies regardless of confidence

        Returns:
            Tuple of (filtered mappings, warning messages)
        """
        warnings = []

        if include_all:
            logger.debug("Including all policies (include_all=True)")
            return mappings, warnings

        # Filter by confidence
        filtered = []
        excluded_count = 0

        for mapping in mappings:
            if mapping.confidence_score >= min_confidence:
                filtered.append(mapping)
            else:
                excluded_count += 1
                logger.debug(
                    f"Excluded {mapping.external_control_id} "
                    f"(confidence {mapping.confidence_score:.2f} < {min_confidence})"
                )

        if excluded_count > 0:
            warnings.append(
                f"{excluded_count} control(s) excluded due to confidence < {min_confidence}"
            )

        # Check for controls with no Azure Policy IDs
        no_policy_count = sum(1 for m in filtered if not m.azure_policy_ids)
        if no_policy_count > 0:
            warnings.append(
                f"{no_policy_count} control(s) have no associated Azure Policy definitions"
            )

        return filtered, warnings

    def _create_policy_definitions(
        self,
        mappings: List[ControlMapping]
    ) -> List[PolicyDefinitionReference]:
        """
        Create policy definition references from mappings.

        Args:
            mappings: List of control mappings

        Returns:
            List of policy definition references
        """
        policy_definitions = []
        seen_policy_ids = set()

        for mapping in mappings:
            # Skip if no Azure Policy IDs
            if not mapping.azure_policy_ids:
                logger.warning(
                    f"Control {mapping.external_control_id} has no Azure Policy IDs"
                )
                continue

            # Create a policy definition reference for each Azure Policy
            for policy_id in mapping.azure_policy_ids:
                # Avoid duplicates
                if policy_id in seen_policy_ids:
                    logger.debug(f"Skipping duplicate policy: {policy_id}")
                    continue

                seen_policy_ids.add(policy_id)

                # Create full policy definition ID
                full_policy_id = (
                    f"/providers/Microsoft.Authorization/policyDefinitions/{policy_id}"
                )

                # Create reference
                policy_def = PolicyDefinitionReference(
                    policy_definition_id=full_policy_id,
                    policy_definition_reference_id=mapping.external_control_id,
                    parameters={}  # Can be extended to support parameterization
                )

                policy_definitions.append(policy_def)

        logger.info(f"Created {len(policy_definitions)} policy definition references")
        return policy_definitions

    def validate_initiative(self, initiative: PolicyInitiative) -> tuple[bool, List[str]]:
        """
        Validate Azure Policy initiative structure.

        Args:
            initiative: Policy initiative to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check display name
        if not initiative.properties.display_name:
            errors.append("Display name is required")

        # Check description
        if not initiative.properties.description:
            errors.append("Description is required")

        # Check policy definitions
        if not initiative.properties.policy_definitions:
            errors.append("At least one policy definition is required")

        # Validate policy definition structure
        for idx, policy_def in enumerate(initiative.properties.policy_definitions):
            if not policy_def.policy_definition_id:
                errors.append(f"Policy definition {idx}: policy_definition_id is required")

            if not policy_def.policy_definition_reference_id:
                errors.append(
                    f"Policy definition {idx}: policy_definition_reference_id is required"
                )

            # Validate policy definition ID format
            if not policy_def.policy_definition_id.startswith(
                "/providers/Microsoft.Authorization/policyDefinitions/"
            ):
                errors.append(
                    f"Policy definition {idx}: Invalid policy_definition_id format"
                )

        is_valid = len(errors) == 0

        if is_valid:
            logger.info("Initiative validation passed")
        else:
            logger.error(f"Initiative validation failed: {errors}")

        return is_valid, errors

    def export_as_json(
        self,
        initiative: PolicyInitiative,
        pretty: bool = True
    ) -> str:
        """
        Export initiative as JSON string.

        Args:
            initiative: Policy initiative to export
            pretty: Whether to pretty-print JSON

        Returns:
            JSON string
        """
        azure_json = initiative.to_azure_json()

        if pretty:
            return json.dumps(azure_json, indent=2)
        else:
            return json.dumps(azure_json)

    def export_as_bicep(
        self,
        initiative: PolicyInitiative,
        initiative_name: str = "customComplianceInitiative"
    ) -> str:
        """
        Export initiative as Bicep template.

        Args:
            initiative: Policy initiative to export
            initiative_name: Name for the Bicep resource

        Returns:
            Bicep template string
        """
        props = initiative.properties

        bicep_template = f"""// Azure Policy Initiative - {props.display_name}
// Generated by CCToolkit AI Mapping Agent

@description('Location for the policy initiative')
param location string = resourceGroup().location

@description('Policy initiative display name')
param displayName string = '{props.display_name}'

@description('Policy initiative description')
param description string = '{props.description}'

resource policyInitiative 'Microsoft.Authorization/policySetDefinitions@2021-06-01' = {{
  name: '{initiative_name}'
  properties: {{
    displayName: displayName
    description: description
    policyType: 'Custom'
    metadata: {{
      category: '{props.metadata.category}'
      source: '{props.metadata.source}'
      version: '{props.metadata.version}'
      frameworkName: '{props.metadata.framework_name}'
    }}
    policyDefinitions: [
"""

        # Add policy definitions
        for policy_def in props.policy_definitions:
            bicep_template += f"""      {{
        policyDefinitionId: '{policy_def.policy_definition_id}'
        policyDefinitionReferenceId: '{policy_def.policy_definition_reference_id}'
        parameters: {{}}
      }}
"""

        bicep_template += """    ]
  }
}

output initiativeId string = policyInitiative.id
output initiativeName string = policyInitiative.name
"""

        return bicep_template

    def generate_deployment_script(
        self,
        initiative: PolicyInitiative,
        initiative_name: str,
        scope_type: str = "subscription"
    ) -> Dict[str, str]:
        """
        Generate deployment scripts for Azure CLI and PowerShell.

        Args:
            initiative: Policy initiative
            initiative_name: Name for the initiative
            scope_type: Deployment scope (subscription, management_group)

        Returns:
            Dictionary with 'cli' and 'powershell' script strings
        """
        # Export as JSON
        json_content = self.export_as_json(initiative, pretty=False)

        # Azure CLI script
        cli_script = f"""#!/bin/bash
# Deploy {initiative.properties.display_name}

# Save initiative definition to file
cat > initiative.json <<'EOF'
{json_content}
EOF

# Create policy initiative
az policy set-definition create \\
  --name "{initiative_name}" \\
  --display-name "{initiative.properties.display_name}" \\
  --description "{initiative.properties.description}" \\
  --definitions initiative.json \\
  --metadata category="{initiative.properties.metadata.category}"

echo "Initiative created successfully"
"""

        # PowerShell script
        ps_script = f"""# Deploy {initiative.properties.display_name}

# Save initiative definition to file
$initiativeJson = @'
{json_content}
'@

Set-Content -Path "initiative.json" -Value $initiativeJson

# Create policy initiative
New-AzPolicySetDefinition `
  -Name "{initiative_name}" `
  -DisplayName "{initiative.properties.display_name}" `
  -Description "{initiative.properties.description}" `
  -PolicyDefinition "initiative.json" `
  -Metadata @{{category="{initiative.properties.metadata.category}"}}

Write-Host "Initiative created successfully"
"""

        return {
            "cli": cli_script,
            "powershell": ps_script
        }


def get_policy_service() -> PolicyGenerationService:
    """Get policy generation service instance."""
    return PolicyGenerationService()
