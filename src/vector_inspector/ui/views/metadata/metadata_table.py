"""Table population and interaction logic for metadata view."""

import json
import math
from collections.abc import Callable
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QTableWidget, QTableWidgetItem

from vector_inspector.core.logging import log_info
from vector_inspector.ui.views.metadata.context import MetadataContext


def populate_table(
    table: QTableWidget,
    ctx: MetadataContext,
) -> None:
    """Populate table with data.

    Args:
        table: QTableWidget to populate
        ctx: MetadataContext containing data and pagination info
    """
    if not ctx.current_data:
        table.setRowCount(0)
        return

    data = ctx.current_data
    current_page = ctx.current_page
    page_size = ctx.page_size
    ids = data.get("ids", [])
    documents = data.get("documents", [])
    metadatas = data.get("metadatas", [])

    if not ids:
        table.setRowCount(0)
        return

    # Determine columns
    columns: list[str] = ["ID", "Document"]
    metadata_keys: list[str] = []
    if metadatas and metadatas[0]:
        metadata_keys = list(metadatas[0].keys())
        columns.extend(metadata_keys)

    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setRowCount(len(ids))

    # Calculate starting row number based on current page
    start_row_number = current_page * page_size + 1

    # Update vertical header labels to show absolute row numbers
    vertical_labels = [str(start_row_number + i) for i in range(len(ids))]
    table.setVerticalHeaderLabels(vertical_labels)

    # Populate rows
    for row, (id_val, doc, meta) in enumerate(zip(ids, documents, metadatas, strict=True)):
        # ID column
        table.setItem(row, 0, QTableWidgetItem(str(id_val)))

        # Document column
        doc_text = str(doc) if doc else ""
        if len(doc_text) > 100:
            doc_text = doc_text[:100] + "..."
        table.setItem(row, 1, QTableWidgetItem(doc_text))

        # Metadata columns
        if meta:
            for col_idx, key in enumerate(metadata_keys, start=2):
                value = meta.get(key, "")
                table.setItem(row, col_idx, QTableWidgetItem(str(value)))

    table.resizeColumnsToContents()


def copy_vectors_to_json(
    table: QTableWidget,
    ctx: MetadataContext,
    selected_rows: list[int],
) -> None:
    """Copy vector(s) from selected row(s) to clipboard as JSON.

    Args:
        table: QTableWidget instance
        ctx: MetadataContext containing current data
        selected_rows: List of selected row indices
    """
    if not ctx.current_data:
        QMessageBox.warning(
            table,
            "No Vector Data",
            "No vector embeddings available for the selected row(s).",
        )
        return

    embeddings = ctx.current_data.get("embeddings", [])
    ids = ctx.current_data.get("ids", [])

    # Check if embeddings exist and have data (avoid truthiness check on arrays)
    if embeddings is None or len(embeddings) == 0:
        QMessageBox.warning(
            table,
            "No Vector Data",
            "No vector embeddings available for the selected row(s).",
        )
        return

    # Collect vectors for selected rows
    vectors_data = []
    for row in selected_rows:
        if row < len(embeddings) and row < len(ids):
            vector = embeddings[row]
            item_id = ids[row]

            # Handle different vector types (list, numpy array, etc.)
            try:
                vector_list = vector.tolist() if hasattr(vector, "tolist") else list(vector)

                vectors_data.append(
                    {
                        "id": str(item_id),
                        "vector": vector_list,
                        "dimension": len(vector_list),
                    }
                )
            except Exception as e:
                log_info("Error processing vector for row %d: %s", row, e)
                continue

    if not vectors_data:
        QMessageBox.warning(
            table,
            "No Vector Data",
            "Could not extract vector data from the selected row(s).",
        )
        return

    # Format as JSON (single object if one row, list if multiple)
    try:
        if len(vectors_data) == 1:
            json_output = json.dumps(vectors_data[0], indent=2)
        else:
            json_output = json.dumps(vectors_data, indent=2)

        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText(json_output)

        # Show success message
        count = len(vectors_data)
        item_text = "vector" if count == 1 else "vectors"
        QMessageBox.information(
            table,
            "Success",
            f"Copied {count} {item_text} to clipboard as JSON.",
        )
    except Exception as e:
        log_info("Error copying vectors to JSON: %s", e)
        QMessageBox.warning(
            table,
            "Error",
            f"Failed to copy vector data: {e}",
        )


def update_pagination_controls(
    ctx: MetadataContext,
    page_label: Any,  # QLabel
    prev_button: Any,  # QPushButton
    next_button: Any,  # QPushButton
    total_count: Optional[int] = None,
    has_next_page: Optional[bool] = None,
) -> None:
    """Update pagination button states.

    Args:
        ctx: MetadataContext containing data and pagination info
        page_label: QLabel widget to update with page information
        prev_button: Previous page button
        next_button: Next page button
        total_count: If provided, compute total pages for client-side pagination
        has_next_page: If provided (for server-side pagination), explicitly sets whether Next is enabled
    """
    if not ctx.current_data:
        return

    current_page = ctx.current_page
    page_size = ctx.page_size

    if total_count is not None:
        # Client-side pagination with known total
        total_pages = max(1, math.ceil(total_count / page_size))
        has_more = (current_page + 1) < total_pages
        page_label.setText(f"{current_page + 1} / {total_pages}")
    elif has_next_page is not None:
        # Server-side pagination with explicit next page indicator
        has_more = has_next_page
        page_label.setText(f"{current_page + 1}")
    else:
        # Fallback: assume no next page
        has_more = False
        page_label.setText(f"{current_page + 1}")

    prev_button.setEnabled(current_page > 0)
    next_button.setEnabled(has_more)


def show_context_menu(
    table: QTableWidget,
    position: Any,  # QPoint
    ctx: MetadataContext,
    on_row_double_clicked_callback: Callable[[Any], None],
) -> None:
    """Show context menu for table rows.

    Args:
        table: QTableWidget instance
        position: Position where context menu was requested
        ctx: MetadataContext containing data and connection info
        on_row_double_clicked_callback: Callback for row edit action
    """
    # Get the item at the position
    item = table.itemAt(position)
    if not item or not ctx.current_data:
        return

    current_data = ctx.current_data
    current_collection = ctx.current_collection
    current_database = ctx.current_database
    connection = ctx.connection

    row = item.row()
    if row < 0 or row >= table.rowCount():
        return

    # Create context menu
    menu = QMenu(table)

    # Add standard "Edit" action
    edit_action = menu.addAction("✏️ Edit")
    edit_action.triggered.connect(
        lambda: on_row_double_clicked_callback(table.model().index(row, 0))
    )

    # Add "Copy vector to JSON" action
    selected_rows = [index.row() for index in table.selectionModel().selectedRows()]
    if not selected_rows:
        selected_rows = [row]

    copy_vector_action = menu.addAction("📋 Copy vector to JSON")
    copy_vector_action.triggered.connect(lambda: copy_vectors_to_json(table, ctx, selected_rows))

    # Call extension hooks to add custom menu items
    try:
        from vector_inspector.extensions import table_context_menu_hook

        table_context_menu_hook.trigger(
            menu=menu,
            table=table,
            row=row,
            data={
                "current_data": current_data,
                "collection_name": current_collection,
                "database_name": current_database,
                "connection": connection,
                "view_type": "metadata",
            },
        )
    except Exception as e:
        log_info("Extension hook error: %s", e)

    # Show menu
    menu.exec(table.viewport().mapToGlobal(position))


def update_row_in_place(
    table: QTableWidget,
    ctx: MetadataContext,
    updated_data: dict[str, Any],
) -> bool:
    """Update a row in-place in the table without reloading.

    Args:
        table: QTableWidget instance
        ctx: MetadataContext containing current data
        updated_data: Updated item data with 'id', 'document', 'metadata'

    Returns:
        True if update succeeded, False otherwise
    """
    if not ctx.current_data:
        return False

    current_data = ctx.current_data
    updated_id = updated_data.get("id")
    if (
        not current_data
        or not current_data.get("ids")
        or updated_id not in current_data.get("ids", [])
    ):
        return False

    try:
        row_idx: int = current_data["ids"].index(updated_id)

        # Update in-memory lists
        if "documents" in current_data and row_idx < len(current_data["documents"]):
            current_data["documents"][row_idx] = (
                updated_data["document"] if updated_data["document"] else ""
            )
        if "metadatas" in current_data and row_idx < len(current_data["metadatas"]):
            current_data["metadatas"][row_idx] = (
                updated_data["metadata"] if updated_data["metadata"] else {}
            )

        # Update table cell text for document column
        doc_text = (
            str(current_data["documents"][row_idx]) if current_data["documents"][row_idx] else ""
        )
        if len(doc_text) > 100:
            doc_text = doc_text[:100] + "..."
        table.setItem(row_idx, 1, QTableWidgetItem(doc_text))

        # Update metadata columns based on current header names
        metadata_keys: list[str] = []
        for col in range(2, table.columnCount()):
            hdr = table.horizontalHeaderItem(col)
            if hdr:
                metadata_keys.append(hdr.text())

        if "metadatas" in current_data:
            meta = current_data["metadatas"][row_idx]
            for col_idx, key in enumerate(metadata_keys, start=2):
                value = meta.get(key, "")
                table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

        # Emit dataChanged on the underlying model so views refresh
        try:
            model = table.model()
            top = model.index(row_idx, 0)
            bottom = model.index(row_idx, table.columnCount() - 1)
            model.dataChanged.emit(
                top,
                bottom,
                [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole],
            )
        except Exception:
            pass

        # Restore selection/scroll
        table.verticalScrollBar().setValue(table.verticalScrollBar().value())
        table.selectRow(row_idx)
        table.scrollToItem(table.item(row_idx, 0))
        return True
    except Exception:
        return False


def find_updated_item_page(
    ctx: MetadataContext,
    updated_id: Optional[str],
) -> Optional[int]:
    """Find which page an updated item is on after server-side changes.

    Args:
        ctx: MetadataContext containing connection and pagination info
        updated_id: ID of updated item to find (optional)

    Returns:
        Page number (0-indexed) where item is located, or None if not found
    """
    if not updated_id:
        return None

    try:
        full = ctx.connection.get_all_items(
            ctx.current_collection, limit=None, offset=None, where=ctx.server_filter
        )
        if full and full.get("ids"):
            all_ids = full.get("ids", [])
            if updated_id in all_ids:
                idx = all_ids.index(updated_id)
                return idx // ctx.page_size
    except Exception:
        pass
    return None
