"""ChromaDB connection manager."""

from typing import Optional, List, Dict, Any, cast
import os
from pathlib import Path
import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from .base_connection import VectorDBConnection


class ChromaDBConnection(VectorDBConnection):
    """Manages connection to ChromaDB and provides query interface."""
    
    def __init__(self, path: Optional[str] = None, host: Optional[str] = None, port: Optional[int] = None):
        """
        Initialize ChromaDB connection.
        
        Args:
            path: Path for persistent client (local storage)
            host: Host for HTTP client
            port: Port for HTTP client
        """
        self.path = path
        self.host = host
        self.port = port
        self._client: Optional[ClientAPI] = None
        self._current_collection: Optional[Collection] = None
        
    def connect(self) -> bool:
        """
        Establish connection to ChromaDB.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.path:
                # Resolve relative paths to project root
                path_to_use = self._resolve_path(self.path)
                # Ensure directory exists
                os.makedirs(path_to_use, exist_ok=True)
                self._client = chromadb.PersistentClient(path=path_to_use)
            elif self.host and self.port:
                self._client = chromadb.HttpClient(host=self.host, port=self.port)
            else:
                # Default to ephemeral client for testing
                self._client = chromadb.Client()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def _resolve_path(self, input_path: str) -> str:
        """Resolve a path relative to the project root if not absolute."""
        if os.path.isabs(input_path):
            return input_path
        # Find project root by searching for pyproject.toml
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return str((parent / input_path).resolve())
        # Fallback to CWD if project root not found
        return str(Path(input_path).resolve())
    
    def disconnect(self):
        """Close connection to ChromaDB."""
        self._client = None
        self._current_collection = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to ChromaDB."""
        return self._client is not None
    
    def list_collections(self) -> List[str]:
        """
        Get list of all collections.
        
        Returns:
            List of collection names
        """
        if not self._client:
            return []
        try:
            collections = self._client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            print(f"Failed to list collections: {e}")
            return []
    
    def get_collection(self, name: str) -> Optional[Collection]:
        """
        Get or create a collection.
        
        Args:
            name: Collection name
            
        Returns:
            Collection object or None if failed
        """
        if not self._client:
            return None
        try:
            self._current_collection = self._client.get_or_create_collection(name=name)
            return self._current_collection
        except Exception as e:
            print(f"Failed to get collection: {e}")
            return None
    
    def get_collection_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get collection metadata and statistics.
        
        Args:
            name: Collection name
            
        Returns:
            Dictionary with collection info
        """
        collection = self.get_collection(name)
        if not collection:
            return None
        
        try:
            count = collection.count()
            # Get a sample to determine metadata fields
            sample = collection.get(limit=1, include=["metadatas"])
            metadata_fields = []
            if sample and sample["metadatas"]:
                metadata_fields = list(sample["metadatas"][0].keys()) if sample["metadatas"][0] else []
            
            return {
                "name": name,
                "count": count,
                "metadata_fields": metadata_fields,
            }
        except Exception as e:
            print(f"Failed to get collection info: {e}")
            return None
    
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
            Query results or None if failed
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return None
        
        try:
            results = collection.query(
                query_texts=query_texts,
                query_embeddings=query_embeddings,  # type: ignore
                n_results=n_results,
                where=where,
                where_document=where_document,  # type: ignore
                include=["metadatas", "documents", "distances", "embeddings"]
            )
            return cast(Dict[str, Any], results)
        except Exception as e:
            print(f"Query failed: {e}")
            return None
    
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
            Collection items or None if failed
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return None
        
        try:
            results = collection.get(
                limit=limit,
                offset=offset,
                where=where,
                include=["metadatas", "documents", "embeddings"]
            )
            return cast(Dict[str, Any], results)
        except Exception as e:
            print(f"Failed to get items: {e}")
            return None
    
    def add_items(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> bool:
        """
        Add items to a collection.
        
        Args:
            collection_name: Name of collection
            documents: Document texts
            metadatas: Metadata for each document
            ids: IDs for each document
            embeddings: Pre-computed embeddings
            
        Returns:
            True if successful, False otherwise
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return False
        
        try:
            collection.add(
                documents=documents,
                metadatas=metadatas,  # type: ignore
                ids=ids,  # type: ignore
                embeddings=embeddings  # type: ignore
            )
            return True
        except Exception as e:
            print(f"Failed to add items: {e}")
            return False
    
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
        collection = self.get_collection(collection_name)
        if not collection:
            return False
        
        try:
            collection.update(
                ids=ids,
                documents=documents,
                metadatas=metadatas,  # type: ignore
                embeddings=embeddings  # type: ignore
            )
            return True
        except Exception as e:
            print(f"Failed to update items: {e}")
            return False
    
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
        collection = self.get_collection(collection_name)
        if not collection:
            return False
        
        try:
            collection.delete(ids=ids, where=where)
            return True
        except Exception as e:
            print(f"Failed to delete items: {e}")
            return False
    
    def delete_collection(self, name: str) -> bool:
        """
        Delete an entire collection.
        
        Args:
            name: Collection name
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False
        
        try:
            self._client.delete_collection(name=name)
            if self._current_collection and self._current_collection.name == name:
                self._current_collection = None
            return True
        except Exception as e:
            print(f"Failed to delete collection: {e}")
            return False

    # Implement base connection uniform APIs
    def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        """Create a collection. Chroma doesn't require vector size at creation."""
        return self.get_collection(name) is not None

    def get_items(self, name: str, ids: List[str]) -> Dict[str, Any]:
        """Retrieve items by IDs."""
        col = self.get_collection(name)
        if not col:
            raise RuntimeError("Collection not available")
        return cast(Dict[str, Any], col.get(ids=ids, include=["metadatas", "documents", "embeddings"]))

    def count_collection(self, name: str) -> int:
        """Count items in a collection."""
        col = self.get_collection(name)
        if not col:
            return 0
        try:
            return col.count()
        except Exception:
            return 0
    
    def get_supported_filter_operators(self) -> List[Dict[str, Any]]:
        """
        Get filter operators supported by ChromaDB.
        
        Returns:
            List of operator dictionaries
        """
        return [
            {"name": "=", "server_side": True},
            {"name": "!=", "server_side": True},
            {"name": ">", "server_side": True},
            {"name": ">=", "server_side": True},
            {"name": "<", "server_side": True},
            {"name": "<=", "server_side": True},
            {"name": "in", "server_side": True},
            {"name": "not in", "server_side": True},
            # Client-side only operators
            {"name": "contains", "server_side": False},
            {"name": "not contains", "server_side": False},
        ]
