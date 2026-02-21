"""Data loading callback helpers for MetadataView.

Extracted from MetadataView to reduce code complexity.
"""

from typing import Any

from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget

from vector_inspector.core.cache_manager import CacheEntry
from vector_inspector.core.logging import log_info
from vector_inspector.services.filter_service import apply_client_side_filters
from vector_inspector.ui.views.metadata.metadata_filters import update_filter_fields
from vector_inspector.ui.views.metadata.metadata_table import (
    populate_table,
    update_pagination_controls,
)


def process_loaded_data(
    data: dict[str, Any],
    table: QTableWidget,
    ctx: Any,
    status_label: QLabel,
    page_label: QLabel,
    prev_button: QPushButton,
    next_button: QPushButton,
    filter_builder: Any,
) -> None:
    """Process data loaded from background thread.

    This function handles:
    - Empty data handling
    - Client-side filtering and pagination
    - Server-side pagination
    - Table population
    - Item selection after load
    - Cache updates

    Args:
        data: Raw data from load thread
        table: Table widget to populate
        ctx: MetadataContext instance
        status_label: Label showing status messages
        page_label: Label showing page number
        prev_button: Previous page button
        next_button: Next page button
        filter_builder: Filter builder component
    """
    # If no data returned
    if not data or not data.get("ids"):
        _handle_empty_data(ctx, status_label, table, page_label, prev_button, next_button)
        return

    # Apply client-side filters across the full dataset if present
    full_data = data
    if ctx.client_filters:
        full_data = apply_client_side_filters(data, ctx.client_filters)

    if not full_data or not full_data.get("ids"):
        status_label.setText("No data after filtering")
        table.setRowCount(0)
        return

    # If client-side filtering was used, perform pagination locally
    if ctx.client_filters:
        _handle_client_side_pagination(full_data, table, ctx, page_label, prev_button, next_button, filter_builder)
        return

    # No client-side filters: display server-paginated data
    _handle_server_side_pagination(data, table, ctx, page_label, prev_button, next_button, filter_builder)


def _handle_empty_data(
    ctx: Any,
    status_label: QLabel,
    table: QTableWidget,
    page_label: QLabel,
    prev_button: QPushButton,
    next_button: QPushButton,
) -> None:
    """Handle case when no data is returned."""
    # If we're on a page beyond 0 and got no data, go back to previous page
    if ctx.current_page > 0:
        ctx.current_page -= 1
        status_label.setText("No more data available")
        update_pagination_controls(
            ctx,
            page_label,
            prev_button,
            next_button,
        )
    else:
        status_label.setText("No data after filtering")
    table.setRowCount(0)


def _handle_client_side_pagination(
    full_data: dict[str, Any],
    table: QTableWidget,
    ctx: Any,
    page_label: QLabel,
    prev_button: QPushButton,
    next_button: QPushButton,
    filter_builder: Any,
) -> None:
    """Handle client-side filtering and pagination."""
    total_count = len(full_data.get("ids", []))
    start = ctx.current_page * ctx.page_size
    end = start + ctx.page_size

    page_data = {}
    for key in ("ids", "documents", "metadatas", "embeddings"):
        lst = full_data.get(key, [])
        page_data[key] = lst[start:end]

    # Keep the full filtered data and expose the current page
    ctx.current_data_full = full_data
    ctx.current_data = page_data

    populate_table(table, ctx)
    _select_item_if_needed(table, ctx)

    update_pagination_controls(
        ctx,
        page_label,
        prev_button,
        next_button,
        total_count=total_count,
    )

    # Update filter fields based on the full filtered dataset
    update_filter_fields(filter_builder, full_data)

    # Save full filtered dataset to cache
    _save_to_cache(ctx, full_data, filter_builder, table)


def _handle_server_side_pagination(
    data: dict[str, Any],
    table: QTableWidget,
    ctx: Any,
    page_label: QLabel,
    prev_button: QPushButton,
    next_button: QPushButton,
    filter_builder: Any,
) -> None:
    """Handle server-side pagination without client filtering."""
    # Check if we fetched more items than page_size (to detect next page)
    item_count = len(data.get("ids", []))
    has_next_page = item_count > ctx.page_size

    # If we got more than page_size, trim to page_size
    if has_next_page:
        data = _trim_data_to_page_size(data, ctx.page_size)

    ctx.current_data = data
    populate_table(table, ctx)
    _select_item_if_needed(table, ctx)

    update_pagination_controls(
        ctx,
        page_label,
        prev_button,
        next_button,
        has_next_page=has_next_page,
    )

    # Update filter builder with available metadata fields
    update_filter_fields(filter_builder, data)

    # Save to cache
    _save_to_cache(ctx, data, filter_builder, table)


def _trim_data_to_page_size(data: dict[str, Any], page_size: int) -> dict[str, Any]:
    """Trim data to page size, handling various array types safely."""
    trimmed_data = {}
    for key in ("ids", "documents", "metadatas", "embeddings"):
        lst = data.get(key, [])
        # Avoid truth-value check on numpy arrays or other array-like objects
        try:
            has_items = lst is not None and len(lst) > 0
        except Exception:
            # Fallback: treat as non-empty if truthy without raising
            has_items = bool(lst)

        if has_items:
            try:
                trimmed_data[key] = lst[:page_size]
            except Exception:
                # If slicing fails, convert to list then slice
                try:
                    trimmed_data[key] = list(lst)[:page_size]
                except Exception:
                    trimmed_data[key] = []
        else:
            trimmed_data[key] = []
    return trimmed_data


def _save_to_cache(
    ctx: Any,
    data: dict[str, Any],
    filter_builder: Any,
    table: QTableWidget,
) -> None:
    """Save data to cache if database and collection are set."""
    if not ctx.cache_manager:
        return

    if not ctx.current_database or not ctx.current_collection:
        log_info(
            "[MetadataView] ✗ NOT saving to cache - db='%s', coll='%s'",
            ctx.current_database,
            ctx.current_collection,
        )
        return

    log_info(
        "[MetadataView] Saving to cache: db='%s', coll='%s'",
        ctx.current_database,
        ctx.current_collection,
    )
    cache_entry = CacheEntry(
        data=data,
        scroll_position=table.verticalScrollBar().value(),
        search_query=(filter_builder.to_dict() if callable(getattr(filter_builder, "to_dict", None)) else ""),
    )
    ctx.cache_manager.set(ctx.current_database, ctx.current_collection, cache_entry)
    log_info(
        "[MetadataView] ✓ Saved to cache. Total entries: %d",
        len(ctx.cache_manager._cache),
    )


def _select_item_if_needed(table: QTableWidget, ctx: Any) -> None:
    """Select an item if ctx has a pending selection request."""
    if not ctx._select_id_after_load:
        return

    try:
        sel_id = ctx._select_id_after_load
        ids = ctx.current_data.get("ids", []) if ctx.current_data else []
        if ids and sel_id in ids:
            row_idx = ids.index(sel_id)
            table.selectRow(row_idx)
            table.scrollToItem(table.item(row_idx, 0))
        ctx._select_id_after_load = None
    except Exception:
        ctx._select_id_after_load = None
