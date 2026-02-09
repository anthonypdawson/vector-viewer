"""Milvus connection manager."""

import uuid
from typing import Any, Optional

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    connections,
)

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.logging import log_error, log_info


class MilvusConnection(VectorDBConnection):
    """Manages connection to Milvus and provides query interface."""

    def __init__(
        self,
        uri: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        db_name: str = "default",
        alias: str = "default",
    ):
        """
        Initialize Milvus connection.

        Args:
            uri: URI for Milvus connection (e.g., "http://localhost:19530" or file path for Milvus Lite)
            host: Host for remote connection
            port: Port for remote connection (default: 19530)
            user: Username for authentication
            password: Password for authentication
            token: Token for authentication
            db_name: Database name (default: "default")
            alias: Connection alias (default: "default")
        """
        self.uri = uri
        self.host = host
        self.port = port or 19530
        self.user = user
        self.password = password
        self.token = token
        self.db_name = db_name
        self.alias = alias
        self._client: Optional[MilvusClient] = None
        self._connected = False

    def connect(self) -> bool:
        """
        Establish connection to Milvus.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Build connection kwargs
            conn_kwargs = {"alias": self.alias}

            if self.uri:
                # Use URI (supports both HTTP and file-based Milvus Lite)
                conn_kwargs["uri"] = self.uri
            elif self.host:
                # Use host/port
                conn_kwargs["host"] = self.host
                conn_kwargs["port"] = str(self.port)
            else:
                # Default to local connection
                conn_kwargs["host"] = "localhost"
                conn_kwargs["port"] = "19530"

            # Add authentication if provided
            if self.user:
                conn_kwargs["user"] = self.user
            if self.password:
                conn_kwargs["password"] = self.password
            if self.token:
                conn_kwargs["token"] = self.token

            # Add db_name if not default
            if self.db_name and self.db_name != "default":
                conn_kwargs["db_name"] = self.db_name

            # Connect using connections module
            connections.connect(**conn_kwargs)  # type: ignore[arg-type]

            # Create MilvusClient for simpler operations
            client_kwargs = {}
            if self.uri:
                client_kwargs["uri"] = self.uri
            else:
                client_kwargs["uri"] = f"http://{self.host}:{self.port}"

            if self.token:
                client_kwargs["token"] = self.token
            elif self.user and self.password:
                client_kwargs["user"] = self.user
                client_kwargs["password"] = self.password

            if self.db_name and self.db_name != "default":
                client_kwargs["db_name"] = self.db_name

            self._client = MilvusClient(**client_kwargs)

            # Test connection by listing collections
            self._client.list_collections()  # type: ignore[unused-coroutine]
            self._connected = True
            return True
        except Exception as e:
            log_error("Milvus connection failed: %s", e)
            self._connected = False
            return False

    def disconnect(self):
        """Close connection to Milvus."""
        try:
            if self._client:
                self._client.close()
            connections.disconnect(alias=self.alias)
        except Exception as e:
            log_error("Error disconnecting from Milvus: %s", e)
        finally:
            self._client = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connected to Milvus."""
        return self._connected and self._client is not None

    def list_collections(self) -> list[str]:
        """
        Get list of all collections.

        Returns:
            List of collection names
        """
        if not self._client:
            return []
        try:
            return self._client.list_collections()  # type: ignore[return-value]
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
            # Get collection stats
            stats = self._client.get_collection_stats(collection_name=name)
            
            # Get collection schema using utility
            collection = Collection(name, using=self.alias)
            schema = collection.schema
            
            # Extract vector field info
            vector_field = None
            vector_dimension = "Unknown"
            metadata_fields = []
            
            for field in schema.fields:
                if field.dtype == DataType.FLOAT_VECTOR:
                    vector_field = field.name
                    vector_dimension = field.params.get("dim", "Unknown")
                elif field.name not in ["id", "pk"]:
                    # Track other fields as metadata fields
                    metadata_fields.append(field.name)
            
            # Get count
            count = int(stats.get("row_count", 0))
            
            # Get index info if available
            index_info = {}
            try:
                if vector_field:
                    indexes = collection.indexes
                    if indexes:
                        for idx in indexes:
                            index_info[idx.field_name] = {
                                "index_type": idx.params.get("index_type", "Unknown"),
                                "metric_type": idx.params.get("metric_type", "Unknown"),
                            }
            except Exception:
                pass
            
            return {
                "name": name,
                "count": count,
                "vector_dimension": vector_dimension,
                "vector_field": vector_field,
                "metadata_fields": metadata_fields,
                "index_info": index_info,
            }
        except Exception as e:
            log_error("Failed to get collection info for %s: %s", name, e)
            return None

    def create_collection(
        self, name: str, vector_size: int, distance: str = "Cosine"
    ) -> bool:
        """
        Create a collection with a given vector size and distance metric.

        Args:
            name: Collection name
            vector_size: Dimension of vectors
            distance: Distance metric (Cosine, L2, IP)

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            # Map distance to Milvus metric type
            metric_map = {
                "Cosine": "COSINE",
                "L2": "L2",
                "Euclidean": "L2",
                "IP": "IP",
                "Dot": "IP",
            }
            metric_type = metric_map.get(distance, "COSINE")

            # Define schema
            fields = [
                FieldSchema(
                    name="id",
                    dtype=DataType.VARCHAR,
                    is_primary=True,
                    auto_id=False,
                    max_length=65535,
                ),
                FieldSchema(
                    name="document", dtype=DataType.VARCHAR, max_length=65535
                ),
                FieldSchema(
                    name="embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=vector_size,
                ),
            ]

            schema = CollectionSchema(
                fields=fields,
                description=f"Vector collection with {vector_size}-dimensional embeddings",
            )

            # Create collection
            collection = Collection(
                name=name,
                schema=schema,
                using=self.alias,
            )

            # Create index on vector field
            index_params = {
                "metric_type": metric_type,
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }
            collection.create_index(  # type: ignore[unused-coroutine]
                field_name="embedding",
                index_params=index_params,
            )

            # Load collection into memory
            collection.load()

            log_info("Created collection %s with dimension %d", name, vector_size)
            return True
        except Exception as e:
            log_error("Failed to create collection %s: %s", name, e)
            return False

    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection.

        Args:
            name: Collection name

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        try:
            self._client.drop_collection(collection_name=name)
            return True
        except Exception as e:
            log_error("Failed to delete collection %s: %s", name, e)
            return False

    def count_collection(self, name: str) -> int:
        """
        Count the number of items in a collection.

        Args:
            name: Collection name

        Returns:
            Number of items in collection
        """
        if not self._client:
            return 0

        try:
            stats = self._client.get_collection_stats(collection_name=name)
            return int(stats.get("row_count", 0))
        except Exception:
            return 0

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
            embeddings: Pre-computed embeddings (required for Milvus)

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False

        if not documents:
            return False

        # If embeddings not provided, compute them
        if embeddings is None:
            try:
                embeddings = self.compute_embeddings_for_documents(
                    collection_name,
                    documents,
                    getattr(self, "profile_name", None),
                )
            except Exception as e:
                log_error("Failed to compute embeddings: %s", e)
                return False

        if len(embeddings) != len(documents):
            log_error(
                "Embeddings length (%d) does not match documents length (%d)",
                len(embeddings),
                len(documents),
            )
            return False

        try:
            # Generate IDs if not provided
            if not ids:
                ids = [str(uuid.uuid4()) for _ in documents]

            # Prepare data for insertion
            data = [
                {
                    "id": id_val,
                    "document": doc,
                    "embedding": emb,
                }
                for id_val, doc, emb in zip(ids, documents, embeddings, strict=True)
            ]

            # Add metadata fields if provided
            if metadatas:
                schema_fields = {f.name: f for f in Collection(collection_name, using=self.alias).schema.fields}

                for i, metadata in enumerate(metadatas):
                    if metadata:
                        for key, value in metadata.items():
                            # Only add if field exists in schema
                            if key in schema_fields:
                                data[i][key] = value

            # Insert data
            self._client.insert(collection_name=collection_name, data=data)
            return True
        except Exception as e:
            log_error("Failed to add items to %s: %s", collection_name, e)
            return False

    def get_items(self, name: str, ids: list[str]) -> dict[str, Any]:
        """
        Retrieve items by IDs.

        Args:
            name: Collection name
            ids: List of item IDs

        Returns:
            Dictionary with 'documents' and 'metadatas'
        """
        if not self._client:
            return {"documents": [], "metadatas": []}

        try:

            results = self._client.query(
                collection_name=name,
                filter=f'id in {ids}',
                output_fields=["*"],
            )

            documents = []
            metadatas = []

            for item in results:
                documents.append(item.get("document", ""))
                # Extract metadata (exclude id, document, embedding)
                metadata = {
                    k: v
                    for k, v in item.items()
                    if k not in ["id", "document", "embedding"]
                }
                metadatas.append(metadata)

            return {"documents": documents, "metadatas": metadatas}
        except Exception as e:
            log_error("Failed to get items: %s", e)
            return {"documents": [], "metadatas": []}

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
            Dictionary with collection items
        """
        if not self._client:
            return None

        try:
            # Build query
            query_kwargs = {
                "collection_name": collection_name,
                "filter": "",
                "output_fields": ["*"],
            }

            if limit:
                query_kwargs["limit"] = limit
            if offset:
                query_kwargs["offset"] = offset

            # Build filter expression if provided
            if where:
                filter_expr = self._build_filter_expression(where)
                if filter_expr:
                    query_kwargs["filter"] = filter_expr

            results = self._client.query(**query_kwargs)

            ids = []
            documents = []
            metadatas = []
            embeddings = []

            for item in results:
                ids.append(item.get("id", ""))
                documents.append(item.get("document", ""))
                embeddings.append(item.get("embedding", []))
                # Extract metadata
                metadata = {
                    k: v
                    for k, v in item.items()
                    if k not in ["id", "document", "embedding"]
                }
                metadatas.append(metadata)

            return {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
                "embeddings": embeddings,
            }
        except Exception as e:
            log_error("Failed to get all items: %s", e)
            return None

    def query_collection(
        self,
        collection_name: str,
        query_texts: Optional[list[str]] = None,
        query_embeddings: Optional[list[list[float]]] = None,
        n_results: int = 10,
        where: Optional[dict[str, Any]] = None,
        where_document: Optional[dict[str, Any]] = None,  # noqa: ARG002
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
            Query results dictionary
        """
        if not self._client:
            return None

        try:
            # Get embeddings for query
            if query_embeddings is None:
                if query_texts is None:
                    log_error("Either query_texts or query_embeddings must be provided")
                    return None
                
                # Compute embeddings for query texts
                query_embeddings = self.compute_embeddings_for_documents(
                    collection_name,
                    query_texts,
                    getattr(self, "profile_name", None),
                )

            # Build filter expression
            filter_expr = ""
            if where:
                filter_expr = self._build_filter_expression(where)

            # Perform search for each query embedding
            all_ids = []
            all_distances = []
            all_documents = []
            all_metadatas = []
            all_embeddings = []

            for query_emb in query_embeddings:
                search_params = {
                    "collection_name": collection_name,
                    "data": [query_emb],
                    "limit": n_results,
                    "output_fields": ["*"],
                }

                if filter_expr:
                    search_params["filter"] = filter_expr

                results = self._client.search(**search_params)

                if results and len(results) > 0:
                    result_set = results[0]
                    
                    ids = []
                    distances = []
                    documents = []
                    metadatas = []
                    embeddings = []

                    for hit in result_set:
                        ids.append(hit.get("id", ""))
                        distances.append(hit.get("distance", 0.0))
                        documents.append(hit.get("document", ""))
                        embeddings.append(hit.get("embedding", []))
                        
                        # Extract metadata
                        metadata = {
                            k: v
                            for k, v in hit.items()
                            if k not in ["id", "document", "embedding", "distance"]
                        }
                        metadatas.append(metadata)

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
            log_error("Failed to query collection: %s", e)
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

        In Milvus, updates are done by deleting and re-inserting.

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
            # Get existing items
            existing = self.get_items(collection_name, ids)
            if not existing:
                return False

            # Delete existing items
            if not self.delete_items(collection_name, ids=ids):
                return False

            # Prepare updated data
            updated_documents = documents if documents else existing.get("documents", [])
            updated_metadatas = metadatas if metadatas else existing.get("metadatas", [])
            updated_embeddings = embeddings

            # Add updated items
            return self.add_items(
                collection_name=collection_name,
                documents=updated_documents,
                metadatas=updated_metadatas,
                ids=ids,
                embeddings=updated_embeddings,
            )
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
                filter_expr = f'id in {ids}'
            elif where:
                # Delete by filter
                filter_expr = self._build_filter_expression(where)
            else:
                log_error("Either ids or where must be provided")
                return False

            self._client.delete(
                collection_name=collection_name,
                filter=filter_expr,
            )
            return True
        except Exception as e:
            log_error("Failed to delete items: %s", e)
            return False

    def _build_filter_expression(self, where: dict[str, Any]) -> str:
        """
        Build a Milvus filter expression from a where clause.

        Args:
            where: Dictionary with filter conditions

        Returns:
            Filter expression string
        """
        if not where:
            return ""

        conditions = []
        for key, value in where.items():
            if isinstance(value, str):
                conditions.append(f'{key} == "{value}"')
            elif isinstance(value, (int, float)):
                conditions.append(f"{key} == {value}")
            elif isinstance(value, list):
                conditions.append(f"{key} in {value}")
            elif isinstance(value, dict):
                # Handle operators like $gt, $lt, etc.
                for op, op_value in value.items():
                    if op == "$gt":
                        conditions.append(f"{key} > {op_value}")
                    elif op == "$gte":
                        conditions.append(f"{key} >= {op_value}")
                    elif op == "$lt":
                        conditions.append(f"{key} < {op_value}")
                    elif op == "$lte":
                        conditions.append(f"{key} <= {op_value}")
                    elif op == "$ne":
                        conditions.append(f"{key} != {op_value}")
                    elif op == "$in":
                        conditions.append(f"{key} in {op_value}")

        return " && ".join(conditions) if conditions else ""
