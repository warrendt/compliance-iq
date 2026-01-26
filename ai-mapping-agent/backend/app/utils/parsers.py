"""
Utilities for parsing uploaded control files (CSV, Excel).
"""

import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict, Any
from io import BytesIO

from app.models import ExternalControl, FrameworkUpload

logger = logging.getLogger(__name__)


class ControlFileParser:
    """Parser for control files in CSV or Excel format."""

    REQUIRED_COLUMNS = ["Control ID", "Control Name", "Description"]
    OPTIONAL_COLUMNS = ["Domain", "Control Type", "Requirements"]

    @staticmethod
    def parse_file(
        file_content: bytes,
        filename: str,
        framework_name: str
    ) -> FrameworkUpload:
        """
        Parse uploaded control file.

        Args:
            file_content: Binary content of uploaded file
            filename: Original filename
            framework_name: Name of the framework

        Returns:
            FrameworkUpload with parsed controls

        Raises:
            ValueError: If file format is invalid or required columns are missing
        """
        logger.info(f"Parsing control file: {filename}")

        # Determine file type
        file_ext = Path(filename).suffix.lower()

        try:
            if file_ext == '.csv':
                df = pd.read_csv(BytesIO(file_content))
            elif file_ext in ['.xlsx', '.xls']:
                df = pd.read_excel(BytesIO(file_content))
            else:
                raise ValueError(f"Unsupported file format: {file_ext}")

            # Validate required columns
            missing_cols = [
                col for col in ControlFileParser.REQUIRED_COLUMNS
                if col not in df.columns
            ]

            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")

            # Parse controls
            controls = []
            for idx, row in df.iterrows():
                try:
                    control = ExternalControl(
                        control_id=str(row['Control ID']).strip(),
                        control_name=str(row['Control Name']).strip(),
                        description=str(row['Description']).strip(),
                        domain=str(row.get('Domain', '')).strip() or None,
                        control_type=str(row.get('Control Type', '')).strip() or None,
                        requirements=str(row.get('Requirements', '')).strip() or None
                    )
                    controls.append(control)

                except Exception as e:
                    logger.warning(f"Skipping row {idx + 1}: {e}")
                    continue

            if not controls:
                raise ValueError("No valid controls found in file")

            framework_upload = FrameworkUpload(
                framework_name=framework_name,
                controls=controls
            )

            logger.info(f"Successfully parsed {len(controls)} controls from {filename}")
            return framework_upload

        except Exception as e:
            logger.error(f"Failed to parse file {filename}: {e}")
            raise

    @staticmethod
    def validate_file_format(df: pd.DataFrame) -> tuple[bool, List[str]]:
        """
        Validate DataFrame has required columns.

        Args:
            df: DataFrame to validate

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check required columns
        missing_cols = [
            col for col in ControlFileParser.REQUIRED_COLUMNS
            if col not in df.columns
        ]

        if missing_cols:
            errors.append(f"Missing required columns: {', '.join(missing_cols)}")

        # Check for empty DataFrame
        if df.empty:
            errors.append("File contains no data rows")

        # Check for duplicate Control IDs
        if 'Control ID' in df.columns:
            duplicates = df[df.duplicated(subset=['Control ID'], keep=False)]
            if not duplicates.empty:
                dup_ids = duplicates['Control ID'].unique().tolist()
                errors.append(f"Duplicate Control IDs found: {dup_ids}")

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def get_column_mapping_suggestions(columns: List[str]) -> Dict[str, str]:
        """
        Suggest column mappings if column names don't match exactly.

        Args:
            columns: List of actual column names in file

        Returns:
            Dictionary mapping required columns to suggested actual columns
        """
        suggestions = {}

        # Common variations of column names
        variations = {
            "Control ID": ["id", "control_id", "controlid", "ctrl_id", "number"],
            "Control Name": ["name", "control_name", "title", "control_title"],
            "Description": ["desc", "description", "requirement", "details"],
            "Domain": ["category", "area", "domain", "control_domain"],
            "Control Type": ["type", "control_type", "classification"]
        }

        for required_col in ControlFileParser.REQUIRED_COLUMNS + ControlFileParser.OPTIONAL_COLUMNS:
            # Try exact match first (case-insensitive)
            exact_match = next(
                (col for col in columns if col.lower() == required_col.lower()),
                None
            )
            if exact_match:
                suggestions[required_col] = exact_match
                continue

            # Try variations
            possible_variations = variations.get(required_col, [])
            for actual_col in columns:
                if any(var in actual_col.lower() for var in possible_variations):
                    suggestions[required_col] = actual_col
                    break

        return suggestions


def parse_control_file(
    file_content: bytes,
    filename: str,
    framework_name: str
) -> FrameworkUpload:
    """
    Convenience function to parse control file.

    Args:
        file_content: Binary file content
        filename: Original filename
        framework_name: Framework name

    Returns:
        FrameworkUpload with parsed controls
    """
    parser = ControlFileParser()
    return parser.parse_file(file_content, filename, framework_name)
