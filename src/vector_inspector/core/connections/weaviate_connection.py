"""Weaviate connection manager.

Supports local (self-hosted), cloud (managed), and embedded instances.

Connection Modes:
-----------------
1. Local: Connect to self-hosted Weaviate instance via HTTP/gRPC
   - Requires: host, port (default: 8080)
   - Optional: API key for authentication

2. Cloud: Connect to Weaviate Cloud (WCD)
   - Requires: cluster URL, API key
   - Format: <cluster-id>.weaviate.cloud

3. Embedded: Run Weaviate within the Python process
   - Requires: persistence_directory (optional)
   - Best for development and testing
   - No external server needed

Collections (Classes):
---------------------
Weaviate uses "classes" rather than "collections". In Vector Inspector,
we use "collection" terminology for consistency, but map to Weaviate classes.

References:
----------
https://docs.weaviate.io/weaviate
https://docs.weaviate.io/weaviate/client-libraries/python/notes-best-practices
"""

import uuid
from pathlib import Path
from typing import Any, Optional

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.logging import log_error, log_info
from vector_inspector.utils.lazy_imports import get_weaviate_client


class WeaviateConnection(VectorDBConnection):
    """Manages connection to Weaviate and provides query interface."""

    def __init__(
        self,
        url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        api_key: Optional[str] = None,
        use_grpc: bool = True,
        timeout: int = 300,
        mode: Optional[str] = None,
        persistence_directory: Optional[str] = None,
        embedded_version: Optional[str] = None,
    ):
        """
        Initialize Weaviate connection.

        Args:
            url: Full URL for Weaviate instance (e.g., "http://localhost:8080" or WCD URL)
            host: Host for local instance (alternative to url)
            port: Port for local instance (default: 8080)
            api_key: API key for authentication (required for WCD, optional for local)
            use_grpc: Use gRPC for data operations (faster, default: True)
            timeout: Request timeout in seconds (default: 300)
            mode: Connection mode ("local", "cloud", "embedded")
            persistence_directory: Directory for embedded instance data
            embedded_version: Weaviate version for embedded instance (e.g., "1.28.0")
        """
        self.url = url
        self.host = host
        # allow port to be None (no port configured)
        self.port = port
        self.api_key = api_key
        self.use_grpc = use_grpc
        self.timeout = timeout
        self.mode = mode
        self.persistence_directory = persistence_directory
        self.embedded_version = embedded_version
        self._client = None
        self._weaviate_module = None

    def connect(self) -> bool:
        """
        Establish connection to Weaviate.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Import weaviate client lazily
            self._weaviate_module = get_weaviate_client()
            weaviate = self._weaviate_module

            # Determine connection mode
            is_embedded = self.mode == "embedded" or (
                not self.url and not self.host and self.persistence_directory
            )

            if is_embedded:
                # Embedded mode: run Weaviate in-process
                log_info("Connecting to Weaviate in embedded mode")

                # Prepare embedded options
                embedded_options = weaviate.embedded.EmbeddedOptions()

                if self.persistence_directory:
                    persistence_path = Path(self.persistence_directory)
                    persistence_path.mkdir(parents=True, exist_ok=True)
                    embedded_options.persistence_data_path = str(persistence_path)

                if self.embedded_version:
                    embedded_options.version = self.embedded_version

                # Create embedded client
                self._client = weaviate.WeaviateClient(
                    embedded_options=embedded_options,
                    additional_config=weaviate.config.AdditionalConfig(
                        timeout=(self.timeout, self.timeout)
                    ),
                )

                self._client.connect()

                if not self._client.is_ready():
                    log_error("Embedded Weaviate instance is not ready")
                    self._client = None
                    return False

                log_info("Successfully started embedded Weaviate instance")
                return True

            # Remote connection (local or cloud)
            # Determine connection URL. If `url` is provided use it directly.
            if self.url:
                connection_url = self.url
            elif self.host:
                # If port provided include it, otherwise default to 8080
                # Use a concrete default here to avoid passing `None` into
                # ProtocolParams (pydantic validation errors). Profiles may
                # still persist an empty port, but for connection attempts
                # assume the common default port 8080.
                if self.port:
                    connection_url = f"http://{self.host}:{self.port}"
                else:
                    connection_url = f"http://{self.host}:8080"
            else:
                # Fallback to localhost default
                connection_url = "http://localhost:8080"

            # Check if this is a cloud URL (contains weaviate.cloud, weaviate.network, or .wcd.)
            is_cloud = (
                "weaviate.cloud" in connection_url
                or "weaviate.network" in connection_url
                or ".wcd." in connection_url.lower()
            )

            # Build connection params and create client
            if is_cloud and self.api_key:
                # Use Weaviate Cloud helper - strip scheme if present as it expects bare hostname
                cluster_url = connection_url
                if cluster_url.startswith(("http://", "https://")):
                    cluster_url = cluster_url.split("://", 1)[1]

                log_info("Connecting to Weaviate Cloud at %s", cluster_url)
                self._client = weaviate.connect_to_weaviate_cloud(
                    cluster_url=cluster_url,
                    auth_credentials=weaviate.auth.AuthApiKey(api_key=self.api_key),
                    additional_config=weaviate.config.AdditionalConfig(
                        timeout=(self.timeout, self.timeout)
                    ),
                )
            else:
                # Local or self-hosted instance
                # Ensure URL has a scheme for ConnectionParams.from_url()
                local_url = connection_url
                if not local_url.startswith(("http://", "https://")):
                    local_url = f"http://{local_url}"

                # Determine grpc_port only when gRPC requested and not cloud
                grpc_port = None
                if self.use_grpc and self.port:
                    grpc_port = 50051

                auth_config = None
                if self.api_key:
                    auth_config = weaviate.auth.AuthApiKey(api_key=self.api_key)

                # Build connection params - only pass grpc_port if it's set
                if grpc_port:
                    connection_params = weaviate.connect.ConnectionParams.from_url(
                        url=local_url,
                        grpc_port=grpc_port,
                    )
                else:
                    connection_params = weaviate.connect.ConnectionParams.from_url(
                        url=local_url,
                    )

                self._client = weaviate.WeaviateClient(
                    connection_params=connection_params,
                    auth_client_secret=auth_config,
                    additional_config=weaviate.config.AdditionalConfig(
                        timeout=(self.timeout, self.timeout)  # (connect, read) timeouts
                    ),
                )

            # Connect and test
            self._client.connect()

            # Verify connection by checking if server is ready
            if not self._client.is_ready():
                log_error("Weaviate server is not ready")
                self._client = None
                return False

            log_info("Successfully connected to Weaviate at %s", connection_url)
            return True

        except Exception as e:
            log_error("Connection failed: %s", e)
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
            self._client = None
            return False

    def disconnect(self):
        """Close connection to Weaviate."""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                log_error("Error during disconnect: %s", e)
            finally:
                self._client = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to Weaviate."""
        if self._client is None:
            return False
        try:
            return self._client.is_ready()
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        """
        Get list of all collections (classes).

        Returns:
            List of collection names
        """
        if not self._client:
            return []
        try:
            # Get all classes from schema
            collections = self._client.collections.list_all()
            return list(collections.keys())
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
            collection = self._client.collections.get(name)

            # Get collection config
            config = collection.config.get()

            # Get aggregate count
            aggregate = collection.aggregate.over_all(total_count=True)
            count = aggregate.total_count if aggregate else 0

            # Extract vector configuration
            vector_dimension = "Unknown"
            distance_metric = "Unknown"

            # Try to get dimensions from vector_config
            if hasattr(config, "vector_config"):
                vector_configs = config.vector_config
                if vector_configs:
                    # Get first vector config (Weaviate supports named vectors)
                    first_config = (
                        next(iter(vector_configs.values()))
                        if isinstance(vector_configs, dict)
                        else vector_configs
                    )

                    # Try to get dimension from vector_index_config
                    if hasattr(first_config, "vector_index_config"):
                        # Try different possible attribute names for dimensions
                        vec_idx_cfg = first_config.vector_index_config
                        if hasattr(vec_idx_cfg, "dimensions"):
                            vector_dimension = vec_idx_cfg.dimensions
                        elif hasattr(vec_idx_cfg, "dimension"):
                            vector_dimension = vec_idx_cfg.dimension

                        # Get distance metric
                        distance = getattr(vec_idx_cfg, "distance_metric", None)
                        if distance:
                            # Map Weaviate distance metrics to readable names
                            distance_str = str(distance).upper()
                            if "COSINE" in distance_str:
                                distance_metric = "Cosine"
                            elif "DOT" in distance_str:
                                distance_metric = "Dot Product"
                            elif "L2" in distance_str or "EUCLIDEAN" in distance_str:
                                distance_metric = "Euclidean (L2)"
                            elif "MANHATTAN" in distance_str or "L1" in distance_str:
                                distance_metric = "Manhattan (L1)"
                            elif "HAMMING" in distance_str:
                                distance_metric = "Hamming"
                            else:
                                distance_metric = distance_str

            # If dimension still unknown, try to get from a sample vector
            if vector_dimension == "Unknown" or vector_dimension is None:
                try:
                    response = collection.query.fetch_objects(limit=1, include_vector=True)
                    if response.objects and len(response.objects) > 0:
                        obj = response.objects[0]
                        if hasattr(obj, "vector") and obj.vector:
                            # Check if it's a dict (named vectors) or list
                            if isinstance(obj.vector, dict):
                                # Get first named vector
                                first_vector = next(iter(obj.vector.values()))
                                vector_dimension = len(first_vector) if first_vector else "Unknown"
                            elif isinstance(obj.vector, list):
                                vector_dimension = len(obj.vector)
                except Exception as e:
                    log_error("Failed to get dimension from sample vector: %s", e)

            # Get metadata fields from a sample object
            metadata_fields = []
            try:
                # Query for one object to inspect properties
                response = collection.query.fetch_objects(limit=1, include_vector=False)
                if response.objects and len(response.objects) > 0:
                    obj = response.objects[0]
                    # Exclude internal fields and 'document'
                    metadata_fields = [
                        k for k in obj.properties if k != "document" and not k.startswith("_")
                    ]
            except Exception as e:
                log_error("Failed to get sample object for metadata fields: %s", e)

            result = {
                "name": name,
                "count": count,
                "metadata_fields": metadata_fields,
                "vector_dimension": vector_dimension,
                "distance_metric": distance_metric,
            }

            # Check for embedding model in config
            if hasattr(config, "vectorizer_config") and config.vectorizer_config:
                vectorizer_configs = config.vectorizer_config
                if vectorizer_configs:
                    first_vectorizer = (
                        next(iter(vectorizer_configs.values()))
                        if isinstance(vectorizer_configs, dict)
                        else vectorizer_configs
                    )

                    if hasattr(first_vectorizer, "model"):
                        result["embedding_model"] = first_vectorizer.model.get("model", "Unknown")
                        result["embedding_model_type"] = "weaviate-vectorizer"

            return result

        except Exception as e:
            log_error("Failed to get collection info: %s", e)
            return None

    def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        """
        Create a new collection (class).

        Args:
            name: Collection name
            vector_size: Dimension of vectors
            distance: Distance metric ("Cosine", "Dot", "L2", "Manhattan", "Hamming")

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            weaviate = self._weaviate_module

            # Map distance string to Weaviate distance metric
            distance_map = {
                "cosine": weaviate.classes.config.VectorDistances.COSINE,
                "dot": weaviate.classes.config.VectorDistances.DOT,
                "dotproduct": weaviate.classes.config.VectorDistances.DOT,
                "l2": weaviate.classes.config.VectorDistances.L2_SQUARED,
                "euclidean": weaviate.classes.config.VectorDistances.L2_SQUARED,
                "manhattan": weaviate.classes.config.VectorDistances.MANHATTAN,
                "l1": weaviate.classes.config.VectorDistances.MANHATTAN,
                "hamming": weaviate.classes.config.VectorDistances.HAMMING,
            }

            weaviate_distance = distance_map.get(
                distance.lower(), weaviate.classes.config.VectorDistances.COSINE
            )

            # Create collection with manual vectorization (we provide embeddings)
            # Use Property to define schema
            self._client.collections.create(
                name=name,
                properties=[
                    weaviate.classes.config.Property(
                        name="document",
                        data_type=weaviate.classes.config.DataType.TEXT,
                    ),
                ],
                # Use new vector_config syntax (replaces deprecated vectorizer_config + vector_index_config)
                vector_config=weaviate.classes.config.Configure.Vectors.self_provided(
                    vector_index_config=weaviate.classes.config.Configure.VectorIndex.hnsw(
                        distance_metric=weaviate_distance,
                    ),
                ),
            )

            log_info(
                "Created collection '%s' with dimension %d and distance %s",
                name,
                vector_size,
                distance,
            )
            return True

        except Exception as e:
            log_error("Failed to create collection: %s", e)
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
        Add items to a collection.

        Args:
            collection_name: Name of collection
            documents: Document texts
            metadatas: Metadata for each document
            ids: IDs for each document (will generate UUIDs if not provided)
            embeddings: Pre-computed embeddings (required for manual vectorization)

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        if not documents:
            return False

        # If embeddings not provided, compute using base helper
        if not embeddings and documents:
            try:
                embeddings = self.compute_embeddings_for_documents(
                    collection_name, documents, getattr(self, "profile_name", None)
                )
            except Exception as e:
                log_error("Embeddings are required for Weaviate and computing them failed: %s", e)
                return False

        if not embeddings:
            log_error("Embeddings are required for Weaviate but none were provided or computed")
            return False

        try:
            collection = self._client.collections.get(collection_name)

            # Prepare data objects for batch insert
            weaviate = self._weaviate_module
            data_objects = []

            for i in range(len(documents)):
                # Build properties with document and metadata
                properties = {"document": documents[i]}

                if metadatas and i < len(metadatas):
                    # Add metadata fields as properties
                    properties.update(metadatas[i])

                # Handle UUID for this item
                item_uuid = None
                if ids and i < len(ids) and ids[i]:
                    # Try to use provided ID as UUID
                    try:
                        # Validate if it's already a valid UUID
                        item_uuid = uuid.UUID(ids[i])
                    except (ValueError, AttributeError):
                        # Not a valid UUID - generate deterministic UUID from the string
                        # Using uuid5 ensures same string always generates same UUID
                        namespace = uuid.UUID(
                            "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
                        )  # DNS namespace
                        item_uuid = uuid.uuid5(namespace, ids[i])
                else:
                    # No ID provided - generate random UUID
                    item_uuid = uuid.uuid4()

                # Create data object
                data_obj = weaviate.classes.data.DataObject(
                    properties=properties,
                    vector=embeddings[i],
                    uuid=item_uuid,
                )
                data_objects.append(data_obj)

            # Batch insert
            with collection.batch.dynamic() as batch:
                for obj in data_objects:
                    batch.add_object(
                        properties=obj.properties,
                        vector=obj.vector,
                        uuid=obj.uuid,
                    )

            log_info("Added %d items to collection '%s'", len(documents), collection_name)
            return True

        except Exception as e:
            log_error("Failed to add items: %s", e)
            return False

    def get_items(self, name: str, ids: list[str]) -> dict[str, Any]:
        """
        Retrieve items by IDs.

        Args:
            name: Collection name
            ids: List of object UUIDs

        Returns:
            Dictionary with documents and metadatas
        """
        if not self._client:
            return {"documents": [], "metadatas": []}

        try:
            collection = self._client.collections.get(name)

            documents = []
            metadatas = []

            for obj_id in ids:
                try:
                    # Fetch object by UUID
                    obj = collection.query.fetch_object_by_id(uuid.UUID(obj_id))

                    if obj:
                        # Extract document from properties
                        properties = obj.properties
                        doc = properties.pop("document", "")
                        documents.append(doc)

                        # Remaining properties are metadata
                        metadatas.append(properties)
                    else:
                        documents.append("")
                        metadatas.append({})
                except Exception as e:
                    log_error("Failed to fetch object %s: %s", obj_id, e)
                    documents.append("")
                    metadatas.append({})

            return {"documents": documents, "metadatas": metadatas}

        except Exception as e:
            log_error("Failed to get items: %s", e)
            return {"documents": [], "metadatas": []}

    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection (class).

        Args:
            name: Collection name

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            self._client.collections.delete(name)
            log_info("Deleted collection '%s'", name)
            return True
        except Exception as e:
            log_error("Failed to delete collection: %s", e)
            return False

    def count_collection(self, name: str) -> int:
        """
        Return the number of objects in the collection.

        Args:
            name: Collection name

        Returns:
            Number of objects
        """
        if not self._client:
            return 0

        try:
            collection = self._client.collections.get(name)
            aggregate = collection.aggregate.over_all(total_count=True)
            return aggregate.total_count if aggregate else 0
        except Exception:
            return 0

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
        if not self._client:
            return None

        if not query_texts and not query_embeddings:
            log_error("Either query_texts or query_embeddings required")
            return None

        try:
            collection = self._client.collections.get(collection_name)

            # If query_texts provided, embed them
            if query_texts and not query_embeddings:
                try:
                    query_embeddings = self.compute_embeddings_for_documents(
                        collection_name, query_texts, getattr(self, "profile_name", None)
                    )
                except Exception as e:
                    log_error("Failed to embed query texts: %s", e)
                    return None

            if not query_embeddings:
                log_error("Query embeddings are required but none were provided or computed")
                return None

            # Build filter if provided
            weaviate_filter = self._build_filter(where) if where else None

            # Perform search for each query
            all_results = {
                "ids": [],
                "distances": [],
                "documents": [],
                "metadatas": [],
                "embeddings": [],
            }

            for query_vector in query_embeddings:
                # Use near_vector for vector similarity search
                response = collection.query.near_vector(
                    near_vector=query_vector,
                    limit=n_results,
                    return_metadata=["distance"],
                    filters=weaviate_filter,
                )

                # Extract results
                ids = []
                distances = []
                documents = []
                metadatas = []
                embeddings = []

                for obj in response.objects:
                    ids.append(str(obj.uuid))

                    # Extract distance from metadata
                    distance = obj.metadata.distance if hasattr(obj.metadata, "distance") else None
                    distances.append(distance)

                    # Extract document and metadata from properties
                    properties = obj.properties.copy()
                    doc = properties.pop("document", "")
                    documents.append(doc)
                    metadatas.append(properties)

                    # Extract embedding vector
                    if hasattr(obj, "vector") and obj.vector:
                        # Handle both dict and list vector formats
                        if isinstance(obj.vector, dict):
                            embeddings.append(next(iter(obj.vector.values())))
                        else:
                            embeddings.append(obj.vector)
                    else:
                        embeddings.append([])

                all_results["ids"].append(ids)
                all_results["distances"].append(distances)
                all_results["documents"].append(documents)
                all_results["metadatas"].append(metadatas)
                all_results["embeddings"].append(embeddings)

            return all_results

        except Exception as e:
            log_error("Query failed: %s", e)
            return None

    def _build_filter(self, where: Optional[dict[str, Any]]) -> Optional[Any]:
        """
        Build Weaviate filter from generic filter dict.

        Args:
            where: Generic filter dictionary

        Returns:
            Weaviate Filter object or None
        """
        if not where:
            return None

        try:
            weaviate = self._weaviate_module
            Filter = weaviate.classes.query.Filter

            # Simple implementation: support basic field equality and operators
            filters = []

            for key, value in where.items():
                if isinstance(value, dict):
                    # Handle operator-based filters
                    for op, val in value.items():
                        if op == "$eq" or op == "=":
                            filters.append(Filter.by_property(key).equal(val))
                        elif op == "$ne" or op == "!=":
                            filters.append(Filter.by_property(key).not_equal(val))
                        elif op == "$gt" or op == ">":
                            filters.append(Filter.by_property(key).greater_than(val))
                        elif op == "$gte" or op == ">=":
                            filters.append(Filter.by_property(key).greater_or_equal(val))
                        elif op == "$lt" or op == "<":
                            filters.append(Filter.by_property(key).less_than(val))
                        elif op == "$lte" or op == "<=":
                            filters.append(Filter.by_property(key).less_or_equal(val))
                        elif op == "$in" or op == "in":
                            # Weaviate supports contains_any for multiple values
                            filters.append(Filter.by_property(key).contains_any(val))
                else:
                    # Simple equality
                    filters.append(Filter.by_property(key).equal(value))

            # Combine filters with AND logic
            if not filters:
                return None

            if len(filters) == 1:
                return filters[0]

            # Combine multiple filters with AND
            combined_filter = filters[0]
            for f in filters[1:]:
                combined_filter = combined_filter & f

            return combined_filter

        except Exception as e:
            log_error("Failed to build filter: %s", e)
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
            collection = self._client.collections.get(collection_name)

            # Build filter if provided
            weaviate_filter = self._build_filter(where) if where else None

            # Fetch objects
            response = collection.query.fetch_objects(
                limit=limit,
                offset=offset,
                filters=weaviate_filter,
                include_vector=True,
            )

            # Transform to standard format
            ids = []
            documents = []
            metadatas = []
            embeddings = []

            for obj in response.objects:
                ids.append(str(obj.uuid))

                # Extract document and metadata from properties
                properties = obj.properties.copy()
                doc = properties.pop("document", "")
                documents.append(doc)
                metadatas.append(properties)

                # Extract embedding vector
                if hasattr(obj, "vector") and obj.vector:
                    # Handle both dict and list vector formats
                    if isinstance(obj.vector, dict):
                        embeddings.append(next(iter(obj.vector.values())))
                    else:
                        embeddings.append(obj.vector)
                else:
                    embeddings.append([])

            return {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
                "embeddings": embeddings,
            }

        except Exception as e:
            log_error("Failed to get all items: %s", e)
            return None

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
            collection = self._client.collections.get(collection_name)

            for i, obj_id in enumerate(ids):
                try:
                    # Fetch existing object
                    existing = collection.query.fetch_object_by_id(uuid.UUID(obj_id))

                    if not existing:
                        continue

                    # Build updated properties
                    properties = existing.properties.copy()
                    vector = existing.vector if hasattr(existing, "vector") else None

                    # Update document if provided
                    if documents and i < len(documents):
                        properties["document"] = documents[i]

                        # If embedding not provided, compute for updated document
                        if not embeddings or i >= len(embeddings):
                            try:
                                computed = self.compute_embeddings_for_documents(
                                    collection_name,
                                    [documents[i]],
                                    getattr(self, "profile_name", None),
                                )
                                if computed:
                                    vector = computed[0]
                            except Exception as e:
                                log_error("Failed to compute embedding for update: %s", e)

                    # Update metadata if provided
                    if metadatas and i < len(metadatas):
                        # Preserve document field
                        doc = properties.get("document", "")
                        properties = metadatas[i].copy()
                        properties["document"] = doc

                    # Update embedding if provided
                    if embeddings and i < len(embeddings):
                        vector = embeddings[i]

                    # Update object
                    collection.data.update(
                        uuid=uuid.UUID(obj_id),
                        properties=properties,
                        vector=vector,
                    )

                except Exception as e:
                    log_error("Failed to update object %s: %s", obj_id, e)
                    continue

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
            collection = self._client.collections.get(collection_name)

            if ids:
                # Delete by IDs
                for obj_id in ids:
                    try:
                        collection.data.delete_by_id(uuid.UUID(obj_id))
                    except Exception as e:
                        log_error("Failed to delete object %s: %s", obj_id, e)
            elif where:
                # Delete by filter
                weaviate_filter = self._build_filter(where)
                if weaviate_filter:
                    collection.data.delete_many(where=weaviate_filter)

            return True

        except Exception as e:
            log_error("Failed to delete items: %s", e)
            return False

    def get_connection_info(self) -> dict[str, Any]:
        """Get information about the current connection."""
        info: dict[str, Any] = {
            "provider": "Weaviate",
            "connected": self.is_connected,
        }

        # Check for embedded mode first
        if self.mode == "embedded" or (
            not self.url and not self.host and self.persistence_directory
        ):
            info["mode"] = "embedded"
            if self.persistence_directory:
                info["persistence_directory"] = self.persistence_directory
            if self.embedded_version:
                info["version"] = self.embedded_version
        elif self.url:
            info["mode"] = (
                "cloud"
                if "weaviate.cloud" in self.url
                or "weaviate.network" in self.url
                or "wcd" in self.url.lower()
                else "remote"
            )
            info["url"] = self.url
        elif self.host:
            info["mode"] = "local"
            info["host"] = self.host
            info["port"] = self.port
        else:
            info["mode"] = "local"
            info["host"] = "localhost"
            info["port"] = 8080

        info["grpc_enabled"] = self.use_grpc

        return info

    def get_supported_filter_operators(self) -> list[dict[str, Any]]:
        """Get filter operators supported by Weaviate."""
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
            {"name": "not contains", "server_side": False},  # Client-side only
        ]
