"""Abstract base class for vector database connections."""

from abc import ABC, abstractmethod
from typing import Any

from vector_inspector.core.logging import log_error


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
    def list_collections(self) -> list[str]:
        """
        Get list of all collections/indexes.

        Returns:
            List of collection/index names
        """
        pass

    @abstractmethod
    def get_collection_info(self, name: str) -> dict[str, Any] | None:
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
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> bool:
        """Add items to a collection."""
        pass

    @abstractmethod
    def get_items(self, name: str, ids: list[str]) -> dict[str, Any]:
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
        query_texts: list[str] | None = None,
        query_embeddings: list[list[float]] | None = None,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
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
        limit: int | None = None,
        offset: int | None = None,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
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
        ids: list[str],
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
        embeddings: list[list[float]] | None = None,
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
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
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

    def get_connection_info(self) -> dict[str, Any]:
        """
        Get information about the current connection.

        Returns:
            Dictionary with connection details (provider-specific)
        """
        return {"provider": self.__class__.__name__, "connected": self.is_connected}

    def get_supported_filter_operators(self) -> list[dict[str, Any]]:
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

    def get_embedding_model(
        self, collection_name: str, connection_id: str | None = None
    ) -> str | None:
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
                from vector_inspector.services.settings_service import SettingsService

                settings = SettingsService()
                model_info = settings.get_embedding_model(connection_id, collection_name)
                if model_info:
                    return model_info["model"]

            return None
        except Exception as e:
            log_error("Failed to get embedding model: %s", e)
            return None

    def load_embedding_model_for_collection(
        self, collection_name: str, connection_id: str | None = None
    ):
        """
        Resolve and load an embedding model for a collection.

        Resolution order:
        1. User settings (SettingsService)
        2. Collection metadata (get_collection_info)
        3. Dimension-based registry (embedding_utils.get_embedding_model_for_dimension)
        4. DEFAULT_MODEL

        Returns:
            (loaded_model, model_name, model_type)
        """
        try:
            from vector_inspector.core.embedding_utils import (
                DEFAULT_MODEL,
                get_embedding_model_for_dimension,
                load_embedding_model,
            )
            from vector_inspector.services.settings_service import SettingsService

            # 1) settings
            if connection_id:
                settings = SettingsService()
                cfg = settings.get_embedding_model(connection_id, collection_name)
                if cfg and cfg.get("model"):
                    model_name = cfg.get("model")
                    model_type = cfg.get("type", "sentence-transformer")
                    model = load_embedding_model(model_name, model_type)
                    return (model, model_name, model_type)

            # 2) collection metadata
            try:
                info = self.get_collection_info(collection_name)
            except Exception:
                info = None

            if info and info.get("embedding_model"):
                model_name = info.get("embedding_model")
                model_type = info.get("embedding_model_type", "sentence-transformer")
                model = load_embedding_model(model_name, model_type)
                return (model, model_name, model_type)

            # 3) dimension based
            if info and info.get("vector_dimension"):
                try:
                    dim = int(info.get("vector_dimension"))
                    model, model_name, model_type = get_embedding_model_for_dimension(dim)
                    return (model, model_name, model_type)
                except Exception:
                    pass

            # 4) fallback
            model_name, model_type = DEFAULT_MODEL
            model = load_embedding_model(model_name, model_type)
            return (model, model_name, model_type)
        except Exception as e:
            log_error("Failed to load embedding model for collection %s: %s", collection_name, e)
            raise

    def compute_embeddings_for_documents(
        self, collection_name: str, documents: list[str], connection_id: str | None = None
    ) -> list[list[float]]:
        """
        Compute embeddings for a list of documents using the resolved model for the collection.

        Returns a list of embedding vectors (one per document). If encoding fails,
        raises an exception.
        """
        model, model_name, model_type = self.load_embedding_model_for_collection(
            collection_name, connection_id
        )

        # Use batch encoding when available (sentence-transformer), otherwise per-doc
        if model_type != "clip":
            # sentence-transformer-like models support batch encode
            return model.encode(documents, show_progress_bar=False).tolist()
        # CLIP - use encode_text helper for each document
        from vector_inspector.core.embedding_utils import encode_text

        return [encode_text(d, model, model_type) for d in documents]
