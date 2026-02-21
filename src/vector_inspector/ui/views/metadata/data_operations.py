"""Data operations for MetadataView that can be run in background tasks.

These functions are designed to be used with ThreadedTaskRunner.
"""

from typing import Any, Optional


def load_collection_data(
    connection: Any,
    collection: str,
    req_limit: Optional[int],
    req_offset: Optional[int],
    server_filter: Optional[dict],
) -> dict[str, Any]:
    """Load data from collection (for background task).

    Args:
        connection: Database connection instance
        collection: Collection name
        req_limit: Optional limit on number of items
        req_offset: Optional offset for pagination
        server_filter: Optional filter to apply server-side

    Returns:
        Dictionary containing ids, documents, metadatas, embeddings

    Raises:
        Exception: If loading fails
    """
    if not connection:
        raise Exception("No database connection available")

    data = connection.get_all_items(
        collection,
        limit=req_limit,
        offset=req_offset,
        where=server_filter,
    )

    if not data:
        raise Exception("Failed to load data")

    return data


def update_collection_item(
    connection: Any,
    collection: str,
    updated_data: dict[str, Any],
    embeddings_arg: Optional[list] = None,
) -> dict[str, Any]:
    """Update an item in the collection (for background task).

    Args:
        connection: Database connection instance
        collection: Collection name
        updated_data: Dictionary with id, document, metadata
        embeddings_arg: Optional embeddings to preserve

    Returns:
        The updated_data dictionary (for consistency with old thread behavior)

    Raises:
        Exception: If update fails
    """
    if not connection:
        raise Exception("No database connection available")

    # Update item in collection
    if embeddings_arg is None:
        success = connection.update_items(
            collection,
            ids=[updated_data["id"]],
            documents=[updated_data["document"]],
            metadatas=[updated_data["metadata"]],
        )
    else:
        success = connection.update_items(
            collection,
            ids=[updated_data["id"]],
            documents=[updated_data["document"]],
            metadatas=[updated_data["metadata"]],
            embeddings=embeddings_arg,
        )

    if not success:
        raise Exception("Failed to update item")

    return updated_data
