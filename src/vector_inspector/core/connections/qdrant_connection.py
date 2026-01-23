"""Qdrant connection manager."""

from typing import Optional, List, Dict, Any
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, 
    Filter, FieldCondition, MatchValue, MatchText, MatchAny, MatchExcept, Range
)

from .base_connection import VectorDBConnection


class QdrantConnection(VectorDBConnection):
    """Manages connection to Qdrant and provides query interface."""
    
    def __init__(
        self, 
        path: Optional[str] = None, 
        url: Optional[str] = None,
        host: Optional[str] = None, 
        port: Optional[int] = None,
        api_key: Optional[str] = None,
        prefer_grpc: bool = False
    ):
        """
        Initialize Qdrant connection.
        
        Args:
            path: Path for local/embedded client
            url: Full URL for remote client (e.g., "http://localhost:6333")
            host: Host for remote client
            port: Port for remote client (default: 6333)
            api_key: API key for authentication (Qdrant Cloud)
            prefer_grpc: Use gRPC instead of REST
        """
        self.path = path
        self.url = url
        self.host = host
        self.port = port or 6333
        self.api_key = api_key
        self.prefer_grpc = prefer_grpc
        self._client: Optional[QdrantClient] = None
        
    def connect(self) -> bool:
        """
        Establish connection to Qdrant.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Common parameters for stability
            common_params = {
                'check_compatibility': False,
                'timeout': 300,  # 5 minutes timeout for long operations
            }
            
            if self.path:
                # Local/embedded mode
                self._client = QdrantClient(path=self.path, **common_params)
            elif self.url:
                # Full URL provided
                self._client = QdrantClient(
                    url=self.url,
                    api_key=self.api_key,
                    prefer_grpc=self.prefer_grpc,
                    **common_params
                )
            elif self.host:
                # Host and port provided
                self._client = QdrantClient(
                    host=self.host,
                    port=self.port,
                    api_key=self.api_key,
                    prefer_grpc=self.prefer_grpc,
                    **common_params
                )
            else:
                # Default to in-memory client
                self._client = QdrantClient(":memory:", **common_params)
            
            # Test connection
            self._client.get_collections()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def _to_uuid(self, id_str: str) -> uuid.UUID:
        """Convert a string ID to a valid UUID.
        
        If the string is already a valid UUID, return it.
        Otherwise, generate a deterministic UUID from the string.
        """
        try:
            return uuid.UUID(id_str)
        except (ValueError, AttributeError):
            # Generate deterministic UUID from string
            return uuid.uuid5(uuid.NAMESPACE_DNS, id_str)
    
    def disconnect(self):
        """Close connection to Qdrant."""
        if self._client:
            self._client.close()
        self._client = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Qdrant."""
        return self._client is not None
    
    def count_collection(self, name: str) -> int:
        """Count the number of items in a collection."""
        if not self._client:
            return 0
        try:
            res = self._client.count(collection_name=name)
            return getattr(res, "count", 0) or 0
        except Exception:
            return 0
    
    def get_items(self, name: str, ids: List[str]) -> Dict[str, Any]:
        """
        Get items by IDs (implementation for compatibility).
        
        Note: This is a simplified implementation that retrieves items by scrolling
        and filtering. For production use, consider using get_all_items with filters.
        """
        if not self._client:
            return {"documents": [], "metadatas": []}
        
        try:
            # Retrieve by scrolling and filtering
            all_items = self.get_all_items(name, limit=1000)
            if not all_items:
                return {"documents": [], "metadatas": []}
            
            # Filter by requested IDs
            documents = []
            metadatas = []
            for i, item_id in enumerate(all_items.get("ids", [])):
                if item_id in ids:
                    documents.append(all_items["documents"][i])
                    metadatas.append(all_items["metadatas"][i])
            
            return {"documents": documents, "metadatas": metadatas}
        except Exception as e:
            print(f"Failed to get items: {e}")
            return {"documents": [], "metadatas": []}
    
    def list_collections(self) -> List[str]:
        """
        Get list of all collections.
        
        Returns:
            List of collection names
        """
        if not self._client:
            return []
        try:
            collections = self._client.get_collections()
            return [col.name for col in collections.collections]
        except Exception as e:
            print(f"Failed to list collections: {e}")
            return []
    
    def get_collection_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get collection metadata and statistics.
        
        Args:
            name: Collection name
            
        Returns:
            Dictionary with collection info
        """
        if not self._client:
            return None
        
        try:
            # Get collection info
            collection_info = self._client.get_collection(name)
            
            # Get a sample point to determine metadata fields
            sample = self._client.scroll(
                collection_name=name,
                limit=1,
                with_payload=True,
                with_vectors=False
            )
            
            metadata_fields = []
            if sample[0] and len(sample[0]) > 0:
                point = sample[0][0]
                if point.payload:
                    # Extract metadata fields, excluding 'document' if present
                    metadata_fields = [k for k in point.payload.keys() if k != 'document']
            
            # Extract vector configuration
            vector_dimension = "Unknown"
            distance_metric = "Unknown"
            config_details = {}
            
            if collection_info.config:
                # Get vector parameters
                if hasattr(collection_info.config, 'params'):
                    params = collection_info.config.params
                    if hasattr(params, 'vectors'):
                        vectors = params.vectors
                        # Handle both dict and object access
                        if isinstance(vectors, dict):
                            # Named vectors
                            first_vector = next(iter(vectors.values()), None)
                            if first_vector:
                                vector_dimension = getattr(first_vector, 'size', 'Unknown')
                                distance = getattr(first_vector, 'distance', None)
                        else:
                            # Single vector config
                            vector_dimension = getattr(vectors, 'size', 'Unknown')
                            distance = getattr(vectors, 'distance', None)
                        
                        # Map distance enum to readable name
                        if distance:
                            distance_str = str(distance)
                            if 'COSINE' in distance_str.upper():
                                distance_metric = "Cosine"
                            elif 'EUCLID' in distance_str.upper():
                                distance_metric = "Euclidean"
                            elif 'DOT' in distance_str.upper():
                                distance_metric = "Dot Product"
                            elif 'MANHATTAN' in distance_str.upper():
                                distance_metric = "Manhattan"
                            else:
                                distance_metric = distance_str
                
                # Get HNSW config if available
                if hasattr(collection_info.config, 'hnsw_config'):
                    hnsw = collection_info.config.hnsw_config
                    config_details['hnsw_config'] = {
                        'm': getattr(hnsw, 'm', None),
                        'ef_construct': getattr(hnsw, 'ef_construct', None),
                    }
                
                # Get optimizer config if available
                if hasattr(collection_info.config, 'optimizer_config'):
                    opt = collection_info.config.optimizer_config
                    config_details['optimizer_config'] = {
                        'indexing_threshold': getattr(opt, 'indexing_threshold', None),
                    }
            
            result = {
                "name": name,
                "count": collection_info.points_count,
                "metadata_fields": metadata_fields,
                "vector_dimension": vector_dimension,
                "distance_metric": distance_metric,
            }
            
            # Check for embedding model metadata (if collection creator stored it)
            if hasattr(collection_info.config, 'metadata') and collection_info.config.metadata:
                metadata = collection_info.config.metadata
                if 'embedding_model' in metadata:
                    result['embedding_model'] = metadata['embedding_model']
                if 'embedding_model_type' in metadata:
                    result['embedding_model_type'] = metadata['embedding_model_type']
            
            if config_details:
                result['config'] = config_details
            
            return result
            
        except Exception as e:
            print(f"Failed to get collection info: {e}")
            return None
    
    def _get_embedding_model_for_collection(self, collection_name: str):
        """Get the appropriate embedding model for a collection based on stored metadata, settings, or dimension."""
        from ..embedding_utils import get_model_for_dimension, load_embedding_model, DEFAULT_MODEL
        
        # Get collection info to determine vector dimension and check metadata
        collection_info = self.get_collection_info(collection_name)
        if not collection_info:
            # Default if we can't determine
            print(f"Warning: Could not determine collection info for {collection_name}, using default")
            model_name, model_type = DEFAULT_MODEL
            model = load_embedding_model(model_name, model_type)
            return (model, model_name, model_type)
        
        # Priority 1: Check if collection metadata has embedding model info (most reliable)
        if 'embedding_model' in collection_info:
            model_name = collection_info['embedding_model']
            model_type = collection_info.get('embedding_model_type', 'sentence-transformer')
            print(f"Using stored embedding model '{model_name}' ({model_type}) for collection '{collection_name}'")
            model = load_embedding_model(model_name, model_type)
            return (model, model_name, model_type)
        
        # Priority 2: Check user settings for manual override (skip in connection class)
        # Settings lookup is done in the UI layer where connection_id is available
        
        # Priority 3: Fall back to dimension-based guessing (least reliable)
        vector_dim = collection_info.get("vector_dimension")
        if not vector_dim or vector_dim == "Unknown":
            print(f"Warning: No vector dimension in collection info, using default")
            model_name, model_type = DEFAULT_MODEL
            model = load_embedding_model(model_name, model_type)
            return (model, model_name, model_type)
        
        # Get the appropriate model for this dimension
        model_name, model_type = get_model_for_dimension(vector_dim)
        model = load_embedding_model(model_name, model_type)
        
        print(f"⚠️ Guessing {model_type} model '{model_name}' based on dimension {vector_dim} for '{collection_name}'")
        print(f"   To specify the correct model, use Settings > Configure Collection Embedding Models")
        return (model, model_name, model_type)
    
    def _build_qdrant_filter(self, where: Optional[Dict[str, Any]] = None) -> Optional[Filter]:
        """
        Build Qdrant filter from ChromaDB-style where clause.
        
        Args:
            where: ChromaDB-style filter dictionary
            
        Returns:
            Qdrant Filter object or None
        """
        if not where:
            return None
        
        try:
            must_conditions = []
            must_not_conditions = []
            
            for key, value in where.items():
                if isinstance(value, dict):
                    # Handle operators like $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $contains, $not_contains
                    for op, val in value.items():
                        if op == "$eq":
                            must_conditions.append(FieldCondition(key=key, match=MatchValue(value=val)))
                        elif op == "$ne":
                            # Use must_not for not-equal
                            must_not_conditions.append(FieldCondition(key=key, match=MatchValue(value=val)))
                        elif op == "$in":
                            # Use MatchAny for IN operator (available since v1.1.0)
                            must_conditions.append(FieldCondition(key=key, match=MatchAny(any=val)))
                        elif op == "$nin":
                            # Use MatchExcept for NOT IN operator (available since v1.2.0)
                            must_conditions.append(FieldCondition(key=key, match=MatchExcept(**{"except": val})))
                        elif op == "$contains":
                            # Text matching in Qdrant (uses full-text index if available)
                            must_conditions.append(FieldCondition(key=key, match=MatchText(text=str(val))))
                        elif op == "$not_contains":
                            # Negative text matching using must_not
                            must_not_conditions.append(FieldCondition(key=key, match=MatchText(text=str(val))))
                        elif op in ["$gt", "$gte", "$lt", "$lte"]:
                            range_args = {}
                            if op == "$gt":
                                range_args["gt"] = val
                            elif op == "$gte":
                                range_args["gte"] = val
                            elif op == "$lt":
                                range_args["lt"] = val
                            elif op == "$lte":
                                range_args["lte"] = val
                            must_conditions.append(FieldCondition(key=key, range=Range(**range_args)))
                else:
                    # Direct equality match
                    must_conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            
            if must_conditions or must_not_conditions:
                return Filter(must=must_conditions if must_conditions else None, 
                            must_not=must_not_conditions if must_not_conditions else None)
            return None
        except Exception as e:
            print(f"Failed to build filter: {e}")
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
            query_texts: Text queries (Qdrant will embed automatically)
            query_embeddings: Direct embedding vectors to search
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter (limited support)
            
        Returns:
            Query results or None if failed
        """
        if not self._client:
            return None
        
        if not query_texts and not query_embeddings:
            print("Either query_texts or query_embeddings required")
            return None
        
        try:
            # Build filter
            qdrant_filter = self._build_qdrant_filter(where)
            
            # Perform search for each query
            all_results = {
                "ids": [],
                "distances": [],
                "documents": [],
                "metadatas": [],
                "embeddings": []
            }
            
            # Use query_texts if provided (Qdrant handles embedding)
            queries = query_texts if query_texts else []
            
            # If embeddings provided instead, use them
            if query_embeddings and not query_texts:
                queries = query_embeddings
            
            for query in queries:
                # Embed text queries if needed
                if isinstance(query, str):
                    # Generate embeddings for text query using appropriate model for this collection
                    try:
                        model, model_name, model_type = self._get_embedding_model_for_collection(collection_name)
                        from ..embedding_utils import encode_text
                        query_vector = encode_text(query, model, model_type)
                    except Exception as e:
                        print(f"Failed to embed query text: {e}")
                        continue
                else:
                    query_vector = query

                # Use modern query_points API
                try:
                    res = self._client.query_points(
                        collection_name=collection_name,
                        query=query_vector,
                        limit=n_results,
                        query_filter=qdrant_filter,
                        with_payload=True,
                        with_vectors=True,
                    )
                    search_results = getattr(res, "points", res)
                except Exception as e:
                    print(f"Query failed: {e}")
                    continue
                
                # Transform results to standard format
                ids = []
                distances = []
                documents = []
                metadatas = []
                embeddings = []
                
                for result in search_results:
                    ids.append(str(result.id))
                    distances.append(result.score)
                    
                    # Extract document and metadata from payload
                    payload = result.payload or {}
                    documents.append(payload.get('document', ''))
                    
                    # Metadata is everything except 'document'
                    metadata = {k: v for k, v in payload.items() if k != 'document'}
                    metadatas.append(metadata)
                    
                    # Extract embedding
                    embeddings.append(result.vector if result.vector else [])
                
                all_results["ids"].append(ids)
                all_results["distances"].append(distances)
                all_results["documents"].append(documents)
                all_results["metadatas"].append(metadatas)
                all_results["embeddings"].append(embeddings)
            
            return all_results
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
        if not self._client:
            return None
        
        try:
            # Build filter
            qdrant_filter = self._build_qdrant_filter(where)
            
            # Use scroll to retrieve items
            points, next_offset = self._client.scroll(
                collection_name=collection_name,
                scroll_filter=qdrant_filter,
                limit=limit,
                offset=offset,
                with_payload=True,
                with_vectors=True
            )
            
            # Transform to standard format
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            for point in points:
                ids.append(str(point.id))
                
                payload = point.payload or {}
                documents.append(payload.get('document', ''))
                
                # Metadata is everything except 'document'
                metadata = {k: v for k, v in payload.items() if k != 'document'}
                metadatas.append(metadata)
                
                # Extract embedding
                if isinstance(point.vector, dict):
                    # Named vectors - use the first one
                    embeddings.append(list(point.vector.values())[0] if point.vector else [])
                else:
                    embeddings.append(point.vector if point.vector else [])
            
            return {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
                "embeddings": embeddings
            }
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
            ids: IDs for each document (will generate UUIDs if not provided)
            embeddings: Pre-computed embeddings (required for Qdrant)
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False
        
        if not embeddings:
            print("Embeddings are required for Qdrant")
            return False
        
        try:
            # Generate IDs if not provided
            if not ids:
                ids = [str(uuid.uuid4()) for _ in documents]
            
            # Build points
            points = []
            for i, (doc_id, document, embedding) in enumerate(zip(ids, documents, embeddings)):
                # Build payload with document and metadata
                payload = {"document": document}
                if metadatas and i < len(metadatas):
                    payload.update(metadatas[i])
                
                # Convert string ID to UUID
                point_id = self._to_uuid(doc_id)
                
                point = PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=payload
                )
                points.append(point)
            
            # Upsert points
            self._client.upsert(
                collection_name=collection_name,
                points=points
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
        if not self._client:
            return False
        
        try:
            # For Qdrant, we need to retrieve existing points, update them, and upsert
            for i, point_id in enumerate(ids):
                # Get existing point
                existing = self._client.retrieve(
                    collection_name=collection_name,
                    ids=[point_id],
                    with_payload=True,
                    with_vectors=True
                )
                
                if not existing:
                    continue
                
                point = existing[0]
                payload = point.payload or {}
                vector = point.vector
                
                # Update fields as provided
                if documents and i < len(documents):
                    payload['document'] = documents[i]
                
                if metadatas and i < len(metadatas):
                    # Update metadata, keeping 'document' field
                    doc = payload.get('document', '')
                    payload = metadatas[i].copy()
                    payload['document'] = doc
                
                if embeddings and i < len(embeddings):
                    vector = embeddings[i]
                
                # Upsert updated point
                self._client.upsert(
                    collection_name=collection_name,
                    points=[PointStruct(id=point_id, vector=vector, payload=payload)]
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
        if not self._client:
            return False
        
        try:
            if ids:
                # Delete by IDs
                self._client.delete(
                    collection_name=collection_name,
                    points_selector=ids
                )
            elif where:
                # Delete by filter
                qdrant_filter = self._build_qdrant_filter(where)
                if qdrant_filter:
                    self._client.delete(
                        collection_name=collection_name,
                        points_selector=qdrant_filter
                    )
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
            self._client.delete_collection(collection_name=name)
            return True
        except Exception as e:
            print(f"Failed to delete collection: {e}")
            return False
    
    def create_collection(
        self, 
        name: str, 
        vector_size: int,
        distance: str = "Cosine"
    ) -> bool:
        """
        Create a new collection.
        
        Args:
            name: Collection name
            vector_size: Dimension of vectors
            distance: Distance metric ("Cosine", "Euclid", "Dot")
            
        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False
        
        try:
            # Map distance string to Qdrant Distance enum
            distance_map = {
                "Cosine": Distance.COSINE,
                "Euclid": Distance.EUCLID,
                "Euclidean": Distance.EUCLID,
                "Dot": Distance.DOT,
            }
            
            qdrant_distance = distance_map.get(distance, Distance.COSINE)
            
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=qdrant_distance
                )
            )
            return True
        except Exception as e:
            print(f"Failed to create collection: {e}")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about the current connection.
        
        Returns:
            Dictionary with connection details
        """
        info = {
            "provider": "Qdrant",
            "connected": self.is_connected,
        }
        
        if self.path:
            info["mode"] = "local"
            info["path"] = self.path
        elif self.url:
            info["mode"] = "remote"
            info["url"] = self.url
        elif self.host:
            info["mode"] = "remote"
            info["host"] = self.host
            info["port"] = self.port
        else:
            info["mode"] = "memory"
        
        return info
    
    def get_supported_filter_operators(self) -> List[Dict[str, Any]]:
        """
        Get filter operators supported by Qdrant.
        
        Qdrant has richer filtering capabilities than ChromaDB.
        
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
            # Qdrant supports text matching server-side
            {"name": "contains", "server_side": True},
            {"name": "not contains", "server_side": True},
        ]
