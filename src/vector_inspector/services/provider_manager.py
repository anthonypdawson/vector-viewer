"""Provider management service."""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from vector_inspector.core.connection_manager import ConnectionInstance

from vector_inspector.core.logging import log_error


class ProviderManager:
    """
    Manages provider/connection lifecycle and operations.

    Responsibilities:
        - Provider connection/disconnection
        - Database listing
        - Collection listing
        - Provider-specific normalization
    """

    def __init__(self, connection: Optional["ConnectionInstance"] = None) -> None:
        """
        Initialize provider manager.

        Args:
            connection: Optional initial connection
        """
        self.connection = connection

    def set_connection(self, connection: Optional["ConnectionInstance"]) -> None:
        """
        Set the active connection.

        Args:
            connection: New connection instance
        """
        self.connection = connection

    def get_databases(self) -> list[str]:
        """
        Get list of available databases.

        Returns:
            List of database names
        """
        if not self.connection:
            return []

        try:
            if hasattr(self.connection, "list_databases"):
                return self.connection.list_databases()
            return []
        except Exception as e:
            log_error(f"Failed to list databases: {e}")
            return []

    def get_collections(self, database: Optional[str] = None) -> list[str]:
        """
        Get list of collections in database.

        Args:
            database: Optional database name

        Returns:
            List of collection names
        """
        if not self.connection:
            return []

        try:
            if hasattr(self.connection, "list_collections"):
                return self.connection.list_collections()
            return []
        except Exception as e:
            log_error(f"Failed to list collections: {e}")
            return []

    def get_collection_info(self, collection: str) -> Optional[dict]:
        """
        Get information about a collection.

        Args:
            collection: Collection name

        Returns:
            Collection info dict or None
        """
        if not self.connection:
            return None

        try:
            if hasattr(self.connection, "get_collection_info"):
                return self.connection.get_collection_info(collection)
            return None
        except Exception as e:
            log_error(f"Failed to get collection info: {e}")
            return None

    def normalize_item(self, item: dict, provider_type: str) -> dict:
        """
        Normalize a data item based on provider quirks.

        Provider-specific transformations:
            - Qdrant: Convert float strings to floats
            - Chroma: Normalize metadata format
            - Weaviate: Unwrap nested payloads
            - Pinecone: Ensure string IDs

        Args:
            item: Raw item from provider
            provider_type: Provider type (e.g., "chromadb", "qdrant")

        Returns:
            Normalized item
        """
        normalized = item.copy()

        if provider_type == "qdrant":
            # Qdrant returns floats as strings in some cases
            if "metadata" in normalized:
                metadata = normalized["metadata"]
                for key, value in metadata.items():
                    if isinstance(value, str):
                        try:
                            # Try to convert to float
                            metadata[key] = float(value)
                        except (ValueError, TypeError):
                            pass

        elif provider_type == "chroma":
            # Chroma has different metadata structure
            if "metadata" not in normalized and "metadatas" in normalized:
                normalized["metadata"] = normalized["metadatas"]

        elif provider_type == "weaviate":
            # Weaviate nests data in payloads
            if "payload" in normalized:
                payload = normalized["payload"]
                normalized = {**normalized, **payload}
                del normalized["payload"]

        elif provider_type == "pinecone":
            # Pinecone IDs must be strings
            if "id" in normalized and not isinstance(normalized["id"], str):
                normalized["id"] = str(normalized["id"])

        return normalized

    def normalize_batch(self, items: list[dict], provider_type: str) -> list[dict]:
        """
        Normalize a batch of items.

        Args:
            items: List of raw items
            provider_type: Provider type

        Returns:
            List of normalized items
        """
        return [self.normalize_item(item, provider_type) for item in items]

    def get_provider_type(self) -> Optional[str]:
        """
        Get the type of the current provider.

        Returns:
            Provider type string or None
        """
        if not self.connection:
            return None

        # Check connection class name to determine type
        class_name = self.connection.__class__.__name__.lower()

        if "chroma" in class_name:
            return "chromadb"
        if "qdrant" in class_name:
            return "qdrant"
        if "pinecone" in class_name:
            return "pinecone"
        if "weaviate" in class_name:
            return "weaviate"
        if "milvus" in class_name:
            return "milvus"
        if "lancedb" in class_name:
            return "lancedb"
        if "pgvector" in class_name:
            return "pgvector"

        return None
