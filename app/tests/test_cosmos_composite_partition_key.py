"""A composite partition key must actually produce a container.

``ensure_container`` built hierarchical keys as::

    PartitionKey(paths=[...], kind="MultiHash", version=2)

but the SDK's keyword is ``path`` (singular) for both shapes — a ``str`` for a
single key, a ``list`` for a hierarchical one — and it infers Hash vs MultiHash
itself. The call above therefore raised ``KeyError('path')`` *inside the
constructor*, before any network request, and the surrounding ``except`` logged
it as a warning and moved on.

``mapping-results`` (``/userId`` + ``/date``) is the only container with a
composite key, so it was the only one never ensured — on every run, since the
code was written. It escaped notice because Bicep pre-provisions the container
in the deployed environment (``infra/core/cosmosdb.bicep``), so writes still
succeeded and the warning looked cosmetic. On a fresh environment the container
would never have been created and every mapping write would have failed.

Discovered from a live log line: ``Failed to ensure container mapping-results:
'path'``.
"""

from __future__ import annotations

import logging

import pytest
from azure.cosmos import PartitionKey

from app.db.cosmos_client import CosmosDBClient


class _FakeDatabase:
    def __init__(self):
        self.calls = []

    async def create_container_if_not_exists(self, *, id, partition_key, default_ttl=None):
        self.calls.append(
            {"id": id, "partition_key": partition_key, "default_ttl": default_ttl}
        )


@pytest.fixture()
def client():
    c = CosmosDBClient()
    c.database = _FakeDatabase()
    return c


def test_the_sdk_rejects_the_old_construction():
    """Pin the root cause, so nobody reintroduces it believing it works."""
    with pytest.raises(KeyError):
        PartitionKey(paths=["/userId", "/date"], kind="MultiHash", version=2)


@pytest.mark.asyncio
async def test_a_composite_key_container_is_actually_created(client):
    await client.ensure_container(
        "mapping-results", partition_key_paths=["/userId", "/date"], default_ttl=100
    )

    assert client.database.calls, (
        "mapping-results was never created. This is the live defect: the "
        "PartitionKey constructor raised before the SDK call was reached."
    )
    pk = client.database.calls[0]["partition_key"]
    assert pk["paths"] == ["/userId", "/date"]
    assert pk["kind"] == "MultiHash"
    assert client.database.calls[0]["default_ttl"] == 100


@pytest.mark.asyncio
async def test_a_composite_key_matches_what_bicep_provisions(client):
    """The runtime and the infrastructure must agree on the key.

    ``infra/core/cosmosdb.bicep`` declares mapping-results with
    ``kind: 'MultiHash'``, ``version: 2``, paths ``/userId`` then ``/date``.
    Order is significant in a hierarchical key, so this asserts the sequence,
    not just membership.
    """
    await client.ensure_container(
        "mapping-results", partition_key_paths=["/userId", "/date"]
    )
    pk = client.database.calls[0]["partition_key"]
    assert pk["paths"] == ["/userId", "/date"]
    assert pk["kind"] == "MultiHash"
    assert pk["version"] == 2


@pytest.mark.asyncio
async def test_single_key_containers_are_unaffected(client):
    await client.ensure_container("user-profiles", partition_key_paths=["/userId"])
    pk = client.database.calls[0]["partition_key"]
    assert pk["paths"] == ["/userId"]
    assert pk["kind"] == "Hash"


@pytest.mark.asyncio
async def test_failure_is_logged_at_error_level_with_its_consequence(client, caplog):
    """Swallowing is deliberate here, but it must not look harmless.

    The startup path ensures every container, so raising would stop the app
    booting over a transient error. The cost of that choice is that the log is
    the only signal, which makes its level and wording load-bearing.
    """
    class _Boom:
        async def create_container_if_not_exists(self, **_):
            raise RuntimeError("service unavailable")

    client.database = _Boom()
    with caplog.at_level(logging.DEBUG):
        await client.ensure_container("mapping-results", partition_key_paths=["/userId", "/date"])

    records = [r for r in caplog.records if "mapping-results" in r.getMessage()]
    assert records, "a failure to ensure a container must be logged"
    assert records[0].levelno >= logging.ERROR, (
        "logged at %s; a container that does not exist is an error, not a "
        "warning, because every later write to it fails"
        % records[0].levelname
    )
    assert "will fail" in records[0].getMessage(), (
        "the log must state the consequence, not just the exception"
    )


@pytest.mark.asyncio
async def test_no_database_is_a_no_op(client):
    client.database = None
    await client.ensure_container("mapping-results", partition_key_paths=["/userId", "/date"])
