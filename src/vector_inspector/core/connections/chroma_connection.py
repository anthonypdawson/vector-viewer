"""ChromaDB connection manager."""

import os
from pathlib import Path
from typing import Any, Optional, cast

import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.logging import log_error, log_info


class DimensionAwareEmbeddingFunction(EmbeddingFunction):
    """Embedding function that selects model based on collection's expected dimension.

    If *model_name* and *model_type* are supplied the dimension heuristic is skipped
    and the explicit model is used instead.  This ensures that collections whose
    embedding model was recorded in SettingsService (e.g. CLIP image collections)
    produce query vectors with the correct encoder.
    """

    def __init__(
        self,
        expected_dimension: int,
        model_name: str | None = None,
        model_type: str | None = None,
    ):
        """Initialize with expected dimension (model loaded lazily on first use)."""
        self.expected_dimension = expected_dimension
        self.model = None
        self.model_name = model_name
        self.model_type = model_type
        self._initialized = False

    def _ensure_model_loaded(self):
        """Lazy load the embedding model on first use."""
        if self._initialized:
            return

        if self.model_name and self.model_type:
            # Explicit model provided — skip dimension heuristic
            from vector_inspector.core.embedding_utils import load_embedding_model

            log_info(
                "[ChromaDB] Loading explicit %s model '%s' for query embedding",
                self.model_type,
                self.model_name,
            )
            self.model = load_embedding_model(self.model_name, self.model_type)
        else:
            from vector_inspector.core.embedding_utils import get_embedding_model_for_dimension

            log_info("[ChromaDB] Loading embedding model for %dd vectors...", self.expected_dimension)
            self.model, self.model_name, self.model_type = get_embedding_model_for_dimension(self.expected_dimension)
            log_info(
                "[ChromaDB] Using %s model '%s' for %dd embeddings",
                self.model_type,
                self.model_name,
                self.expected_dimension,
            )
        self._initialized = True

    def __call__(self, input: Documents) -> Embeddings:
        """Embed documents using the dimension-appropriate model."""
        self._ensure_model_loaded()
        from vector_inspector.core.embedding_utils import encode_text

        # After _ensure_model_loaded(), model and model_type are always set
        assert self.model is not None and self.model_type is not None
        embeddings = []
        for text in input:
            embedding = encode_text(text, self.model, self.model_type)
            embeddings.append(embedding)
        return embeddings


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
            log_error("Connection failed: %s", e)
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

    def list_collections(self) -> list[str]:
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
            log_info("Failed to list collections: %s", e)
            return []

    def _get_collection_basic(self, name: str) -> Optional[Collection]:
        """Get collection without custom embedding function (for info lookup)."""
        if not self._client:
            return None
        try:
            return self._client.get_collection(name=name)
        except Exception:
            return None

    def _get_embedding_function_for_collection(self, name: str) -> Optional[EmbeddingFunction]:
        """Get the appropriate embedding function for a collection.

        Resolution order:
        1. SettingsService (model explicitly saved for this profile + collection)
        2. Dimension heuristic (sample a vector and pick by length)
        """
        # 1) Check SettingsService first so explicitly-recorded models (e.g. CLIP) are honoured
        explicit_model_name: str | None = None
        explicit_model_type: str | None = None
        try:
            from vector_inspector.services.settings_service import SettingsService

            profile_name = getattr(self, "profile_name", None)
            if profile_name:
                cfg = SettingsService().get_embedding_model(profile_name, name)
                if cfg and cfg.get("model"):
                    explicit_model_name = cfg["model"]
                    explicit_model_type = cfg.get("type", "sentence-transformer")
                    log_info(
                        "[ChromaDB] Using settings-recorded model '%s' (%s) for collection '%s'",
                        explicit_model_name,
                        explicit_model_type,
                        name,
                    )
        except Exception:
            pass

        # 2) Dimension sniff — still needed to construct DimensionAwareEmbeddingFunction
        basic_col = self._get_collection_basic(name)
        if not basic_col:
            return None

        try:
            sample = basic_col.get(limit=1, include=["embeddings"])
            embeddings = sample.get("embeddings") if sample else None
            if embeddings is not None and len(embeddings) > 0:
                from vector_inspector.utils import has_embedding

                first_embedding = embeddings[0]
                if has_embedding(first_embedding):
                    vector_dim = len(first_embedding)
                    log_info("[ChromaDB] Collection '%s' has %dd vectors", name, vector_dim)
                    return DimensionAwareEmbeddingFunction(
                        vector_dim,
                        model_name=explicit_model_name,
                        model_type=explicit_model_type,
                    )
        except Exception as e:
            import traceback

            log_error(
                "[ChromaDB] Failed to determine embedding function: %s\n%s",
                e,
                traceback.format_exc(),
            )

        return None

    def get_collection(self, name: str, embedding_function: Optional[EmbeddingFunction] = None) -> Optional[Collection]:
        """Get a collection (without overriding existing embedding function).

        Args:
            name: Collection name
            embedding_function: Optional custom embedding function (ignored if collection exists)

        Returns:
            Collection object or None if failed
        """
        if not self._client:
            return None
        try:
            # Just get the collection without trying to override embedding function
            # This avoids conflicts with existing collections
            self._current_collection = self._client.get_collection(name=name)
            return self._current_collection
        except Exception as e:
            log_error("Failed to get collection: %s", e)
            return None

    def get_collection_info(self, name: str) -> Optional[dict[str, Any]]:
        """
        Get collection metadata and statistics.

        Args:
            name: Collection name

        Returns:
            Dictionary with collection info
        """
        collection = self._get_collection_basic(name)
        if not collection:
            return None

        try:
            count = collection.count()
            # Get a sample to determine metadata fields and vector dimensions
            sample = collection.get(limit=1, include=["metadatas", "embeddings"])
            metadata_fields = []
            vector_dimension = "Unknown"

            if sample and sample["metadatas"]:
                metadata_fields = list(sample["metadatas"][0].keys()) if sample["metadatas"][0] else []

            # Determine vector dimensions from embeddings
            embeddings = sample.get("embeddings") if sample else None
            if embeddings is not None and len(embeddings) > 0:
                from vector_inspector.utils import has_embedding

                if has_embedding(embeddings[0]):
                    vector_dimension = len(embeddings[0])

            # ChromaDB uses cosine distance by default (or can be configured)
            # Try to get metadata from collection if available
            distance_metric = "Cosine (default)"
            embedding_model = None
            try:
                # ChromaDB collections may have metadata about distance function
                col_metadata = collection.metadata
                if col_metadata:
                    if "hnsw:space" in col_metadata:
                        space = col_metadata["hnsw:space"]
                        if space == "l2":
                            distance_metric = "Euclidean (L2)"
                        elif space == "ip":
                            distance_metric = "Inner Product"
                        elif space == "cosine":
                            distance_metric = "Cosine"
                    # Get embedding model if stored
                    if "embedding_model" in col_metadata:
                        embedding_model = col_metadata["embedding_model"]
            except:
                pass  # Use default if unable to determine

            result = {
                "name": name,
                "count": count,
                "metadata_fields": metadata_fields,
                "vector_dimension": vector_dimension,
                "distance_metric": distance_metric,
            }

            if embedding_model:
                result["embedding_model"] = embedding_model

            return result
        except Exception as e:
            log_error("Failed to get collection info: %s", e)
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
            query_texts: Text queries to embed and search
            query_embeddings: Direct embedding vectors to search
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter

        Returns:
            Query results or None if failed
        """
        log_info("[ChromaDB] query_collection called for '%s'", collection_name)
        collection = self.get_collection(collection_name)
        if not collection:
            log_error("[ChromaDB] Failed to get collection '%s'", collection_name)
            return None

        # If query_texts provided, we need to manually embed them with dimension-aware model
        _query_embedding = None
        _query_embedding_model = None
        _embedding_function_used = None
        if query_texts and not query_embeddings:
            embedding_function = self._get_embedding_function_for_collection(collection_name)
            if embedding_function:
                log_info("[ChromaDB] Manually embedding query texts with dimension-aware model")
                query_embeddings = embedding_function(query_texts)
                _embedding_function_used = embedding_function
                query_texts = None  # Use embeddings instead of texts
            else:
                log_info("[ChromaDB] Warning: Could not determine embedding function, using collection's default")

        if query_embeddings:
            _query_embedding = query_embeddings[0]
        if _embedding_function_used is not None:
            _query_embedding_model = _embedding_function_used.model_name

        try:
            results = collection.query(
                query_texts=query_texts,
                query_embeddings=query_embeddings,  # type: ignore
                n_results=n_results,
                where=where,
                where_document=where_document,  # type: ignore
                include=["metadatas", "documents", "distances", "embeddings"],
            )
            result_dict = cast(dict[str, Any], results)
            result_dict["query_embedding"] = _query_embedding
            result_dict["query_embedding_model"] = _query_embedding_model
            return result_dict
        except Exception as e:
            import traceback

            log_error("Query failed: %s\n%s", e, traceback.format_exc())
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
        collection = self.get_collection(collection_name)
        if not collection:
            return None

        try:
            results = collection.get(
                limit=limit,
                offset=offset,
                where=where,
                include=["metadatas", "documents", "embeddings"],
            )
            return cast(dict[str, Any], results)
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
            ids: IDs for each document
            embeddings: Pre-computed embeddings

        Returns:
            True if successful, False otherwise
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return False

        try:
            # If embeddings not provided, compute using collection model
            if not embeddings and documents:
                try:
                    embeddings = self.compute_embeddings_for_documents(
                        collection_name, documents, getattr(self, "profile_name", None)
                    )
                except Exception as e:
                    log_error("Failed to compute embeddings for Chroma add_items: %s", e)
                    return False

            collection.add(
                documents=documents,
                metadatas=metadatas,  # type: ignore
                ids=ids,  # type: ignore
                embeddings=embeddings,  # type: ignore
            )
            return True
        except Exception as e:
            log_error("Failed to add items: %.400s", str(e))
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
        collection = self.get_collection(collection_name)
        if not collection:
            return False

        try:
            # If embeddings not provided but documents changed, compute embeddings
            if (not embeddings) and documents:
                try:
                    embeddings = self.compute_embeddings_for_documents(
                        collection_name, documents, getattr(self, "connection_id", None)
                    )
                except Exception as e:
                    log_error("Failed to compute embeddings for Chroma update_items: %s", e)
                    return False

            collection.update(
                ids=ids,
                documents=documents,
                metadatas=metadatas,  # type: ignore
                embeddings=embeddings,  # type: ignore
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
        collection = self.get_collection(collection_name)
        if not collection:
            return False

        try:
            collection.delete(ids=ids, where=where)
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
            True if successful or collection does not exist, False otherwise
        """
        if not self._client:
            return False

        try:
            self._client.delete_collection(name=name)
            if self._current_collection and self._current_collection.name == name:
                self._current_collection = None
            return True
        except Exception as e:
            # If the exception is about the collection not existing, treat as success (idempotent)
            if "does not exist" in str(e).lower():
                return True
            log_error("Failed to delete collection: %s", e)
            return False

    # Implement base connection uniform APIs
    @property
    def supports_configurable_vector_size(self) -> bool:
        return False

    def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        if not self._client:
            return False

        try:
            # Prefer get_or_create_collection if available
            if hasattr(self._client, "get_or_create_collection"):
                col = self._client.get_or_create_collection(name=name)
                self._current_collection = col
                return True

            # Fallback to create_collection/create and then fetch
            if hasattr(self._client, "create_collection"):
                try:
                    self._client.create_collection(name=name)
                except Exception:
                    # Some clients may raise if already exists; ignore
                    pass
                col = self._client.get_collection(name=name)
                self._current_collection = col
                return col is not None

            # As a last resort, check if collection exists
            col = self.get_collection(name)
            return col is not None
        except Exception as e:
            log_error("Failed to create collection: %s", e)
            return False

    def get_items(self, name: str, ids: list[str]) -> dict[str, Any]:
        """Retrieve items by IDs."""
        col = self.get_collection(name)
        if not col:
            raise RuntimeError("Collection not available")
        return cast(dict[str, Any], col.get(ids=ids, include=["metadatas", "documents", "embeddings"]))

    def count_collection(self, name: str) -> int:
        """Count items in a collection."""
        col = self.get_collection(name)
        if not col:
            return 0
        try:
            return col.count()
        except Exception:
            return 0

    def get_supported_filter_operators(self) -> list[dict[str, Any]]:
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
