"""Connection-pooling guards for the frontend API client.

The ``APIClient`` is a process-wide ``@st.cache_resource`` singleton shared
across sessions. These tests lock in that per-call clients (a) reuse one shared
keep-alive connection pool and (b) still carry only the *current* caller's auth
headers, so a pooled connection can never leak one user's token to another.
"""

import utils.auth as auth
from utils.api_client import APIClient, _SharedHTTPTransport


def test_get_client_reuses_one_shared_connection_pool(monkeypatch):
    monkeypatch.setattr(auth, "get_backend_auth_headers", lambda: {})
    client = APIClient(base_url="https://backend.internal")
    a = client._get_client()
    b = client._get_client()
    try:
        assert a._transport is b._transport
        assert isinstance(a._transport, _SharedHTTPTransport)
    finally:
        a.close()
        b.close()


def test_shared_transport_survives_a_per_call_client_close(monkeypatch):
    monkeypatch.setattr(auth, "get_backend_auth_headers", lambda: {})
    client = APIClient(base_url="https://backend.internal")
    first = client._get_client()
    pool = first._transport
    first.close()  # a finished 'with' block must not tear down the shared pool
    second = client._get_client()
    try:
        assert second._transport is pool
    finally:
        second.close()


def test_each_call_carries_fresh_auth_headers(monkeypatch):
    """No cross-user token leak: headers are resolved per call even though the
    underlying connection pool is shared."""
    tokens = iter(["tok-alice", "tok-bob"])
    monkeypatch.setattr(
        auth,
        "get_backend_auth_headers",
        lambda: {"X-MS-TOKEN-AAD-ACCESS-TOKEN": next(tokens)},
    )
    client = APIClient(base_url="https://backend.internal")
    a = client._get_client()
    b = client._get_client()
    try:
        assert a.headers["X-MS-TOKEN-AAD-ACCESS-TOKEN"] == "tok-alice"
        assert b.headers["X-MS-TOKEN-AAD-ACCESS-TOKEN"] == "tok-bob"
        assert a._transport is b._transport  # same pool, isolated headers
    finally:
        a.close()
        b.close()
