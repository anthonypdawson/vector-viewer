"""Item update callback helpers for MetadataView.

Extracted from MetadataView to reduce code complexity.
"""

from typing import Any

from PySide6.QtWidgets import QMessageBox

from vector_inspector.ui.views.metadata import find_updated_item_page, update_row_in_place


def process_item_update_success(
    updated_data: dict[str, Any],
    ctx: Any,
    view: Any,  # MetadataView instance
    generate_on_edit: bool,
) -> None:
    """Handle successful item update.

    Args:
        updated_data: Data for the updated item
        ctx: MetadataContext instance
        view: MetadataView instance (for accessing table, callbacks, etc.)
        generate_on_edit: Whether embeddings should be regenerated on edit
    """
    # Invalidate cache after updating item
    if ctx.current_database and ctx.current_collection:
        ctx.cache_manager.invalidate(ctx.current_database, ctx.current_collection)

    # Show info about embedding regeneration/preservation when applicable
    regen_count = 0
    try:
        regen_count = int(getattr(ctx.connection, "_last_regenerated_count", 0) or 0)
        if update_row_in_place(view.table, ctx, updated_data):
            return

        # If in-place update failed, try to find the item on the server
        server_filter = None
        if view.filter_group.isChecked() and view.filter_builder.has_filters():
            server_filter, _ = view.filter_builder.get_filters_split()
        ctx.server_filter = server_filter

        target_page = find_updated_item_page(
            ctx,
            updated_data.get("id"),
        )
        if target_page is not None:
            # set selection flag and load target page
            ctx._select_id_after_load = updated_data.get("id")
            ctx.current_page = target_page
            view._load_data()
            return
    except Exception:
        pass

    # Fallback: reload current page so UI reflects server state
    view._load_data()


def _show_update_success_message(
    view: Any,
    generate_on_edit: bool,
    regen_count: int,
) -> None:
    """Show appropriate success message based on update settings."""
    if generate_on_edit:
        if regen_count > 0:
            QMessageBox.information(
                view,
                "Success",
                f"Item updated and embeddings regenerated ({regen_count}).",
            )
        else:
            QMessageBox.information(view, "Success", "Item updated. No embeddings were regenerated.")
    else:
        # embedding preservation mode
        if regen_count == 0:
            QMessageBox.information(view, "Success", "Item updated and existing embedding preserved.")
        else:
            QMessageBox.information(
                view,
                "Success",
                "Item updated.",  # Fallback message
            )
