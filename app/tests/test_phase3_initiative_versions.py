"""
Phase 3 gate tests — full-union initiative build + per-user version history.

No LLM and no live Cosmos: the pipeline mapper/validator/builder are monkeypatched
and Cosmos is mocked. Covers the union builder, the background build job (incl. the
2MB payload size guard), the build/version routes, and the immutable-revert gate.
"""

import os
import types
from unittest.mock import AsyncMock

import pytest

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://dummy.openai.azure.com/")
os.environ.setdefault("ENABLE_AUTH", "false")

from fastapi.testclient import TestClient

import app.api.routes.comparison as comp
import app.pipeline as pipeline_mod
from app.auth.azure_ad_auth import User, get_current_user
from app.main import app
from app.services import comparison_service as cs
from app.services import version_service as vs

_API = "/api/v1"


# ── Union builder (pure, real catalogue) ──────────────────────────────────────

def _completed_doc(framework_key="SAMA_Catalog", extra_ids=None):
    _, ext = cs.load_external_controls(framework_key)
    extra_ids = extra_ids if extra_ids is not None else [ext[0].control_id, ext[1].control_id]
    return {
        "id": "c1",
        "userId": "me@example.com",
        "status": "completed",
        "internalFileName": "policy.pdf",
        "externalFramework": framework_key,
        "result": {
            "internal_framework": "POPIA",
            "external_framework": "SAMA (Saudi Central Bank)",
            "counts": {"matched": 1, "partial-overlap": 1, "gap": 1, "extra": len(extra_ids)},
            "internal_controls": [
                {"id": "INT-1", "title": "Access Control", "description": "Restrict access",
                 "domain": "IAM", "control_type": "governance"},
                {"id": "INT-2", "title": "", "description": "", "domain": "", "control_type": "weird"},
                {"id": "", "title": "skip", "description": "no id", "domain": "X"},
                {"id": "INT-1", "title": "dup", "description": "dup", "domain": "IAM"},
            ],
            "matches": [
                {"bucket": "extra", "external_control_id": cid, "external_control_name": "x"}
                for cid in extra_ids
            ] + [{"bucket": "gap", "internal_control_id": "INT-2", "external_control_id": None}],
        },
    }


def test_union_dedup_fallbacks_and_coercion():
    res = cs.build_union_extraction(_completed_doc())
    ids = [c.control_id for c in res.controls]
    assert ids.count("INT-1") == 1           # deduped
    assert "" not in ids                      # empty id skipped
    by_id = {c.control_id: c for c in res.controls}
    assert by_id["INT-1"].control_type == "Governance"   # coerced from 'governance'
    assert by_id["INT-2"].control_title == "INT-2"        # title fallback -> id
    assert by_id["INT-2"].domain == "General"             # domain fallback
    assert by_id["INT-2"].control_type == "Technical"     # unknown type -> default
    assert "Effective Union" in res.framework_name


def test_union_includes_only_extra_external_controls():
    _, ext = cs.load_external_controls("SAMA_Catalog")
    extra = [ext[2].control_id]
    res = cs.build_union_extraction(_completed_doc(extra_ids=extra))
    ids = {c.control_id for c in res.controls}
    assert ext[2].control_id in ids          # the one 'extra' external control is included
    assert ext[5].control_id not in ids       # a non-extra external control is excluded


def test_union_requires_internal_controls_backcompat():
    with pytest.raises(ValueError):
        cs.build_union_extraction({"externalFramework": "SAMA_Catalog", "result": {"matches": []}})


# ── Background build job (pipeline + version_service mocked) ───────────────────

def _fake_mapping(automatable=True):
    return types.SimpleNamespace(is_automatable=automatable)


@pytest.mark.asyncio
async def test_run_build_job_persists_version(monkeypatch):
    doc = _completed_doc()

    monkeypatch.setattr(comp.cosmos_client, "database", object())
    monkeypatch.setattr(comp.cosmos_client, "get_document", AsyncMock(return_value=doc))
    monkeypatch.setattr(comp.cosmos_client, "upsert_document", AsyncMock())
    monkeypatch.setattr(comp.cosmos_client, "ensure_container", AsyncMock())

    monkeypatch.setattr(pipeline_mod, "map_controls_to_azure_policies",
                        lambda extraction, config: [_fake_mapping(), _fake_mapping(False)])
    monkeypatch.setattr(pipeline_mod, "validate_mappings",
                        lambda extraction, mappings: types.SimpleNamespace(model_dump=lambda: {}))

    def fake_build(extraction, mappings, validation, output_dir, allowed_locations=None):
        from pathlib import Path
        p1 = Path(output_dir) / "initiative.json"
        p1.write_text('{"ok": true}', encoding="utf-8")
        p2 = Path(output_dir) / "mappings.csv"
        p2.write_text("a,b\n1,2\n", encoding="utf-8")
        return [str(p1), str(p2)]

    monkeypatch.setattr(pipeline_mod, "build_initiative_artifacts", fake_build)
    monkeypatch.setattr(pipeline_mod.PipelineConfig, "from_env",
                        classmethod(lambda cls: types.SimpleNamespace(validate=lambda: [])))

    created = AsyncMock(return_value={"id": "v1", "version_number": 1})
    monkeypatch.setattr(comp.version_service, "create_version", created)
    monkeypatch.setattr(comp.audit_service, "write_audit", AsyncMock())

    await comp._run_build_job("c1", "me@example.com")

    created.assert_awaited_once()
    payload = created.await_args.kwargs["artifact_payload"]
    names = {f["name"] for f in payload["files"]}
    assert names == {"initiative.json", "mappings.csv"}
    assert payload["control_count"] == len(cs.build_union_extraction(doc).controls)
    assert payload["automatable_count"] == 1
    # final _update_job upsert marks the comparison completed
    upserts = comp.cosmos_client.upsert_document.await_args_list
    assert any(c.args[1].get("buildStatus") == "completed" for c in upserts)


@pytest.mark.asyncio
async def test_run_build_job_size_guard_omits_large_files(monkeypatch):
    doc = _completed_doc()
    monkeypatch.setattr(comp.cosmos_client, "database", object())
    monkeypatch.setattr(comp.cosmos_client, "get_document", AsyncMock(return_value=doc))
    monkeypatch.setattr(comp.cosmos_client, "upsert_document", AsyncMock())
    monkeypatch.setattr(comp, "_MAX_PAYLOAD_BYTES", 20)  # tiny budget

    monkeypatch.setattr(pipeline_mod, "map_controls_to_azure_policies",
                        lambda extraction, config: [_fake_mapping()])
    monkeypatch.setattr(pipeline_mod, "validate_mappings",
                        lambda extraction, mappings: types.SimpleNamespace())
    monkeypatch.setattr(pipeline_mod.PipelineConfig, "from_env",
                        classmethod(lambda cls: types.SimpleNamespace(validate=lambda: [])))

    def fake_build(extraction, mappings, validation, output_dir, allowed_locations=None):
        from pathlib import Path
        p = Path(output_dir) / "big.json"
        p.write_text("x" * 5000, encoding="utf-8")
        return [str(p)]

    monkeypatch.setattr(pipeline_mod, "build_initiative_artifacts", fake_build)
    created = AsyncMock(return_value={"id": "v1", "version_number": 1})
    monkeypatch.setattr(comp.version_service, "create_version", created)
    monkeypatch.setattr(comp.audit_service, "write_audit", AsyncMock())

    await comp._run_build_job("c1", "me@example.com")

    payload = created.await_args.kwargs["artifact_payload"]
    assert payload["files"] == []
    assert "big.json" in payload["omitted_files"]


# ── Build routes ──────────────────────────────────────────────────────────────

def _client(monkeypatch, **cosmos_methods):
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


def test_build_requires_completed_comparison(monkeypatch):
    doc = {"id": "c1", "userId": "me@example.com", "status": "running"}
    client = _client(monkeypatch, get_document=AsyncMock(return_value=doc))
    try:
        resp = client.post(f"{_API}/comparison/c1/build-initiative")
        assert resp.status_code == 400
    finally:
        _teardown()


def test_build_requires_internal_controls(monkeypatch):
    doc = {"id": "c1", "userId": "me@example.com", "status": "completed",
           "result": {"matches": []}}
    client = _client(monkeypatch, get_document=AsyncMock(return_value=doc))
    try:
        resp = client.post(f"{_API}/comparison/c1/build-initiative")
        assert resp.status_code == 400
    finally:
        _teardown()


def test_build_conflicts_when_already_building(monkeypatch):
    doc = _completed_doc()
    doc["buildStatus"] = "building"
    client = _client(monkeypatch, get_document=AsyncMock(return_value=doc))
    try:
        resp = client.post(f"{_API}/comparison/c1/build-initiative")
        assert resp.status_code == 409
    finally:
        _teardown()


def test_build_returns_existing_when_completed(monkeypatch):
    doc = _completed_doc()
    doc["buildStatus"] = "completed"
    doc["buildVersionId"] = "v7"
    doc["buildVersionNumber"] = 7
    client = _client(monkeypatch, get_document=AsyncMock(return_value=doc))
    try:
        resp = client.post(f"{_API}/comparison/c1/build-initiative")
        assert resp.status_code == 200
        body = resp.json()
        assert body["buildStatus"] == "completed"
        assert body["buildVersionId"] == "v7"
    finally:
        _teardown()


def test_build_schedules_job_and_marks_building(monkeypatch):
    doc = _completed_doc()
    monkeypatch.setattr(comp, "_run_build_job", AsyncMock())
    monkeypatch.setattr(comp.audit_service, "write_audit", AsyncMock())
    client = _client(
        monkeypatch,
        get_document=AsyncMock(return_value=doc),
        upsert_document=AsyncMock(),
    )
    try:
        resp = client.post(f"{_API}/comparison/c1/build-initiative")
        assert resp.status_code == 200
        assert resp.json()["buildStatus"] == "building"
        comp._run_build_job.assert_awaited_once()
    finally:
        _teardown()


def test_build_status_cross_user_404(monkeypatch):
    other = {"id": "c1", "userId": "other@example.com", "status": "completed"}
    client = _client(monkeypatch, get_document=AsyncMock(return_value=other))
    try:
        resp = client.get(f"{_API}/comparison/c1/build-status")
        assert resp.status_code == 404
    finally:
        _teardown()


def test_build_status_reports_fields(monkeypatch):
    doc = {"id": "c1", "userId": "me@example.com", "buildStatus": "completed",
           "buildVersionId": "v1", "buildVersionNumber": 1}
    client = _client(monkeypatch, get_document=AsyncMock(return_value=doc))
    try:
        resp = client.get(f"{_API}/comparison/c1/build-status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["buildStatus"] == "completed"
        assert body["buildVersionNumber"] == 1
    finally:
        _teardown()


# ── Version routes ────────────────────────────────────────────────────────────

import app.api.routes.version as ver


def _ver_client(monkeypatch):
    monkeypatch.setattr(ver.cosmos_client, "database", object())
    app.dependency_overrides[get_current_user] = lambda: User(
        oid="u1", email="me@example.com", name="Me"
    )
    return TestClient(app)


def test_versions_list(monkeypatch):
    rows = [{"id": "v2", "version_number": 2}, {"id": "v1", "version_number": 1}]
    monkeypatch.setattr(ver.version_service, "list_version_summaries", AsyncMock(return_value=rows))
    client = _ver_client(monkeypatch)
    try:
        resp = client.get(f"{_API}/versions")
        assert resp.status_code == 200
        assert resp.json()["versions"] == rows
    finally:
        _teardown()


def test_version_get_cross_user_404(monkeypatch):
    other = {"id": "v1", "userId": "other@example.com"}
    monkeypatch.setattr(ver.version_service, "get_version", AsyncMock(return_value=other))
    client = _ver_client(monkeypatch)
    try:
        resp = client.get(f"{_API}/versions/v1")
        assert resp.status_code == 404
    finally:
        _teardown()


def test_version_get_ok(monkeypatch):
    own = {"id": "v1", "userId": "me@example.com", "version_number": 1,
           "artifact_payload": {"files": []}, "_etag": "x"}
    monkeypatch.setattr(ver.version_service, "get_version", AsyncMock(return_value=own))
    client = _ver_client(monkeypatch)
    try:
        resp = client.get(f"{_API}/versions/v1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["version_number"] == 1
        assert "_etag" not in body          # scrubbed
    finally:
        _teardown()


def test_version_revert_creates_new(monkeypatch):
    new = {"id": "v2", "userId": "me@example.com", "version_number": 2, "parent_version": 1}
    revert = AsyncMock(return_value=new)
    monkeypatch.setattr(ver.version_service, "revert_to_version", revert)
    monkeypatch.setattr(ver.audit_service, "write_audit", AsyncMock())
    client = _ver_client(monkeypatch)
    try:
        resp = client.post(f"{_API}/versions/v1/revert")
        assert resp.status_code == 200
        assert resp.json()["version_number"] == 2
        revert.assert_awaited_once_with("me@example.com", "v1")
    finally:
        _teardown()


def test_version_download_returns_payload(monkeypatch):
    own = {"id": "v1", "userId": "me@example.com",
           "artifact_payload": {"files": [{"name": "x.json", "content": "{}"}]}}
    monkeypatch.setattr(ver.version_service, "get_version", AsyncMock(return_value=own))
    monkeypatch.setattr(ver.audit_service, "write_audit", AsyncMock())
    client = _ver_client(monkeypatch)
    try:
        resp = client.get(f"{_API}/versions/v1/download")
        assert resp.status_code == 200
        assert resp.json()["files"][0]["name"] == "x.json"
    finally:
        _teardown()


# ── Immutable-revert gate (version_service, fake cosmos) ───────────────────────

@pytest.mark.asyncio
async def test_revert_copies_bundle_without_mutating_target(monkeypatch):
    target = {
        "id": "v1", "userId": "me@example.com", "version_number": 1,
        "artifact_payload": {"files": [{"name": "initiative.json", "content": "{}"}]},
        "sourceComparisonId": "c1",
    }
    inserted = {}

    async def fake_get(container, doc_id, partition_key=None):
        return dict(target) if doc_id == "v1" else None

    async def fake_query(container, query, parameters=None, partition_key=None):
        return [1]  # current MAX(version_number)

    async def fake_insert(container, body):
        inserted.update(body)
        return body

    monkeypatch.setattr(vs.cosmos_client, "database", object())
    monkeypatch.setattr(vs.cosmos_client, "ensure_container", AsyncMock())
    monkeypatch.setattr(vs.cosmos_client, "get_document", fake_get)
    monkeypatch.setattr(vs.cosmos_client, "query_documents", fake_query)
    monkeypatch.setattr(vs.cosmos_client, "insert_document", fake_insert)

    new_version = await vs.revert_to_version("me@example.com", "v1")

    assert new_version["version_number"] == 2
    assert new_version["parent_version"] == 1
    # bundle copied verbatim
    assert new_version["artifact_payload"] == target["artifact_payload"]
    assert new_version["metadata"]["reverted_from_version"] == 1
    # target untouched
    assert target["version_number"] == 1
    assert "reverted_from_version" not in target.get("metadata", {})
