"""
Cosmos DB client for data persistence
"""
import os
from typing import List, Dict, Any, Optional, Union
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey, exceptions
from azure.identity.aio import DefaultAzureCredential
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _sanitize_document_for_write(document: Dict[str, Any]) -> None:
    """Mutate a document in place so Cosmos accepts it.

    Documents built from ``BaseDocument`` always carry a ``ttl`` key which is
    ``None`` unless explicitly set. Cosmos rejects an explicit ``ttl: null`` on a
    TTL-enabled container ("The input ttl 'null' is invalid"). Omitting the key
    lets Cosmos apply the container's default TTL. Valid values (a positive int
    or ``-1`` for never-expire) are preserved.
    """
    if document.get("ttl") is None:
        document.pop("ttl", None)


class CosmosDBClient:
    """Async Cosmos DB client with managed identity authentication"""
    
    def __init__(self):
        self.endpoint = os.getenv("COSMOS_DB_ENDPOINT")
        self.database_name = os.getenv("COSMOS_DB_DATABASE_NAME", "compliance-iq-db")
        self.client: Optional[CosmosClient] = None
        self.database = None
        self.credential = None
        
        # Container names
        self.MAPPING_RESULTS = "mapping-results"
        self.AUDIT_LOGS = "audit-logs"
        self.USER_UPLOADS = "user-uploads"
        self.GENERATED_ARTIFACTS = "generated-artifacts"
        self.MAPPING_JOBS = "mapping-jobs"
        self.POLICY_CACHE = "policy-cache"
        self.USER_PROFILES = "user-profiles"
        self.COMPARISONS = "comparisons"
        self.POLICY_VERSIONS = "policy-versions"
    
    async def initialize(self) -> None:
        """Initialize Cosmos DB client with managed identity"""
        if not self.endpoint:
            logger.warning("COSMOS_DB_ENDPOINT not configured. Database features disabled.")
            return
            
        try:
            # Use managed identity for authentication
            self.credential = DefaultAzureCredential()
            
            self.client = CosmosClient(
                url=self.endpoint,
                credential=self.credential
            )
            
            self.database = self.client.get_database_client(self.database_name)

            # Ensure containers needed at runtime exist (no-op if already provisioned)
            await self.ensure_container(
                self.MAPPING_JOBS,
                partition_key_paths=["/job_id"],
                default_ttl=2592000  # 30 days
            )

            await self.ensure_container(
                self.POLICY_CACHE,
                partition_key_paths=["/policy_id"],
                default_ttl=1209600  # 14 days
            )

            await self.ensure_container(
                self.GENERATED_ARTIFACTS,
                partition_key_paths=["/session_id"],
                default_ttl=7776000  # 90 days
            )

            await self.ensure_container(
                self.USER_PROFILES,
                partition_key_paths=["/userId"],
            )

            # Per-user diff comparisons (90-day TTL — regenerable analysis output)
            await self.ensure_container(
                self.COMPARISONS,
                partition_key_paths=["/userId"],
                default_ttl=7776000,  # 90 days
            )

            # Immutable per-user policy version history (no TTL — permanent)
            await self.ensure_container(
                self.POLICY_VERSIONS,
                partition_key_paths=["/userId"],
            )

            logger.info("Cosmos DB client initialized successfully", extra={
                "endpoint": self.endpoint,
                "database": self.database_name
            })
            
        except Exception as e:
            logger.error(f"Failed to initialize Cosmos DB client: {e}")
            raise
    
    async def close(self) -> None:
        """Close connections"""
        if self.client:
            await self.client.close()
        if self.credential:
            await self.credential.close()
    
    async def insert_document(self, container_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a document into a container.
        
        Args:
            container_name: Container name
            document: Document to insert
            
        Returns:
            Inserted document with metadata
        """
        try:
            container = self.database.get_container_client(container_name)
            
            # Add timestamp if not present
            if '_ts' not in document:
                document['timestamp'] = datetime.now(timezone.utc).isoformat()
            
            _sanitize_document_for_write(document)
            result = await container.create_item(body=document)
            
            logger.info("document_inserted", extra={
                "container": container_name,
                "document_id": document.get('id')
            })
            
            return result
            
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Failed to insert document: {e}", extra={
                "container": container_name,
                "status_code": e.status_code
            })
            raise

    async def upsert_document(self, container_name: str, document: Dict[str, Any],
                               partition_key: Optional[str] = None) -> Dict[str, Any]:
        """Create or replace a document (idempotent).

        Note: We let the SDK infer the partition key from the document to avoid
        passing unsupported kwargs through the HTTP client in older SDKs.
        """
        try:
            container = self.database.get_container_client(container_name)

            if '_ts' not in document:
                document['timestamp'] = datetime.now(timezone.utc).isoformat()

            _sanitize_document_for_write(document)
            result = await container.upsert_item(body=document)

            logger.info("document_upserted", extra={
                "container": container_name,
                "document_id": document.get('id')
            })
            return result
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Failed to upsert document: {e}", extra={
                "container": container_name,
                "status_code": getattr(e, 'status_code', None)
            })
            raise
    
    async def query_documents(self, container_name: str, query: str, 
                            parameters: Optional[List[Dict[str, Any]]] = None,
                            partition_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query documents from a container.
        
        Args:
            container_name: Container name
            query: SQL query string
            parameters: Query parameters
            partition_key: Partition key for cross-partition queries
            
        Returns:
            List of matching documents
        """
        try:
            container = self.database.get_container_client(container_name)
            
            query_options = {}
            if partition_key:
                query_options['partition_key'] = partition_key
            
            items = []
            async for item in container.query_items(
                query=query,
                parameters=parameters,
                **query_options
            ):
                items.append(item)
            
            logger.info("documents_queried", extra={
                "container": container_name,
                "result_count": len(items)
            })
            
            return items
            
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Failed to query documents: {e}", extra={
                "container": container_name,
                "status_code": e.status_code
            })
            raise
    
    async def get_document(self, container_name: str, document_id: str, 
                          partition_key: str) -> Optional[Dict[str, Any]]:
        """
        Get a single document by ID.
        
        Args:
            container_name: Container name
            document_id: Document ID
            partition_key: Partition key value
            
        Returns:
            Document or None if not found
        """
        try:
            container = self.database.get_container_client(container_name)
            item = await container.read_item(
                item=document_id,
                partition_key=partition_key
            )
            return item
            
        except exceptions.CosmosResourceNotFoundError:
            logger.warning(f"Document not found: {document_id}")
            return None
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Failed to get document: {e}")
            raise
    
    async def update_document(self, container_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing document.
        
        Args:
            container_name: Container name
            document: Document with updated fields (must include 'id')
            
        Returns:
            Updated document
        """
        try:
            container = self.database.get_container_client(container_name)
            _sanitize_document_for_write(document)
            result = await container.replace_item(
                item=document['id'],
                body=document
            )
            
            logger.info("document_updated", extra={
                "container": container_name,
                "document_id": document.get('id')
            })
            
            return result
            
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Failed to update document: {e}")
            raise
    
    async def delete_document(self, container_name: str, document_id: str, 
                             partition_key: str) -> None:
        """
        Delete a document.
        
        Args:
            container_name: Container name
            document_id: Document ID
            partition_key: Partition key value
        """
        try:
            container = self.database.get_container_client(container_name)
            await container.delete_item(
                item=document_id,
                partition_key=partition_key
            )
            
            logger.info("document_deleted", extra={
                "container": container_name,
                "document_id": document_id
            })
            
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Failed to delete document: {e}")
            raise

    async def ensure_container(
        self,
        container_name: str,
        *,
        partition_key_paths: List[str],
        default_ttl: Optional[int] = None
    ) -> None:
        """Create container if it does not exist (idempotent).

        Best-effort by design: this runs on the startup path for every
        container, and a transient Cosmos error there should not stop the app
        from booting. A failure is logged at error level rather than raised,
        because the consequence is deferred — writes to that container will
        fail later, somewhere else.
        """
        if not self.database:
            return

        try:
            # The SDK's kwarg is `path`, singular, for both shapes: pass a str
            # for a single key and a list for a hierarchical one, and it infers
            # Hash vs MultiHash itself. Passing `paths=`/`kind=` raises
            # KeyError('path') inside the constructor before any network call,
            # which is why `mapping-results` — the only container with a
            # composite key (/userId, /date) — failed to be ensured on every
            # single run. It went unnoticed because Bicep pre-provisions the
            # container in the deployed environment, so writes still landed;
            # on a fresh environment nothing would have created it.
            path: Union[str, List[str]] = (
                partition_key_paths[0]
                if len(partition_key_paths) == 1
                else list(partition_key_paths)
            )
            pk = PartitionKey(path=path)

            await self.database.create_container_if_not_exists(
                id=container_name,
                partition_key=pk,
                default_ttl=default_ttl
            )

            logger.info("container_ready", extra={
                "container": container_name,
                "partition_keys": partition_key_paths
            })

        except Exception as e:
            logger.error(
                "Failed to ensure container %s (partition keys %s): %s. "
                "Writes to this container will fail unless it already exists.",
                container_name, partition_key_paths, e,
            )


# Global client instance
cosmos_client = CosmosDBClient()
