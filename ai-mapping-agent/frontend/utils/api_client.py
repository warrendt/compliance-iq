"""
API Client for communicating with the FastAPI backend.
"""

import httpx
import os
from typing import Dict, List, Any, Optional
import streamlit as st


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
        """Get an HTTP client with configured timeout."""
        return httpx.Client(timeout=self.timeout)
    
    def health_check(self) -> Dict[str, Any]:
        """Check if the backend is healthy.
        
        Returns:
            Health status information
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/health")
            response.raise_for_status()
            return response.json()
    
    def get_mcsb_controls(self) -> List[Dict[str, Any]]:
        """Get all MCSB controls.
        
        Returns:
            List of MCSB controls
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/mapping/mcsb/controls")
            response.raise_for_status()
            return response.json()
    
    def get_mcsb_domains(self) -> List[str]:
        """Get all MCSB domains.
        
        Returns:
            List of MCSB domain names
        """
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/mapping/mcsb/domains")
            response.raise_for_status()
            return response.json()
    
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
        framework_name: str
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
            "framework_name": framework_name
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
        min_confidence: float = 0.7
    ) -> Dict[str, Any]:
        """Generate an Azure Policy initiative.
        
        Args:
            mappings: List of control mappings
            framework_name: Name of the framework
            min_confidence: Minimum confidence threshold
            
        Returns:
            Policy initiative JSON
        """
        payload = {
            "mappings": mappings,
            "framework_name": framework_name,
            "min_confidence": min_confidence
        }
        
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/policy/generate",
                json=payload
            )
            response.raise_for_status()
            return response.json()

    # --- Sovereignty / SLZ endpoints ---

    def get_sovereignty_summary(self) -> Dict[str, Any]:
        """Get SLZ policy data summary."""
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/sovereignty/summary")
            response.raise_for_status()
            return response.json()

    def get_sovereignty_objectives(self) -> List[Dict[str, Any]]:
        """Get all sovereignty control objectives."""
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/sovereignty/objectives")
            response.raise_for_status()
            return response.json()

    def get_sovereignty_archetypes(self) -> List[Dict[str, Any]]:
        """Get SLZ archetypes."""
        with self._get_client() as client:
            response = client.get(f"{self.base_url}/api/v1/sovereignty/archetypes")
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
    ) -> Dict[str, Any]:
        """Generate SLZ per-archetype policy initiatives.

        Args:
            mappings: Control mappings (must contain sovereignty data)
            framework_name: Compliance framework name
            allowed_locations: Optional Azure regions for data residency

        Returns:
            Per-archetype artifacts dict
        """
        payload: Dict[str, Any] = {
            "framework_name": framework_name,
            "mappings": mappings,
        }
        if allowed_locations:
            payload["allowed_locations"] = allowed_locations

        self.timeout = 120.0
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/policy/generate/slz",
                json=payload,
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


@st.cache_resource
def get_api_client() -> APIClient:
    """Get a cached API client instance.
    
    Returns:
        Singleton API client
    """
    return APIClient()
