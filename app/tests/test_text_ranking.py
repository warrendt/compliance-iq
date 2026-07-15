"""
Unit tests for TF-IDF ranking and MCSBService relevance retrieval.

Run from app/ with:
  AZURE_OPENAI_ENDPOINT=https://dummy.openai.azure.com/ ENABLE_AUTH=false \
  PYTHONPATH=backend python -m pytest tests/test_text_ranking.py -q -p no:cacheprovider --noconftest
"""

import pytest

from app.services import text_ranking as tr
from app.services.mcsb_service import MCSBService


@pytest.fixture(scope="module")
def service() -> MCSBService:
    svc = MCSBService()
    svc.load_controls()
    return svc


class TestRankerHelpers:
    def test_tokenize_drops_stopwords_and_short_tokens(self):
        tokens = tr.tokenize("Encrypt the data at rest using CMK")
        assert "encrypt" in tokens and "data" in tokens and "cmk" in tokens
        assert "the" not in tokens  # stop-word
        assert "at" not in tokens   # stop-word

    def test_cosine_identity_and_orthogonal(self):
        idf = tr.compute_idf([["encrypt", "data"], ["network", "firewall"]])
        v_a = tr.tfidf_vector(["encrypt", "data"], idf)
        v_b = tr.tfidf_vector(["network", "firewall"], idf)
        assert tr.cosine(v_a, v_a) == pytest.approx(1.0, abs=1e-9)
        assert tr.cosine(v_a, v_b) == pytest.approx(0.0, abs=1e-9)

    def test_rank_orders_by_relevance_stably(self):
        docs = [
            tr.tokenize("customer managed key encryption at rest"),
            tr.tokenize("network firewall segmentation"),
            tr.tokenize("multi factor authentication identity"),
        ]
        idf = tr.compute_idf(docs)
        ranking = tr.rank_documents(tr.tokenize("encryption customer managed key"), docs, idf)
        assert ranking[0][0] == 0  # the encryption document ranks first
        scores = [score for _index, score in ranking]
        assert scores == sorted(scores, reverse=True)  # non-increasing


class TestServiceRelevanceRetrieval:
    def test_returns_all_controls_by_default(self, service):
        result = service.get_controls_for_external_control(
            "some description", "Some Domain", external_control_name="Some Control")
        assert len(result) == len(service.get_all_controls())  # max recall - nothing excluded

    @pytest.mark.parametrize("description,domain,name,expected_first", [
        ("Encrypt data at rest using customer-managed keys (CMK)",
         "Data Protection", "Customer-Managed Keys", "DP-5"),
        ("Enforce multi-factor authentication for privileged and user access",
         "Identity & Access", "Strong Authentication", "IM-6"),
        ("Perform regular automated backups and test restoration",
         "Resilience", "Backup and Recovery", "BR-1"),
        ("Segment networks and restrict traffic with firewalls and NSGs",
         "Network", "Network Segmentation", "NS-1"),
    ])
    def test_targeted_query_ranks_expected_control_first(
        self, service, description, domain, name, expected_first):
        result = service.get_controls_for_external_control(
            description, domain, external_control_name=name)
        assert result[0].control_id == expected_first

    def test_ai_query_surfaces_ai_domain(self, service):
        result = service.get_controls_for_external_control(
            "Filter harmful prompts and outputs from generative AI models",
            "AI", external_control_name="Content Safety")
        assert all(c.domain == "AI Security" for c in result[:3])

    def test_top_k_caps_the_list(self, service):
        result = service.get_controls_for_external_control(
            "Encrypt data at rest with customer-managed keys",
            "Data Protection", top_k=5)
        assert len(result) == 5
        assert all(c.domain == "Data Protection" for c in result[:2])
        assert "DP-5" in {c.control_id for c in result}

    def test_empty_query_returns_all_in_natural_order(self, service):
        result = service.get_controls_for_external_control("", None)
        assert [c.control_id for c in result] == [
            c.control_id for c in service.get_all_controls()]
