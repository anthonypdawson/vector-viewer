"""Metadata browsing and data view."""

from datetime import UTC
from typing import Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.connection_manager import ConnectionInstance
from vector_inspector.core.logging import log_info
from vector_inspector.services import CollectionLoader, MetadataLoader, ThreadedTaskRunner
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.state import AppState
from vector_inspector.ui.components.filter_builder import FilterBuilder
from vector_inspector.ui.components.inline_details_pane import InlineDetailsPane
from vector_inspector.ui.components.item_dialog import ItemDialog
from vector_inspector.ui.components.loading_dialog import LoadingDialog
from vector_inspector.ui.components.metadata_action_buttons import MetadataActionButtons
from vector_inspector.ui.components.pagination_controls import PaginationControls
from vector_inspector.ui.views.metadata import (
    DataImportThread,
    MetadataContext,
    export_data,
    show_context_menu,
)
from vector_inspector.ui.views.metadata.cache_helpers import try_load_from_cache
from vector_inspector.ui.views.metadata.data_loading_helpers import process_loaded_data
from vector_inspector.ui.views.metadata.data_operations import (
    load_collection_data,
    update_collection_item,
)
from vector_inspector.ui.views.metadata.item_update_helpers import (
    process_item_update_success,
)
from vector_inspector.ui.views.metadata.metadata_table import _show_item_details


class MetadataView(QWidget):
    """View for browsing collection data and metadata."""

    ctx: MetadataContext
    app_state: AppState
    task_runner: ThreadedTaskRunner
    collection_loader: CollectionLoader
    metadata_loader: MetadataLoader
    loading_dialog: LoadingDialog
    settings_service: SettingsService
    import_thread: Optional[DataImportThread]
    filter_reload_timer: QTimer

    def __init__(
        self,
        app_state: AppState,
        task_runner: ThreadedTaskRunner,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        # Store AppState and task runner
        self.app_state = app_state
        self.task_runner = task_runner
        self.collection_loader = CollectionLoader()
        self.metadata_loader = MetadataLoader()

        # Initialize context with connection and cache manager from AppState
        self.ctx = MetadataContext(
            connection=self.app_state.provider,
            cache_manager=self.app_state.cache_manager,
        )
        self.loading_dialog = LoadingDialog("Loading data...", self)
        self.settings_service = SettingsService()
        self.import_thread = None
        self.filter_reload_timer = QTimer()
        self.filter_reload_timer.setSingleShot(True)
        self.filter_reload_timer.timeout.connect(self._reload_with_filters)
        self._setup_ui()

        # Connect to AppState signals
        self._connect_state_signals()
        # Update services with current connection if available
        if self.app_state.provider:
            self._on_provider_changed(self.app_state.provider)

    def _connect_state_signals(self) -> None:
        """Subscribe to AppState changes."""
        # React to connection changes
        self.app_state.provider_changed.connect(self._on_provider_changed)

        # React to collection changes
        self.app_state.collection_changed.connect(self._on_collection_changed)

        # React to loading state
        self.app_state.loading_started.connect(self._on_loading_started)
        self.app_state.loading_finished.connect(self._on_loading_finished)

        # React to errors
        self.app_state.error_occurred.connect(self._on_error)

    def _on_provider_changed(self, connection: Optional[ConnectionInstance]) -> None:
        """React to provider/connection change."""
        # Update services
        if self.collection_loader:
            self.collection_loader.set_connection(connection)
        if self.metadata_loader:
            self.metadata_loader.set_connection(connection)

        # Update context
        self.ctx.connection = connection

        # Clear table
        self.table.setRowCount(0)
        self.status_label.setText("No collection selected" if not connection else "Connected - select a collection")

    def _on_collection_changed(self, collection: str) -> None:
        """React to collection change."""
        if collection:
            # Use AppState's database name
            database_name = self.app_state.database or ""
            self.set_collection(collection, database_name)

    def _on_loading_started(self, message: str) -> None:
        """React to loading started."""
        self.loading_dialog.show_loading(message)

    def _on_loading_finished(self) -> None:
        """React to loading finished."""
        self.loading_dialog.hide()

    def _on_error(self, title: str, message: str) -> None:
        """React to error."""
        QMessageBox.critical(self, title, message)

    @property
    def connection(self) -> Optional[ConnectionInstance]:
        """Get the current connection."""
        return self.ctx.connection

    @connection.setter
    def connection(self, value: Optional[ConnectionInstance]) -> None:
        """Set the current connection."""
        self.ctx.connection = value
        # Also update app_state if using new pattern
        if self.app_state and value != self.app_state.provider:
            self.app_state.provider = value

    @property
    def current_collection(self) -> Optional[str]:
        """Get the current collection name."""
        return self.ctx.current_collection

    @current_collection.setter
    def current_collection(self, value: Optional[str]) -> None:
        """Set the current collection name."""
        if value is not None:
            self.ctx.current_collection = value
        # Also update app_state if using new pattern
        if self.app_state and value and value != self.app_state.collection:
            self.app_state.collection = value

    def _setup_ui(self) -> None:
        """Setup widget UI."""
        layout = QVBoxLayout(self)

        # Top controls row
        controls_layout = QHBoxLayout()

        # Pagination controls
        controls_layout.addWidget(QLabel("Page:"))
        self.pagination = PaginationControls()
        self.pagination.previous_clicked.connect(self._previous_page)
        self.pagination.next_clicked.connect(self._next_page)
        self.pagination.page_size_changed.connect(self._on_page_size_changed)
        # Get the widgets we need to reference
        self.prev_button = self.pagination.prev_button
        self.next_button = self.pagination.next_button
        self.page_label = self.pagination.page_label
        self.page_size_spin = self.pagination.page_size_spin
        controls_layout.addWidget(self.pagination)

        controls_layout.addStretch()

        # Action buttons
        self.action_buttons = MetadataActionButtons()
        self.action_buttons.refresh_clicked.connect(self._refresh_data)
        self.action_buttons.add_clicked.connect(self._add_item)
        self.action_buttons.delete_clicked.connect(self._delete_selected)
        self.action_buttons.export_requested.connect(self._export_data)
        self.action_buttons.import_requested.connect(self._import_data)
        # Get widgets we need to reference
        self.refresh_button = self.action_buttons.refresh_button
        self.add_button = self.action_buttons.add_button
        self.delete_button = self.action_buttons.delete_button
        self.generate_on_edit_checkbox = self.action_buttons.generate_on_edit_checkbox
        self.export_button = self.action_buttons.export_button
        self.import_button = self.action_buttons.import_button
        controls_layout.addWidget(self.action_buttons)

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
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # Disable inline editing
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionsMovable(True)  # Allow column reordering
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        # Enable context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        # Connect selection changes to update inline details
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        # Inline details pane
        self.details_pane = InlineDetailsPane(view_mode="data_browser")
        self.details_pane.open_full_details.connect(
            lambda: self._on_row_double_clicked(self.table.currentIndex()) if self.table.currentRow() >= 0 else None
        )
        self.details_pane.setMinimumHeight(120)
        splitter.addWidget(self.details_pane)

        # Set initial sizes: filter section small, table large, details medium
        splitter.setStretchFactor(0, 0)  # Filter section
        splitter.setStretchFactor(1, 3)  # Table gets most space
        splitter.setStretchFactor(2, 1)  # Details pane

        # Restore splitter sizes from settings
        saved_sizes = self.settings_service.get("metadata_view_splitter_sizes", [])
        # Only apply saved sizes if they are a list/tuple of length 3
        if isinstance(saved_sizes, (list, tuple)) and len(saved_sizes) == 3:
            splitter.setSizes(saved_sizes)

        # Save splitter sizes when changed
        self.main_splitter = splitter
        splitter.splitterMoved.connect(
            lambda: self.settings_service.set("metadata_view_splitter_sizes", splitter.sizes())
        )

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

        log_info(
            "[MetadataView] Setting collection: db='%s', coll='%s'",
            self.ctx.current_database,
            collection_name,
        )
        log_info("[MetadataView] Cache enabled: %s", self.ctx.cache_manager.is_enabled())

        # Try loading from cache first
        if try_load_from_cache(
            self.ctx,
            self.table,
            self.page_label,
            self.prev_button,
            self.next_button,
            self.filter_builder,
            self.status_label,
        ):
            return

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

        # Start background task to load data
        self.ctx.server_filter = server_filter

        # Use TaskRunner if available, otherwise fall back to legacy threading
        if self.task_runner:
            self.task_runner.run_task(
                lambda: load_collection_data(
                    self.ctx.connection,
                    self.ctx.current_collection,
                    req_limit,
                    req_offset,
                    server_filter,
                ),
                on_finished=self._on_data_loaded,
                on_error=self._on_load_error,
            )
        else:
            # Legacy path for backward compatibility
            from vector_inspector.ui.views.metadata import DataLoadThread

            load_thread = DataLoadThread(self.ctx, req_limit, req_offset)
            load_thread.finished.connect(self._on_data_loaded)
            load_thread.error.connect(self._on_load_error)
            load_thread.start()

    def _on_data_loaded(self, data: dict[str, Any]) -> None:
        """Handle data loaded from background thread."""
        process_loaded_data(
            data,
            self.table,
            self.ctx,
            self.status_label,
            self.page_label,
            self.prev_button,
            self.next_button,
            self.filter_builder,
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

            # Inject created_at timestamp if checkbox is enabled and not already present
            auto_timestamp = item_data.pop("auto_timestamp", False)
            if auto_timestamp:
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
                    self.ctx.cache_manager.invalidate(self.ctx.current_database, self.ctx.current_collection)
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
            success = self.ctx.connection.delete_items(self.ctx.current_collection, ids=ids_to_delete)
            if success:
                # Invalidate cache after deletion
                if self.ctx.current_database and self.ctx.current_collection:
                    self.ctx.cache_manager.invalidate(self.ctx.current_database, self.ctx.current_collection)
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
            self.ctx.cache_manager.invalidate(self.ctx.current_database, self.ctx.current_collection)
        self.ctx.current_page = 0
        self._load_data()

    def _on_row_double_clicked(self, index: Any) -> None:
        """Handle double-click on a row to view item details."""
        if not self.ctx.connection:
            QMessageBox.warning(self, "No Connection", "No database connection available.")
            return

        if not self.ctx.current_collection or not self.ctx.current_data:
            return

        row = index.row()
        if row < 0 or row >= self.table.rowCount():
            return

        # Show read-only details dialog (same as right-click -> View Details)
        _show_item_details(self.table, self.ctx, row)

    def _edit_item(self, index: Any) -> None:
        """Handle editing an item (called from context menu)."""
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

            # Inject updated_at timestamp if checkbox is enabled
            auto_timestamp = updated_data.pop("auto_timestamp", True)
            if auto_timestamp:
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

                existing_embs = self.ctx.current_data.get("embeddings", []) if self.ctx.current_data else []
                if row < len(existing_embs):
                    existing = existing_embs[row]
                    if has_embedding(existing):
                        embeddings_arg = [existing]

            # Show loading dialog during update
            self.loading_dialog.show_loading("Updating item...")

            # Use TaskRunner if available, otherwise fall back to legacy threading
            if self.task_runner:
                self.task_runner.run_task(
                    lambda: update_collection_item(
                        self.ctx.connection,
                        self.ctx.current_collection,
                        updated_data,
                        embeddings_arg,
                    ),
                    on_finished=self._on_item_update_finished,
                    on_error=self._on_item_update_error,
                )
            else:
                # Legacy path for backward compatibility
                from vector_inspector.ui.views.metadata import ItemUpdateThread

                update_thread = ItemUpdateThread(
                    self.ctx.connection,
                    self.ctx.current_collection,
                    updated_data,
                    embeddings_arg,
                    parent=self,
                )
                update_thread.finished.connect(self._on_item_update_finished)
                update_thread.error.connect(self._on_item_update_error)
                update_thread.start()

    def _on_item_update_finished(self, updated_data: dict[str, Any]) -> None:
        """Handle successful item update."""
        self.loading_dialog.hide_loading()

        try:
            generate_on_edit = bool(self.generate_on_edit_checkbox.isChecked())
        except Exception:
            generate_on_edit = False

        process_item_update_success(
            updated_data,
            self.ctx,
            self,
            generate_on_edit,
        )

    def _on_item_update_error(self, error_message: str) -> None:
        """Handle item update error."""
        self.loading_dialog.hide_loading()
        QMessageBox.warning(self, "Update Error", f"Failed to update item: {error_message}")

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

    def _on_selection_changed(self) -> None:
        """Handle table selection changes to update inline details pane."""
        selected_rows = self.table.selectionModel().selectedRows()

        if not selected_rows or not self.ctx.current_data:
            self.details_pane.update_item(None)
            return

        row = selected_rows[0].row()
        if row < 0 or row >= self.table.rowCount() or row >= len(self.ctx.current_data.get("ids", [])):
            return

        # Get item data for this row
        item_data = {
            "id": self.ctx.current_data["ids"][row],
            "document": self.ctx.current_data.get("documents", [])[row]
            if row < len(self.ctx.current_data.get("documents", []))
            else "",
            "metadata": self.ctx.current_data.get("metadatas", [])[row]
            if row < len(self.ctx.current_data.get("metadatas", []))
            else {},
            "embedding": self.ctx.current_data.get("embeddings", [])[row]
            if row < len(self.ctx.current_data.get("embeddings", []))
            else None,
        }
        self.details_pane.update_item(item_data)

    def _show_context_menu(self, position: Any) -> None:
        """Show context menu for table rows."""
        show_context_menu(
            self.table,
            position,
            self.ctx,
            self._edit_item,
        )

    def _import_data(self, format_type: str) -> None:
        """Import data from file into collection."""
        from vector_inspector.ui.views.metadata.import_export_helpers import start_import

        start_import(
            self,
            self.ctx,
            format_type,
            self.settings_service,
            self.loading_dialog,
            "import_thread",
            self._on_import_finished,
            self._on_import_error,
            self._on_import_progress,
        )

    def _on_import_progress(self, message: str) -> None:
        """Handle import progress update."""
        self.loading_dialog.setLabelText(message)

    def _on_import_finished(self, imported_data: dict, item_count: int, file_path: str) -> None:
        """Handle import completion."""
        from vector_inspector.ui.views.metadata.import_export_helpers import on_import_finished

        on_import_finished(
            self,
            self.ctx,
            self.settings_service,
            self.loading_dialog,
            self._load_data,
            imported_data,
            item_count,
            file_path,
        )

    def _on_import_error(self, error_message: str) -> None:
        """Handle import error."""
        from vector_inspector.ui.views.metadata.import_export_helpers import on_import_error

        on_import_error(self.loading_dialog, self, error_message)

    def closeEvent(self, event):
        """Save state before closing."""
        if hasattr(self, "details_pane"):
            self.details_pane.save_state()
        super().closeEvent(event)
