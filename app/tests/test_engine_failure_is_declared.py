"""The engine must not answer confidently when it has failed.

Two defects are locked here, found by running real regulation PDFs through the
deployed engine rather than by reading code:

1. ``settings.ai_max_tokens`` did not exist. A lost newline in ``config.py``
   absorbed the field declaration into the comment on the line above, so every
   call to ``_request_mapping`` raised ``AttributeError``.
2. That exception was swallowed by a broad ``except Exception`` and turned into
   a fallback mapping labelled ``C_Process`` with ``coverage_gap`` unset - which
   downstream reads as "a process control Azure cannot enforce".

Together they meant the mapping engine returned "process control, no policy" for
every control of every framework while looking perfectly healthy. Neither defect
is visible to a test that mocks the model, which is why neither was caught.
"""

import pytest

from app.config import Settings
from app.models.control import ExternalControl
from app.services import coverage


def test_every_setting_the_mapping_call_reads_actually_exists():
    """A missing setting is an AttributeError at request time, not import time.

    Asserting the attribute rather than a value: the number may be tuned, but
    the field disappearing is what broke the product.
    """
    s = Settings()
    for name in (
        "ai_max_tokens",
        "ai_temperature",
        "ai_batch_size",
        "coverage_classification_max_tokens",
        "policy_catalog_expansion_max_tokens",
        "policy_catalog_rerank_max_tokens",
    ):
        assert hasattr(s, name), f"settings.{name} is read at runtime but not declared"


def test_structured_output_budgets_leave_room_for_reasoning_tokens():
    """A reasoning model spends completion tokens before it emits any output.

    Measured live: the rerank call was capped at 2000 completion tokens and the
    deployed model spent all 2000 on reasoning, so the request failed with
    "length limit reached" having produced nothing parseable. The caller
    degraded quietly to unranked retrieval, so retrieval quality dropped with no
    visible symptom. These ceilings were sized for a non-reasoning model.

    The floor, not the exact value, is what matters - tuning is expected,
    silently returning to a non-reasoning budget is not.
    """
    s = Settings()
    reasoning_floor = 4000
    for name in (
        "coverage_classification_max_tokens",
        "policy_catalog_expansion_max_tokens",
        "policy_catalog_rerank_max_tokens",
        "ai_max_tokens",
    ):
        assert getattr(s, name) >= reasoning_floor, (
            f"settings.{name} is below the budget a reasoning model needs before "
            "it produces any structured output; the call fails with a length "
            "limit and the failure is easy to mistake for a poor answer"
        )


def test_no_declaration_is_lost_into_a_trailing_comment():
    """Guard the specific mangling, since it is invisible and syntactically legal."""
    import inspect

    import app.config as config_module

    source = inspect.getsource(config_module)
    for lineno, line in enumerate(source.splitlines(), 1):
        if "#" not in line:
            continue
        comment = line.split("#", 1)[1]
        assert ":" not in comment or "=" not in comment, (
            f"config.py line {lineno} looks like a field declaration swallowed by a "
            f"comment - this exact mangling removed ai_max_tokens: {line.strip()!r}"
        )


def test_ai_temperature_is_not_described_as_giving_consistency():
    """A dead setting is tolerable; a comment claiming it does something is not.

    ``ai_temperature`` is read by nothing, and on the deployed reasoning model
    (``gpt-5.6-luna``) the Responses API would reject ``temperature`` if it were
    passed. Its comment used to read "Lower for consistency", which asserts a
    property the system measurably does not have: extraction returned 53 and 108
    controls from byte-identical input on two runs of the same sweep.

    The risk this guards is not the unused float. It is that the next person to
    ask "is extraction deterministic?" greps config.py, reads that comment, and
    concludes the question was already settled.
    """
    import inspect

    import app.config as config_module

    for line in inspect.getsource(config_module).splitlines():
        if "ai_temperature" in line and "#" in line:
            comment = line.split("#", 1)[1].lower()
            assert "consisten" not in comment and "determinis" not in comment, (
                "ai_temperature is not applied anywhere and cannot be honoured by a "
                f"reasoning deployment, so it must not be annotated as if it were: {line.strip()!r}"
            )


def _fallback():
    from app.services.ai_mapping_service import AIMappingService

    control = ExternalControl(
        control_id="1.1",
        control_name="Encrypt data at rest",
        description="All customer data must be encrypted at rest.",
    )
    return AIMappingService._create_fallback_mapping(
        object.__new__(AIMappingService), control, "boom"
    )


def test_a_failed_mapping_declares_itself_rather_than_judging_the_control():
    m = _fallback()
    assert m.coverage_gap is True, "an engine failure reported as a settled answer"
    assert m.coverage_reason, "a failure with no stated reason is indistinguishable from a finding"
    assert "fail" in m.coverage_reason.lower()
    assert m.confidence_score == 0.0
    assert m.azure_policy_ids == []


def test_a_failed_mapping_asserts_no_responsibility_it_did_not_determine():
    assert _fallback().responsibility is None


def test_a_failed_mapping_still_reaches_the_manual_register():
    """It must not vanish from the deliverable - that is worse than a flag."""
    rows = coverage.manual_register_rows([_fallback()])
    assert len(rows) == 1
    assert rows[0]["control_id"] == "1.1"
