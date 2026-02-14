"""Filter-related logic for metadata view."""

from typing import Any


def update_filter_fields(filter_builder: Any, data: dict[str, Any]) -> None:
    """Update filter builder with available metadata field names.

    Args:
        filter_builder: FilterBuilder instance to update
        data: Collection data dictionary with documents and metadatas
    """
    field_names: list[str] = []

    # Add metadata fields
    metadatas = data.get("metadatas", [])
    if metadatas and len(metadatas) > 0 and metadatas[0]:
        # Get all unique metadata keys from the first item
        metadata_keys = sorted(metadatas[0].keys())
        field_names.extend(metadata_keys)

    if field_names:
        filter_builder.set_available_fields(field_names)
