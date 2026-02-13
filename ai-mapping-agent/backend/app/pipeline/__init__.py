"""
Compliance Pipeline Package.
Automated PDF-to-Defender-for-Cloud initiative generation.
"""

from .models import (
    ExtractedControl,
    ControlExtractionResult,
    AzurePolicyMapping,
    ControlPolicyMapping,
    BatchPolicyMappingResult,
    ValidationIssue,
    ValidationReport,
    PipelineResult,
)
from .config import PipelineConfig
from .pdf_extractor import extract_text_from_pdf, chunk_text, get_pdf_metadata
from .control_extractor import extract_controls_from_text
from .policy_mapper import map_controls_to_azure_policies
from .validator import validate_mappings
from .initiative_builder import build_initiative_artifacts

__all__ = [
    "PipelineConfig",
    "ExtractedControl",
    "ControlExtractionResult",
    "AzurePolicyMapping",
    "ControlPolicyMapping",
    "BatchPolicyMappingResult",
    "ValidationIssue",
    "ValidationReport",
    "PipelineResult",
    "extract_text_from_pdf",
    "chunk_text",
    "get_pdf_metadata",
    "extract_controls_from_text",
    "map_controls_to_azure_policies",
    "validate_mappings",
    "build_initiative_artifacts",
]
