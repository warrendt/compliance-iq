"""
Microsoft Learn Client for Azure Policy Discovery.
Searches Microsoft Learn documentation to find relevant Azure Policies.
"""

import logging
import httpx
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)


class MicrosoftLearnClient:
    """Client for Microsoft Learn search API."""
    
    def __init__(self):
        """Initialize Microsoft Learn client."""
        self.search_url = "https://learn.microsoft.com/api/search"
        self.timeout = 30.0
    
    async def search_azure_policies(
        self,
        control_name: str,
        description: str,
        domain: Optional[str] = None
    ) -> List[Dict]:
        """
        Search Microsoft Learn for relevant Azure Policies.
        
        Args:
            control_name: Name of the security control
            description: Description of what the control requires
            domain: Security domain (e.g., "Identity", "Network", "Data Protection")
            
        Returns:
            List of relevant Azure Policy documents with IDs and descriptions
        """
        logger.info(f"Searching Microsoft Learn for: {control_name}")
        
        try:
            # Build a concise, targeted search query
            query = f"Azure Policy built-in {control_name[:60]}"
            if domain:
                query += f" {domain[:30]}"
            
            logger.info(f"Search query: {query}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Primary search for Azure Policies
                results = await self._search_docs(client, query)
                
                # If sovereignty-relevant, do an additional SLZ search
                desc_lower = f"{control_name} {description}".lower()
                sovereignty_keywords = [
                    "data residency", "location", "region", "encryption", "encrypt",
                    "customer-managed key", "cmk", "byok", "confidential",
                    "trusted launch", "secure boot", "lockbox",
                ]
                if any(kw in desc_lower for kw in sovereignty_keywords):
                    slz_query = f"Azure Policy Sovereignty Baseline {control_name[:40]}"
                    logger.info(f"Adding SLZ search: {slz_query}")
                    slz_results = await self._search_docs(client, slz_query, max_results=3)
                    results.extend(slz_results)
                
                # Extract policy info from results
                policies = self._extract_policy_info(results)
                logger.info(f"Found {len(policies)} relevant policies")
                return policies
                
        except Exception as e:
            logger.error(f"Failed to search Microsoft Learn: {e}")
            return []
    
    async def _search_docs(
        self,
        client: httpx.AsyncClient,
        query: str,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Search Microsoft Learn documentation.
        
        Args:
            client: HTTP client
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of search results
        """
        try:
            params = {
                "search": query,
                "locale": "en-us",
                "$top": max_results,
                "scope": "Azure",
            }
            
            response = await client.get(self.search_url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                logger.info(f"Microsoft Learn returned {len(results)} results")
                return results
            else:
                logger.warning(f"Search API returned {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Search request failed: {e}")
            return []
    
    def _extract_policy_info(self, search_results: List[Dict]) -> List[Dict]:
        """
        Extract Azure Policy IDs and information from search results.
        
        Args:
            search_results: Raw search results from Microsoft Learn
            
        Returns:
            List of policy information dictionaries
        """
        policies = []
        seen_urls = set()
        guid_pattern = re.compile(
            r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            re.IGNORECASE
        )
        
        for result in search_results:
            try:
                title = result.get("title", "")
                url = result.get("url", "")
                description = result.get("description", "")
                
                # Deduplicate
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Look for policy GUID in URL
                match = guid_pattern.search(url)
                policy_id = match.group(0) if match else None
                
                # Include results that have a policy ID or mention policy in title
                if policy_id or "policy" in title.lower():
                    policies.append({
                        "policy_id": policy_id or "See documentation",
                        "policy_name": title,
                        "description": description[:200],
                        "learn_url": url
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to extract policy info: {e}")
                continue
        
        return policies


def get_microsoft_learn_client() -> MicrosoftLearnClient:
    """Get Microsoft Learn client instance."""
    return MicrosoftLearnClient()
