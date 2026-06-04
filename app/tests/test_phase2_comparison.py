"""
Phase 2 gate tests — control comparison (diff) service + routes.

The LLM is never called: ``comparison_service._compare_batch`` is monkeypatched
to return deterministic ``ComparisonResult`` objects, and Cosmos is mocked.
"""

import os
import types

import pytest

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from app.services import comparison_service as cs
from app.services.comparison_service import (
    ComparisonControlMatch,
    ComparisonResult,
    ExternalControl,
)


def _cfg(batch_size: int = 50):
    return types.SimpleNamespace(batch_size=batch_size)


def _ext(*ids):
    return [
        ExternalControl(control_id=i, control_name=f"Ext {i}", description=f"desc {i}", domain="D")
        for i in ids
    ]


# ── Catalogue loading (real bundled CSVs) ─────────────────────────────────────

def test_list_external_frameworks_returns_bundled():
    frameworks = cs.list_external_frameworks()
    keys = {f["key"] for f in frameworks}
    assert {"SAMA_Catalog", "ADHICS_Framework", "Saudi_Arabia_Government",
            "Oman_Government", "South_African_Government"}.issubset(keys)
    for f in frameworks:
        assert f["control_count"] > 0
        assert f["display_name"]


def test_load_external_controls_real_csv():
    display_name, controls = cs.load_external_controls("SAMA_Catalog")
    assert display_name
    assert len(controls) > 10
    first = controls[0]
    assert first.control_id and first.control_name


def test_load_external_controls_rejects_path_traversal():
    for bad in ("../etc/passwd", "a/b", "..", "x\\y"):
        with pytest.raises(ValueError):
            cs.load_external_controls(bad)


def test_load_external_controls_unknown_key():
    with pytest.raises(ValueError):
        cs.load_external_controls("NoSuchFramework")


# ── Comparison engine (LLM mocked) ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_compare_buckets_counts_and_extra(monkeypatch):
    internal = [
        {"id": "INT-1", "title": "Access control", "description": "", "domain": "IAM"},
        {"id": "INT-2", "title": "Logging", "description": "", "domain": "Ops"},
        {"id": "INT-3", "title": "Unique req", "description": "", "domain": "X"},
    ]
    external = _ext("EXT-1", "EXT-2", "EXT-9")  # EXT-9 will be 'extra'

    def fake_batch(config, batch, ext):
        return ComparisonResult(
            matches=[
                ComparisonControlMatch(internal_control_id="INT-1", bucket="matched",
                                       external_control_id="EXT-1", similarity=0.95),
                ComparisonControlMatch(internal_control_id="INT-2", bucket="partial-overlap",
                                       external_control_id="EXT-2", similarity=0.6),
                # INT-3 omitted → must be gap-filled.
            ],
            summary="batch summary",
        )

    monkeypatch.setattr(cs, "_compare_batch", fake_batch)
    result = await cs.compare_controls(internal, external, _cfg())

    assert result["counts"] == {"matched": 1, "partial-overlap": 1, "gap": 1, "extra": 1}
    by_int = {m["internal_control_id"]: m for m in result["matches"] if m["internal_control_id"]}
    assert by_int["INT-1"]["bucket"] == "matched"
    assert by_int["INT-1"]["external_control_id"] == "EXT-1"
    assert by_int["INT-3"]["bucket"] == "gap"
    extras = [m for m in result["matches"] if m["bucket"] == "extra"]
    assert len(extras) == 1 and extras[0]["external_control_id"] == "EXT-9"
    assert result["summary"] == "batch summary"


@pytest.mark.asyncio
async def test_compare_downgrades_unknown_external_to_gap(monkeypatch):
    internal = [{"id": "INT-1", "title": "X", "description": "", "domain": ""}]
    external = _ext("EXT-1")

    def fake_batch(config, batch, ext):
        return ComparisonResult(matches=[
            ComparisonControlMatch(internal_control_id="INT-1", bucket="matched",
                                   external_control_id="GHOST", similarity=0.9),
        ])

    monkeypatch.setattr(cs, "_compare_batch", fake_batch)
    result = await cs.compare_controls(internal, external, _cfg())
    m = [x for x in result["matches"] if x["internal_control_id"] == "INT-1"][0]
    assert m["bucket"] == "gap"
    assert m["external_control_id"] is None
    # EXT-1 was never matched → becomes extra.
    assert result["counts"]["extra"] == 1


@pytest.mark.asyncio
async def test_compare_dedup_keeps_strongest(monkeypatch):
    internal = [{"id": "INT-1", "title": "X", "description": "", "domain": ""}]
    external = _ext("EXT-1", "EXT-2")

    def fake_batch(config, batch, ext):
        return ComparisonResult(matches=[
            ComparisonControlMatch(internal_control_id="INT-1", bucket="partial-overlap",
                                   external_control_id="EXT-2", similarity=0.5),
            ComparisonControlMatch(internal_control_id="INT-1", bucket="matched",
                                   external_control_id="EXT-1", similarity=0.9),
        ])

    monkeypatch.setattr(cs, "_compare_batch", fake_batch)
    result = await cs.compare_controls(internal, external, _cfg())
    m = [x for x in result["matches"] if x["internal_control_id"] == "INT-1"][0]
    assert m["bucket"] == "matched" and m["external_control_id"] == "EXT-1"
    assert result["counts"]["matched"] == 1


@pytest.mark.asyncio
async def test_compare_normalizes_ids(monkeypatch):
    internal = [{"id": "AC-1", "title": "X", "description": "", "domain": ""}]
    external = _ext("EXT-1")

    def fake_batch(config, batch, ext):
        # LLM echoes the id with different case/spacing.
        return ComparisonResult(matches=[
            ComparisonControlMatch(internal_control_id="  ac-1 ", bucket="matched",
                                   external_control_id="ext-1", similarity=0.8),
        ])

    monkeypatch.setattr(cs, "_compare_batch", fake_batch)
    result = await cs.compare_controls(internal, external, _cfg())
    m = [x for x in result["matches"] if x["internal_control_id"] == "AC-1"][0]
    assert m["bucket"] == "matched"
    assert m["external_control_id"] == "EXT-1"


@pytest.mark.asyncio
async def test_compare_batch_failure_yields_gaps(monkeypatch):
    internal = [{"id": "INT-1", "title": "X", "description": "", "domain": ""}]
    external = _ext("EXT-1")

    def boom(config, batch, ext):
        raise RuntimeError("LLM exploded")

    monkeypatch.setattr(cs, "_compare_batch", boom)
    result = await cs.compare_controls(internal, external, _cfg())
    # Internal control still surfaces as a gap; external as extra. No crash.
    assert result["counts"]["gap"] == 1
    assert result["counts"]["extra"] == 1


# ── Routes (Cosmos mocked, auth in dev mode) ──────────────────────────────────

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import app.api.routes.comparison as comp
from app.auth.azure_ad_auth import User, get_current_user
from app.main import app

_API = "/api/v1"


def _client(monkeypatch, **cosmos_methods):
    """TestClient with a forced dev user and a fully-mocked cosmos_client."""
    monkeypatch.setattr(comp.cosmos_client, "database", object())
    monkeypatch.setattr(comp.cosmos_client, "ensure_container", AsyncMock())
    for name, mock in cosmos_methods.items():
        monkeypatch.setattr(comp.cosmos_client, name, mock)
    app.dependency_overrides[get_current_user] = lambda: User(
        oid="u1", email="me@example.com", name="Me"
    )
    return TestClient(app)


def _teardown():
    app.dependency_overrides.pop(get_current_user, None)


def test_route_list_frameworks(monkeypatch):
    client = _client(monkeypatch)
    try:
        resp = client.get(f"{_API}/comparison/frameworks")
        assert resp.status_code == 200
        keys = {f["key"] for f in resp.json()}
        assert "SAMA_Catalog" in keys
    finally:
        _teardown()


def test_route_status_cross_user_returns_404(monkeypatch):
    other_doc = {"id": "c1", "userId": "someone-else@example.com", "status": "completed"}
    client = _client(monkeypatch, get_document=AsyncMock(return_value=other_doc))
    try:
        resp = client.get(f"{_API}/comparison/status/c1")
        assert resp.status_code == 404
    finally:
        _teardown()


def test_route_get_missing_returns_404(monkeypatch):
    client = _client(monkeypatch, get_document=AsyncMock(return_value=None))
    try:
        resp = client.get(f"{_API}/comparison/does-not-exist")
        assert resp.status_code == 404
    finally:
        _teardown()


def test_route_status_own_doc_ok(monkeypatch):
    own = {"id": "c1", "userId": "me@example.com", "status": "completed",
           "stage": "completed", "externalFramework": "SAMA_Catalog",
           "internalFileName": "p.pdf", "counts": {"matched": 2}}
    client = _client(monkeypatch, get_document=AsyncMock(return_value=own))
    try:
        resp = client.get(f"{_API}/comparison/status/c1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["counts"] == {"matched": 2}
    finally:
        _teardown()


def test_route_list_comparisons(monkeypatch):
    rows = [{"id": "c1", "status": "completed"}]
    client = _client(monkeypatch, query_documents=AsyncMock(return_value=rows))
    try:
        resp = client.get(f"{_API}/comparison")
        assert resp.status_code == 200
        assert resp.json()["comparisons"] == rows
    finally:
        _teardown()


def test_route_run_unknown_framework_400(monkeypatch):
    client = _client(monkeypatch, insert_document=AsyncMock())
    try:
        resp = client.post(
            f"{_API}/comparison/run",
            data={"external_framework": "NoSuchFramework"},
            files={"pdf_file": ("p.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert resp.status_code == 400
    finally:
        _teardown()
