"""Data loading services for vectors, metadata, and collections."""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from vector_inspector.core.connection_manager import ConnectionInstance

from vector_inspector.core.logging import log_error, log_info
from vector_inspector.utils import has_embedding


class CollectionLoader:
    """
    Service for loading collection-level data.

    Responsibilities:
        - Load all items from a collection
        - Handle pagination
        - Apply filters
    """

    def __init__(self, connection: Optional["ConnectionInstance"] = None) -> None:
        """Initialize collection loader."""
        self.connection = connection

    def set_connection(self, connection: Optional["ConnectionInstance"]) -> None:
        """Set the active connection."""
        self.connection = connection

    def load_all(
        self,
        collection: str,
        limit: Optional[int] = None,
        offset: int = 0,
        filters: Optional[dict] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Load all items from a collection.

        Args:
            collection: Collection name
            limit: Maximum number of items to load
            offset: Number of items to skip
            filters: Optional filter criteria

        Returns:
            Dictionary with 'ids', 'embeddings', 'metadatas', 'documents'
        """
        if not self.connection:
            log_error("No connection available")
            return None

        try:
            # Use get_all_items if available
            if hasattr(self.connection, "get_all_items"):
                data = self.connection.get_all_items(
                    collection_name=collection, limit=limit, offset=offset
                )
                return data

            log_error("Connection does not support get_all_items")
            return None

        except Exception as e:
            log_error(f"Failed to load collection data: {e}")
            return None

    def load_page(
        self, collection: str, page: int, page_size: int, filters: Optional[dict] = None
    ) -> Optional[dict[str, Any]]:
        """
        Load a specific page of items.

        Args:
            collection: Collection name
            page: Page number (1-indexed)
            page_size: Number of items per page
            filters: Optional filter criteria

        Returns:
            Dictionary with paginated data
        """
        offset = (page - 1) * page_size
        return self.load_all(collection, limit=page_size, offset=offset, filters=filters)

    def get_count(self, collection: str) -> int:
        """
        Get total number of items in collection.

        Args:
            collection: Collection name

        Returns:
            Number of items
        """
        if not self.connection:
            return 0

        try:
            if hasattr(self.connection, "count"):
                return self.connection.count(collection)
            if hasattr(self.connection, "get_collection_count"):
                return self.connection.get_collection_count(collection)
            return 0
        except Exception as e:
            log_error(f"Failed to get collection count: {e}")
            return 0


class VectorLoader:
    """
    Service for loading and processing vector embeddings.

    Responsibilities:
        - Load embeddings from collection
        - Sample vectors for visualization
        - Filter invalid/missing embeddings
    """

    def __init__(self, connection: Optional["ConnectionInstance"] = None) -> None:
        """Initialize vector loader."""
        self.connection = connection

    def set_connection(self, connection: Optional["ConnectionInstance"]) -> None:
        """Set the active connection."""
        self.connection = connection

    def load_vectors(
        self, collection: str, sample_size: Optional[int] = None
    ) -> Optional[dict[str, Any]]:
        """
        Load vector embeddings from collection.

        Args:
            collection: Collection name
            sample_size: Optional number of vectors to sample

        Returns:
            Dictionary with 'ids', 'embeddings', 'metadatas'
        """
        if not self.connection:
            log_error("No connection available")
            return None

        try:
            # Load data
            if hasattr(self.connection, "get_all_items"):
                data = self.connection.get_all_items(collection_name=collection, limit=sample_size)

                # Filter out items without embeddings
                if data:
                    data = self._filter_valid_embeddings(data)

                return data

            log_error("Connection does not support get_all_items")
            return None

        except Exception as e:
            log_error(f"Failed to load vectors: {e}")
            return None

    def _filter_valid_embeddings(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Filter out items without valid embeddings.

        Args:
            data: Raw data dictionary

        Returns:
            Filtered data dictionary
        """
        if not data or "embeddings" not in data:
            return data

        ids = data.get("ids", [])
        embeddings = data.get("embeddings", [])
        metadatas = data.get("metadatas", [])
        documents = data.get("documents", [])

        # Filter items with valid embeddings
        valid_indices = [i for i, emb in enumerate(embeddings) if has_embedding(emb)]

        if not valid_indices:
            log_info("No valid embeddings found")
            return {"ids": [], "embeddings": [], "metadatas": [], "documents": []}

        # Refilter all arrays
        filtered_data = {
            "ids": [ids[i] for i in valid_indices] if ids else [],
            "embeddings": [embeddings[i] for i in valid_indices],
            "metadatas": [metadatas[i] for i in valid_indices] if metadatas else [],
            "documents": [documents[i] for i in valid_indices] if documents else [],
        }

        if len(valid_indices) < len(embeddings):
            log_info(f"Filtered {len(embeddings) - len(valid_indices)} items without embeddings")

        return filtered_data


class MetadataLoader:
    """
    Service for loading metadata and documents.

    Responsibilities:
        - Load metadata for items
        - Load documents/content
        - Parse metadata fields
    """

    def __init__(self, connection: Optional["ConnectionInstance"] = None) -> None:
        """Initialize metadata loader."""
        self.connection = connection

    def set_connection(self, connection: Optional["ConnectionInstance"]) -> None:
        """Set the active connection."""
        self.connection = connection

    def load_metadata(
        self, collection: str, item_ids: Optional[list[str]] = None
    ) -> Optional[dict[str, Any]]:
        """
        Load metadata for items.

        Args:
            collection: Collection name
            item_ids: Optional list of specific item IDs

        Returns:
            Dictionary with 'ids', 'metadatas', 'documents'
        """
        if not self.connection:
            log_error("No connection available")
            return None

        try:
            if item_ids:
                # Load specific items
                if hasattr(self.connection, "get_by_ids"):
                    data = self.connection.get_by_ids(collection, item_ids)
                    return data
            else:
                # Load all metadata
                if hasattr(self.connection, "get_all_items"):
                    data = self.connection.get_all_items(collection_name=collection)
                    # Extract just metadata (no embeddings)
                    return {
                        "ids": data.get("ids", []),
                        "metadatas": data.get("metadatas", []),
                        "documents": data.get("documents", []),
                    }

            return None

        except Exception as e:
            log_error(f"Failed to load metadata: {e}")
            return None

    def get_metadata_fields(self, data: dict[str, Any]) -> list[str]:
        """
        Extract all unique metadata field names.

        Args:
            data: Data dictionary with 'metadatas'

        Returns:
            List of unique field names
        """
        if not data or "metadatas" not in data:
            return []

        metadatas = data["metadatas"]
        if not metadatas:
            return []

        # Collect all keys from all metadata dicts
        fields = set()
        for metadata in metadatas:
            if isinstance(metadata, dict):
                fields.update(metadata.keys())

        return sorted(fields)
