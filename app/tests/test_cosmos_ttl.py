"""Regression tests for Cosmos TTL handling.

A TTL-enabled container rejects an explicit ``ttl: null`` ("The input ttl
'null' is invalid"). All documents built from ``BaseDocument`` carry a ``ttl``
key defaulting to ``None``, so the Cosmos write helpers must strip a ``None``
ttl while preserving valid values.
"""
import os

import pytest

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.db.cosmos_client import CosmosDBClient, _sanitize_document_for_write
from app.models.db_models import ComparisonDocument


class _FakeContainer:
    """Captures the body passed to each Cosmos write call."""

    def __init__(self):
        self.created = None
        self.upserted = None
        self.replaced = None

    async def create_item(self, body):
        self.created = body
        return body

    async def upsert_item(self, body):
        self.upserted = body
        return body

    async def replace_item(self, item, body):
        self.replaced = body
        return body


class _FakeDatabase:
    def __init__(self, container):
        self._container = container

    def get_container_client(self, _name):
        return self._container


def _client_with(container):
    client = CosmosDBClient()
    client.database = _FakeDatabase(container)
    return client


def test_sanitize_strips_none_ttl():
    doc = {"id": "x", "ttl": None}
    _sanitize_document_for_write(doc)
    assert "ttl" not in doc


def test_sanitize_preserves_never_expire():
    doc = {"id": "x", "ttl": -1}
    _sanitize_document_for_write(doc)
    assert doc["ttl"] == -1


def test_sanitize_preserves_positive_ttl():
    doc = {"id": "x", "ttl": 3600}
    _sanitize_document_for_write(doc)
    assert doc["ttl"] == 3600


def test_sanitize_no_ttl_key_is_noop():
    doc = {"id": "x"}
    _sanitize_document_for_write(doc)
    assert doc == {"id": "x"}


@pytest.mark.asyncio
async def test_insert_document_drops_none_ttl():
    container = _FakeContainer()
    client = _client_with(container)

    doc = ComparisonDocument(userId="user@example.com").model_dump(mode="json")
    assert doc["ttl"] is None  # the bug source: model emits ttl: null

    await client.insert_document(client.COMPARISONS, doc)

    assert "ttl" not in container.created


@pytest.mark.asyncio
async def test_upsert_document_drops_none_ttl():
    container = _FakeContainer()
    client = _client_with(container)

    await client.upsert_document("comparisons", {"id": "c1", "ttl": None})

    assert "ttl" not in container.upserted


@pytest.mark.asyncio
async def test_update_document_drops_none_ttl():
    container = _FakeContainer()
    client = _client_with(container)

    await client.update_document("comparisons", {"id": "c1", "ttl": None})

    assert "ttl" not in container.replaced


@pytest.mark.asyncio
async def test_insert_document_keeps_valid_ttl():
    container = _FakeContainer()
    client = _client_with(container)

    await client.insert_document("comparisons", {"id": "c1", "ttl": 3600})

    assert container.created["ttl"] == 3600
