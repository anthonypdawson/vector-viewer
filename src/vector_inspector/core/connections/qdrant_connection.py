"""Qdrant connection manager."""

import uuid
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Filter,
    PointStruct,
    VectorParams,
)

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver import (
    resolve_embedding_model,
)
from vector_inspector.core.connections.qdrant_helpers.qdrant_filter_builder import build_filter
from vector_inspector.core.logging import log_error, log_info


class QdrantConnection(VectorDBConnection):
    """Manages connection to Qdrant and provides query interface."""

    def __init__(
        self,
        path: Optional[str] = None,
        url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        api_key: Optional[str] = None,
        prefer_grpc: bool = False,
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
                "check_compatibility": False,
                "timeout": 300,  # 5 minutes timeout for long operations
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
                    **common_params,
                )
            elif self.host:
                # Host and port provided
                self._client = QdrantClient(
                    host=self.host,
                    port=self.port,
                    api_key=self.api_key,
                    prefer_grpc=self.prefer_grpc,
                    **common_params,
                )
            else:
                # Default to in-memory client
                self._client = QdrantClient(":memory:", **common_params)

            # Test connection
            self._client.get_collections()
            return True
        except Exception as e:
            log_error("Connection failed: %s", e)
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

    def get_items(self, name: str, ids: list[str]) -> dict[str, Any]:
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
            log_error("Failed to get items: %s", e)
            return {"documents": [], "metadatas": []}

    def list_collections(self) -> list[str]:
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
            log_error("Failed to list collections: %s", e)
            return []

    def get_collection_info(self, name: str) -> Optional[dict[str, Any]]:
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
                collection_name=name, limit=1, with_payload=True, with_vectors=False
            )

            metadata_fields = []
            if sample[0] and len(sample[0]) > 0:
                point = sample[0][0]
                if point.payload:
                    # Extract metadata fields, excluding 'document' if present
                    metadata_fields = [k for k in point.payload.keys() if k != "document"]

            # Extract vector configuration
            vector_dimension = "Unknown"
            distance_metric = "Unknown"
            config_details = {}

            if collection_info.config:
                # Get vector parameters
                if hasattr(collection_info.config, "params"):
                    params = collection_info.config.params
                    if hasattr(params, "vectors"):
                        vectors = params.vectors
                        # Handle both dict and object access
                        if isinstance(vectors, dict):
                            # Named vectors
                            first_vector = next(iter(vectors.values()), None)
                            if first_vector:
                                vector_dimension = getattr(first_vector, "size", "Unknown")
                                distance = getattr(first_vector, "distance", None)
                        else:
                            # Single vector config
                            vector_dimension = getattr(vectors, "size", "Unknown")
                            distance = getattr(vectors, "distance", None)

                        # Map distance enum to readable name
                        if distance:
                            distance_str = str(distance)
                            if "COSINE" in distance_str.upper():
                                distance_metric = "Cosine"
                            elif "EUCLID" in distance_str.upper():
                                distance_metric = "Euclidean"
                            elif "DOT" in distance_str.upper():
                                distance_metric = "Dot Product"
                            elif "MANHATTAN" in distance_str.upper():
                                distance_metric = "Manhattan"
                            else:
                                distance_metric = distance_str

                # Get HNSW config if available
                if hasattr(collection_info.config, "hnsw_config"):
                    hnsw = collection_info.config.hnsw_config
                    config_details["hnsw_config"] = {
                        "m": getattr(hnsw, "m", None),
                        "ef_construct": getattr(hnsw, "ef_construct", None),
                    }

                # Get optimizer config if available
                if hasattr(collection_info.config, "optimizer_config"):
                    opt = collection_info.config.optimizer_config
                    config_details["optimizer_config"] = {
                        "indexing_threshold": getattr(opt, "indexing_threshold", None),
                    }

            result = {
                "name": name,
                "count": collection_info.points_count,
                "metadata_fields": metadata_fields,
                "vector_dimension": vector_dimension,
                "distance_metric": distance_metric,
            }

            # Check for embedding model metadata (if collection creator stored it)
            if hasattr(collection_info.config, "metadata") and collection_info.config.metadata:
                metadata = collection_info.config.metadata
                if "embedding_model" in metadata:
                    result["embedding_model"] = metadata["embedding_model"]
                if "embedding_model_type" in metadata:
                    result["embedding_model_type"] = metadata["embedding_model_type"]

            if config_details:
                result["config"] = config_details

            return result

        except Exception as e:
            log_error("Failed to get collection info: %s", e)
            return None

    def _get_embedding_model_for_collection(self, collection_name: str):
        """Delegate embedding-model selection to helper resolver."""
        try:
            return resolve_embedding_model(self, collection_name)
        except Exception as e:
            log_error("Failed to resolve embedding model for %s: %s", collection_name, e)
            from vector_inspector.core.embedding_utils import DEFAULT_MODEL, load_embedding_model

            model_name, model_type = DEFAULT_MODEL
            model = load_embedding_model(model_name, model_type)
            return (model, model_name, model_type)

    def _build_qdrant_filter(self, where: Optional[dict[str, Any]] = None) -> Optional[Filter]:
        """Delegate filter construction to helper module."""
        try:
            return build_filter(where)
        except Exception as e:
            log_error("Failed to build filter: %s", e)
            return None

    def query_collection(
        self,
        collection_name: str,
        query_texts: Optional[list[str]] = None,
        query_embeddings: Optional[list[list[float]]] = None,
        n_results: int = 10,
        where: Optional[dict[str, Any]] = None,
        where_document: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
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
            log_error("Either query_texts or query_embeddings required")
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
                "embeddings": [],
            }

            # Use query_texts if provided (Qdrant handles embedding)
            queries = query_texts if query_texts else []

            # If embeddings provided instead, use them
            if query_embeddings and not query_texts:
                queries = query_embeddings

            for query in queries:
                # Embed text queries if needed
                if isinstance(query, str):
                    # Generate embeddings for text query using inherited method
                    try:
                        model, model_name, model_type = self.load_embedding_model_for_collection(
                            collection_name
                        )

                        from vector_inspector.core.embedding_utils import encode_text

                        query_vector = encode_text(query, model, model_type)
                    except Exception as e:
                        log_error("Failed to embed query text: %s", e)
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
                    log_error("Query failed: %s", e)
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
                    documents.append(payload.get("document", ""))

                    # Metadata is everything except 'document'
                    metadata = {k: v for k, v in payload.items() if k != "document"}
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
            log_error("Query failed: %s", e)
            return None

    def get_all_items(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
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
                with_vectors=True,
            )

            # Transform to standard format
            ids = []
            documents = []
            metadatas = []
            embeddings = []

            for point in points:
                ids.append(str(point.id))

                payload = point.payload or {}
                documents.append(payload.get("document", ""))

                # Metadata is everything except 'document'
                metadata = {k: v for k, v in payload.items() if k != "document"}
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
                "embeddings": embeddings,
            }
        except Exception as e:
            log_error("Failed to get items: %s", e)
            return None

    def add_items(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
        ids: Optional[list[str]] = None,
        embeddings: Optional[list[list[float]]] = None,
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
            
        Note:
            Qdrant requires UUIDs for point IDs. If a provided ID is not a valid UUID,
            it will be converted to a deterministic UUID using uuid5, and the original
            ID will be preserved in the metadata under the key "original_id" to ensure
            data preservation during import/export or migration operations.
        """
        if not self._client:
            return False
        # Reject empty document lists early
        if not documents:
            return False

        # If embeddings provided, ensure counts match
        if embeddings is not None and len(embeddings) != len(documents):
            log_error(
                "Embeddings length (%d) does not match documents length (%d) for collection %s",
                len(embeddings),
                len(documents),
                collection_name,
            )
            return False

        # If embeddings not provided, compute using model resolution helper
        if not embeddings and documents:
            try:
                embeddings = self.compute_embeddings_for_documents(
                    collection_name,
                    documents,
                    getattr(self, "profile_name", None),
                )
            except Exception as e:
                log_error("Embeddings are required for Qdrant and computing them failed: %s", e)
                return False

        try:
            # Generate IDs if not provided
            if not ids:
                ids = [str(uuid.uuid4()) for _ in documents]

            # Ensure metadatas list exists and matches document count
            if not metadatas:
                metadatas = [{} for _ in documents]
            else:
                # Pad metadatas if needed
                while len(metadatas) < len(documents):
                    metadatas.append({})

            # Build points
            points = []
            for i, (doc_id, document, embedding) in enumerate(zip(ids, documents, embeddings)):
                # Build payload with document and metadata
                payload = {"document": document}
                if metadatas and i < len(metadatas):
                    # Copy metadata to avoid modifying the original
                    if metadatas[i] is None:
                        metadatas[i] = {}
                    payload.update(metadatas[i])

                # Convert string ID to UUID
                # If the ID is not a valid UUID, we preserve the original ID in metadata
                # This ensures data preservation when importing/exporting or migrating data
                try:
                    point_id = uuid.UUID(doc_id)
                except (ValueError, AttributeError):
                    # ID is not a valid UUID, generate one and preserve original
                    point_id = uuid.uuid5(uuid.NAMESPACE_DNS, str(doc_id))
                    # Store original ID in metadata for data preservation
                    payload["original_id"] = doc_id

                point = PointStruct(id=point_id, vector=embedding, payload=payload)
                points.append(point)

            # Upsert points
            self._client.upsert(collection_name=collection_name, points=points)
            return True
        except Exception as e:
            log_error("Failed to add items: %s", e)
            return False

    def update_items(
        self,
        collection_name: str,
        ids: list[str],
        documents: Optional[list[str]] = None,
        metadatas: Optional[list[dict[str, Any]]] = None,
        embeddings: Optional[list[list[float]]] = None,
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
                    with_vectors=True,
                )

                if not existing:
                    continue

                point = existing[0]
                payload = point.payload or {}
                vector = point.vector

                # Update fields as provided
                if documents and i < len(documents):
                    payload["document"] = documents[i]

                if metadatas and i < len(metadatas):
                    # Update metadata, keeping 'document' field
                    doc = payload.get("document", "")
                    payload = metadatas[i].copy()
                    payload["document"] = doc

                # If embeddings provided use them; otherwise compute for updated documents
                if embeddings and i < len(embeddings):
                    vector = embeddings[i]
                elif documents and i < len(documents) and documents[i]:
                    try:
                        # Compute single embedding for this document
                        computed = self.compute_embeddings_for_documents(
                            collection_name,
                            [documents[i]],
                            getattr(self, "profile_name", None),
                        )
                        vector = computed[0] if computed else vector
                    except Exception as e:
                        log_error("Failed to compute embedding for Qdrant update: %s", e)
                        # leave existing vector unchanged
                        pass

                # Upsert updated point
                self._client.upsert(
                    collection_name=collection_name,
                    points=[PointStruct(id=point_id, vector=vector, payload=payload)],
                )

            return True
        except Exception as e:
            log_error("Failed to update items: %s", e)
            return False

    def delete_items(
        self,
        collection_name: str,
        ids: Optional[list[str]] = None,
        where: Optional[dict[str, Any]] = None,
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
                self._client.delete(collection_name=collection_name, points_selector=ids)
            elif where:
                # Delete by filter
                qdrant_filter = self._build_qdrant_filter(where)
                if qdrant_filter:
                    self._client.delete(
                        collection_name=collection_name, points_selector=qdrant_filter
                    )
            return True
        except Exception as e:
            log_error("Failed to delete items: %s", e)
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
            log_error("Failed to delete collection: %s", e)
            return False

    def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
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
                vectors_config=VectorParams(size=vector_size, distance=qdrant_distance),
            )
            return True
        except Exception as e:
            log_error(f"Failed to create collection: {e}")
            return False

    def prepare_restore(self, metadata: dict[str, Any], data: dict[str, Any]) -> bool:
        """Provider-specific hook invoked before restoring data.

        The connection can use metadata and data to pre-create collections,
        normalize ids, and generate embeddings if needed. Returns True on
        success or False on fatal failure.
        """
        try:
            coll_info = metadata.get("collection_info") if metadata else None

            # Prefer `vector_dimension` but fall back to older `vector_size` for compatibility
            vector_size = None
            if coll_info:
                vector_size = coll_info.get("vector_dimension") or coll_info.get("vector_size")

            embeddings = data.get("embeddings") if data else None
            embeddings_present = bool(embeddings) and len(embeddings) > 0
            if not vector_size and embeddings_present:
                first = embeddings[0]
                if isinstance(first, (list, tuple)):
                    vector_size = len(first)

            if not vector_size:
                log_error("Cannot determine vector size for Qdrant collection during restore")
                return False

            # Determine distance metric (try several known keys)
            distance = None
            if coll_info:
                distance = coll_info.get("distance_metric") or coll_info.get("distance")
            distance = distance or "Cosine"

            log_info(
                "Preparing restore: collection=%s, vector_size=%s, distance=%s",
                metadata.get("collection_name"),
                vector_size,
                distance,
            )

            if not self.create_collection(
                metadata.get("collection_name"), int(vector_size), distance
            ):
                log_error("Failed to create collection %s", metadata.get("collection_name"))
                return False

            # Ensure IDs are strings — actual insertion will convert to UUIDs
            if data and data.get("ids"):
                data["ids"] = [str(i) for i in data.get("ids")]

            # If embeddings present, validate their dimensionality
            if embeddings_present:
                for i, emb in enumerate(embeddings):
                    if not isinstance(emb, (list, tuple)):
                        # leave conversion to normalize_embeddings later
                        continue
                    if len(emb) != int(vector_size):
                        log_error(
                            "Embedding at index %d has length %d but expected %d",
                            i,
                            len(emb),
                            int(vector_size),
                        )
                        return False

            # If embeddings missing or empty, try to generate using connection utilities
            if not embeddings_present:
                try:
                    model, model_name, model_type = self._get_embedding_model_for_collection(
                        metadata.get("collection_name")
                    )
                    from vector_inspector.core.embedding_utils import encode_documents

                    documents = data.get("documents", []) if data else []
                    if documents:
                        data["embeddings"] = encode_documents(documents, model, model_type)
                        log_info(
                            "Generated %d embeddings using model %s",
                            len(data.get("embeddings")),
                            model_name,
                        )
                except Exception as e:
                    log_error("Failed to generate embeddings during prepare_restore: %s", e)
                    return False

            # Normalize coll_info key for downstream code expectations
            if coll_info and "vector_dimension" not in coll_info:
                coll_info["vector_dimension"] = vector_size

            return True
        except Exception as e:
            log_error("prepare_restore failed: %s", e)
            return False

    def get_connection_info(self) -> dict[str, Any]:
        """Get information about the current connection."""
        info: dict[str, Any] = {
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

    def get_supported_filter_operators(self) -> list[dict[str, Any]]:
        """Get filter operators supported by Qdrant."""
        return [
            {"name": "=", "server_side": True},
            {"name": "!=", "server_side": True},
            {"name": ">", "server_side": True},
            {"name": ">=", "server_side": True},
            {"name": "<", "server_side": True},
            {"name": "<=", "server_side": True},
            {"name": "in", "server_side": True},
            {"name": "not in", "server_side": True},
            {"name": "contains", "server_side": True},
            {"name": "not contains", "server_side": True},
        ]
