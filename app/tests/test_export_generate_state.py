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
