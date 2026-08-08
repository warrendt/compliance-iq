"""Unit tests for the CSV/Excel column auto-detection helpers.

Hermetic: ``utils.column_mapping`` is pure and imports nothing from streamlit,
so these run with ``PYTHONPATH=app/frontend`` and no server.
"""

from utils.column_mapping import (
    COLUMN_MAPPING_KEYS,
    detect_columns,
    sanitize_selection,
)


def test_detects_conventional_headers():
    result = detect_columns(
        ["Control ID", "Control Name", "Control Description", "Control Domain"]
    )
    assert result == {
        "control_id_col": "Control ID",
        "control_name_col": "Control Name",
        "description_col": "Control Description",
        "domain_col": "Control Domain",
    }


def test_detects_abbreviated_headers():
    result = detect_columns(["id", "title", "desc", "category"])
    assert result["control_id_col"] == "id"
    assert result["control_name_col"] == "title"
    assert result["description_col"] == "desc"
    assert result["domain_col"] == "category"


def test_each_field_resolves_independently():
    """A column matching an earlier field must not starve a later one.

    The previous if/elif chain assigned the first matching column and moved on,
    so "Control Description" could be consumed as the *name* column and leave
    the description unmapped.
    """
    result = detect_columns(["Control Description", "Control Name"])
    assert result["description_col"] == "Control Description"
    assert result["control_name_col"] == "Control Name"


def test_no_column_is_assigned_to_two_fields():
    result = detect_columns(["Control ID", "Control Name", "Description", "Domain"])
    assigned = [value for value in result.values() if value]
    assert len(assigned) == len(set(assigned))


def test_unmatched_fields_are_blank_not_missing():
    result = detect_columns(["Foo", "Bar"])
    assert set(result) == set(COLUMN_MAPPING_KEYS)
    assert all(value == "" for value in result.values())


def test_empty_column_list_is_safe():
    assert detect_columns([]) == {key: "" for key in COLUMN_MAPPING_KEYS}


def test_sanitize_drops_selections_absent_from_the_new_file():
    available = ["Control ID", "Domain"]
    assert sanitize_selection("Control ID", available) == "Control ID"
    assert sanitize_selection("Gone", available) == ""
    assert sanitize_selection("", available) == ""
