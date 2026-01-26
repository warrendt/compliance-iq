"""
Microsoft Learn MCP Client for Azure Policy Discovery.
Integrates with Microsoft Learn documentation to find relevant Azure Policies.
"""

import logging
import httpx
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)


class MicrosoftLearnClient:
    """Client for Microsoft Learn MCP server."""
    
    def __init__(self):
        """Initialize Microsoft Learn client."""
        self.base_url = "https://learn.microsoft.com/api"
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
            # Build search query - keep it concise to avoid 400 errors
            query_parts = [control_name[:50]]  # Limit control name length
            if domain:
                query_parts.append(domain[:30])
            # Add first 50 chars of description
            if description:
                query_parts.append(description[:50])
            
            search_query = " ".join(query_parts)
            full_query = f"Azure Policy {search_query} security compliance"
            
            logger.info(f"Built search query (length={len(full_query)}): {full_query}")
            logger.debug(f"Query components - name: '{control_name[:50]}', domain: '{domain[:30] if domain else 'N/A'}', desc: '{description[:50] if description else 'N/A'}'")
            
            # Search for Azure Policy documentation
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Search the documentation
                search_results = await self._search_docs(
                    client,
                    query=full_query
                )
                
                # Extract policy IDs and relevant info
                logger.info(f"Extracting policy info from {len(search_results)} search results")
                policies = await self._extract_policy_info(search_results)
                
                logger.info(f"✓ Found {len(policies)} relevant policies")
                for i, policy in enumerate(policies, 1):
                    logger.debug(f"  Policy {i}: {policy.get('policy_name', 'N/A')[:80]}")
                    logger.debug(f"    ID: {policy.get('policy_id', 'N/A')}")
                    logger.debug(f"    URL: {policy.get('learn_url', 'N/A')}")
                
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
            # Limit query length to avoid 400 errors
            original_length = len(query)
            if len(query) > 150:
                query = query[:150]
                logger.debug(f"Truncated query from {original_length} to 150 chars")
            
            # Build URL and params
            url = f"{self.base_url}/search"
            params = {
                "search": query,
                "facet": "category:Azure,products:Azure Policy",
                "top": max_results
            }
            
            logger.info(f"Calling Microsoft Learn API: {url}")
            logger.debug(f"Request params: {params}")
            
            # Use Microsoft Learn search API
            response = await client.get(url, params=params)
            
            logger.info(f"Microsoft Learn API response: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                logger.info(f"Microsoft Learn returned {len(results)} results")
                logger.debug(f"Response data keys: {list(data.keys())}")
                return results
            else:
                logger.warning(f"Search API returned {response.status_code}")
                try:
                    error_body = response.text[:500]
                    logger.debug(f"Error response body: {error_body}")
                except:
                    pass
                return []
                
        except Exception as e:
            logger.error(f"Search request failed: {e}")
            return []
    
    async def _extract_policy_info(self, search_results: List[Dict]) -> List[Dict]:
        """
        Extract Azure Policy IDs and information from search results.
        
        Args:
            search_results: Raw search results from Microsoft Learn
            
        Returns:
            List of policy information dictionaries
        """
        policies = []
        
        logger.debug(f"Processing {len(search_results)} search results for policy extraction")
        
        for idx, result in enumerate(search_results, 1):
            try:
                title = result.get("title", "")
                url = result.get("url", "")
                description = result.get("description", "")
                
                logger.debug(f"Result {idx}: {title[:60]}...")
                logger.debug(f"  URL: {url}")
                
                # Look for policy IDs in the content
                # Policy IDs are typically GUIDs or have format: /providers/Microsoft.Authorization/policyDefinitions/{guid}
                policy_id = self._extract_policy_id_from_url(url)
                
                if policy_id:
                    logger.debug(f"  ✓ Found policy ID: {policy_id}")
                elif "policy" in title.lower():
                    logger.debug(f"  ✓ Title contains 'policy', including result")
                else:
                    logger.debug(f"  ✗ No policy ID found, title doesn't contain 'policy', skipping")
                
                if policy_id or "policy" in title.lower():
                    policies.append({
                        "policy_id": policy_id or "See documentation",
                        "policy_name": title,
                        "description": description[:200],
                        "learn_url": url
                    })
                    
            except Exception as e:
                logger.warning(f"Failed to extract policy info from result {idx}: {e}")
                continue
        
        return policies
    
    def _extract_policy_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract Azure Policy ID from documentation URL.
        
        Args:
            url: Documentation URL
            
        Returns:
            Policy ID if found, None otherwise
        """
        # Look for GUID pattern (Azure Policy IDs are GUIDs)
        import re
        guid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        
        match = re.search(guid_pattern, url, re.IGNORECASE)
        if match:
            return match.group(0)
        
        return None
    


def get_microsoft_learn_client() -> MicrosoftLearnClient:
    """Get Microsoft Learn client instance."""
    return MicrosoftLearnClient()
