"""
API Client for communicating with the FastAPI backend.
"""

import httpx
from typing import Dict, List, Any, Optional
import streamlit as st


class APIClient:
    """Client for interacting with the AI Mapping Agent backend API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """Initialize the API client.
        
        Args:
            base_url: Base URL of the backend API
        """
        self.base_url = base_url
        self.timeout = 30.0  # Default timeout
        
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
        domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """Map a single control to MCSB.
        
        Args:
            control_id: External control ID
            control_name: Control name
            description: Control description
            domain: Optional control domain
            
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
        
        with self._get_client() as client:
            response = client.post(
                f"{self.base_url}/api/v1/mapping/map-single",
                json=payload
            )
            response.raise_for_status()
            return response.json()
    
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
        
        self.timeout = 300.0  # 5 minutes for batch jobs
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


@st.cache_resource
def get_api_client() -> APIClient:
    """Get a cached API client instance.
    
    Returns:
        Singleton API client
    """
    return APIClient()
