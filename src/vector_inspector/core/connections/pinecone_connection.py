"""Pinecone connection manager."""

from typing import Optional, List, Dict, Any
import time
from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeException

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.logging import log_error


class PineconeConnection(VectorDBConnection):
    """Manages connection to Pinecone and provides query interface."""

    def __init__(
        self, api_key: str, environment: Optional[str] = None, index_host: Optional[str] = None
    ):
        """
        Initialize Pinecone connection.

        Args:
            api_key: Pinecone API key
            environment: Pinecone environment (optional, auto-detected)
            index_host: Specific index host URL (optional)
        """
        self.api_key = api_key
        self.environment = environment
        self.index_host = index_host
        self._client: Optional[Pinecone] = None
        self._current_index = None
        self._current_index_name: Optional[str] = None

    def connect(self) -> bool:
        """
        Establish connection to Pinecone.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Initialize Pinecone client
            self._client = Pinecone(api_key=self.api_key)

            # Test connection by listing indexes
            self._client.list_indexes()
            return True
        except Exception as e:
            log_error("Connection failed: %s", e)
            self._client = None  # Reset client on failure
            return False

    def disconnect(self):
        """Close connection to Pinecone."""
        self._client = None
        self._current_index = None
        self._current_index_name = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to Pinecone."""
        return self._client is not None

    def list_collections(self) -> List[str]:
        """
        Get list of all indexes (collections in Pinecone terminology).

        Returns:
            List of index names
        """
        if not self._client:
            return []
        try:
            indexes = self._client.list_indexes()
            return [str(idx.name) for idx in indexes]  # type: ignore
        except Exception as e:
            log_error("Failed to list indexes: %s", e)
            return []

    def _get_index(self, name: str):
        """Get or create index reference."""
        if not self._client:
            return None

        try:
            # Cache the current index to avoid repeated lookups
            if self._current_index_name != name:
                self._current_index = self._client.Index(name)
                self._current_index_name = name
            return self._current_index
        except Exception as e:
            log_error("Failed to get index: %s", e)
            return None

    def get_collection_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get index metadata and statistics.

        Args:
            name: Index name

        Returns:
            Dictionary with index info
        """
        if not self._client:
            return None

        try:
            # Get index description
            index_description = self._client.describe_index(name)

            # Get index stats
            index = self._get_index(name)
            if not index:
                return None

            stats = index.describe_index_stats()

            # Extract information
            total_vector_count = stats.get("total_vector_count", 0)
            dimension = index_description.dimension
            metric = index_description.metric

            # Get metadata fields from a sample query (if vectors exist)
            metadata_fields = []
            if total_vector_count > 0:
                try:
                    # Query for a small sample to see metadata structure
                    dimension_val = int(dimension) if dimension else 0
                    sample_query = index.query(
                        vector=[0.0] * dimension_val, top_k=1, include_metadata=True
                    )
                    if hasattr(sample_query, "matches") and sample_query.matches:  # type: ignore
                        metadata = sample_query.matches[0].metadata  # type: ignore
                        if metadata:
                            metadata_fields = list(metadata.keys())
                except Exception:
                    pass  # Metadata fields will remain empty

            return {
                "name": name,
                "count": total_vector_count,
                "metadata_fields": metadata_fields,
                "vector_dimension": dimension,
                "distance_metric": str(metric).upper() if metric else "UNKNOWN",
                "host": str(index_description.host)
                if hasattr(index_description, "host")
                else "N/A",
                "status": index_description.status.get("state", "unknown")
                if hasattr(index_description.status, "get")
                else str(index_description.status),  # type: ignore
                "spec": str(index_description.spec)
                if hasattr(index_description, "spec")
                else "N/A",
            }
        except Exception as e:
            log_error("Failed to get index info: %s", e)
            return None

    def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        """
        Create a new index.

        Args:
            name: Index name
            vector_size: Dimension of vectors
            distance: Distance metric (Cosine, Euclidean, DotProduct)

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            # Map distance names to Pinecone metrics
            metric_map = {
                "cosine": "cosine",
                "euclidean": "euclidean",
                "dotproduct": "dotproduct",
                "dot": "dotproduct",
            }
            metric = metric_map.get(distance.lower(), "cosine")

            # Create serverless index (default configuration)
            self._client.create_index(
                name=name,
                dimension=vector_size,
                metric=metric,
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )

            # Wait for index to be ready
            max_wait = 60  # seconds
            start_time = time.time()
            while time.time() - start_time < max_wait:
                desc = self._client.describe_index(name)
                status = (
                    desc.status.get("state", "unknown")
                    if hasattr(desc.status, "get")
                    else str(desc.status)
                )  # type: ignore
                if status.lower() == "ready":
                    return True
                time.sleep(2)

            return False
        except Exception as e:
            log_error("Failed to create index: %s", e)
            return False

    def add_items(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> bool:
        """
        Add items to an index.

        Args:
            collection_name: Name of index
            documents: Document texts (stored in metadata)
            metadatas: Metadata for each vector
            ids: IDs for each vector
            embeddings: Pre-computed embeddings (required for Pinecone)

        Returns:
            True if successful, False otherwise
        """
        # If embeddings not provided, compute using base helper
        if not embeddings and documents:
            try:
                embeddings = self.compute_embeddings_for_documents(
                    collection_name, documents, getattr(self, "profile_name", None)
                )
            except Exception as e:
                log_error("Embeddings are required for Pinecone and computing them failed: %s", e)
                return False

        if not embeddings:
            log_error("Embeddings are required for Pinecone but none were provided or computed")
            return False

        index = self._get_index(collection_name)
        if not index:
            return False

        try:
            # Generate IDs if not provided
            if not ids:
                ids = [f"vec_{i}" for i in range(len(embeddings))]

            # Prepare vectors for upsert
            vectors = []
            for i, embedding in enumerate(embeddings):
                metadata = {}
                if metadatas and i < len(metadatas):
                    metadata = metadatas[i].copy()

                # Add document text to metadata
                if documents and i < len(documents):
                    metadata["document"] = documents[i]

                vectors.append({"id": ids[i], "values": embedding, "metadata": metadata})

            # Upsert in batches of 100 (Pinecone limit)
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                index.upsert(vectors=batch)

            return True
        except Exception as e:
            log_error("Failed to add items: %s", e)
            return False

    def get_items(self, name: str, ids: List[str]) -> Dict[str, Any]:
        """
        Retrieve items by IDs.

        Args:
            name: Index name
            ids: List of vector IDs

        Returns:
            Dictionary with documents and metadatas
        """
        index = self._get_index(name)
        if not index:
            return {"documents": [], "metadatas": []}

        try:
            # Fetch vectors
            result = index.fetch(ids=ids)

            documents = []
            metadatas = []

            for vid in ids:
                if vid in result.vectors:
                    vector_data = result.vectors[vid]
                    metadata = vector_data.metadata or {}

                    # Extract document from metadata
                    doc = metadata.pop("document", "")
                    documents.append(doc)
                    metadatas.append(metadata)
                else:
                    documents.append("")
                    metadatas.append({})

            return {"documents": documents, "metadatas": metadatas}
        except Exception as e:
            log_error("Failed to get items: %s", e)
            return {"documents": [], "metadatas": []}

    def delete_collection(self, name: str) -> bool:
        """
        Delete an index.

        Args:
            name: Index name

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            self._client.delete_index(name)
            if self._current_index_name == name:
                self._current_index = None
                self._current_index_name = None
            return True
        except Exception as e:
            log_error("Failed to delete index: %s", e)
            return False

    def count_collection(self, name: str) -> int:
        """
        Return the number of vectors in the index.

        Args:
            name: Index name

        Returns:
            Number of vectors
        """
        index = self._get_index(name)
        if not index:
            return 0

        try:
            stats = index.describe_index_stats()
            return stats.get("total_vector_count", 0)
        except Exception:
            return 0

    def _get_embedding_function_for_collection(self, collection_name: str):
        """
        Returns embedding function and model type for a given collection, matching ChromaDB/Qdrant API.
        """
        info = self.get_collection_info(collection_name)
        dim = info.get("vector_dimension") if info else None
        try:
            dim_int = int(dim) if dim is not None else None
        except Exception:
            dim_int = None

        # Prefer user-configured model for this collection
        from vector_inspector.services.settings_service import SettingsService

        model = None
        model_type: str = "sentence-transformer"
        profile_name = getattr(self, "profile_name", None)
        if profile_name and collection_name:
            settings = SettingsService()
            cfg = settings.get_embedding_model(profile_name, collection_name)
            if cfg and cfg.get("model") and cfg.get("type"):
                from vector_inspector.core.embedding_utils import load_embedding_model

                model = load_embedding_model(cfg["model"], cfg["type"])
                model_type = str(cfg["type"]) or "sentence-transformer"

        # Fallback to dimension-based model if none configured
        if model is None:
            from vector_inspector.core.embedding_utils import get_embedding_model_for_dimension

            if dim_int is None:
                dim_int = 384  # default for MiniLM
            loaded_model, _, inferred_type = get_embedding_model_for_dimension(dim_int)
            model = loaded_model
            model_type = str(inferred_type) or "sentence-transformer"

        from vector_inspector.core.embedding_utils import encode_text

        def embedding_fn(text: str):
            return encode_text(text, model, model_type)

        return embedding_fn, model_type

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
        Query an index for similar vectors.

        Args:
            collection_name: Name of index
            query_texts: Text queries (will be embedded if provided)
            query_embeddings: Query embedding vectors
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter (not directly supported)
        Returns:
            Query results or None if failed
        """

        # If query_embeddings not provided, but query_texts are, embed them using the embedding function
        if query_embeddings is None and query_texts:
            embedding_fn, _ = self._get_embedding_function_for_collection(collection_name)
            query_embeddings = [embedding_fn(q) for q in query_texts]
            query_texts = None

        if not query_embeddings:
            log_error("Query embeddings are required for Pinecone")
            return None

        index = self._get_index(collection_name)
        if not index:
            return None

        try:
            # Pinecone queries one vector at a time
            all_ids = []
            all_distances = []
            all_documents = []
            all_metadatas = []
            all_embeddings = []

            for query_vector in query_embeddings:
                # Build filter if provided
                filter_dict = None
                if where:
                    filter_dict = self._convert_filter(where)

                result = index.query(
                    vector=query_vector,
                    top_k=n_results,
                    include_metadata=True,
                    include_values=True,
                    filter=filter_dict,
                )

                # Extract results
                ids = []
                distances = []
                documents = []
                metadatas = []
                embeddings = []

                if hasattr(result, "matches"):
                    for match in result.matches:  # type: ignore
                        ids.append(match.id)  # type: ignore
                        # Convert similarity to distance for cosine metric
                        score = getattr(match, "score", None)
                        if score is not None:
                            distances.append(1.0 - score)
                        else:
                            distances.append(None)

                        metadata = match.metadata or {}  # type: ignore
                        doc = metadata.pop("document", "")
                        documents.append(doc)
                        metadatas.append(metadata)

                        if hasattr(match, "values") and match.values:  # type: ignore
                            embeddings.append(match.values)  # type: ignore
                        else:
                            embeddings.append([])

                all_ids.append(ids)
                all_distances.append(distances)
                all_documents.append(documents)
                all_metadatas.append(metadatas)
                all_embeddings.append(embeddings)

            return {
                "ids": all_ids,
                "distances": all_distances,
                "documents": all_documents,
                "metadatas": all_metadatas,
                "embeddings": all_embeddings,
            }
        except Exception as e:
            import traceback

            log_error("Query failed: %s\n%s", e, traceback.format_exc())
            return None

    def _convert_filter(self, where: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert generic filter to Pinecone filter format.

        Pinecone supports: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin
        """
        # Simple conversion - map field equality
        # For more complex filters, this would need expansion
        pinecone_filter = {}

        for key, value in where.items():
            if isinstance(value, dict):
                # Handle operator-based filters
                pinecone_filter[key] = value
            else:
                # Simple equality
                pinecone_filter[key] = {"$eq": value}

        return pinecone_filter

    def get_all_items(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get all items from an index using pagination.

        Note: Uses Pinecone's list() method which returns a generator of ID lists.
        Offset-based pagination is simulated by skipping items.

        Args:
            collection_name: Name of index
            limit: Maximum number of items to return
            offset: Number of items to skip
            where: Metadata filter (not supported in list operation)

        Returns:
            Index items or None if failed
        """
        index = self._get_index(collection_name)
        if not index:
            return None

        try:
            ids_to_fetch = []
            items_collected = 0
            items_skipped = 0
            target_offset = offset or 0
            target_limit = limit or 100

            # list() returns a generator that yields lists of IDs
            for id_list in index.list():  # type: ignore
                if not id_list:
                    continue

                # Handle offset by skipping items
                for vid in id_list:
                    if items_skipped < target_offset:
                        items_skipped += 1
                        continue

                    if items_collected < target_limit:
                        ids_to_fetch.append(vid)
                        items_collected += 1
                    else:
                        break

                # Stop if we have enough
                if items_collected >= target_limit:
                    break

            # If no IDs found, return empty result
            if not ids_to_fetch:
                return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

            # Fetch the actual vector data in batches (Pinecone fetch limit is 1000)
            batch_size = 1000
            all_ids = []
            all_documents = []
            all_metadatas = []
            all_embeddings = []

            for i in range(0, len(ids_to_fetch), batch_size):
                batch_ids = ids_to_fetch[i : i + batch_size]
                fetch_result = index.fetch(ids=batch_ids)

                for vid in batch_ids:
                    if vid in fetch_result.vectors:
                        vector_data = fetch_result.vectors[vid]
                        all_ids.append(vid)

                        metadata = vector_data.metadata.copy() if vector_data.metadata else {}
                        doc = metadata.pop("document", "")
                        all_documents.append(doc)
                        all_metadatas.append(metadata)
                        all_embeddings.append(vector_data.values)

            return {
                "ids": all_ids,
                "documents": all_documents,
                "metadatas": all_metadatas,
                "embeddings": all_embeddings,
            }

        except Exception as e:
            import traceback

            log_error("Failed to get all items: %s\n%s", e, traceback.format_exc())
            return {"ids": [], "documents": [], "metadatas": [], "embeddings": []}

    def update_items(
        self,
        collection_name: str,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> bool:
        """
        Update items in an index.

        Note: Pinecone updates via upsert (add_items can be used)

        Args:
            collection_name: Name of index
            ids: IDs of items to update
            documents: New document texts
            metadatas: New metadata
            embeddings: New embeddings

        Returns:
            True if successful, False otherwise
        """
        index = self._get_index(collection_name)
        if not index:
            return False

        try:
            # Fetch existing vectors to preserve data not being updated
            existing = index.fetch(ids=ids)

            vectors = []
            for i, vid in enumerate(ids):
                # Start with existing data
                if vid in existing.vectors:
                    vector_data = existing.vectors[vid]
                    values = vector_data.values if embeddings is None else embeddings[i]
                    metadata = vector_data.metadata.copy() if vector_data.metadata else {}
                else:
                    # New vector
                    if embeddings is None or i >= len(embeddings):
                        continue
                    values = embeddings[i]
                    metadata = {}

                # Update metadata
                if metadatas and i < len(metadatas):
                    metadata.update(metadatas[i])

                # Update document
                if documents and i < len(documents):
                    # If embedding not supplied, compute for this updated document
                    if (
                        embeddings is None or i >= len(embeddings) or embeddings[i] is None
                    ) and documents[i]:
                        try:
                            computed = self.compute_embeddings_for_documents(
                                collection_name,
                                [documents[i]],
                                getattr(self, "connection_id", None),
                            )
                            if computed:
                                values = computed[0]
                        except Exception as e:
                            log_error("Failed to compute embedding for Pinecone update: %s", e)
                    metadata["document"] = documents[i]

                vectors.append({"id": vid, "values": values, "metadata": metadata})

            # Upsert in batches
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                index.upsert(vectors=batch)

            return True
        except Exception as e:
            log_error("Failed to update items: %s", e)
            return False

    def delete_items(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Delete items from an index.

        Args:
            collection_name: Name of index
            ids: IDs of items to delete
            where: Metadata filter for items to delete

        Returns:
            True if successful, False otherwise
        """
        index = self._get_index(collection_name)
        if not index:
            return False

        try:
            if ids:
                # Delete by IDs
                index.delete(ids=ids)
            elif where:
                # Delete by filter
                filter_dict = self._convert_filter(where)
                index.delete(filter=filter_dict)
            else:
                # Delete all (use with caution)
                index.delete(delete_all=True)

            return True
        except Exception as e:
            log_error("Failed to delete items: %s", e)
            return False

    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about the current connection.

        Returns:
            Dictionary with connection details
        """
        info = {"provider": "Pinecone", "connected": self.is_connected}

        if self.is_connected and self._client:
            try:
                # Get account/environment info if available
                indexes = self._client.list_indexes()
                info["index_count"] = len(indexes)
            except Exception:
                pass

        return info

    def get_supported_filter_operators(self) -> List[Dict[str, Any]]:
        """
        Get filter operators supported by Pinecone.

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
