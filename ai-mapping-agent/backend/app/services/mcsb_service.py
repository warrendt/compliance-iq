"""
MCSB (Microsoft Cloud Security Benchmark) data service.
Loads, indexes, and provides search functionality for MCSB controls.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from functools import lru_cache

from app.models import MCSBControl
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MCSBService:
    """Service for loading and searching MCSB controls."""

    def __init__(self, data_path: Optional[str] = None):
        """
        Initialize MCSB service.

        Args:
            data_path: Path to MCSB controls JSON file
        """
        self.data_path = data_path or settings.mcsb_data_path
        self._controls: List[MCSBControl] = []
        self._controls_by_id: Dict[str, MCSBControl] = {}
        self._controls_by_domain: Dict[str, List[MCSBControl]] = {}
        self._loaded = False

    def load_controls(self) -> None:
        """Load MCSB controls from JSON file."""
        if self._loaded:
            logger.info("MCSB controls already loaded")
            return

        try:
            file_path = Path(self.data_path)

            if not file_path.exists():
                logger.warning(f"MCSB data file not found: {file_path}")
                # Load from existing CCToolkit catalogs as fallback
                self._load_from_existing_catalogs()
                return

            logger.info(f"Loading MCSB controls from {file_path}")

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Parse controls
            if isinstance(data, list):
                controls_data = data
            elif isinstance(data, dict) and 'controls' in data:
                controls_data = data['controls']
            else:
                raise ValueError("Invalid MCSB data format")

            self._controls = [MCSBControl(**ctrl) for ctrl in controls_data]

            # Build indexes
            self._build_indexes()

            self._loaded = True
            logger.info(f"Successfully loaded {len(self._controls)} MCSB controls")

        except Exception as e:
            logger.error(f"Failed to load MCSB controls: {e}")
            # Load from existing catalogs as fallback
            self._load_from_existing_catalogs()

    def _load_from_existing_catalogs(self) -> None:
        """
        Load MCSB-like structure from existing CCToolkit catalogs.
        This provides a fallback if the MCSB JSON file doesn't exist.
        """
        logger.info("Loading MCSB data from existing CCToolkit catalogs")

        try:
            import pandas as pd

            # Load existing SAMA catalog as reference
            catalog_path = Path("../../catalogues/SAMA_Catalog_Azure_Mappings.csv")

            if not catalog_path.exists():
                logger.warning("No existing catalogs found, creating default controls")
                self._create_default_controls()
                return

            df = pd.read_csv(catalog_path)

            # Extract unique MCSB-like controls from mappings
            # This is simplified - in reality you'd parse the actual MCSB structure
            self._create_default_controls()

        except Exception as e:
            logger.error(f"Failed to load from existing catalogs: {e}")
            self._create_default_controls()

    def _create_default_controls(self) -> None:
        """Create default MCSB controls for demonstration."""
        logger.info("Creating default MCSB control set")

        default_controls = [
            {
                "control_id": "IM-1",
                "domain": "Identity Management",
                "control_name": "Use centralized identity and authentication system",
                "description": "Use a centralized identity and authentication system to manage organizational identities for people and services.",
                "azure_policy_ids": [],
                "defender_recommendations": ["Enable MFA for all users"],
                "related_frameworks": {"CIS": ["CIS-5.1"], "NIST": ["IA-2"]}
            },
            {
                "control_id": "IM-6",
                "domain": "Identity Management",
                "control_name": "Use strong authentication controls",
                "description": "Use strong authentication controls including MFA and passwordless authentication.",
                "azure_policy_ids": ["4e6c27d5-a6ee-49cf-b2b4-d8fe90fa2b8b"],
                "defender_recommendations": ["Enable MFA - Require multifactor authentication for all users"],
                "related_frameworks": {"CIS": ["CIS-5.2"], "NIST": ["IA-2(1)"]}
            },
            {
                "control_id": "PA-7",
                "domain": "Privileged Access",
                "control_name": "Follow just enough administration (least privilege) principle",
                "description": "Follow the principle of least privilege when granting access.",
                "azure_policy_ids": [],
                "defender_recommendations": ["Manage access and permissions"],
                "related_frameworks": {"CIS": ["CIS-5.4"], "NIST": ["AC-6"]}
            },
            {
                "control_id": "NS-2",
                "domain": "Network Security",
                "control_name": "Secure cloud services with network controls",
                "description": "Protect cloud services by implementing network security controls.",
                "azure_policy_ids": ["ca610c1d-041c-4332-9d88-7ed3094967c7"],
                "defender_recommendations": ["Restrict unauthorized network access"],
                "related_frameworks": {"CIS": ["CIS-9.2"], "NIST": ["SC-7"]}
            },
            {
                "control_id": "DP-3",
                "domain": "Data Protection",
                "control_name": "Encrypt sensitive data in transit",
                "description": "Encrypt sensitive data in transit using approved cryptographic protocols.",
                "azure_policy_ids": [],
                "defender_recommendations": ["Encrypt data in transit"],
                "related_frameworks": {"CIS": ["CIS-3.7"], "NIST": ["SC-8"]}
            },
            {
                "control_id": "DP-5",
                "domain": "Data Protection",
                "control_name": "Use customer-managed key option in data at rest encryption",
                "description": "Use customer-managed keys for encryption at rest when required.",
                "azure_policy_ids": ["18adea5e-f416-4d0f-8aa8-d24321e3e274"],
                "defender_recommendations": ["Enable encryption at rest"],
                "related_frameworks": {"CIS": ["CIS-3.5"], "NIST": ["SC-28"]}
            },
            {
                "control_id": "LT-3",
                "domain": "Logging and Threat Detection",
                "control_name": "Enable logging for security investigation",
                "description": "Enable logging capabilities for security investigation and monitoring.",
                "azure_policy_ids": [],
                "defender_recommendations": ["Enable auditing and logging"],
                "related_frameworks": {"CIS": ["CIS-6.1"], "NIST": ["AU-2"]}
            },
            {
                "control_id": "PV-3",
                "domain": "Posture and Vulnerability Management",
                "control_name": "Establish and maintain a secure configuration process",
                "description": "Establish and maintain security configuration standards.",
                "azure_policy_ids": [],
                "defender_recommendations": ["Apply system updates", "Remediate vulnerabilities"],
                "related_frameworks": {"CIS": ["CIS-5.1"], "NIST": ["CM-6"]}
            },
            {
                "control_id": "BR-1",
                "domain": "Backup and Recovery",
                "control_name": "Ensure regular automated backups",
                "description": "Implement automated backup solutions for critical data and systems.",
                "azure_policy_ids": [],
                "defender_recommendations": ["Enable backup for critical resources"],
                "related_frameworks": {"CIS": ["CIS-10.1"], "NIST": ["CP-9"]}
            },
            {
                "control_id": "GS-1",
                "domain": "Governance and Strategy",
                "control_name": "Establish security governance and compliance program",
                "description": "Establish a comprehensive security governance program.",
                "azure_policy_ids": [],
                "defender_recommendations": ["Implement security policies"],
                "related_frameworks": {"CIS": ["CIS-1.1"], "NIST": ["PM-1"]}
            }
        ]

        self._controls = [MCSBControl(**ctrl) for ctrl in default_controls]
        self._build_indexes()
        self._loaded = True

        logger.info(f"Created {len(self._controls)} default MCSB controls")

    def _build_indexes(self) -> None:
        """Build lookup indexes for faster searching."""
        self._controls_by_id = {ctrl.control_id: ctrl for ctrl in self._controls}

        # Group by domain
        self._controls_by_domain = {}
        for ctrl in self._controls:
            if ctrl.domain not in self._controls_by_domain:
                self._controls_by_domain[ctrl.domain] = []
            self._controls_by_domain[ctrl.domain].append(ctrl)

        logger.debug(f"Built indexes: {len(self._controls_by_id)} controls, "
                    f"{len(self._controls_by_domain)} domains")

    def get_all_controls(self) -> List[MCSBControl]:
        """
        Get all MCSB controls.

        Returns:
            List of all MCSB controls
        """
        if not self._loaded:
            self.load_controls()
        return self._controls

    def get_control_by_id(self, control_id: str) -> Optional[MCSBControl]:
        """
        Get MCSB control by ID.

        Args:
            control_id: MCSB control ID (e.g., "IM-1")

        Returns:
            MCSB control or None if not found
        """
        if not self._loaded:
            self.load_controls()
        return self._controls_by_id.get(control_id)

    def get_controls_by_domain(self, domain: str) -> List[MCSBControl]:
        """
        Get all controls in a specific domain.

        Args:
            domain: Security domain name

        Returns:
            List of controls in the domain
        """
        if not self._loaded:
            self.load_controls()
        return self._controls_by_domain.get(domain, [])

    def get_all_domains(self) -> List[str]:
        """
        Get all unique domain names.

        Returns:
            List of domain names
        """
        if not self._loaded:
            self.load_controls()
        return list(self._controls_by_domain.keys())

    def search_by_keywords(self, keywords: List[str]) -> List[MCSBControl]:
        """
        Search controls by keywords in name and description.

        Args:
            keywords: List of keywords to search for

        Returns:
            List of matching controls
        """
        if not self._loaded:
            self.load_controls()

        results = []
        keywords_lower = [kw.lower() for kw in keywords]

        for ctrl in self._controls:
            # Search in control name and description
            search_text = f"{ctrl.control_name} {ctrl.description}".lower()

            # Check if any keyword matches
            if any(kw in search_text for kw in keywords_lower):
                results.append(ctrl)

        logger.debug(f"Keyword search for {keywords} returned {len(results)} results")
        return results

    def get_controls_for_external_control(
        self,
        external_control_description: str,
        external_control_domain: Optional[str] = None
    ) -> List[MCSBControl]:
        """
        Get relevant MCSB controls for an external control.
        Used to provide context to the AI mapping service.

        Args:
            external_control_description: Description of external control
            external_control_domain: Optional domain hint

        Returns:
            List of potentially relevant MCSB controls
        """
        if not self._loaded:
            self.load_controls()

        # If domain is provided, filter by domain first
        if external_control_domain:
            # Try exact match
            domain_controls = self.get_controls_by_domain(external_control_domain)
            if domain_controls:
                return domain_controls

            # Try fuzzy match on domain names
            for domain in self._controls_by_domain.keys():
                if external_control_domain.lower() in domain.lower():
                    return self._controls_by_domain[domain]

        # Otherwise, return all controls for the AI to analyze
        # In production, you might want to use semantic search here
        return self._controls


@lru_cache
def get_mcsb_service() -> MCSBService:
    """Get cached MCSB service instance."""
    service = MCSBService()
    service.load_controls()
    return service
