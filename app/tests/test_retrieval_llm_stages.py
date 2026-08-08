"""Unit tests for the two LLM stages added to retrieval.

Both services sit on the critical path of the measured 15.6% -> 84.4% recall
gain, and both are deliberately *best-effort*: they degrade to the historical
behaviour rather than failing a mapping run. That degradation is the property
worth pinning, because it is invisible when it works and silent when it breaks --
a reranker that quietly returns nothing, or an expansion that quietly replaces a
good query, would show up only as a recall regression weeks later.

Self-contained (no conftest): CI runs these with --noconftest.
"""

import asyncio
import os

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-test")
os.environ.setdefault("ENABLE_AUTH", "false")

import pytest  # noqa: F401  (import guards that the suite runs under pytest)

from app.services import control_intent_service as intent_mod
from app.services import policy_rerank_service as rerank_mod
from app.services.control_intent_service import (
    ControlIntent,
    ControlIntentService,
    passthrough_intent,
)
from app.services.policy_rerank_service import PolicyRerankService, RerankResult


class _Candidate:
    """Duck-typed stand-in for PolicyCandidate."""

    def __init__(self, name, display_name="P", category="Storage", description="d"):
        self.name = name
        self.display_name = display_name
        self.category = category
        self.description = description

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<C {self.name}>"


class _StubClient:
    """Minimal stand-in for the Azure OpenAI client's parse interface."""

    def __init__(self, parsed=None, error=None):
        self._parsed = parsed
        self._error = error
        self.calls = []
        self.beta = self

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error

        class _Msg:
            parsed = self._parsed

        class _Choice:
            message = _Msg()

        class _Completion:
            choices = [_Choice()]

        return _Completion()


# --------------------------------------------------------------------------
# Control intent expansion
# --------------------------------------------------------------------------


def test_expansion_is_additive_not_substitutive():
    """A weak expansion must degrade toward the baseline, not replace the query.

    Substituting would mean a bad expansion destroys a query that already
    retrieved correctly -- turning a best-effort enhancement into a regression
    risk on every control.
    """
    intent = ControlIntent(
        azure_restatement="Storage accounts should use customer-managed keys",
        azure_services=["Storage Account"],
        security_features=["customer-managed key"],
    )
    query = intent.build_query("Keys shall be maintained by the cloud consumer.")

    assert "Keys shall be maintained by the cloud consumer." in query
    assert "customer-managed keys" in query
    assert "Storage Account" in query


def test_empty_expansion_returns_the_original_query_unchanged():
    assert passthrough_intent().build_query("original text") == "original text"


def test_is_empty_ignores_categories():
    """Categories alone are not an expansion: they add no retrievable terms.

    A category is a boost signal, not query text, so an intent carrying only
    categories must still report itself empty or it would claim a lift it
    cannot deliver.
    """
    assert ControlIntent(policy_categories=["Storage"]).is_empty
    assert not ControlIntent(azure_services=["Key Vault"]).is_empty


def test_expansion_text_drops_blank_parts():
    intent = ControlIntent(
        azure_restatement="  ", azure_services=["", "Key Vault"], security_features=[]
    )
    assert intent.expansion_text() == "Key Vault"


def test_expand_returns_passthrough_when_disabled(monkeypatch):
    monkeypatch.setattr(
        intent_mod.settings, "policy_catalog_query_expansion", False, raising=False
    )
    service = ControlIntentService(client=_StubClient())
    intent = asyncio.run(service.expand("Name", "Description"))
    assert intent.is_empty


def test_expand_returns_passthrough_for_empty_control_text(monkeypatch):
    monkeypatch.setattr(
        intent_mod.settings, "policy_catalog_query_expansion", True, raising=False
    )
    service = ControlIntentService(client=_StubClient())
    assert asyncio.run(service.expand("", "", "")).is_empty


def test_expand_survives_a_model_failure(monkeypatch):
    """An expansion outage must cost recall, never the whole mapping run."""
    monkeypatch.setattr(
        intent_mod.settings, "policy_catalog_query_expansion", True, raising=False
    )
    service = ControlIntentService(client=_StubClient(error=RuntimeError("boom")))
    intent = asyncio.run(service.expand("Encryption", "Encrypt data at rest"))

    assert intent.is_empty
    assert intent.build_query("Encrypt data at rest") == "Encrypt data at rest"


def test_expand_returns_the_parsed_intent(monkeypatch):
    monkeypatch.setattr(
        intent_mod.settings, "policy_catalog_query_expansion", True, raising=False
    )
    parsed = ControlIntent(
        azure_restatement="TLS 1.2 minimum on Azure SQL",
        azure_services=["SQL Server"],
    )
    service = ControlIntentService(client=_StubClient(parsed=parsed))
    intent = asyncio.run(service.expand("TLS", "Use strong transport security"))

    assert intent.azure_restatement == "TLS 1.2 minimum on Azure SQL"
    assert intent.azure_services == ["SQL Server"]


def test_expand_treats_an_unparsed_response_as_failure(monkeypatch):
    monkeypatch.setattr(
        intent_mod.settings, "policy_catalog_query_expansion", True, raising=False
    )
    service = ControlIntentService(client=_StubClient(parsed=None))
    assert asyncio.run(service.expand("N", "D")).is_empty


# --------------------------------------------------------------------------
# Candidate reranking
# --------------------------------------------------------------------------


def _candidates(n):
    return [_Candidate(f"g{i}") for i in range(1, n + 1)]


def test_rerank_is_skipped_when_the_shortlist_already_fits(monkeypatch):
    """No model call is worth making when there is nothing to narrow."""
    monkeypatch.setattr(rerank_mod.settings, "policy_catalog_rerank", True, raising=False)
    client = _StubClient(parsed=RerankResult(selected=[3, 2, 1]))
    service = PolicyRerankService(client=client)

    out = asyncio.run(service.rerank("control", _candidates(5), top_n=10))

    assert [c.name for c in out] == ["g1", "g2", "g3", "g4", "g5"]
    assert client.calls == []


def test_rerank_disabled_truncates_in_retrieval_order(monkeypatch):
    monkeypatch.setattr(
        rerank_mod.settings, "policy_catalog_rerank", False, raising=False
    )
    client = _StubClient(parsed=RerankResult(selected=[9, 8]))
    service = PolicyRerankService(client=client)

    out = asyncio.run(service.rerank("control", _candidates(10), top_n=2))

    assert [c.name for c in out] == ["g1", "g2"]
    assert client.calls == []


def test_rerank_reorders_by_model_preference(monkeypatch):
    monkeypatch.setattr(rerank_mod.settings, "policy_catalog_rerank", True, raising=False)
    service = PolicyRerankService(client=_StubClient(parsed=RerankResult(selected=[4, 1])))

    out = asyncio.run(service.rerank("control", _candidates(10), top_n=5))

    assert [c.name for c in out] == ["g4", "g1"]


def test_rerank_ignores_out_of_range_and_duplicate_indices(monkeypatch):
    """The model's arithmetic is not trusted.

    A hallucinated index would otherwise raise IndexError mid-run, or silently
    duplicate a candidate and crowd the selection window.
    """
    monkeypatch.setattr(rerank_mod.settings, "policy_catalog_rerank", True, raising=False)
    service = PolicyRerankService(
        client=_StubClient(parsed=RerankResult(selected=[0, 99, -3, 2, 2, 1]))
    )

    out = asyncio.run(service.rerank("control", _candidates(10), top_n=5))

    assert [c.name for c in out] == ["g2", "g1"]


def test_rerank_never_exceeds_the_requested_window(monkeypatch):
    monkeypatch.setattr(rerank_mod.settings, "policy_catalog_rerank", True, raising=False)
    service = PolicyRerankService(
        client=_StubClient(parsed=RerankResult(selected=[1, 2, 3, 4, 5, 6]))
    )

    out = asyncio.run(service.rerank("control", _candidates(10), top_n=3))

    assert len(out) == 3


def test_rerank_falls_back_to_retrieval_order_on_failure(monkeypatch):
    """A reranker outage must cost precision, not recall.

    Retrieval already found the right answer; returning nothing would discard it.
    """
    monkeypatch.setattr(rerank_mod.settings, "policy_catalog_rerank", True, raising=False)
    service = PolicyRerankService(client=_StubClient(error=RuntimeError("boom")))

    out = asyncio.run(service.rerank("control", _candidates(10), top_n=3))

    assert [c.name for c in out] == ["g1", "g2", "g3"]


def test_rerank_preserves_an_empty_shortlist_as_a_real_answer(monkeypatch):
    """"Nothing applies" is the correct answer for a process control.

    Falling back to retrieval order here would re-attach policies to exactly the
    controls the classification stage exists to keep out of the initiative.
    """
    monkeypatch.setattr(rerank_mod.settings, "policy_catalog_rerank", True, raising=False)
    service = PolicyRerankService(client=_StubClient(parsed=RerankResult(selected=[])))

    out = asyncio.run(service.rerank("control", _candidates(10), top_n=3))

    assert out == []


def test_rerank_handles_no_candidates():
    service = PolicyRerankService(client=_StubClient())
    assert asyncio.run(service.rerank("control", [], top_n=5)) == []


def test_rerank_prompt_truncates_long_descriptions(monkeypatch):
    """A depth-200 shortlist of full descriptions would blow the prompt budget."""
    monkeypatch.setattr(rerank_mod.settings, "policy_catalog_rerank", True, raising=False)
    client = _StubClient(parsed=RerankResult(selected=[1]))
    service = PolicyRerankService(client=client)
    candidates = [_Candidate("g1", description="x" * 500)] + _candidates(9)

    asyncio.run(service.rerank("control", candidates, top_n=2))

    prompt = client.calls[0]["messages"][1]["content"]
    assert "..." in prompt
    assert "x" * 200 not in prompt


def test_rerank_unparsed_response_falls_back(monkeypatch):
    monkeypatch.setattr(rerank_mod.settings, "policy_catalog_rerank", True, raising=False)
    service = PolicyRerankService(client=_StubClient(parsed=None))

    out = asyncio.run(service.rerank("control", _candidates(10), top_n=2))

    assert [c.name for c in out] == ["g1", "g2"]
