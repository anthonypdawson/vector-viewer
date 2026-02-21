"""Cache handling helpers for MetadataView.

Extracted from MetadataView to reduce code complexity.
"""

from typing import Any

from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget

from vector_inspector.core.logging import log_info
from vector_inspector.ui.views.metadata.metadata_filters import update_filter_fields
from vector_inspector.ui.views.metadata.metadata_table import (
    populate_table,
    update_pagination_controls,
)


def try_load_from_cache(
    ctx: Any,
    table: QTableWidget,
    page_label: QLabel,
    prev_button: QPushButton,
    next_button: QPushButton,
    filter_builder: Any,
    status_label: QLabel,
) -> bool:
    """Try to load data from cache.

    Returns True if data was loaded from cache, False otherwise.
    """
    cached = ctx.cache_manager.get(ctx.current_database, ctx.current_collection)
    if not cached or not cached.data:
        log_info("[MetadataView] ✗ Cache MISS. Loading from database...")
        return False

    log_info("[MetadataView] ✓ Cache HIT! Loading from cache.")
    # Restore from cache
    ctx.current_page = 0
    ctx.current_data = cached.data
    populate_table(table, ctx)

    # For cached data, check if it's less than page_size (no next page)
    # or if it might be the full dataset (client-side filtered)
    cached_count = len(cached.data.get("ids", []))
    if cached_count < ctx.page_size:
        # Definitely no next page
        update_pagination_controls(
            ctx,
            page_label,
            prev_button,
            next_button,
            has_next_page=False,
        )
    elif cached.search_query:
        # Has filters, likely the full filtered dataset
        update_pagination_controls(
            ctx,
            page_label,
            prev_button,
            next_button,
            total_count=cached_count,
        )
    else:
        # Best guess: enable Next if we have a full page
        update_pagination_controls(
            ctx,
            page_label,
            prev_button,
            next_button,
            has_next_page=(cached_count >= ctx.page_size),
        )

    update_filter_fields(filter_builder, cached.data)

    # Restore UI state
    if cached.scroll_position:
        table.verticalScrollBar().setValue(cached.scroll_position)
    if cached.search_query:
        # Restore filter state if applicable
        pass

    status_label.setText(f"✓ Loaded from cache - {len(cached.data.get('ids', []))} items")
    return True
