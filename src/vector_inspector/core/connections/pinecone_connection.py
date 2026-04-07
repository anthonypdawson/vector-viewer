"""Pinecone connection manager.

Namespace Best Practices:
-------------------------
Pinecone supports namespaces within indexes to organize vectors. In Vector Inspector,
namespaces are specified using the format: 'index_name::namespace'

IMPORTANT: Always use named namespaces (e.g., 'my-index::production') rather than
the default namespace (just 'my-index'). The default namespace has limitations:
- Not reported in describe_index_stats() API
- Not visible in Pinecone data browser
- Vectors exist and are queryable, but discovery is limited

Named namespaces work perfectly and are fully visible in all interfaces.

Examples:
- Good: 'embeddings::production', 'embeddings::staging', 'embeddings::dev'
- Avoid: 'embeddings' (uses default namespace with limited visibility)
"""

import time
from typing import Any, Optional

from pinecone import IndexModel, Pinecone, ServerlessSpec

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.logging import log_error


class PineconeConnection(VectorDBConnection):
    """Manages connection to Pinecone and provides query interface."""

    def __init__(self, api_key: str, environment: Optional[str] = None, index_host: Optional[str] = None):
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
        self._hosted_models: dict[str, Optional[str]] = {}  # Cache: index_name -> model_name

    @staticmethod
    def _parse_collection_name(collection_name: str) -> tuple[str, str]:
        """
        Parse a collection name into (index_name, namespace).

        Format: 'index_name' or 'index_name::namespace'
        Empty namespace is represented as empty string ''.

        Args:
            collection_name: Collection name, optionally with namespace

        Returns:
            Tuple of (index_name, namespace)
        """
        if "::" in collection_name:
            parts = collection_name.split("::", 1)
            return parts[0], parts[1]
        return collection_name, ""

    @staticmethod
    def _format_collection_name(index_name: str, namespace: str) -> str:
        """
        Format an index name and namespace into a collection name.

        Args:
            index_name: Name of the Pinecone index
            namespace: Namespace within the index (empty string for default)

        Returns:
            Formatted collection name
        """
        if namespace:
            return f"{index_name}::{namespace}"
        return index_name

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

    def list_collections(self) -> list[str]:
        """
        Get list of all indexes and their namespaces.

        Returns collection names in format:
        - 'index_name' for default namespace
        - 'index_name::namespace' for named namespaces

        Returns:
            List of collection names (index::namespace combinations)
        """
        if not self._client:
            return []
        try:
            indexes = self._client.list_indexes()
            collections = []

            for idx in indexes:
                index_name = str(idx.name)  # type: ignore

                try:
                    # Get stats to discover namespaces
                    index = self._client.Index(index_name)
                    stats = index.describe_index_stats()

                    # Extract namespaces from stats
                    namespaces_info = stats.get("namespaces", {})

                    if not namespaces_info:
                        # No vectors yet, just add the index with default namespace
                        collections.append(index_name)
                    else:
                        # Add entry for each namespace that has vectors
                        for namespace, ns_stats in namespaces_info.items():
                            vector_count = ns_stats.get("vector_count", 0)
                            if vector_count > 0:
                                collections.append(self._format_collection_name(index_name, namespace))

                        # If no namespaces have vectors, still show the index
                        if not collections or not any(c.startswith(f"{index_name}") for c in collections):
                            collections.append(index_name)

                except Exception as e:
                    log_error("Failed to get namespace info for index %s: %s", index_name, e)
                    # Fallback: just add the index name
                    collections.append(index_name)

            return collections
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

    def _check_hosted_model(self, index_name: str) -> Optional[str]:
        """
        Check if an index uses a Pinecone-hosted embedding model.

        Args:
            index_name: Name of the Pinecone index

        Returns:
            Model name if hosted model is used, None otherwise
        """
        # Check cache first
        if index_name in self._hosted_models:
            return self._hosted_models[index_name]

        # Query index description to check for hosted model
        if not self._client:
            return None

        try:
            index_description: IndexModel = self._client.describe_index(index_name)
            hosted_model = None

            # Check for model in embed field (Pinecone's hosted model info)
            if hasattr(index_description, "embed") and index_description.embed is not None:
                embed = index_description.embed
                # embed might be a dict or an object
                if isinstance(embed, dict) and "model" in embed:
                    hosted_model = embed["model"]
                elif hasattr(embed, "model") and embed.model:
                    hosted_model = embed.model
            # Also check spec (legacy/alternative location)
            elif hasattr(index_description, "spec") and index_description.spec is not None:
                spec = index_description.spec
                if hasattr(spec, "model") and spec.model:
                    hosted_model = spec.model
                elif hasattr(spec, "index_config") and hasattr(spec.index_config, "model"):
                    hosted_model = spec.index_config.model

            # Cache the result
            self._hosted_models[index_name] = hosted_model
            if hosted_model:
                log_error("✓ Detected Pinecone hosted model for '%s': %s", index_name, hosted_model)
            return hosted_model
        except Exception as e:
            log_error("Failed to check hosted model for index %s: %s", index_name, e)
            return None

    def _embed_with_inference_api(self, model: str, texts: list[str], input_type: str = "query") -> list[list[float]]:
        """
        Use Pinecone's inference API to embed texts.

        Args:
            model: Model name (e.g., 'llama-text-embed-v2')
            texts: List of texts to embed
            input_type: 'query' or 'passage'

        Returns:
            List of embedding vectors

        Raises:
            Exception if inference API is not available or fails
        """
        if not self._client or not hasattr(self._client, "inference"):
            raise Exception("Pinecone inference API not available on this client")

        try:
            result = self._client.inference.embed(model=model, inputs=texts, parameters={"input_type": input_type})

            # Extract embeddings from result
            embeddings = []
            for item in result:
                if hasattr(item, "values"):
                    embeddings.append(item.values)
                elif isinstance(item, dict) and "values" in item:
                    embeddings.append(item["values"])
                else:
                    raise Exception(f"Unexpected inference API response format: {type(item)}")

            return embeddings
        except Exception as e:
            raise Exception(f"Inference API embedding failed: {e}") from e

    def get_collection_info(self, name: str) -> Optional[dict[str, Any]]:
        """
        Get index metadata and statistics for a specific namespace.

        Args:
            name: Collection name (format: 'index' or 'index::namespace')

        Returns:
            Dictionary with index info
        """
        if not self._client:
            return None

        try:
            # Parse collection name to get index and namespace
            index_name, namespace = self._parse_collection_name(name)

            # Get index description
            index_description = self._client.describe_index(index_name)

            # Get index stats
            index = self._get_index(index_name)
            if not index:
                return None

            # Get all stats (describe_index_stats returns stats for all namespaces)
            stats = index.describe_index_stats()

            # Extract information for this specific namespace
            if namespace and "namespaces" in stats:
                namespace_stats = stats["namespaces"].get(namespace, {})
                total_vector_count = namespace_stats.get("vector_count", 0)
            else:
                # For default namespace or when no namespaces exist
                total_vector_count = stats.get("total_vector_count", 0)

            dimension = index_description.dimension
            metric = index_description.metric

            # Check if index uses a Pinecone-hosted embedding model
            hosted_model = None
            if hasattr(index_description, "embed"):
                embed = index_description.embed
                # embed might be a dict or an object
                if isinstance(embed, dict) and "model" in embed:
                    hosted_model = embed["model"]
                elif hasattr(embed, "model") and embed.model:
                    hosted_model = embed.model
            # Also check spec (legacy/alternative location)
            elif hasattr(index_description, "spec"):
                spec = index_description.spec
                if hasattr(spec, "model") and spec.model:
                    hosted_model = spec.model
                elif hasattr(spec, "index_config") and hasattr(spec.index_config, "model"):
                    hosted_model = spec.index_config.model

            # Cache the hosted model info for this index
            self._hosted_models[index_name] = hosted_model

            # Get metadata fields from a sample query (if vectors exist)
            metadata_fields = []
            if total_vector_count > 0:
                try:
                    # Query for a small sample to see metadata structure
                    dimension_val = int(dimension) if dimension else 0
                    sample_query = index.query(
                        vector=[0.0] * dimension_val,
                        top_k=1,
                        include_metadata=True,
                        namespace=namespace,
                    )
                    if hasattr(sample_query, "matches") and sample_query.matches:  # type: ignore
                        metadata = sample_query.matches[0].metadata  # type: ignore
                        if metadata:
                            metadata_fields = list(metadata.keys())
                except Exception:
                    pass  # Metadata fields will remain empty

            info_dict = {
                "name": name,
                "index_name": index_name,
                "namespace": namespace if namespace else "(default)",
                "count": total_vector_count,
                "metadata_fields": metadata_fields,
                "vector_dimension": dimension,
                "distance_metric": str(metric).upper() if metric else "UNKNOWN",
                "host": str(index_description.host) if hasattr(index_description, "host") else "N/A",
                "status": index_description.status.get("state", "unknown")
                if hasattr(index_description.status, "get")
                else str(index_description.status),  # type: ignore
                "spec": str(index_description.spec) if hasattr(index_description, "spec") else "N/A",
            }

            # Add hosted model info if detected
            if hosted_model:
                info_dict["embedding_model"] = hosted_model
                info_dict["embedding_model_type"] = "pinecone-hosted"

            return info_dict
        except Exception as e:
            log_error("Failed to get index info: %s", e)
            return None

    def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        """
        Create a new index.

        Note: In Pinecone, indexes are created but namespaces are implicit.
        If name includes '::namespace', only the index will be created.
        Namespaces are automatically created when data is added to them.

        IMPORTANT: For Pinecone, it's recommended to always use named namespaces
        (e.g., 'index::production' rather than just 'index') because the default
        namespace has limitations with visibility in stats API and data browser.

        Args:
            name: Index name (format: 'index::namespace' recommended, or 'index' alone)
            vector_size: Dimension of vectors
            distance: Distance metric (Cosine, Euclidean, DotProduct)

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            # Parse name - only use index part for creation
            index_name, namespace = self._parse_collection_name(name)

            # Warn if using default namespace
            if not namespace:
                log_error(
                    "RECOMMENDATION: Consider using a named namespace (e.g., '%s::main') "
                    "instead of the default namespace. Named namespaces are fully visible "
                    "in Pinecone's data browser and stats API.",
                    index_name,
                )

            if namespace:
                log_error(
                    "Note: Creating index '%s'. Namespace '%s' will be created when data is added.",
                    index_name,
                    namespace,
                )

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
                name=index_name,
                dimension=vector_size,
                metric=metric,
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )

            # Wait for index to be ready
            max_wait = 60  # seconds
            start_time = time.time()
            while time.time() - start_time < max_wait:
                desc = self._client.describe_index(index_name)
                status = desc.status.get("state", "unknown") if hasattr(desc.status, "get") else str(desc.status)  # type: ignore
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
        documents: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
        ids: Optional[list[str]] = None,
        embeddings: Optional[list[list[float]]] = None,
    ) -> bool:
        """
        Add items to an index namespace.

        Args:
            collection_name: Collection name (format: 'index' or 'index::namespace')
            documents: Document texts (stored in metadata)
            metadatas: Metadata for each vector
            ids: IDs for each vector
            embeddings: Pre-computed embeddings (required for Pinecone)

        Returns:
            True if successful, False otherwise
        """
        # Parse collection name
        index_name, namespace = self._parse_collection_name(collection_name)

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

        index = self._get_index(index_name)
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

            # Upsert in batches of 100 (Pinecone limit) with namespace
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                # For default namespace, omit the namespace parameter
                if namespace:
                    index.upsert(vectors=batch, namespace=namespace)
                else:
                    index.upsert(vectors=batch)

            return True
        except Exception as e:
            log_error("Failed to add items: %s", e)
            return False

    def get_items(self, name: str, ids: list[str]) -> dict[str, Any]:
        """
        Retrieve items by IDs from a namespace.

        Args:
            name: Collection name (format: 'index' or 'index::namespace')
            ids: List of vector IDs

        Returns:
            Dictionary with documents and metadatas
        """
        # Parse collection name
        index_name, namespace = self._parse_collection_name(name)

        index = self._get_index(index_name)
        if not index:
            return {"documents": [], "metadatas": []}

        try:
            # Fetch vectors from namespace
            # For default namespace, omit the namespace parameter
            if namespace:
                result = index.fetch(ids=ids, namespace=namespace)
            else:
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
        Delete an index or clear a namespace.

        If name is just an index name, deletes the entire index.
        If name includes '::namespace', deletes all vectors in that namespace.

        Args:
            name: Collection name (format: 'index' or 'index::namespace')

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            # Parse collection name
            index_name, namespace = self._parse_collection_name(name)

            if namespace:
                # Delete all vectors in the namespace (keeps index and other namespaces)
                index = self._get_index(index_name)
                if not index:
                    return False
                index.delete(delete_all=True, namespace=namespace)
            else:
                # Delete the entire index
                self._client.delete_index(index_name)
                if self._current_index_name == index_name:
                    self._current_index = None
                    self._current_index_name = None

            return True
        except Exception as e:
            log_error("Failed to delete collection: %s", e)
            return False

    def count_collection(self, name: str) -> int:
        """
        Return the number of vectors in the namespace.

        Args:
            name: Collection name (format: 'index' or 'index::namespace')

        Returns:
            Number of vectors
        """
        # Parse collection name
        index_name, namespace = self._parse_collection_name(name)

        index = self._get_index(index_name)
        if not index:
            return 0

        try:
            stats = index.describe_index_stats()

            # Get count for specific namespace
            if namespace and "namespaces" in stats:
                namespace_stats = stats["namespaces"].get(namespace, {})
                return namespace_stats.get("vector_count", 0)

            return stats.get("total_vector_count", 0)
        except Exception:
            return 0

    def _get_embedding_function_for_collection(self, collection_name: str):
        """
        Returns embedding function and model type for a given collection.

        Delegates model resolution to the base-class ``load_embedding_model_for_collection``
        so the full resolution order (SettingsService → collection metadata → dimension →
        DEFAULT_MODEL) is respected for all providers, including CLIP-based collections.

        Note: For collections using Pinecone-hosted models, this should not be called.
        Text queries are handled directly by Pinecone.
        """
        # Warn if the caller is trying to embed locally for a hosted-model collection.
        info = self.get_collection_info(collection_name)
        if info and info.get("embedding_model_type") == "pinecone-hosted":
            hosted_model = info.get("embedding_model", "unknown")
            log_error(
                "Warning: Attempting to generate local embeddings for collection '%s' "
                "that uses Pinecone-hosted model '%s'. This may indicate a configuration issue. "
                "Consider using text queries instead.",
                collection_name,
                hosted_model,
            )

        from vector_inspector.core.embedding_utils import encode_text

        model, _, model_type = self.load_embedding_model_for_collection(collection_name)

        def embedding_fn(text: str):
            return encode_text(text, model, model_type)

        return embedding_fn, model_type

    def query_collection(
        self,
        collection_name: str,
        query_texts: Optional[list[str]] = None,
        query_embeddings: Optional[list[list[float]]] = None,
        n_results: int = 10,
        where: Optional[dict[str, Any]] = None,
        _where_document: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Query a namespace for similar vectors.

        For indexes with hosted models, uses direct text-based search API.

        Args:
            collection_name: Collection name (format: 'index' or 'index::namespace')
            query_texts: Text queries (for hosted models, searches directly; otherwise embedded locally)
            query_embeddings: Query embedding vectors
            n_results: Number of results to return
            where: Metadata filter
            _where_document: Document content filter (not directly supported)
        Returns:
            Query results or None if failed
        """
        # Parse collection name
        index_name, namespace = self._parse_collection_name(collection_name)

        # Check if index uses hosted model
        hosted_model = self._check_hosted_model(index_name)

        # If hosted model and text queries, use direct text search
        if hosted_model and query_texts and query_embeddings is None:
            log_error("Using Pinecone hosted model '%s' for text-based search", hosted_model)
            return self._query_with_hosted_model(index_name, namespace, query_texts, n_results, where)

        # Otherwise, use vector-based query
        # If query_embeddings not provided, embed the query texts
        if query_embeddings is None and query_texts:
            try:
                embedding_fn, _ = self._get_embedding_function_for_collection(collection_name)
                query_embeddings = [embedding_fn(q) for q in query_texts]
            except Exception as e:
                log_error("Failed to generate embeddings for query. Error: %s", e)
                return None

        if not query_embeddings:
            log_error("Query embeddings are required for Pinecone")
            return None

        index = self._get_index(index_name)
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

                # For default namespace, omit the namespace parameter
                if namespace:
                    result = index.query(
                        vector=query_vector,
                        top_k=n_results,
                        include_metadata=True,
                        include_values=True,
                        filter=filter_dict,
                        namespace=namespace,
                    )
                else:
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
                "query_embedding": query_embeddings[0] if query_embeddings else None,
                "query_embedding_model": None,
            }
        except Exception as e:
            import traceback

            log_error("Query failed: %s\n%s", e, traceback.format_exc())
            return None

    def _query_with_hosted_model(
        self,
        index_name: str,
        namespace: str,
        query_texts: list[str],
        n_results: int,
        where: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Query using Pinecone-hosted embedding model with direct text search.

        Uses index.search() with text inputs - Pinecone embeds the text server-side.

        Args:
            index_name: Name of the Pinecone index
            namespace: Namespace within the index
            query_texts: Text queries (embedded server-side by Pinecone)
            n_results: Number of results to return
            where: Metadata filter

        Returns:
            Query results or None if failed
        """
        index = self._get_index(index_name)
        if not index:
            return None

        try:
            # Pinecone queries one text at a time for hosted models
            all_ids = []
            all_distances = []
            all_documents = []
            all_metadatas = []
            all_embeddings = []

            for query_text in query_texts:
                # Build filter if provided
                filter_dict = None
                if where:
                    filter_dict = self._convert_filter(where)

                # Use index.search() with text input format for hosted models
                query_dict = {
                    "inputs": {"text": query_text},
                    "top_k": n_results,
                }

                search_params: dict[str, Any] = {"query": query_dict}

                # Add namespace if specified
                if namespace:
                    search_params["namespace"] = namespace

                # Add filter if provided
                if filter_dict:
                    query_dict["filter"] = filter_dict

                # Use search() method for text-based queries with hosted models
                # Note: search() doesn't use include_metadata/include_values like query()
                result = index.search(**search_params)

                # Extract results
                # Note: search() returns {'result': {'hits': [...]}} structure
                # while query() returns {'matches': [...]} structure
                ids = []
                distances = []
                documents = []
                metadatas = []
                embeddings = []

                # Handle search() response structure
                if hasattr(result, "result") and hasattr(result.result, "hits"):
                    hits = result.result.hits
                elif isinstance(result, dict) and "result" in result and "hits" in result["result"]:
                    hits = result["result"]["hits"]
                else:
                    log_error("Unexpected search response structure: %s", result)
                    hits = []

                for hit in hits:
                    # Extract ID (search uses '_id' not 'id')
                    hit_id = hit.get("_id") if isinstance(hit, dict) else getattr(hit, "_id", None)
                    if hit_id:
                        ids.append(hit_id)

                    # Extract score (search uses '_score' not 'score')
                    score = hit.get("_score") if isinstance(hit, dict) else getattr(hit, "_score", None)
                    if score is not None:
                        # Convert similarity to distance for cosine metric
                        distances.append(1.0 - score)
                    else:
                        distances.append(None)

                    # Extract fields (search uses 'fields' not 'metadata')
                    fields = hit.get("fields", {}) if isinstance(hit, dict) else getattr(hit, "fields", {})
                    if isinstance(fields, dict):
                        metadata = dict(fields)
                        doc = metadata.pop("document", "")
                        documents.append(doc)
                        metadatas.append(metadata)
                    else:
                        documents.append("")
                        metadatas.append({})

                    # search() doesn't return vector values
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

            log_error("Text query with hosted model failed: %s\n%s", e, traceback.format_exc())
            return None

    def _convert_filter(self, where: dict[str, Any]) -> dict[str, Any]:
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
        where: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Get all items from a namespace using pagination.

        Note: Uses Pinecone's list() method which returns a generator of ID lists.
        Offset-based pagination is simulated by skipping items.

        Args:
            collection_name: Collection name (format: 'index' or 'index::namespace')
            limit: Maximum number of items to return
            offset: Number of items to skip
            where: Metadata filter (not supported in list operation)

        Returns:
            Index items or None if failed
        """
        # Parse collection name
        index_name, namespace = self._parse_collection_name(collection_name)

        index = self._get_index(index_name)
        if not index:
            return None

        try:
            ids_to_fetch = []
            items_collected = 0
            items_skipped = 0
            target_offset = offset or 0
            target_limit = limit or 100

            # list() returns a generator that yields lists of IDs
            # For default namespace, omit the namespace parameter
            id_generator = index.list(namespace=namespace) if namespace else index.list()  # type: ignore
            for id_list in id_generator:
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
                # For default namespace, omit the namespace parameter
                if namespace:
                    fetch_result = index.fetch(ids=batch_ids, namespace=namespace)
                else:
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
        ids: list[str],
        documents: Optional[list[str]] = None,
        metadatas: Optional[list[dict[str, Any]]] = None,
        embeddings: Optional[list[list[float]]] = None,
    ) -> bool:
        """
        Update items in a namespace.

        Note: Pinecone updates via upsert (add_items can be used)

        Args:
            collection_name: Collection name (format: 'index' or 'index::namespace')
            ids: IDs of items to update
            documents: New document texts
            metadatas: New metadata
            embeddings: New embeddings

        Returns:
            True if successful, False otherwise
        """
        # Parse collection name
        index_name, namespace = self._parse_collection_name(collection_name)

        index = self._get_index(index_name)
        if not index:
            return False

        try:
            # Fetch existing vectors to preserve data not being updated
            # For default namespace, omit the namespace parameter
            if namespace:
                existing = index.fetch(ids=ids, namespace=namespace)
            else:
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
                    if (embeddings is None or i >= len(embeddings) or embeddings[i] is None) and documents[i]:
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

            # Upsert in batches with namespace
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                # For default namespace, omit the namespace parameter
                if namespace:
                    index.upsert(vectors=batch, namespace=namespace)
                else:
                    index.upsert(vectors=batch)

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
        Delete items from a namespace.

        Args:
            collection_name: Collection name (format: 'index' or 'index::namespace')
            ids: IDs of items to delete
            where: Metadata filter for items to delete

        Returns:
            True if successful, False otherwise
        """
        # Parse collection name
        index_name, namespace = self._parse_collection_name(collection_name)

        index = self._get_index(index_name)
        if not index:
            return False

        try:
            if ids:
                # Delete by IDs in namespace
                # For default namespace, omit the namespace parameter
                if namespace:
                    index.delete(ids=ids, namespace=namespace)
                else:
                    index.delete(ids=ids)
            elif where:
                # Delete by filter in namespace
                filter_dict = self._convert_filter(where)
                if namespace:
                    index.delete(filter=filter_dict, namespace=namespace)
                else:
                    index.delete(filter=filter_dict)
            else:
                # Delete all in namespace (use with caution)
                if namespace:
                    index.delete(delete_all=True, namespace=namespace)
                else:
                    index.delete(delete_all=True)

            return True
        except Exception as e:
            log_error("Failed to delete items: %s", e)
            return False

    def get_connection_info(self) -> dict[str, Any]:
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

    def get_supported_filter_operators(self) -> list[dict[str, Any]]:
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
