"""Tests for the Azure Policy catalog retrieval service (TF-IDF)."""

import json
import os

import pytest

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.services.policy_catalog_service import PolicyCatalogService, _tokenize


_SAMPLE = {
    "count": 4,
    "definitions": [
        {
            "name": "11111111-1111-1111-1111-111111111111",
            "display_name": "Storage accounts should use customer-managed keys to encrypt data at rest",
            "description": "Secure your storage account with greater flexibility using customer-managed keys.",
            "category": "Storage",
            "mode": "Indexed",
        },
        {
            "name": "22222222-2222-2222-2222-222222222222",
            "display_name": "Enforce multi-factor authentication for users",
            "description": "Require MFA for all user sign-ins to reduce account compromise.",
            "category": "Identity",
            "mode": "All",
        },
        {
            "name": "33333333-3333-3333-3333-333333333333",
            "display_name": "SQL servers should disable public network access",
            "description": "Disabling public network access improves security by restricting exposure.",
            "category": "SQL",
            "mode": "All",
        },
        {
            "name": "44444444-4444-4444-4444-444444444444",
            "display_name": "Virtual machines should have backup configured",
            "description": "Ensure recoverability by configuring Azure Backup on virtual machines.",
            "category": "Backup",
            "mode": "All",
        },
    ],
}


def _write_catalog(tmp_path, payload=_SAMPLE):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_tokenize_drops_stopwords_and_short_tokens():
    toks = _tokenize("Ensure the data is encrypted at rest")
    assert "data" in toks and "encrypted" in toks and "rest" in toks
    # stopwords / single chars removed
    assert "the" not in toks and "is" not in toks and "at" not in toks


def test_load_and_count(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    svc.load()
    assert svc.count == 4
    assert svc.source.startswith("snapshot")


def test_search_returns_relevant_policy_first(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    results = svc.search("encrypt storage data at rest with customer managed keys", top_n=3)
    assert results, "expected at least one candidate"
    assert results[0].name == "11111111-1111-1111-1111-111111111111"
    # scores are sorted descending
    assert all(
        results[i].score >= results[i + 1].score for i in range(len(results) - 1)
    )


def test_search_mfa_and_network(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    assert svc.search("multi-factor authentication", top_n=1)[0].name.startswith("2222")
    assert svc.search("disable public network access to SQL", top_n=1)[0].name.startswith("3333")


def test_get_by_guid(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    got = svc.get("44444444-4444-4444-4444-444444444444")
    assert got and got["category"] == "Backup"
    assert svc.get("does-not-exist") is None


def test_missing_catalog_degrades_gracefully(tmp_path):
    svc = PolicyCatalogService(data_path=str(tmp_path / "nope.json"))
    svc.load()
    assert svc.count == 0
    assert svc.source == "missing"
    assert svc.search("anything") == []


def test_empty_query_returns_empty(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    assert svc.search("the a an of to") == []  # all stopwords


def test_refresh_from_definitions_rebuilds_index(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    svc.load()
    svc.refresh_from_definitions(
        [
            {
                "name": "99999999-9999-9999-9999-999999999999",
                "display_name": "Key Vault should have purge protection enabled",
                "description": "Prevent permanent data loss by enabling purge protection.",
                "category": "Key Vault",
            }
        ],
        source="arm(1)",
    )
    assert svc.count == 1
    assert svc.source == "arm(1)"
    assert svc.search("key vault purge protection", top_n=1)[0].name.startswith("9999")


def test_shipped_snapshot_loads_full_catalog():
    """The committed snapshot ships the real built-in catalog, not a stub."""
    svc = PolicyCatalogService()  # default shipped path
    svc.load()
    assert svc.count > 2000, f"expected the full catalog, got {svc.count}"
    assert svc.source.startswith("snapshot")
    # A customer-managed-keys query should surface CMK encryption policies.
    top = svc.search("encrypt data at rest customer managed keys storage", top_n=5)
    assert any("customer-managed keys" in c.display_name.lower() for c in top)


# --- Regulatory Compliance (manual attestation) demotion --------------------

_DEMOTE_SAMPLE = {
    "count": 2,
    "definitions": [
        {
            # Manual-attestation control. Identical searchable text to the
            # enforceable policy below, so category is the ONLY differentiator.
            "name": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "display_name": "Review development process standards and tools",
            "description": "Review development process standards and tools",
            "category": "Regulatory Compliance",
            "mode": "All",
        },
        {
            "name": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "display_name": "Review development process standards and tools",
            "description": "Review development process standards and tools",
            "category": "Security Center",
            "mode": "All",
        },
    ],
}


def test_regulatory_compliance_is_demoted_below_enforceable(tmp_path, monkeypatch):
    import app.services.policy_catalog_service as mod

    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path, _DEMOTE_SAMPLE))
    query = "review development process standards and tools"

    # No demotion: identical text -> tie -> stable order keeps the RegC entry
    # (declared first) on top.
    monkeypatch.setattr(mod.settings, "policy_catalog_regulatory_penalty", 1.0)
    no_demote = svc.search(query, top_n=2)
    assert no_demote[0].category == "Regulatory Compliance"

    # With demotion: the enforceable policy is ranked first.
    monkeypatch.setattr(mod.settings, "policy_catalog_regulatory_penalty", 0.35)
    demoted = svc.search(query, top_n=2)
    assert demoted[0].category == "Security Center"
    # The manual control is demoted, not dropped.
    assert any(c.category == "Regulatory Compliance" for c in demoted)


def test_regulatory_penalty_reorders_rather_than_rescales(tmp_path, monkeypatch):
    """The penalty acts on rank, which is what ``score`` now reports.

    Since hybrid retrieval landed, ``PolicyCandidate.score`` is a rank score
    (reciprocal-rank fusion when embeddings contribute, ``1/(rank+1)``
    otherwise), not the raw TF-IDF cosine. Both branches must report on the same
    scale or scores would be meaningless across configurations, so the penalty
    is no longer observable as a multiplicative change to a score — it is
    observable as a change in ordering, which is the behaviour that actually
    affects what the model sees.
    """
    import app.services.policy_catalog_service as mod

    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path, _DEMOTE_SAMPLE))
    query = "review development process standards and tools"

    reg_guid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    enf_guid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    monkeypatch.setattr(mod.settings, "policy_catalog_regulatory_penalty", 1.0)
    full = [c.name for c in svc.search(query, top_n=2)]
    monkeypatch.setattr(mod.settings, "policy_catalog_regulatory_penalty", 0.5)
    half = [c.name for c in svc.search(query, top_n=2)]

    assert full.index(reg_guid) < full.index(enf_guid)
    assert half.index(enf_guid) < half.index(reg_guid)
    # Demoted, never dropped: a Manual-effect definition can still be the only
    # sensible answer for an attestation-shaped control.
    assert set(half) == set(full)

    scores = [c.score for c in svc.search(query, top_n=2)]
    assert scores == sorted(scores, reverse=True)


# ── exists / available (built-in existence checks for deploy safety) ──────────

def test_exists_true_for_known_guid(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    assert svc.exists("11111111-1111-1111-1111-111111111111") is True


def test_exists_accepts_full_resource_id(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    full = "/providers/Microsoft.Authorization/policyDefinitions/22222222-2222-2222-2222-222222222222"
    assert svc.exists(full) is True


def test_exists_false_for_unknown_guid(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    assert svc.exists("aeedaca3-0f56-429f-945d-8bb66bd06841") is False
    assert svc.exists("") is False


def test_available_true_when_loaded(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path))
    assert svc.available is True


def test_available_false_when_snapshot_missing(tmp_path):
    svc = PolicyCatalogService(data_path=str(tmp_path / "missing.json"))
    assert svc.available is False
    assert svc.exists("11111111-1111-1111-1111-111111111111") is False


_EFFECT_CATALOG = {
    "count": 4,
    "definitions": [
        {
            "name": "a0000000-0000-0000-0000-000000000000",
            "display_name": "Real enforceable audit policy",
            "description": "Audits a resource configuration.",
            "category": "Security Center",
            "effect": "AuditIfNotExists",
        },
        {
            "name": "b0000000-0000-0000-0000-000000000000",
            "display_name": "Manual attestation control filed under Regulatory Compliance",
            "description": "Microsoft managed control.",
            "category": "Regulatory Compliance",
            "effect": "Manual",
        },
        {
            "name": "c0000000-0000-0000-0000-000000000000",
            "display_name": "Manual placeholder NOT filed under Regulatory Compliance",
            "description": "Placeholder whose category alone would not flag it.",
            "category": "Security Center",
            "effect": "Manual",
        },
        {
            "name": "d0000000-0000-0000-0000-000000000000",
            "display_name": "Disabled no-op policy",
            "description": "Does nothing on its own.",
            "category": "General",
            "effect": "Disabled",
        },
    ],
}


def test_is_non_enforceable_by_category_and_effect(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path, _EFFECT_CATALOG))
    # Enforceable audit effect + real category -> enforceable.
    assert svc.is_non_enforceable("a0000000-0000-0000-0000-000000000000") is False
    # Manual + Regulatory Compliance -> non-enforceable (category signal).
    assert svc.is_non_enforceable("b0000000-0000-0000-0000-000000000000") is True
    # Manual effect but a *real* category -> non-enforceable via the EFFECT
    # signal alone, which the category filter would have missed.
    assert svc.is_non_enforceable("c0000000-0000-0000-0000-000000000000") is True
    # Disabled effect is a no-op -> non-enforceable.
    assert svc.is_non_enforceable("d0000000-0000-0000-0000-000000000000") is True
    # Unknown GUIDs are never stripped (snapshot may be incomplete).
    assert svc.is_non_enforceable("ffffffff-ffff-ffff-ffff-ffffffffffff") is False


def test_effect_stored_on_ingest(tmp_path):
    svc = PolicyCatalogService(data_path=_write_catalog(tmp_path, _EFFECT_CATALOG))
    entry = svc.get("a0000000-0000-0000-0000-000000000000")
    assert entry is not None and entry["effect"] == "AuditIfNotExists"
