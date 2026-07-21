"""
API Client for communicating with the FastAPI backend.
"""

import httpx
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
import streamlit as st

# ---------------------------------------------------------------------------
# API request/response log (session-scoped ring buffer)
# ---------------------------------------------------------------------------
_MAX_LOG_ENTRIES = 100

# Backend /api/v1/policy/details caps policy_ids at 100 per request; the client
# chunks larger lists into batches of this size and merges the results.
_POLICY_DETAILS_BATCH_SIZE = 100


def _ensure_log() -> deque:
    """Return the session-scoped API log deque."""
    if "api_logs" not in st.session_state:
        st.session_state["api_logs"] = deque(maxlen=_MAX_LOG_ENTRIES)
    return st.session_state["api_logs"]


def _on_response(response: httpx.Response) -> None:
    """httpx event hook — called after every response.

    In httpx 0.27+, the hook fires before the response body is consumed, so
    ``response.elapsed`` and ``response.text`` are both unavailable at this
    point.  Calling ``response.read()`` buffers the body which (a) makes
    ``elapsed`` available and (b) lets ``response.text`` work; the buffered
    bytes are cached by httpx so the caller's ``.json()`` / ``.text`` calls
    still work normally.
    """
    try:
        response.read()
    except Exception:
        pass  # network error or already-read response — carry on

    elapsed_ms = 0
    try:
        elapsed_ms = response.elapsed.total_seconds() * 1000
    except Exception:
        pass

    req = response.request

    # Truncate bodies for display
    # req.content raises httpx.RequestNotRead for streaming/multipart uploads
    # (e.g. PDF file uploads) where the request body was never buffered.
    req_body = ""
    try:
        if req.content:
            req_body = req.content.decode("utf-8", errors="replace")[:2048]
    except Exception:
        req_body = "<multipart/binary>"

    resp_body = ""
    try:
        resp_body = response.text[:2048]
    except Exception:
        resp_body = ""

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": str(req.method),
        "url": str(req.url),
        "status": response.status_code,
        "elapsed_ms": round(elapsed_ms, 1),
        "request_body": req_body,
        "response_body": resp_body,
        "error": None,
    }

    try:
        _ensure_log().append(entry)
    except Exception:
        pass  # outside Streamlit context (e.g. tests)


def _raise_for_status_with_detail(response: httpx.Response) -> None:
    """Raise a clear error carrying the backend's ``detail`` on 4xx/5xx.

    ``httpx.Response.raise_for_status`` surfaces only the status line (e.g.
    "Server error '502 Bad Gateway'"), hiding the FastAPI ``{"detail": ...}``
    body — which for deploy failures is the real ARM error (e.g.
    ``PolicyDefinitionNotFound``). Extract it so the UI shows the true cause.
    """
    if response.status_code < 400:
        return
    detail = None
    try:
        body = response.json()
        if isinstance(body, dict):
            detail = body.get("detail")
    except Exception:
        detail = None
    if detail:
        raise RuntimeError(str(detail))
    response.raise_for_status()


class _SharedHTTPTransport(httpx.HTTPTransport):
    """An ``httpx`` transport whose connection pool outlives per-request clients.

    ``httpx.Client.close()`` (called when a ``with client:`` block exits) closes
    the client's transport. We deliberately build a fresh, lightweight
    ``httpx.Client`` per request so each call carries only the *current* user's
    auth headers — the ``APIClient`` is a process-wide ``@st.cache_resource``
    singleton shared across sessions, so a single mutable pooled client would
    risk leaking one user's token onto another user's request. Sharing one
    underlying connection pool (this transport) across those per-call clients
    keeps TCP/TLS keep-alive reuse without that risk. Overriding ``close`` to a
    no-op stops a finished request from tearing down the shared pool; the pool
    is released when the process exits.
    """

    def close(self) -> None:  # keep the shared pool alive across requests
        pass


_shared_transport: Optional[_SharedHTTPTransport] = None


def _get_shared_transport() -> _SharedHTTPTransport:
    """Return the process-wide shared connection pool, creating it on first use."""
    global _shared_transport
    if _shared_transport is None:
        _shared_transport = _SharedHTTPTransport()
    return _shared_transport


class APIClient:
    """Client for interacting with the AI Mapping Agent backend API."""
    
    def __init__(self, base_url: str | None = None):
        """Initialize the API client.
        
        Args:
            base_url: Base URL of the backend API. If not provided, falls back to
                the BACKEND_URL environment variable, then localhost.
        """
        self.base_url = (base_url or os.getenv("BACKEND_URL") or "http://localhost:8000").rstrip("/")
        self.timeout = 120.0  # Default timeout (2 minutes for AI operations)
        
    def _get_client(self) -> httpx.Client:
        """Return a per-call HTTP client that reuses a shared connection pool.

        Auth headers are resolved on every call so each request carries the
        current user's token, while all clients share one keep-alive connection
        pool (see :class:`_SharedHTTPTransport`) so navigation reruns no longer
        pay a fresh TCP/TLS handshake per backend call.
        """
        headers: Dict[str, str] = {}
        try:
            from utils.auth import get_backend_auth_headers

            headers.update(get_backend_auth_headers())
        except Exception:
            pass  # auth module unavailable or no token
        return httpx.Client(
            timeout=self.timeout,
            headers=headers,
            transport=_get_shared_transport(),
            event_hooks={"response": [_on_response]},
        )
    
    def health_check(self) -> Dict[str, Any]:
        """Check if the backend is healthy.
        
        Returns:
            Health status information
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/health")
            response.raise_for_status()
            return response.json()
    
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_mcsb_controls(_self) -> List[Dict[str, Any]]:
        """Get all MCSB controls.

        Cached: the MCSB catalog is static reference data, so this avoids a
        backend round-trip on every rerun/navigation. Cache keyed only on the
        endpoint (``_self`` is excluded from the cache key by the leading
        underscore).

        Returns:
            List of MCSB controls
        """
        with _self._get_client() as client:
            response = client.get(f"{_self.base_url}/api/v1/mapping/mcsb/controls")
            response.raise_for_status()
            data = response.json()
            # Backend wraps the list in {"controls": [...]}
            if isinstance(data, dict) and "controls" in data:
                return data["controls"]
            return data
    
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_mcsb_domains(_self) -> List[str]:
        """Get all MCSB domains (cached static reference data).

        Returns:
            List of MCSB domain names
        """
        with _self._get_client() as client:
            response = client.get(f"{_self.base_url}/api/v1/mapping/mcsb/domains")
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and "domains" in data:
                return data["domains"]
            return data
    
    def map_single_control(
        self, 
        control_id: str,
        control_name: str,
        description: str,
        domain: Optional[str] = None,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """Map a single control to MCSB.
        
        Args:
            control_id: External control ID
            control_name: Control name
            description: Control description
            domain: Optional control domain
            timeout: Request timeout in seconds (default: 120)
            
        Returns:
            Mapping result with confidence score and reasoning
        """
        payload = {
            "control": {
                "control_id": control_id,
                "control_name": control_name,
                "description": description,
                "domain": domain
            }
        }
        
        # Use custom timeout for this request
        original_timeout = self.timeout
        self.timeout = timeout
        
        try:
            with self._get_client() as client:
                response = client.post(
                    f"{self.base_url}/api/v1/mapping/map-single",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        finally:
            self.timeout = original_timeout
    
    def map_batch_controls(
        self,
        controls: List[Dict[str, str]],
        concurrency: int = 5,
        timeout: float = 600.0
    ) -> Dict[str, Any]:
        """Map multiple controls concurrently via the batch endpoint.
        
        Args:
            controls: List of control dicts with control_id, control_name, description, domain
            concurrency: Max concurrent AI calls (1-10)
            timeout: Request timeout in seconds
            
        Returns:
            Batch result with mappings, total, mapped, failed, avg_confidence
        """
        payload = {
            "controls": controls,
            "concurrency": concurrency
        }
        
        original_timeout = self.timeout
        self.timeout = timeout
        
        try:
            with self._get_client() as client:
                response = client.post(
                    f"{self.base_url}/api/v1/mapping/map-batch",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        finally:
            self.timeout = original_timeout

    def start_batch_mapping(
        self,
        controls: List[Dict[str, str]],
        framework_name: str,
        concurrency: int = 1,
    ) -> str:
        """Start a batch mapping job.
        
        Args:
            controls: List of controls to map
            framework_name: Name of the framework
            
        Returns:
            Job ID for tracking progress
        """
        payload = {
            "controls": controls,
            "framework_name": framework_name,
            "concurrency": concurrency,
        }
        
        self.timeout = 600.0  # 10 minutes for batch jobs
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/mapping/analyze",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            return result.get("job_id")
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a mapping job.
        
        Args:
            job_id: Job ID to check
            
        Returns:
            Job status information
        """
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/mapping/status/{job_id}"
            )
            response.raise_for_status()
            return response.json()
    
    def generate_policy_initiative(
        self,
        mappings: List[Dict[str, Any]],
        framework_name: str,
        min_confidence: float = 0.7,
        session_id: Optional[str] = None,
        enforce_mode: bool = False,
        policy_parameter_values: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Generate an Azure Policy initiative.
        
        Args:
            mappings: List of control mappings
            framework_name: Name of the framework
            min_confidence: Minimum confidence threshold
            session_id: Session identifier for artifact persistence
            enforce_mode: When False (default), assignments use DoNotEnforce (audit-only).
                          When True, assignments use Default (enforcement enabled).
            policy_parameter_values: Optional operator-supplied values for
                          parameterized built-ins, keyed by policy GUID then
                          parameter name. Supplying every required value for a
                          built-in includes it (values baked in) instead of
                          dropping it.
            
        Returns:
            Policy initiative JSON
        """
        payload: Dict[str, Any] = {
            "mappings": mappings,
            "framework_name": framework_name,
            "min_confidence_threshold": min_confidence,
            "enforce_mode": enforce_mode,
        }
        if policy_parameter_values:
            payload["policy_parameter_values"] = policy_parameter_values
        headers = {}
        if session_id:
            headers["X-Session-ID"] = session_id
        
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/policy/generate",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def get_policy_details(self, policy_ids: List[str]) -> Dict[str, Any]:
        """Batch-lookup Azure Policy details by GUID (cached).

        The backend caps each request at ``_POLICY_DETAILS_BATCH_SIZE`` GUIDs,
        so requests are split into chunks and the results are merged. Without
        this, initiatives with more than 100 policies would 422 and the UI
        would fall back to showing bare GUIDs instead of policy names.

        Args:
            policy_ids: List of Azure Policy definition GUIDs

        Returns:
            Dict with 'policies' key mapping GUIDs to detail dicts
        """
        if not policy_ids:
            return {"requested": 0, "found": 0, "policies": {}}

        chunks = [
            policy_ids[i : i + _POLICY_DETAILS_BATCH_SIZE]
            for i in range(0, len(policy_ids), _POLICY_DETAILS_BATCH_SIZE)
        ]

        merged_policies: Dict[str, Any] = {}
        with self._get_client() as client:
            for chunk in chunks:
                response = client.post(
                    f"{self.base_url}/api/v1/policy/details",
                    json={"policy_ids": chunk},
                    timeout=60.0,
                )
                response.raise_for_status()
                merged_policies.update(response.json().get("policies", {}))

        return {
            "requested": len(policy_ids),
            "found": len(merged_policies),
            "policies": merged_policies,
        }

    # --- Sovereignty / SLZ endpoints ---

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_sovereignty_summary(_self) -> Dict[str, Any]:
        """Get SLZ policy data summary (cached static reference data)."""
        with _self._get_client() as client:
            response = client.get(f"{_self.base_url}/api/v1/sovereignty/summary")
            response.raise_for_status()
            return response.json()

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_sovereignty_objectives(_self) -> List[Dict[str, Any]]:
        """Get all sovereignty control objectives (cached static reference data)."""
        with _self._get_client() as client:
            response = client.get(f"{_self.base_url}/api/v1/sovereignty/objectives")
            response.raise_for_status()
            return response.json()

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_sovereignty_archetypes(_self) -> List[Dict[str, Any]]:
        """Get SLZ archetypes (cached static reference data)."""
        with _self._get_client() as client:
            response = client.get(f"{_self.base_url}/api/v1/sovereignty/archetypes")
            response.raise_for_status()
            return response.json()

    def get_sovereignty_policies(
        self,
        level: Optional[str] = None,
        service: Optional[str] = None,
        objective: Optional[str] = None,
        q: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query SLZ policies with optional filters."""
        params: Dict[str, str] = {}
        if level:
            params["level"] = level
        if service:
            params["service"] = service
        if objective:
            params["objective"] = objective
        if q:
            params["q"] = q
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/sovereignty/policies",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    def generate_slz_initiatives(
        self,
        mappings: List[Dict[str, Any]],
        framework_name: str,
        allowed_locations: Optional[List[str]] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate SLZ per-archetype policy initiatives.

        Args:
            mappings: Control mappings (must contain sovereignty data)
            framework_name: Compliance framework name
            allowed_locations: Optional Azure regions for data residency
            session_id: Session identifier for artifact persistence

        Returns:
            Per-archetype artifacts dict
        """
        payload: Dict[str, Any] = {
            "framework_name": framework_name,
            "mappings": mappings,
        }
        if allowed_locations:
            payload["allowed_locations"] = allowed_locations

        headers = {}
        if session_id:
            headers["X-Session-ID"] = session_id

        self.timeout = 120.0
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/policy/generate/slz",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    # --- Artifact retrieval ---

    def list_artifacts(
        self,
        artifact_type: Optional[str] = None,
        limit: int = 20,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List recently generated policy artifacts.

        Args:
            artifact_type: Filter by type (mcsb_initiative, slz_initiative)
            limit: Max number of results
            session_id: Session identifier for header

        Returns:
            Dict with 'artifacts' list and 'total' count
        """
        params: Dict[str, Any] = {"limit": limit}
        if artifact_type:
            params["artifact_type"] = artifact_type

        headers = {}
        if session_id:
            headers["X-Session-ID"] = session_id

        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/policy/artifacts",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def get_artifact(self, artifact_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve a single generated artifact by ID.

        Args:
            artifact_id: Artifact UUID
            session_id: Session identifier for header

        Returns:
            Full artifact document
        """
        headers = {}
        if session_id:
            headers["X-Session-ID"] = session_id

        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/policy/artifacts/{artifact_id}",
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    def sync_slz_policies(self, fallback: bool = False) -> Dict[str, Any]:
        """Trigger an SLZ data sync on the backend."""
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/sovereignty/admin/sync-slz",
                params={"fallback": str(fallback).lower()},
            )
            response.raise_for_status()
            return response.json()

    # --- PDF Pipeline endpoints ---

    def run_pipeline(
        self,
        pdf_bytes: bytes,
        filename: str,
        min_confidence: float = 0.5,
        allowed_locations: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a compliance PDF for end-to-end pipeline processing.

        Args:
            pdf_bytes: Raw PDF file bytes
            filename: Original filename
            min_confidence: Minimum mapping confidence threshold
            allowed_locations: Optional comma-separated Azure regions

        Returns:
            Dict with job_id and initial status
        """
        data: Dict[str, str] = {"min_confidence": str(min_confidence)}
        if allowed_locations:
            data["allowed_locations"] = allowed_locations

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/api/v1/pipeline/run",
                files={"pdf_file": (filename, pdf_bytes, "application/pdf")},
                data=data,
            )
            response.raise_for_status()
            return response.json()

    def extract_controls_from_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """Extract controls from a compliance PDF (Stages 1-2 only).

        Returns controls in CSV-flow format ready for session_state.controls.

        Args:
            pdf_bytes: Raw PDF file bytes
            filename: Original filename

        Returns:
            Dict with framework_name, controls list, total_controls, etc.
        """
        saved_timeout = self.timeout
        self.timeout = 300.0  # PDF extraction can be slow
        try:
            with self._get_client() as client:
                response = client.post(
                    f"{self.base_url}/api/v1/pipeline/extract",
                    files={"pdf_file": (filename, pdf_bytes, "application/pdf")},
                )
                response.raise_for_status()
                return response.json()
        finally:
            self.timeout = saved_timeout

    def start_pdf_extraction(
        self,
        pdf_bytes: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """Submit PDF extraction and return immediately with a pollable job ID."""
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/pipeline/extract/jobs",
                files={"pdf_file": (filename, pdf_bytes, "application/pdf")},
            )
            response.raise_for_status()
            return response.json()

    def get_pipeline_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a pipeline job.

        Args:
            job_id: Pipeline job identifier

        Returns:
            Job status with progress, stage, and result info
        """
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/pipeline/status/{job_id}"
            )
            response.raise_for_status()
            return response.json()

    def cancel_pipeline_job(self, job_id: str) -> Dict[str, Any]:
        """Request cooperative cancellation of an active PDF pipeline job."""
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/pipeline/status/{job_id}/cancel"
            )
            response.raise_for_status()
            return response.json()

    def get_pipeline_logs(self, job_id: str, since: int = 0) -> Dict[str, Any]:
        """Fetch debug logs for a pipeline job (when enabled on backend).

        Args:
            job_id: Pipeline job identifier
            since: Cursor offset to fetch new log entries

        Returns:
            Dict with logs list and next_cursor; raises if logging disabled.
        """
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/pipeline/logs/{job_id}",
                params={"since": since},
            )
            response.raise_for_status()
            return response.json()

    def download_pipeline_output(self, job_id: str) -> bytes:
        """Download the pipeline output as a ZIP archive.

        Args:
            job_id: Pipeline job identifier

        Returns:
            Raw ZIP bytes
        """
        with httpx.Client(timeout=60.0) as client:
            response = client.get(
                f"{self.base_url}/api/v1/pipeline/download/{job_id}"
            )
            response.raise_for_status()
            return response.content

    def repack_pipeline_output(self, job_id: str, mappings_csv: str) -> bytes:
        """Repack the initiative ZIP with edited mappings CSV.

        Args:
            job_id: Pipeline job identifier
            mappings_csv: Edited CSV content

        Returns:
            Raw ZIP bytes
        """
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.base_url}/api/v1/pipeline/repack/{job_id}",
                json={"mappings_csv": mappings_csv},
            )
            response.raise_for_status()
            return response.content

    def get_pipeline_artifacts(self, job_id: str) -> Dict[str, Any]:
        """Fetch parsed pipeline artifacts for review/edit.

        Args:
            job_id: Pipeline job identifier

        Returns:
            Dict with initiative, groups, policies, params, validation_report, mappings
        """
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/pipeline/artifacts/{job_id}"
            )
            response.raise_for_status()
            return response.json()

    def run_pipeline_selftest(
        self,
        pdf_url: str = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        min_confidence: float = 0.5,
        allowed_locations: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Trigger the backend self-test pipeline run using a public PDF.

        Returns:
            Dict with job_id and status
        """
        data: Dict[str, str] = {"min_confidence": str(min_confidence), "pdf_url": pdf_url}
        if allowed_locations:
            data["allowed_locations"] = allowed_locations

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{self.base_url}/api/v1/pipeline/selftest",
                data=data,
            )
            response.raise_for_status()
            return response.json()

    def list_pipeline_jobs(self) -> List[Dict[str, Any]]:
        """List all pipeline jobs.

        Returns:
            List of pipeline job summaries
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/pipeline/jobs")
            response.raise_for_status()
            return response.json()

    # --- Deploy & Explorer endpoints ---

    def list_deploy_scopes(self) -> Dict[str, Any]:
        """List subscriptions and management groups visible to the caller."""
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/deploy/scopes")
            _raise_for_status_with_detail(response)
            return response.json()

    def validate_deploy(
        self, scope: str, initiative_name: str, initiative_body: dict
    ) -> Dict[str, Any]:
        """Non-destructive validation of an initiative (no tenant writes)."""
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/deploy/validate",
                json={
                    "scope": scope,
                    "initiative_name": initiative_name,
                    "initiative_body": initiative_body,
                },
            )
            _raise_for_status_with_detail(response)
            return response.json()

    def deploy_initiative_to_azure(
        self,
        scope: str,
        initiative_name: str,
        initiative_body: dict,
        assign: bool = False,
        assignment_display_name: Optional[str] = None,
        assignment_description: str = "",
        enforce_mode: bool = False,
        location: Optional[str] = None,
        trigger_scan: bool = True,
    ) -> Dict[str, Any]:
        """Deploy a policy set definition (and optionally assign it).

        ``enforce_mode`` controls the assignment's enforcement: when False
        (default) the assignment is created with ``DoNotEnforce`` (audit-only —
        compliance is still assessed, effects are never applied/remediated).

        ``trigger_scan`` (default True) asks the backend to fire an on-demand
        compliance evaluation after a successful assignment so results refresh
        without waiting for Azure Policy's ~24h cycle. Best-effort and only for
        subscription/resource-group scopes.
        """
        payload: Dict[str, Any] = {
            "scope": scope,
            "initiative_name": initiative_name,
            "initiative_body": initiative_body,
            "assign": assign,
            "enforce_mode": enforce_mode,
            "trigger_scan": trigger_scan,
        }
        if assignment_display_name:
            payload["assignment_display_name"] = assignment_display_name
        if assignment_description:
            payload["assignment_description"] = assignment_description
        if location:
            payload["location"] = location
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/deploy/initiative",
                json=payload,
            )
            _raise_for_status_with_detail(response)
            return response.json()

    def list_policy_definitions_arm(
        self, scope: str, custom_only: bool = True
    ) -> Dict[str, Any]:
        """List policy definitions at scope via ARM."""
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/deploy/definitions",
                params={"scope": scope, "custom_only": str(custom_only).lower()},
            )
            response.raise_for_status()
            return response.json()

    def list_policy_initiatives_arm(
        self, scope: str, custom_only: bool = True
    ) -> Dict[str, Any]:
        """List initiative definitions at scope via ARM."""
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/deploy/initiatives",
                params={"scope": scope, "custom_only": str(custom_only).lower()},
            )
            response.raise_for_status()
            return response.json()

    def list_policy_assignments_arm(self, scope: str) -> Dict[str, Any]:
        """List policy assignments at scope via ARM."""
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/deploy/assignments",
                params={"scope": scope},
            )
            response.raise_for_status()
            return response.json()

    # --- Backend application logs ---

    def get_backend_logs(
        self,
        since: int = 0,
        level: str = "DEBUG",
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Fetch recent application log entries from the backend's in-memory buffer.

        Args:
            since: Sequence cursor for incremental polling.
            level: Minimum log level filter.
            limit: Max entries to return.

        Returns:
            Dict with ``logs``, ``next_cursor``, ``total_buffered``.
        """
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/health/logs",
                params={"since": since, "level": level, "limit": limit},
            )
            response.raise_for_status()
            return response.json()

    # --- Session persistence ---

    def save_session(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist critical session state to the backend (Cosmos DB).

        Args:
            session_id: Unique session identifier.
            payload: State dict to persist.

        Returns:
            Backend response.
        """
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/session/save",
                json={"session_id": session_id, **payload},
            )
            response.raise_for_status()
            return response.json()

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load a previously saved session from the backend.

        Args:
            session_id: Session identifier.

        Returns:
            Session state dict, or None if not found.
        """
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.base_url}/api/v1/session/{session_id}",
                )
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    def load_latest_session(self) -> Optional[Dict[str, Any]]:
        """Load the authenticated user's latest persisted workflow."""
        try:
            with self._get_client() as client:
                response = client.get(f"{self.base_url}/api/v1/session/latest")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    # --- User profile & history ---

    def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Fetch the current user's profile from the backend.

        Returns:
            Profile dict or None if unavailable.
        """
        try:
            with self._get_client() as client:
                response = client.get(f"{self.base_url}/api/v1/user/profile")
                if response.status_code == 401:
                    return None
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    def update_user_profile(self, display_name: Optional[str] = None, preferred_platform: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Update the current user's profile.

        Args:
            display_name: New display name (optional).
            preferred_platform: New preferred platform ID (optional).

        Returns:
            Updated profile dict or None on error.
        """
        payload: Dict[str, Any] = {}
        if display_name is not None:
            payload["displayName"] = display_name
        if preferred_platform is not None:
            payload["preferredPlatform"] = preferred_platform

        try:
            with self._get_client() as client:
                response = client.put(
                    f"{self.base_url}/api/v1/user/profile",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    def get_user_history(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch the user's activity history.

        Args:
            limit: Maximum number of events to return.
            event_type: Optional filter (``upload``, ``mapping``, ``export``).

        Returns:
            List of history event dicts.
        """
        params: Dict[str, Any] = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.base_url}/api/v1/user/history",
                    params=params,
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return []

    def get_user_uploads(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch the user's upload records.

        Returns:
            List of upload dicts.
        """
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.base_url}/api/v1/user/uploads",
                    params={"limit": limit},
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return []

    def get_user_mappings(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch the user's AI mapping results.

        Returns:
            List of mapping result dicts.
        """
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.base_url}/api/v1/user/mappings",
                    params={"limit": limit},
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return []

    def get_user_exports(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch the user's policy export records.

        Returns:
            List of export artifact dicts.
        """
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.base_url}/api/v1/user/exports",
                    params={"limit": limit},
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return []

    # ── Workspace activity recording (best-effort writers) ────────────────────
    # These persist the logged-in user's pipeline milestones (uploads, AI
    # mappings, exports, edits) so the "My Workspace" page reflects everything
    # they do in their tenant. All are best-effort: any failure returns None
    # and never blocks the UI. Identity is server-stamped from the Easy Auth
    # principal, so a client cannot forge another user's activity.

    def record_upload(
        self,
        *,
        file_name: str,
        file_type: str = "text/csv",
        category: str = "document",
        file_size: int = 0,
        row_count: int = 0,
        column_names: Optional[List[str]] = None,
        controls: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Record a document upload or control-set load for the current user.

        Best-effort: returns None on any failure so it never blocks the UI.
        """
        payload: Dict[str, Any] = {
            "fileName": file_name,
            "fileType": file_type,
            "category": category,
            "fileSize": file_size,
            "rowCount": row_count,
            "columnNames": column_names or [],
            "metadata": metadata or {},
        }
        if controls is not None:
            payload["controls"] = controls
        try:
            with self._get_client() as client:
                response = client.post(
                    f"{self.base_url}/api/v1/user/uploads",
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    def record_mappings(
        self,
        *,
        framework: str,
        mappings: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Record a batch of AI mapping results for the current user."""
        try:
            with self._get_client() as client:
                response = client.post(
                    f"{self.base_url}/api/v1/user/mappings",
                    json={
                        "framework": framework,
                        "mappings": mappings,
                        "metadata": metadata or {},
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    def record_export(
        self,
        *,
        framework: str,
        artifact_type: str = "initiative",
        control_count: int = 0,
        file_name: str = "",
        file_size: int = 0,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Record a generated/exported policy artifact for the current user."""
        try:
            with self._get_client() as client:
                response = client.post(
                    f"{self.base_url}/api/v1/user/exports",
                    json={
                        "framework": framework,
                        "artifactType": artifact_type,
                        "controlCount": control_count,
                        "fileName": file_name,
                        "fileSize": file_size,
                        "sessionId": session_id,
                        "metadata": metadata or {},
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    def record_activity(
        self,
        *,
        action: str,
        summary: str,
        resource_type: str = "edit",
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Record a generic activity (e.g. an edit) into the unified feed."""
        try:
            with self._get_client() as client:
                response = client.post(
                    f"{self.base_url}/api/v1/user/activity",
                    json={
                        "action": action,
                        "summary": summary,
                        "resourceType": resource_type,
                        "resourceId": resource_id,
                        "metadata": metadata or {},
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    def get_user_upload(self, upload_id: str) -> Dict[str, Any]:
        """Fetch a single stored control set (including its parsed ``controls``).

        Used by the workspace to rebuild a downloadable CSV on demand.

        Returns:
            The upload detail dict, or an empty dict on any failure.
        """
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.base_url}/api/v1/user/uploads/{upload_id}",
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return {}

    def get_user_export(
        self, export_id: str, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch a single export artifact including its downloadable ``content``.

        Args:
            export_id: The export/artifact id.
            session_id: Optional partition hint for an efficient point read.

        Returns:
            The export detail dict, or an empty dict on any failure.
        """
        try:
            params = {"session_id": session_id} if session_id else None
            with self._get_client() as client:
                response = client.get(
                    f"{self.base_url}/api/v1/user/exports/{export_id}",
                    params=params,
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return {}

    # ── Control comparison (diff) ─────────────────────────────────────────

    def list_comparison_frameworks(self) -> List[Dict[str, Any]]:
        """List external frameworks available for comparison.

        Returns:
            List of dicts with key, display_name, control_count.
        """
        try:
            with self._get_client() as client:
                response = client.get(
                    f"{self.base_url}/api/v1/comparison/frameworks"
                )
                response.raise_for_status()
                return response.json()
        except Exception:
            return []

    def run_comparison(
        self,
        pdf_bytes: bytes,
        filename: str,
        external_framework: str,
    ) -> Dict[str, Any]:
        """Start an internal-vs-external comparison job.

        Args:
            pdf_bytes: Raw internal control PDF bytes.
            filename: Original filename.
            external_framework: External framework key (see list_comparison_frameworks).

        Returns:
            Dict with comparison_id and initial status.
        """
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/comparison/run",
                files={"pdf_file": (filename, pdf_bytes, "application/pdf")},
                data={"external_framework": external_framework},
            )
            response.raise_for_status()
            return response.json()

    def get_comparison_status(self, comparison_id: str) -> Dict[str, Any]:
        """Poll the status of a comparison job."""
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/comparison/status/{comparison_id}"
            )
            response.raise_for_status()
            return response.json()

    def get_comparison(self, comparison_id: str) -> Dict[str, Any]:
        """Fetch the full comparison result document."""
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/comparison/{comparison_id}"
            )
            response.raise_for_status()
            return response.json()

    def list_comparisons(self) -> List[Dict[str, Any]]:
        """List the current user's comparisons (newest first)."""
        try:
            with self._get_client() as client:
                response = client.get(f"{self.base_url}/api/v1/comparison")
                response.raise_for_status()
                return response.json().get("comparisons", [])
        except Exception:
            return []

    # ── Initiative build (full union) + versions ──────────────────────────────

    def build_initiative(self, comparison_id: str) -> Dict[str, Any]:
        """Kick off (or return) an initiative build for a completed comparison."""
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/comparison/{comparison_id}/build-initiative"
            )
            response.raise_for_status()
            return response.json()

    def get_build_status(self, comparison_id: str) -> Dict[str, Any]:
        """Poll the status of an initiative build for a comparison."""
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/comparison/{comparison_id}/build-status"
            )
            response.raise_for_status()
            return response.json()

    def list_versions(self) -> List[Dict[str, Any]]:
        """List the current user's policy versions (newest first, metadata only)."""
        try:
            with self._get_client() as client:
                response = client.get(f"{self.base_url}/api/v1/versions")
                response.raise_for_status()
                return response.json().get("versions", [])
        except Exception:
            return []

    def get_version(self, version_id: str) -> Dict[str, Any]:
        """Fetch a single version document (including its artifact bundle)."""
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/versions/{version_id}")
            response.raise_for_status()
            return response.json()

    def download_version(self, version_id: str) -> Dict[str, Any]:
        """Fetch just the artifact payload (files) for a version."""
        with self._get_client() as client:
            response = client.get(
                f"{self.base_url}/api/v1/versions/{version_id}/download"
            )
            response.raise_for_status()
            return response.json()

    def revert_version(self, version_id: str) -> Dict[str, Any]:
        """Revert by creating a new version that copies the target's bundle."""
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/versions/{version_id}/revert"
            )
            response.raise_for_status()
            return response.json()


@st.cache_resource
def get_api_client() -> APIClient:
    """Get a cached API client instance.
    
    Returns:
        Singleton API client
    """
    return APIClient()
