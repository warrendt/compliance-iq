"""The frontend must surface the backend's error ``detail`` (the real ARM cause,
e.g. ``PolicyDefinitionNotFound``) on a failed deploy/validate instead of a bare
"Server error '502 Bad Gateway'" that hides what actually went wrong.
"""

import json

import httpx
import pytest

from utils.api_client import _raise_for_status_with_detail


def _response(status: int, body) -> httpx.Response:
    request = httpx.Request("POST", "https://backend.internal/api/v1/deploy/initiative")
    if isinstance(body, (dict, list)):
        content = json.dumps(body).encode()
        headers = {"content-type": "application/json"}
    else:
        content = str(body).encode()
        headers = {"content-type": "text/plain"}
    return httpx.Response(status, request=request, content=content, headers=headers)


def test_raises_backend_detail_on_error():
    resp = _response(502, {"detail": "PolicyDefinitionNotFound: aeedaca3-... not found"})
    with pytest.raises(RuntimeError) as exc:
        _raise_for_status_with_detail(resp)
    assert "PolicyDefinitionNotFound" in str(exc.value)


def test_noop_on_success():
    resp = _response(200, {"status": "deployed"})
    # Must not raise for a 2xx response
    _raise_for_status_with_detail(resp)


def test_falls_back_to_status_when_no_detail():
    resp = _response(500, "internal error")
    with pytest.raises(httpx.HTTPStatusError):
        _raise_for_status_with_detail(resp)
