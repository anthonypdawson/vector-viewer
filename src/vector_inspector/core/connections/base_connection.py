"""Abstract base class for vector database connections."""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class VectorDBConnection(ABC):
    """Abstract base class for vector database connections.
    
    This class defines the interface that all vector database providers
    must implement to be compatible with Vector Inspector.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the vector database.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def disconnect(self):
        """Close connection to the vector database."""
        pass
    
    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if connected to the vector database.
        
        Returns:
            True if connected, False otherwise
        """
        pass
    
    @abstractmethod
    def list_collections(self) -> List[str]:
        """
        Get list of all collections/indexes.
        
        Returns:
            List of collection/index names
        """
        pass
    
    @abstractmethod
    def get_collection_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get collection metadata and statistics.
        
        Args:
            name: Collection/index name
            
        Returns:
            Dictionary with collection info including:
                - name: Collection name
                - count: Number of items
                - metadata_fields: List of available metadata field names
        """
        pass

    @abstractmethod
    def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        """Create a collection/index with a given vector size and distance metric."""
        pass

    @abstractmethod
    def add_items(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> bool:
        """Add items to a collection."""
        pass

    @abstractmethod
    def get_items(self, name: str, ids: List[str]) -> Dict[str, Any]:
        """Retrieve items by original ids. Should return a dict with 'documents' and 'metadatas'."""
        pass

    @abstractmethod
    def delete_collection(self, name: str) -> bool:
        """Delete a collection/index."""
        pass

    @abstractmethod
    def count_collection(self, name: str) -> int:
        """Return the number of items in the collection."""
        pass
    
    @abstractmethod
    def query_collection(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Query a collection for similar vectors.
        
        Args:
            collection_name: Name of collection to query
            query_texts: Text queries to embed and search
            query_embeddings: Direct embedding vectors to search
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter
            
        Returns:
            Query results dictionary with keys:
                - ids: List of result IDs
                - distances: List of distances/scores
                - documents: List of document texts
                - metadatas: List of metadata dicts
                - embeddings: List of embedding vectors (optional)
        """
        pass
    
    @abstractmethod
    def get_all_items(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get all items from a collection.
        
        Args:
            collection_name: Name of collection
            limit: Maximum number of items to return
            offset: Number of items to skip
            where: Metadata filter
            
        Returns:
            Dictionary with collection items:
                - ids: List of item IDs
                - documents: List of document texts
                - metadatas: List of metadata dicts
                - embeddings: List of embedding vectors
        """
        pass
    
    @abstractmethod
    def update_items(
        self,
        collection_name: str,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> bool:
        """
        Update items in a collection.
        
        Args:
            collection_name: Name of collection
            ids: IDs of items to update
            documents: New document texts
            metadatas: New metadata
            embeddings: New embeddings
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def delete_items(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Delete items from a collection.
        
        Args:
            collection_name: Name of collection
            ids: IDs of items to delete
            where: Metadata filter for items to delete
            
        Returns:
            True if successful, False otherwise
        """
        pass
    

    # Optional: Methods that may be provider-specific but useful to define
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about the current connection.
        
        Returns:
            Dictionary with connection details (provider-specific)
        """
        return {
            "provider": self.__class__.__name__,
            "connected": self.is_connected
        }
    
    def get_supported_filter_operators(self) -> List[Dict[str, Any]]:
        """
        Get list of filter operators supported by this provider.
        
        Returns:
            List of operator dictionaries with 'name' and 'server_side' keys
        """
        # Default operators supported by most providers
        return [
            {"name": "=", "server_side": True},
            {"name": "!=", "server_side": True},
            {"name": ">", "server_side": True},
            {"name": ">=", "server_side": True},
            {"name": "<", "server_side": True},
            {"name": "<=", "server_side": True},
            {"name": "in", "server_side": True},
            {"name": "not in", "server_side": True},
            {"name": "contains", "server_side": False},
        ]
    
    def get_embedding_model(self, collection_name: str, connection_id: Optional[str] = None) -> Optional[str]:
        """
        Get the embedding model used for a collection.
        
        Retrieves the model name from:
        1. Collection-level metadata (if supported)
        2. Vector metadata (_embedding_model field)
        3. User settings (for collections we can't modify)
        
        Args:
            collection_name: Name of collection
            connection_id: Optional connection ID for settings lookup
            
        Returns:
            Model name string (e.g., "sentence-transformers/all-MiniLM-L6-v2") or None
        """
        try:
            # First try to get from collection-level metadata
            info = self.get_collection_info(collection_name)
            if info and info.get("embedding_model"):
                return info["embedding_model"]
            
            # Fall back to checking a sample vector's metadata
            data = self.get_all_items(collection_name, limit=1, offset=0)
            if data and data.get("metadatas") and len(data["metadatas"]) > 0:
                metadata = data["metadatas"][0]
                if "_embedding_model" in metadata:
                    return metadata["_embedding_model"]
            
            # Finally, check user settings (for collections we can't modify)
            if connection_id:
                from ...services.settings_service import SettingsService
                settings = SettingsService()
                model_info = settings.get_embedding_model(connection_id, collection_name)
                if model_info:
                    return model_info["model"]
            
            return None
        except Exception as e:
            print(f"Failed to get embedding model: {e}")
            return None
