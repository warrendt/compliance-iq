"""Tests for the Azure Policy catalog retrieval service (TF-IDF)."""

import json
import os

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
