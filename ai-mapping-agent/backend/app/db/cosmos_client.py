"""
Cosmos DB client for data persistence
"""
import os
from typing import List, Dict, Any, Optional
from azure.cosmos.aio import CosmosClient
from azure.cosmos import PartitionKey, exceptions
from azure.identity.aio import DefaultAzureCredential
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class CosmosDBClient:
    """Async Cosmos DB client with managed identity authentication"""
    
    def __init__(self):
        self.endpoint = os.getenv("COSMOS_DB_ENDPOINT")
        self.database_name = os.getenv("COSMOS_DB_DATABASE_NAME", "cctoolkit-db")
        self.client: Optional[CosmosClient] = None
        self.database = None
        self.credential = None
        
        # Container names
        self.MAPPING_RESULTS = "mapping-results"
        self.AUDIT_LOGS = "audit-logs"
        self.USER_UPLOADS = "user-uploads"
        self.GENERATED_ARTIFACTS = "generated-artifacts"
    
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
                document['timestamp'] = datetime.utcnow().isoformat()
            
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


# Global client instance
cosmos_client = CosmosDBClient()
