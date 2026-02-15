"""Metadata browsing and data view."""

from datetime import UTC
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.cache_manager import CacheEntry, get_cache_manager
from vector_inspector.core.connection_manager import ConnectionInstance
from vector_inspector.core.logging import log_info
from vector_inspector.services.filter_service import apply_client_side_filters
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.ui.components.filter_builder import FilterBuilder
from vector_inspector.ui.components.item_dialog import ItemDialog
from vector_inspector.ui.components.loading_dialog import LoadingDialog
from vector_inspector.ui.views.metadata import (
    DataLoadThread,
    MetadataContext,
    export_data,
    find_updated_item_page,
    import_data,
    populate_table,
    show_context_menu,
    update_filter_fields,
    update_pagination_controls,
    update_row_in_place,
)


class MetadataView(QWidget):
    """View for browsing collection data and metadata."""

    ctx: MetadataContext
    loading_dialog: LoadingDialog
    settings_service: SettingsService
    load_thread: Optional[DataLoadThread]
    filter_reload_timer: QTimer

    def __init__(
        self, connection: Optional[ConnectionInstance] = None, parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        # Initialize context with connection and cache manager
        cache_manager = get_cache_manager()
        self.ctx = MetadataContext(
            connection=connection,
            cache_manager=cache_manager,
        )
        self.loading_dialog = LoadingDialog("Loading data...", self)
        self.settings_service = SettingsService()
        self.load_thread = None
        self.filter_reload_timer = QTimer()
        self.filter_reload_timer.setSingleShot(True)
        self.filter_reload_timer.timeout.connect(self._reload_with_filters)
        self._setup_ui()

    @property
    def connection(self) -> Optional[ConnectionInstance]:
        """Get the current connection."""
        return self.ctx.connection

    @connection.setter
    def connection(self, value: Optional[ConnectionInstance]) -> None:
        """Set the current connection."""
        self.ctx.connection = value

    @property
    def current_collection(self) -> Optional[str]:
        """Get the current collection name."""
        return self.ctx.current_collection

    @current_collection.setter
    def current_collection(self, value: Optional[str]) -> None:
        """Set the current collection name."""
        self.ctx.current_collection = value

    def _setup_ui(self) -> None:
        """Setup widget UI."""
        layout = QVBoxLayout(self)

        # Controls
        controls_layout = QHBoxLayout()

        # Pagination controls
        controls_layout.addWidget(QLabel("Page:"))

        self.prev_button = QPushButton("◀ Previous")
        self.prev_button.clicked.connect(self._previous_page)
        self.prev_button.setEnabled(False)
        controls_layout.addWidget(self.prev_button)

        self.page_label = QLabel("0 / 0")
        controls_layout.addWidget(self.page_label)

        self.next_button = QPushButton("Next ▶")
        self.next_button.clicked.connect(self._next_page)
        self.next_button.setEnabled(False)
        controls_layout.addWidget(self.next_button)

        controls_layout.addWidget(QLabel("  Items per page:"))

        self.page_size_spin = QSpinBox()
        self.page_size_spin.setMinimum(10)
        self.page_size_spin.setMaximum(500)
        self.page_size_spin.setValue(50)
        self.page_size_spin.setSingleStep(10)
        self.page_size_spin.valueChanged.connect(self._on_page_size_changed)
        controls_layout.addWidget(self.page_size_spin)

        controls_layout.addStretch()

        # Refresh button
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self._refresh_data)
        self.refresh_button.setToolTip("Refresh data and clear cache")
        controls_layout.addWidget(self.refresh_button)

        # Add/Delete buttons
        self.add_button = QPushButton("Add Item")
        self.add_button.clicked.connect(self._add_item)
        controls_layout.addWidget(self.add_button)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self._delete_selected)
        controls_layout.addWidget(self.delete_button)

        # Checkbox: generate embeddings on edit
        self.generate_on_edit_checkbox = QCheckBox("Generate embeddings on edit")
        # Load persisted preference (default False)
        try:
            pref = bool(self.settings_service.get("generate_embeddings_on_edit", False))
        except Exception:
            pref = False
        self.generate_on_edit_checkbox.setChecked(pref)
        self.generate_on_edit_checkbox.toggled.connect(
            lambda v: self.settings_service.set("generate_embeddings_on_edit", bool(v))
        )
        controls_layout.addWidget(self.generate_on_edit_checkbox)

        # Export button with menu
        self.export_button = QPushButton("Export...")
        self.export_button.setStyleSheet("QPushButton::menu-indicator { width: 0px; }")
        export_menu = QMenu(self)
        export_menu.addAction("Export to JSON", lambda: self._export_data("json"))
        export_menu.addAction("Export to CSV", lambda: self._export_data("csv"))
        export_menu.addAction("Export to Parquet", lambda: self._export_data("parquet"))
        self.export_button.setMenu(export_menu)
        controls_layout.addWidget(self.export_button)

        # Import button with menu
        self.import_button = QPushButton("Import...")
        self.import_button.setStyleSheet("QPushButton::menu-indicator { width: 0px; }")
        import_menu = QMenu(self)
        import_menu.addAction("Import from JSON", lambda: self._import_data("json"))
        import_menu.addAction("Import from CSV", lambda: self._import_data("csv"))
        import_menu.addAction("Import from Parquet", lambda: self._import_data("parquet"))
        self.import_button.setMenu(import_menu)
        controls_layout.addWidget(self.import_button)

        layout.addLayout(controls_layout)

        # Show/Hide Filters button
        filters_toggle_layout = QHBoxLayout()
        self.show_filters_button = QPushButton("🔍 Show Filters")
        self.show_filters_button.clicked.connect(self._toggle_filters)
        self.show_filters_button.setCheckable(True)
        filters_toggle_layout.addWidget(self.show_filters_button)
        filters_toggle_layout.addStretch()
        layout.addLayout(filters_toggle_layout)

        # Create a splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Filter section
        filter_group = QGroupBox("Metadata Filters")
        filter_group.setCheckable(True)
        filter_group.setChecked(False)  # Not checked by default when visible
        filter_group_layout = QVBoxLayout()

        self.filter_builder = FilterBuilder()
        # Remove auto-reload on filter changes - only reload when user clicks Refresh
        # self.filter_builder.filter_changed.connect(self._on_filter_changed)
        # But DO reload when user presses Enter or clicks away from value input
        self.filter_builder.apply_filters.connect(self._apply_filters)
        filter_group_layout.addWidget(self.filter_builder)

        filter_group.setLayout(filter_group_layout)
        splitter.addWidget(filter_group)
        self.filter_group = filter_group
        # Hide filter section by default
        self.filter_group.setVisible(False)

        # Data table - takes up most of the space
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        # Enable context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        splitter.addWidget(self.table)

        # Set initial sizes: filter section small, table large
        splitter.setStretchFactor(0, 0)  # Filter section
        splitter.setStretchFactor(1, 1)  # Table gets most space

        # Add splitter to main layout
        layout.addWidget(splitter, stretch=1)

        # Status bar
        self.status_label = QLabel("No collection selected")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

    def set_collection(self, collection_name: str, database_name: str = "") -> None:
        """Set the current collection to display."""
        self.ctx.current_collection = collection_name
        # Always update database_name if provided (even if empty string on first call)
        if database_name:  # Only update if non-empty
            self.ctx.current_database = database_name

        # Debug: Check cache status
        log_info(
            "[MetadataView] Setting collection: db='%s', coll='%s'",
            self.ctx.current_database,
            collection_name,
        )
        log_info("[MetadataView] Cache enabled: %s", self.ctx.cache_manager.is_enabled())

        # Check cache first
        cached = self.ctx.cache_manager.get(self.ctx.current_database, self.ctx.current_collection)
        if cached and cached.data:
            log_info("[MetadataView] ✓ Cache HIT! Loading from cache.")
            # Restore from cache
            self.ctx.current_page = 0
            self.ctx.current_data = cached.data
            populate_table(self.table, self.ctx)

            # For cached data, check if it's less than page_size (no next page)
            # or if it might be the full dataset (client-side filtered)
            cached_count = len(cached.data.get("ids", []))
            if cached_count < self.ctx.page_size:
                # Definitely no next page
                update_pagination_controls(
                    self.ctx,
                    self.page_label,
                    self.prev_button,
                    self.next_button,
                    has_next_page=False,
                )
            elif cached.search_query:
                # Has filters, likely the full filtered dataset
                update_pagination_controls(
                    self.ctx,
                    self.page_label,
                    self.prev_button,
                    self.next_button,
                    total_count=cached_count,
                )
            else:
                # Best guess: enable Next if we have a full page
                update_pagination_controls(
                    self.ctx,
                    self.page_label,
                    self.prev_button,
                    self.next_button,
                    has_next_page=(cached_count >= self.ctx.page_size),
                )

            update_filter_fields(self.filter_builder, cached.data)

            # Restore UI state
            if cached.scroll_position:
                self.table.verticalScrollBar().setValue(cached.scroll_position)
            if cached.search_query:
                # Restore filter state if applicable
                pass

            self.status_label.setText(
                f"✓ Loaded from cache - {len(cached.data.get('ids', []))} items"
            )
            return

        log_info("[MetadataView] ✗ Cache MISS. Loading from database...")
        # Not in cache, load from database
        self.ctx.current_page = 0

        # Update filter builder with supported operators
        if self.ctx.connection:
            operators = self.ctx.connection.get_supported_filter_operators()
            self.filter_builder.set_operators(operators)

        self._load_data_internal()

    def _load_data(self) -> None:
        """Load data from current collection (with loading dialog)."""
        if not self.ctx.current_collection:
            self.status_label.setText("No collection selected")
            self.table.setRowCount(0)
            return

        self.loading_dialog.show_loading("Loading data from collection...")
        QApplication.processEvents()
        try:
            self._load_data_internal()
        finally:
            self.loading_dialog.hide_loading()

    def _load_data_internal(self) -> None:
        """Internal method to load data without managing loading dialog."""
        if not self.ctx.connection:
            self.status_label.setText("No database connection")
            self.table.setRowCount(0)
            return

        if not self.ctx.current_collection:
            self.status_label.setText("No collection selected")
            self.table.setRowCount(0)
            return

        # Cancel any existing load thread
        if self.load_thread and self.load_thread.isRunning():
            self.load_thread.quit()
            self.load_thread.wait()

        offset = self.ctx.current_page * self.ctx.page_size

        # Get filters split into server-side and client-side
        server_filter = None
        self.ctx.client_filters = []
        if self.filter_group.isChecked() and self.filter_builder.has_filters():
            server_filter, self.ctx.client_filters = self.filter_builder.get_filters_split()

        # If there are client-side filters, fetch the entire server-filtered set
        # so we can apply client filters across all items, then paginate client-side.
        req_limit = self.ctx.page_size
        req_offset = offset
        if self.ctx.client_filters:
            req_limit = None
            req_offset = None
        else:
            # Request one extra item to check if there's more data beyond this page
            req_limit = self.ctx.page_size + 1

        # Start background thread to load data
        self.ctx.server_filter = server_filter
        self.load_thread = DataLoadThread(
            self.ctx,
            req_limit,
            req_offset,
        )
        self.load_thread.finished.connect(self._on_data_loaded)
        self.load_thread.error.connect(self._on_load_error)
        self.load_thread.start()

    def _on_data_loaded(self, data: dict[str, Any]) -> None:
        """Handle data loaded from background thread."""
        # If no data returned
        if not data or not data.get("ids"):
            # If we're on a page beyond 0 and got no data, go back to previous page
            if self.ctx.current_page > 0:
                self.ctx.current_page -= 1
                self.status_label.setText("No more data available")
                update_pagination_controls(
                    self.ctx,
                    self.page_label,
                    self.prev_button,
                    self.next_button,
                )
            else:
                self.status_label.setText("No data after filtering")
            self.table.setRowCount(0)
            return

        # Apply client-side filters across the full dataset if present
        full_data = data
        if self.ctx.client_filters:
            full_data = apply_client_side_filters(data, self.ctx.client_filters)

        if not full_data or not full_data.get("ids"):
            self.status_label.setText("No data after filtering")
            self.table.setRowCount(0)
            return

        # If client-side filtering was used, perform pagination locally
        if self.ctx.client_filters:
            total_count = len(full_data.get("ids", []))
            start = self.ctx.current_page * self.ctx.page_size
            end = start + self.ctx.page_size

            page_data = {}
            for key in ("ids", "documents", "metadatas", "embeddings"):
                lst = full_data.get(key, [])
                page_data[key] = lst[start:end]

            # Keep the full filtered data and expose the current page
            self.ctx.current_data_full = full_data
            self.ctx.current_data = page_data

            populate_table(self.table, self.ctx)

            # After populating table, check if we should select a specific item
            if self.ctx._select_id_after_load:
                try:
                    sel_id = self.ctx._select_id_after_load
                    ids = self.ctx.current_data.get("ids", []) if self.ctx.current_data else []
                    if ids and sel_id in ids:
                        row_idx = ids.index(sel_id)
                        self.table.selectRow(row_idx)
                        self.table.scrollToItem(self.table.item(row_idx, 0))
                    self.ctx._select_id_after_load = None
                except Exception:
                    self.ctx._select_id_after_load = None

            update_pagination_controls(
                self.ctx,
                self.page_label,
                self.prev_button,
                self.next_button,
                total_count=total_count,
            )

            # Update filter fields based on the full filtered dataset
            update_filter_fields(self.filter_builder, full_data)

            # Save full filtered dataset to cache
            if self.ctx.current_database and self.ctx.current_collection:
                log_info(
                    "[MetadataView] Saving filtered full dataset to cache: db='%s', coll='%s'",
                    self.ctx.current_database,
                    self.ctx.current_collection,
                )
                cache_entry = CacheEntry(
                    data=full_data,
                    scroll_position=self.table.verticalScrollBar().value(),
                    search_query=(
                        self.filter_builder.to_dict()
                        if callable(getattr(self.filter_builder, "to_dict", None))
                        else ""
                    ),
                )
                self.ctx.cache_manager.set(
                    self.ctx.current_database, self.ctx.current_collection, cache_entry
                )
            return

        # No client-side filters: display server-paginated data
        # Check if we fetched more items than page_size (to detect next page)
        item_count = len(data.get("ids", []))
        has_next_page = item_count > self.ctx.page_size

        # If we got more than page_size, trim to page_size
        if has_next_page:
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
                        trimmed_data[key] = lst[: self.ctx.page_size]
                    except Exception:
                        # If slicing fails, convert to list then slice
                        try:
                            trimmed_data[key] = list(lst)[: self.ctx.page_size]
                        except Exception:
                            trimmed_data[key] = []
                else:
                    trimmed_data[key] = []
            data = trimmed_data

        self.ctx.current_data = data
        populate_table(self.table, self.ctx)

        # After populating table with new page data, check if we should select a specific item
        if self.ctx._select_id_after_load:
            try:
                sel_id = self.ctx._select_id_after_load
                ids = self.ctx.current_data.get("ids", []) if self.ctx.current_data else []
                if ids and sel_id in ids:
                    row_idx = ids.index(sel_id)
                    # select and scroll to the row
                    self.table.selectRow(row_idx)
                    self.table.scrollToItem(self.table.item(row_idx, 0))
                # clear the flag
                self.ctx._select_id_after_load = None
            except Exception:
                self.ctx._select_id_after_load = None

        update_pagination_controls(
            self.ctx,
            self.page_label,
            self.prev_button,
            self.next_button,
            has_next_page=has_next_page,
        )

        # Update filter builder with available metadata fields
        update_filter_fields(self.filter_builder, data)

        # Save to cache
        if self.ctx.current_database and self.ctx.current_collection:
            log_info(
                "[MetadataView] Saving to cache: db='%s', coll='%s'",
                self.ctx.current_database,
                self.ctx.current_collection,
            )
            cache_entry = CacheEntry(
                data=data,
                scroll_position=self.table.verticalScrollBar().value(),
                search_query=(
                    self.filter_builder.to_dict()
                    if callable(getattr(self.filter_builder, "to_dict", None))
                    else ""
                ),
            )
            self.ctx.cache_manager.set(
                self.ctx.current_database, self.ctx.current_collection, cache_entry
            )
            log_info(
                "[MetadataView] ✓ Saved to cache. Total entries: %d",
                len(self.ctx.cache_manager._cache),
            )
        else:
            log_info(
                "[MetadataView] ✗ NOT saving to cache - db='%s', coll='%s'",
                self.ctx.current_database,
                self.ctx.current_collection,
            )

    def _on_load_error(self, error_msg: str) -> None:
        """Handle error from background thread."""
        self.status_label.setText(f"Failed to load data: {error_msg}")
        self.table.setRowCount(0)

    def _previous_page(self) -> None:
        """Go to previous page."""
        if self.ctx.current_page > 0:
            self.ctx.current_page -= 1
            self._load_data()

    def _next_page(self) -> None:
        """Go to next page."""
        self.ctx.current_page += 1
        self._load_data()

    def _on_page_size_changed(self, value: int) -> None:
        """Handle page size change."""
        self.ctx.page_size = value
        self.ctx.current_page = 0
        self._load_data()

    def _add_item(self) -> None:
        """Add a new item to the collection."""
        if not self.ctx.connection:
            QMessageBox.warning(self, "No Connection", "No database connection available.")
            return

        if not self.ctx.current_collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first.")
            return

        dialog = ItemDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            item_data = dialog.get_item_data()
            if not item_data:
                return

            # Inject created_at timestamp if not already present
            from datetime import datetime

            if item_data["metadata"] is None:
                item_data["metadata"] = {}
            if "created_at" not in item_data["metadata"]:
                item_data["metadata"]["created_at"] = datetime.now(UTC).isoformat()

            # Add item to collection
            success = self.ctx.connection.add_items(
                self.ctx.current_collection,
                documents=[item_data["document"]],
                metadatas=[item_data["metadata"]] if item_data["metadata"] else None,
                ids=[item_data["id"]] if item_data["id"] else None,
            )

            if success:
                # Invalidate cache after adding item
                if self.ctx.current_database and self.ctx.current_collection:
                    self.ctx.cache_manager.invalidate(
                        self.ctx.current_database, self.ctx.current_collection
                    )
                QMessageBox.information(self, "Success", "Item added successfully.")
                # Fallback to full reload (row index is not available here)
                self._load_data()
            else:
                QMessageBox.warning(self, "Error", "Failed to add item.")

    def _delete_selected(self) -> None:
        """Delete selected items."""
        if not self.ctx.connection:
            QMessageBox.warning(self, "No Connection", "No database connection available.")
            return

        if not self.ctx.current_collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first.")
            return

        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select items to delete.")
            return

        # Get IDs of selected items
        ids_to_delete = []
        for row in selected_rows:
            id_item = self.table.item(row.row(), 0)
            if id_item:
                ids_to_delete.append(id_item.text())

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete {len(ids_to_delete)} item(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            success = self.ctx.connection.delete_items(
                self.ctx.current_collection, ids=ids_to_delete
            )
            if success:
                # Invalidate cache after deletion
                if self.ctx.current_database and self.ctx.current_collection:
                    self.ctx.cache_manager.invalidate(
                        self.ctx.current_database, self.ctx.current_collection
                    )
                QMessageBox.information(self, "Success", "Items deleted successfully.")
                self._load_data()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete items.")

    def _on_filter_changed(self) -> None:
        """Handle filter changes - debounce and reload data."""
        if self.filter_group.isChecked():
            # Restart the timer - will only fire 500ms after last change
            self.filter_reload_timer.stop()
            self.filter_reload_timer.start(500)  # 500ms debounce

    def _reload_with_filters(self) -> None:
        """Reload data with current filters (called after debounce)."""
        self.ctx.current_page = 0
        self._load_data()

    def _apply_filters(self) -> None:
        """Apply filters when user presses Enter or clicks away."""
        if self.filter_group.isChecked() and self.ctx.current_collection:
            self.ctx.current_page = 0
            self._load_data()

    def _toggle_filters(self) -> None:
        """Toggle the visibility of the filter section."""
        is_visible = self.filter_group.isVisible()
        self.filter_group.setVisible(not is_visible)

        # Update button text and state
        if not is_visible:
            self.show_filters_button.setText("🔍 Hide Filters")
            self.show_filters_button.setChecked(True)
        else:
            self.show_filters_button.setText("🔍 Show Filters")
            self.show_filters_button.setChecked(False)

    def _refresh_data(self) -> None:
        """Refresh data and invalidate cache."""
        if self.ctx.current_database and self.ctx.current_collection:
            self.ctx.cache_manager.invalidate(
                self.ctx.current_database, self.ctx.current_collection
            )
        self.ctx.current_page = 0
        self._load_data()

    def _on_row_double_clicked(self, index: Any) -> None:
        """Handle double-click on a row to edit item."""
        if not self.ctx.connection:
            QMessageBox.warning(self, "No Connection", "No database connection available.")
            return

        if not self.ctx.current_collection or not self.ctx.current_data:
            return

        row = index.row()
        if row < 0 or row >= self.table.rowCount():
            return

        # Get item data for this row
        ids = self.ctx.current_data.get("ids", [])
        documents = self.ctx.current_data.get("documents", [])
        metadatas = self.ctx.current_data.get("metadatas", [])

        if row >= len(ids):
            return

        item_data = {
            "id": ids[row],
            "document": documents[row] if row < len(documents) else "",
            "metadata": metadatas[row] if row < len(metadatas) else {},
        }

        # Open edit dialog
        dialog = ItemDialog(self, item_data=item_data)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_data = dialog.get_item_data()
            if not updated_data:
                return

            # Inject updated_at timestamp
            from datetime import datetime

            if updated_data["metadata"] is None:
                updated_data["metadata"] = {}
            updated_data["metadata"]["updated_at"] = datetime.now(UTC).isoformat()

            # Decide whether to generate embeddings on edit or preserve existing
            embeddings_arg = None
            try:
                generate_on_edit = bool(self.generate_on_edit_checkbox.isChecked())
            except Exception:
                generate_on_edit = False

            if not generate_on_edit:
                # Try to preserve existing embedding for this row if present
                from vector_inspector.utils import has_embedding

                existing_embs = (
                    self.ctx.current_data.get("embeddings", []) if self.ctx.current_data else []
                )
                if row < len(existing_embs):
                    existing = existing_embs[row]
                    if has_embedding(existing):
                        embeddings_arg = [existing]

            # Update item in collection
            if embeddings_arg is None:
                # No embeddings passed -> will trigger regeneration when update_items supports it
                success = self.ctx.connection.update_items(
                    self.ctx.current_collection,
                    ids=[updated_data["id"]],
                    documents=[updated_data["document"]] if updated_data["document"] else None,
                    metadatas=[updated_data["metadata"]] if updated_data["metadata"] else None,
                )
            else:
                # Pass existing embeddings to preserve them
                success = self.ctx.connection.update_items(
                    self.ctx.current_collection,
                    ids=[updated_data["id"]],
                    documents=[updated_data["document"]] if updated_data["document"] else None,
                    metadatas=[updated_data["metadata"]] if updated_data["metadata"] else None,
                    embeddings=embeddings_arg,
                )

            if success:
                # Invalidate cache after updating item
                if self.ctx.current_database and self.ctx.current_collection:
                    self.ctx.cache_manager.invalidate(
                        self.ctx.current_database, self.ctx.current_collection
                    )

                # Show info about embedding regeneration/preservation when applicable
                try:
                    generate_on_edit = bool(self.generate_on_edit_checkbox.isChecked())
                except Exception:
                    generate_on_edit = False

                regen_count = 0
                try:
                    regen_count = int(
                        getattr(self.ctx.connection, "_last_regenerated_count", 0) or 0
                    )
                except Exception:
                    regen_count = 0

                if generate_on_edit:
                    if regen_count > 0:
                        QMessageBox.information(
                            self,
                            "Success",
                            f"Item updated and embeddings regenerated ({regen_count}).",
                        )
                    else:
                        QMessageBox.information(
                            self, "Success", "Item updated. No embeddings were regenerated."
                        )
                else:
                    # embedding preservation mode
                    if regen_count == 0:
                        QMessageBox.information(
                            self, "Success", "Item updated and existing embedding preserved."
                        )
                    else:
                        QMessageBox.information(
                            self,
                            "Success",
                            "Item updated.",  # Fallback message
                        )

                # If embeddings were regenerated, server ordering may have changed.
                # Locate the updated item on the server (respecting server-side filters),
                # compute its page and load that page while selecting the row. This
                # ensures the edited item becomes visible even if the backend moved it.
                try:
                    # Quick in-place update: if the updated item is still on the
                    # currently-visible page, update the in-memory page and
                    # table cells and emit `dataChanged` so the view refreshes
                    # immediately without a full reload.
                    if update_row_in_place(self.table, self.ctx, updated_data):
                        return

                    # If in-place update failed, try to find the item on the server
                    server_filter = None
                    if self.filter_group.isChecked() and self.filter_builder.has_filters():
                        server_filter, _ = self.filter_builder.get_filters_split()
                    self.ctx.server_filter = server_filter

                    target_page = find_updated_item_page(
                        self.ctx,
                        updated_data.get("id"),
                    )
                    if target_page is not None:
                        # set selection flag and load target page
                        self.ctx._select_id_after_load = updated_data.get("id")
                        self.ctx.current_page = target_page
                        self._load_data()
                        return
                except Exception:
                    pass

                # Fallback: reload current page so UI reflects server state
                self._load_data()
            else:
                QMessageBox.warning(self, "Error", "Failed to update item.")

    def select_item_by_id(self, item_id: str) -> bool:
        """Select and scroll to a row by item ID.

        If the item is on the current page, selects it immediately.
        If not, attempts to find which page it's on and loads that page.

        Args:
            item_id: The ID of the item to select

        Returns:
            True if item was found and selected, False otherwise
        """
        if not self.ctx.current_data:
            return False

        # Check if item is on current page
        ids = self.ctx.current_data.get("ids", [])
        if item_id in ids:
            row_idx = ids.index(item_id)
            self.table.selectRow(row_idx)
            self.table.scrollToItem(self.table.item(row_idx, 0))
            return True

        # Item not on current page - try to find it
        try:
            from vector_inspector.ui.views.metadata import find_updated_item_page

            server_filter = None
            if self.filter_group.isChecked() and self.filter_builder.has_filters():
                server_filter, _ = self.filter_builder.get_filters_split()
            self.ctx.server_filter = server_filter

            target_page = find_updated_item_page(self.ctx, item_id)

            if target_page is not None:
                self.ctx._select_id_after_load = item_id
                self.ctx.current_page = target_page
                self._load_data()
                return True
        except Exception:
            pass

        return False

    def _export_data(self, format_type: str) -> None:
        """Export current table data to file (visible rows or selected rows)."""
        export_data(
            self,
            self.ctx,
            format_type,
            self.table,
        )

    def _show_context_menu(self, position: Any) -> None:
        """Show context menu for table rows."""
        show_context_menu(
            self.table,
            position,
            self.ctx,
            self._on_row_double_clicked,
        )

    def _import_data(self, format_type: str) -> None:
        """Import data from file into collection."""
        imported_data = import_data(
            self,
            self.ctx,
            format_type,
            self.loading_dialog,
        )
        if imported_data:
            # Invalidate cache after import
            if self.ctx.current_database and self.ctx.current_collection:
                self.ctx.cache_manager.invalidate(
                    self.ctx.current_database, self.ctx.current_collection
                )
            self._load_data()
