"""Column-mapping helpers shared by the control upload page.

Detection is a pure function over column names so it can be unit-tested without
Streamlit, and so the "Auto-Detect Columns" button and the on-upload detection
can never drift apart.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

# Session-state keys holding the user's column choices, in display order.
COLUMN_MAPPING_KEYS: tuple[str, ...] = (
    "control_id_col",
    "control_name_col",
    "description_col",
    "domain_col",
)

# Ordered candidate substrings per field. The first column whose lower-cased
# name contains one of these wins; earlier entries are stronger signals.
_FIELD_HINTS: Dict[str, tuple[str, ...]] = {
    "control_id_col": ("control id", "control_id", "controlid", "ref", "id"),
    "control_name_col": ("control name", "control_name", "title", "name"),
    "description_col": ("description", "desc", "requirement", "objective"),
    "domain_col": ("domain", "category", "family", "section", "area"),
}


def detect_columns(columns: Iterable[str]) -> Dict[str, str]:
    """Map each mapping key to the best-matching column name.

    Every field is resolved independently against the full column list, so an
    early column can no longer consume a later field's match (the previous
    if/elif chain let "Control ID" block "Control Name"). A column is never
    assigned to two fields. Returns "" for fields with no plausible match.
    """
    available: List[str] = [str(c) for c in columns]
    resolved: Dict[str, str] = {key: "" for key in COLUMN_MAPPING_KEYS}
    taken: set[str] = set()

    for key in COLUMN_MAPPING_KEYS:
        for hint in _FIELD_HINTS[key]:
            match = next(
                (
                    col
                    for col in available
                    if col not in taken and hint in col.lower()
                ),
                None,
            )
            if match is not None:
                resolved[key] = match
                taken.add(match)
                break

    return resolved


def sanitize_selection(current: str, available: Iterable[str]) -> str:
    """Drop a stored column choice that no longer exists in the current file."""
    return current if current in set(available) else ""
