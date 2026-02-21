"""Search service for similarity queries."""

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from vector_inspector.core.connection_manager import ConnectionInstance

from vector_inspector.core.logging import log_error


class SearchRunner:
    """
    Service for executing similarity searches.

    Responsibilities:
        - Execute similarity queries
        - Parse and format search results
        - Handle search errors
    """

    def __init__(self, connection: Optional["ConnectionInstance"] = None) -> None:
        """Initialize search runner."""
        self.connection = connection

    def set_connection(self, connection: Optional["ConnectionInstance"]) -> None:
        """Set the active connection."""
        self.connection = connection

    def search(
        self,
        collection: str,
        query: str,
        n_results: int = 10,
        filters: Optional[dict] = None,
        use_embeddings: bool = False,
    ) -> Optional[dict[str, Any]]:
        """
        Execute similarity search.

        Args:
            collection: Collection name
            query: Query text or embedding
            n_results: Number of results to return
            filters: Optional metadata filters
            use_embeddings: If True, query is already an embedding

        Returns:
            Search results dictionary with 'ids', 'distances', 'metadatas', 'documents'
        """
        if not self.connection:
            log_error("No connection available")
            return None

        try:
            # Execute search based on connection capabilities
            if hasattr(self.connection, "query"):
                results = self.connection.query(
                    collection_name=collection,
                    query_texts=[query] if not use_embeddings else None,
                    query_embeddings=[query] if use_embeddings else None,
                    n_results=n_results,
                    where=filters,
                )
                return self._normalize_results(results)

            log_error("Connection does not support query operation")
            return None

        except Exception as e:
            log_error(f"Search failed: {e}")
            return None

    def search_by_id(
        self, collection: str, item_id: str, n_results: int = 10, filters: Optional[dict] = None
    ) -> Optional[dict[str, Any]]:
        """
        Search for similar items to a given item ID.

        Args:
            collection: Collection name
            item_id: ID of the reference item
            n_results: Number of results to return
            filters: Optional metadata filters

        Returns:
            Search results dictionary
        """
        if not self.connection:
            log_error("No connection available")
            return None

        try:
            # Get the item's embedding first
            if hasattr(self.connection, "get_by_ids"):
                data = self.connection.get_by_ids(collection, [item_id])
                if not data or not data.get("embeddings"):
                    log_error(f"Item {item_id} not found or has no embedding")
                    return None

                embedding = data["embeddings"][0]
                return self.search(
                    collection, embedding, n_results=n_results, filters=filters, use_embeddings=True
                )

            log_error("Connection does not support get_by_ids operation")
            return None

        except Exception as e:
            log_error(f"Search by ID failed: {e}")
            return None

    def _normalize_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize search results format.

        Args:
            results: Raw results from provider

        Returns:
            Normalized results dictionary
        """
        # Ensure consistent format
        normalized = {
            "ids": results.get("ids", []),
            "distances": results.get("distances", []),
            "metadatas": results.get("metadatas", []),
            "documents": results.get("documents", []),
        }

        # Flatten if results are nested in lists
        for key in ["ids", "distances", "metadatas", "documents"]:
            if normalized[key] and isinstance(normalized[key][0], list):
                normalized[key] = normalized[key][0]

        return normalized

    def calculate_similarity(self, distance: float, metric: str = "cosine") -> float:
        """
        Convert distance to similarity score.

        Args:
            distance: Distance value from search
            metric: Distance metric used ("cosine", "euclidean", "dotproduct")

        Returns:
            Similarity score (0-1, higher is more similar)
        """
        if metric == "cosine":
            # Cosine distance is 1 - cosine_similarity
            # So similarity = 1 - distance
            return max(0.0, min(1.0, 1.0 - distance))
        if metric == "dotproduct":
            # Dot product can be used directly (higher is more similar)
            # Assuming normalized vectors, this is same as cosine similarity
            return max(0.0, min(1.0, distance))
        if metric == "euclidean":
            # Convert Euclidean distance to similarity
            # Use reciprocal: similarity = 1 / (1 + distance)
            return 1.0 / (1.0 + distance)
        # Default: assume higher distance = less similar
        return max(0.0, 1.0 / (1.0 + distance))
