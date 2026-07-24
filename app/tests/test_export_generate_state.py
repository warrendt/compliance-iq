"""Regression guards for the Export/Deploy parameter-collection rewire.

Two correctness bugs made the opt-in parameterized-built-in flow a one-way door
against the persisted base initiative:

1. The base **Generate** call read the sticky ``policy_parameter_values`` from
   session state, so once values were supplied they leaked into every
   regeneration and the built-in could never be excluded again.
2. ``_regenerate_with_parameters`` overwrote and persisted
   ``st.session_state.generated_policy``, permanently clobbering the clean base
   initiative after any Validate/Deploy-with-values.

The page module executes Streamlit at import time (not hermetically importable),
so these guards assert against the source of the two specific code paths.
"""

import ast
from pathlib import Path

_PAGE = (
    Path(__file__).resolve().parents[1]
    / "frontend"
    / "pages"
    / "4_Export_Policy.py"
)


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found in page module")


def _tree() -> ast.Module:
    return ast.parse(_PAGE.read_text())


def test_regenerate_does_not_persist_generated_policy():
    """The transient regen must never assign st.session_state.generated_policy."""
    fn = _func(_tree(), "_regenerate_with_parameters")
    for node in ast.walk(fn):
        # Detect attribute assignments to st.session_state.generated_policy.
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr == "generated_policy"
                ):
                    raise AssertionError(
                        "_regenerate_with_parameters must not overwrite "
                        "st.session_state.generated_policy (clobbers the base)"
                    )
        # And it must not persist the transient result to workflow state.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "persist_workflow_state", (
                "_regenerate_with_parameters must not call "
                "persist_workflow_state (base contamination)"
            )


def test_base_generate_does_not_read_sticky_parameter_values():
    """The base Generate must not feed sticky params back into itself."""
    src = _PAGE.read_text()
    # The base generate handler is the only call NOT inside
    # _regenerate_with_parameters. Strip that function's body, then assert the
    # sticky read is gone from the remaining (base) generate path.
    tree = _tree()
    regen = _func(tree, "_regenerate_with_parameters")
    lines = src.splitlines()
    outside = "\n".join(
        line
        for i, line in enumerate(lines, start=1)
        if not (regen.lineno <= i <= (regen.end_lineno or regen.lineno))
    )
    assert 'policy_parameter_values=st.session_state.get("policy_parameter_values")' not in outside, (
        "base Generate must not pass sticky policy_parameter_values — it leaks "
        "supplied values into every regeneration (one-way door)"
    )


def _extract_callable(name: str):
    """Exec a single top-level function from the page in isolation.

    The page runs Streamlit at import, so we compile only the target function's
    source (plus module-level literal constants it may reference, e.g.
    ``_VALID_MAPPING_TYPES``) and return the callable.
    """
    import ast as _ast

    tree = _tree()
    fn = _func(tree, name)
    consts = [
        node
        for node in tree.body
        if isinstance(node, _ast.Assign)
        and all(isinstance(t, _ast.Name) for t in node.targets)
        and isinstance(node.value, (_ast.Constant, _ast.Set, _ast.List, _ast.Tuple, _ast.Dict))
    ]
    module = _ast.Module(body=[*consts, fn], type_ignores=[])
    _ast.fix_missing_locations(module)
    ns: dict = {"Dict": dict, "Any": object}
    exec(compile(module, str(_PAGE), "exec"), ns)
    return ns[name]


def test_to_backend_mapping_forwards_coverage_fields():
    """The generate request MUST carry the coverage taxonomy through, else the
    backend coverage gate silently no-ops and non-Azure controls stay in the
    initiative."""
    to_backend = _extract_callable("_to_backend_mapping")
    out = to_backend(
        {
            "control_id": "C-1",
            "control_name": "A process control",
            "coverage_category": "C_Process",
            "control_type": "Governance",
            "azure_enforceable": False,
            "azure_policy_ids": [],
        }
    )
    assert out["coverage_category"] == "C_Process"
    assert out["control_type"] == "Governance"
    assert out["azure_enforceable"] is False


def test_page_renders_separate_manual_register_tab():
    """The Export page exposes a distinct Manual Register section/tab."""
    src = _PAGE.read_text()
    assert "Manual Register" in src
    assert "_render_manual_register" in src


_AI_MAPPING_PAGE = (
    Path(__file__).resolve().parents[1] / "frontend" / "pages" / "2_AI_Mapping.py"
)


def _extract_callable_from(page: Path, name: str):
    """Exec a single top-level function from an arbitrary page in isolation."""
    import ast as _ast

    tree = _ast.parse(page.read_text())
    fn = next(
        (
            n
            for n in _ast.walk(tree)
            if isinstance(n, _ast.FunctionDef) and n.name == name
        ),
        None,
    )
    assert fn is not None, f"{name!r} not found in {page.name}"
    module = _ast.Module(body=[fn], type_ignores=[])
    _ast.fix_missing_locations(module)
    ns: dict = {}
    exec(compile(module, str(page), "exec"), ns)
    return ns[name]


def test_session_mapping_preserves_coverage_taxonomy():
    """_complete_mapping_job must not drop coverage fields when storing results.

    Regression: the reconstruction whitelist omitted coverage_category/
    control_type/azure_enforceable, so every session mapping became
    coverage_category=None and the manual register was always empty.
    """
    build = _extract_callable_from(_AI_MAPPING_PAGE, "_session_mapping_from_result")
    out = build(
        {
            "external_control_id": "C-1",
            "external_control_name": "Personnel Security",
            "coverage_category": "C_Process",
            "control_type": "Governance",
            "azure_enforceable": False,
        },
        [],
    )
    assert out["coverage_category"] == "C_Process"
    assert out["control_type"] == "Governance"
    assert out["azure_enforceable"] is False


def test_generate_sends_export_superset_not_confidence_filtered():
    """The generate paths must send ``export_mappings`` — the full working set
    (backend applies confidence + coverage gating) — so the backend can build a
    complete manual register. Re-applying the confidence filter client-side
    drops low-confidence non-Azure controls from the register (empty-register
    bug) and low-confidence Azure controls from the coverage summary."""
    src = _PAGE.read_text()
    assert "for m in export_mappings" in src, (
        "generate call must send export_mappings, not the confidence-filtered set"
    )
    assert (
        "mappings=[_to_backend_mapping(m) for m in filtered_mappings]" not in src
    ), "no generate call may send only the confidence-filtered set"

    assign = next(
        (
            n
            for n in ast.walk(_tree())
            if isinstance(n, ast.AnnAssign)
            and isinstance(n.target, ast.Name)
            and n.target.id == "export_mappings"
        ),
        None,
    )
    assert assign is not None, "export_mappings assignment not found"
    segment = ast.get_source_segment(src, assign)
    assert "st.session_state.mappings" in segment, (
        "export_mappings must be built from the full working set"
    )
    assert "confidence_score" not in segment, (
        "export_mappings must not re-apply the confidence gate client-side"
    )
