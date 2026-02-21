"""Search interface for similarity queries."""

import json
import time
import uuid
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.connection_manager import ConnectionInstance
from vector_inspector.core.logging import log_info
from vector_inspector.services import SearchRunner, ThreadedTaskRunner
from vector_inspector.services.filter_service import apply_client_side_filters
from vector_inspector.services.telemetry_service import TelemetryService
from vector_inspector.state import AppState
from vector_inspector.ui.components.filter_builder import FilterBuilder
from vector_inspector.ui.components.inline_details_pane import InlineDetailsPane
from vector_inspector.ui.components.item_details_dialog import ItemDetailsDialog
from vector_inspector.ui.components.loading_dialog import LoadingDialog
from vector_inspector.ui.views.search_threads import SearchThread


class SearchView(QWidget):
    """View for performing similarity searches."""

    app_state: AppState
    task_runner: ThreadedTaskRunner
    search_runner: SearchRunner
    breadcrumb_label: QLabel
    query_input: QTextEdit
    results_table: QTableWidget
    results_status: QLabel
    refresh_button: QPushButton
    n_results_spin: QSpinBox
    filter_builder: FilterBuilder
    filter_group: QGroupBox
    search_button: QPushButton
    loading_dialog: LoadingDialog
    search_thread: Optional[Any]
    cache_manager: Any
    connection: Optional[ConnectionInstance]
    current_collection: str
    current_database: str
    search_results: Optional[dict[str, Any]]
    _full_breadcrumb: str
    _elide_mode: str

    def __init__(
        self,
        app_state: AppState,
        task_runner: ThreadedTaskRunner,
        parent=None,
    ):
        super().__init__(parent)

        # Store AppState and task runner
        self.app_state = app_state
        self.task_runner = task_runner
        self.search_runner = SearchRunner()
        self.connection = self.app_state.provider
        self.cache_manager = self.app_state.cache_manager

        self.current_collection = ""
        self.current_database = ""
        self.search_results = None
        self.loading_dialog = LoadingDialog("Searching...", self)
        self.search_thread = None

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
        self.search_runner.set_connection(connection)

        # Update connection
        self.connection = connection

        # Clear results
        self.results_table.setRowCount(0)
        self.results_status.setText("No search performed" if not connection else "Connected - enter query")

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

    def _setup_ui(self):
        """Setup widget UI."""
        # Assign all UI attributes at the top to avoid NoneType errors
        self.breadcrumb_label = QLabel("")
        self.query_input = QTextEdit()
        self.results_table = QTableWidget()
        self.results_status = QLabel("No search performed")
        self.refresh_button = QPushButton("Refresh")
        self.n_results_spin = QSpinBox()
        self.filter_builder = FilterBuilder()
        self.filter_group = QGroupBox("Advanced Metadata Filters")
        self.search_button = QPushButton("Search")

        layout = QVBoxLayout(self)

        # Breadcrumb bar (for pro features)
        self.breadcrumb_label.setStyleSheet("color: #2980b9; font-weight: bold; padding: 2px 0 4px 0;")
        # Configure breadcrumb label sizing
        self.breadcrumb_label.setWordWrap(False)
        self.breadcrumb_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Store full breadcrumb text for tooltip and eliding
        self._full_breadcrumb = ""
        # Elide mode: 'left' or 'middle'
        self._elide_mode = "left"
        layout.addWidget(self.breadcrumb_label)

        # Create splitter for query and results
        splitter = QSplitter(Qt.Vertical)

        # Query section
        query_widget = QWidget()
        query_layout = QVBoxLayout(query_widget)

        query_group = QGroupBox("Search Query")
        query_group_layout = QVBoxLayout()

        # Query input
        query_group_layout.addWidget(QLabel("Enter search text:"))
        self.query_input.setMaximumHeight(60)
        self.query_input.setPlaceholderText("Enter text to search for similar vectors...")
        query_group_layout.addWidget(self.query_input)

        # Search controls
        controls_layout = QHBoxLayout()

        controls_layout.addWidget(QLabel("Results:"))
        self.n_results_spin.setMinimum(1)
        self.n_results_spin.setMaximum(100)
        self.n_results_spin.setValue(10)
        controls_layout.addWidget(self.n_results_spin)

        controls_layout.addStretch()

        self.search_button.clicked.connect(self._perform_search)
        self.search_button.setDefault(True)

        self.refresh_button.setToolTip("Reset search input and results")
        self.refresh_button.clicked.connect(self._refresh_search)
        controls_layout.addWidget(self.refresh_button)

        controls_layout.addWidget(self.search_button)

        query_group_layout.addLayout(controls_layout)
        query_group.setLayout(query_group_layout)
        query_layout.addWidget(query_group)

        # Advanced filters section
        self.filter_group.setCheckable(True)
        self.filter_group.setChecked(False)
        filter_group_layout = QVBoxLayout()

        # Filter builder (already created at top)
        filter_group_layout.addWidget(self.filter_builder)

        self.filter_group.setLayout(filter_group_layout)
        # Hide content when unchecked, show when checked
        self.filter_group.toggled.connect(self.filter_builder.setVisible)
        self.filter_builder.setVisible(False)  # Start not visible
        query_layout.addWidget(self.filter_group)

        # Add stretch to push content to top
        query_layout.addStretch()

        splitter.addWidget(query_widget)

        # Results section
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)

        # Create sub-splitter for results table and details pane
        results_splitter = QSplitter(Qt.Vertical)

        # Results table container
        results_table_widget = QWidget()
        results_table_layout = QVBoxLayout(results_table_widget)
        results_table_layout.setContentsMargins(0, 0, 0, 0)

        results_group = QGroupBox("Search Results")
        results_group_layout = QVBoxLayout()

        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.horizontalHeader().setSectionsMovable(True)  # Allow column reordering
        # Enable context menu
        self.results_table.setContextMenuPolicy(Qt.CustomContextMenu)
        # Enable double-click to view details
        self.results_table.doubleClicked.connect(self._on_row_double_clicked)
        self.results_table.customContextMenuRequested.connect(self._show_context_menu)
        # Connect selection changes to update inline details
        self.results_table.itemSelectionChanged.connect(self._on_selection_changed)
        results_group_layout.addWidget(self.results_table)

        self.results_status.setStyleSheet("color: gray;")
        results_group_layout.addWidget(self.results_status)

        results_group.setLayout(results_group_layout)
        results_table_layout.addWidget(results_group)
        results_splitter.addWidget(results_table_widget)

        # Inline details pane
        self.details_pane = InlineDetailsPane(view_mode="search")
        self.details_pane.open_full_details.connect(self._open_full_details_from_pane)
        self.details_pane.setMinimumHeight(120)
        results_splitter.addWidget(self.details_pane)

        # Set initial sizes for results splitter
        results_splitter.setStretchFactor(0, 3)  # Table
        results_splitter.setStretchFactor(1, 1)  # Details pane

        # Restore splitter sizes from settings
        from vector_inspector.services.settings_service import SettingsService

        settings_service = SettingsService()
        saved_sizes = settings_service.get("search_view_results_splitter_sizes", [])
        if saved_sizes and len(saved_sizes) == 2:
            results_splitter.setSizes(saved_sizes)

        # Save splitter sizes when changed
        results_splitter.splitterMoved.connect(
            lambda: self._save_results_splitter_sizes(results_splitter, settings_service)
        )
        self.results_splitter = results_splitter

        results_layout.addWidget(results_splitter)
        splitter.addWidget(results_widget)

        # Set splitter proportions
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)
        self.setLayout(layout)

    def set_breadcrumb(self, text: str):
        """Set the breadcrumb indicator (for pro features)."""
        # Keep the full breadcrumb for tooltip and compute an elided
        # display that fits the current label width (elide from the left).
        self._full_breadcrumb = text or ""
        self.breadcrumb_label.setToolTip(self._full_breadcrumb)
        self._update_breadcrumb_display()

    def _update_breadcrumb_display(self):
        """Compute and apply an elided breadcrumb display based on label width."""
        if not hasattr(self, "breadcrumb_label") or self.breadcrumb_label is None:
            return

        fm = QFontMetrics(self.breadcrumb_label.font())
        avail_width = max(10, self.breadcrumb_label.width())
        if not self._full_breadcrumb:
            self.breadcrumb_label.setText("")
            return

        # Choose elide mode from settings
        elide_flag = Qt.ElideLeft if self._elide_mode == "left" else Qt.ElideMiddle
        elided = fm.elidedText(self._full_breadcrumb, elide_flag, avail_width)
        self.breadcrumb_label.setText(elided)

    def set_elide_mode(self, mode: str):
        """Set elide mode ('left' or 'middle') and refresh display."""
        if mode not in ("left", "middle"):
            mode = "left"
        self._elide_mode = mode
        self._update_breadcrumb_display()

    def resizeEvent(self, event):
        """Handle resize to recompute breadcrumb eliding."""
        try:
            super().resizeEvent(event)
        finally:
            self._update_breadcrumb_display()

    def clear_breadcrumb(self):
        """Clear the breadcrumb indicator."""
        self.breadcrumb_label.setText("")

    def _refresh_search(self):
        """Reset search input, results, and breadcrumb."""
        self.query_input.clear()
        self.results_table.setRowCount(0)
        self.results_status.setText("No search performed")
        self.clear_breadcrumb()
        self.search_results = None
        if hasattr(self, "details_pane"):
            self.details_pane.update_item(None)

    def set_collection(self, collection_name: str, database_name: str = ""):
        """Set the current collection to search."""
        self.current_collection = collection_name
        # Always update database_name if provided (even if empty string on first call)
        if database_name:  # Only update if non-empty
            self.current_database = database_name

        log_info(
            "[SearchView] Setting collection: db='%s', coll='%s'",
            self.current_database,
            collection_name,
        )

        # Guard: if results_table is not yet initialized, do nothing
        if self.results_table is None:
            log_info("[SearchView] set_collection called before UI setup; skipping.")
            return

        # Check cache first
        cached = self.cache_manager.get(self.current_database, self.current_collection)
        if cached:
            log_info("[SearchView] ✓ Cache HIT! Restoring search state.")
            # Restore search query and results from cache
            if cached.search_query:
                self.query_input.setPlainText(cached.search_query)
            if cached.search_results:
                self.search_results = cached.search_results
                self._display_results(cached.search_results)
                return

        log_info("[SearchView] ✗ Cache MISS or no cached search.")
        # Not in cache, clear form
        self.search_results = None
        self.query_input.clear()
        self.results_table.setRowCount(0)
        self.results_status.setText(f"Collection: {collection_name}")
        if hasattr(self, "details_pane"):
            self.details_pane.update_item(None)

        # Reset filters
        self.filter_builder._clear_all()
        self.filter_group.setChecked(False)

        # Update filter builder with supported operators
        operators = self.connection.get_supported_filter_operators()
        self.filter_builder.set_operators(operators)

        # Load metadata fields immediately (even if tab is not visible)
        self._load_metadata_fields()

    def _load_metadata_fields(self):
        """Load metadata field names from collection for filter builder."""
        if not self.current_collection:
            return

        try:
            # Get a small sample to extract field names
            sample_data = self.connection.get_all_items(self.current_collection, limit=1)

            if sample_data and sample_data.get("metadatas"):
                metadatas = sample_data["metadatas"]
                if metadatas and len(metadatas) > 0 and metadatas[0]:
                    field_names = sorted(metadatas[0].keys())
                    self.filter_builder.set_available_fields(field_names)
        except Exception as e:
            # Silently ignore errors - fields can still be typed manually
            log_info("Note: Could not auto-populate filter fields: %s", e)

    def _perform_search(self):
        """Perform similarity search."""
        if not self.current_collection:
            self.results_status.setText("No collection selected")
            return

        query_text = self.query_input.toPlainText().strip()
        if not query_text:
            self.results_status.setText("Please enter search text")
            return

        n_results = self.n_results_spin.value()

        # Get filters split into server-side and client-side
        server_filter = None
        client_filters = []
        if self.filter_group.isChecked() and self.filter_builder.has_filters():
            server_filter, client_filters = self.filter_builder.get_filters_split()
            if server_filter or client_filters:
                filter_summary = self.filter_builder.get_filter_summary()
                self.results_status.setText(f"Searching with filters: {filter_summary}")

        # Store search context for use in handlers
        self._search_client_filters = client_filters
        self._search_correlation_id = str(uuid.uuid4())
        self._search_start_time = time.time()
        self._search_server_filter = server_filter
        self._search_n_results = n_results
        self._search_query_text = query_text

        # Cancel any existing search thread
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.quit()
            self.search_thread.wait()

        # Create and start search thread
        self.search_thread = SearchThread(
            self.connection,
            self.current_collection,
            query_text,
            n_results,
            server_filter,
            parent=self,
        )
        self.search_thread.finished.connect(self._on_search_finished)
        self.search_thread.error.connect(self._on_search_error)

        # Show loading indicator and run in background thread
        self.loading_dialog.show_loading("Searching for similar vectors...")
        self.search_thread.start()

    def _on_search_finished(self, results: dict[str, Any]) -> None:
        """Handle successful search completion."""
        self.loading_dialog.hide_loading()

        # Calculate duration and send telemetry
        duration_ms = int((time.time() - self._search_start_time) * 1000)
        result_count = 0

        try:
            provider_type = (
                type(self.connection._connection).__name__.replace("Connection", "").lower()
                if hasattr(self.connection, "_connection")
                else "unknown"
            )
            if results and results.get("ids") and len(results["ids"]) > 0:
                result_count = len(results["ids"][0])

            telemetry = TelemetryService()
            telemetry.queue_event(
                {
                    "event_name": "query.executed",
                    "metadata": {
                        "query_type": "similarity",
                        "db_type": provider_type,
                        "result_count": result_count,
                        "latency_ms": duration_ms,
                        "correlation_id": self._search_correlation_id,
                        "has_filters": bool(self._search_server_filter or self._search_client_filters),
                        "success": True,
                    },
                }
            )
            telemetry.send_batch()
        except Exception:
            pass  # Best effort telemetry

        # Check if results have the expected structure
        if not results.get("ids") or not isinstance(results["ids"], list) or len(results["ids"]) == 0:
            self.results_status.setText("No results found or query failed")
            self.results_table.setRowCount(0)
            if hasattr(self, "details_pane"):
                self.details_pane.update_item(None)
            return

        # Apply client-side filters if any
        if self._search_client_filters and results:
            # Restructure results for filtering
            filter_data = {
                "ids": results.get("ids", [[]])[0],
                "documents": results.get("documents", [[]])[0],
                "metadatas": results.get("metadatas", [[]])[0],
            }
            filtered = apply_client_side_filters(filter_data, self._search_client_filters)

            # Restructure back to query results format
            results = {
                "ids": [filtered["ids"]],
                "documents": [filtered["documents"]],
                "metadatas": [filtered["metadatas"]],
                "distances": [
                    [
                        results.get("distances", [[]])[0][i]
                        for i, orig_id in enumerate(results.get("ids", [[]])[0])
                        if orig_id in filtered["ids"]
                    ]
                ],
            }

        self.search_results = results
        self._display_results(results)

        # Save to cache
        if self.current_database and self.current_collection:
            self.cache_manager.update(
                self.current_database,
                self.current_collection,
                search_query=self._search_query_text,
                search_results=results,
                user_inputs={
                    "n_results": self._search_n_results,
                    "filters": self.filter_builder.to_dict() if hasattr(self.filter_builder, "to_dict") else {},
                },
            )

    def _on_search_error(self, error_message: str) -> None:
        """Handle search error."""
        self.loading_dialog.hide_loading()

        # Send telemetry for failed search
        duration_ms = int((time.time() - self._search_start_time) * 1000)
        try:
            provider_type = (
                type(self.connection._connection).__name__.replace("Connection", "").lower()
                if hasattr(self.connection, "_connection")
                else "unknown"
            )

            telemetry = TelemetryService()
            telemetry.queue_event(
                {
                    "event_name": "query.executed",
                    "metadata": {
                        "query_type": "similarity",
                        "db_type": provider_type,
                        "result_count": 0,
                        "latency_ms": duration_ms,
                        "correlation_id": self._search_correlation_id,
                        "has_filters": bool(self._search_server_filter or self._search_client_filters),
                        "success": False,
                    },
                }
            )
            telemetry.send_batch()
        except Exception:
            pass  # Best effort telemetry

        self.results_status.setText(f"Search failed: {error_message}")
        self.results_table.setRowCount(0)
        if hasattr(self, "details_pane"):
            self.details_pane.update_item(None)

    def _on_row_double_clicked(self, index):
        """Handle double-click on a row to view item details."""
        if not self.search_results:
            return

        row = index.row()
        if row < 0 or row >= self.results_table.rowCount():
            return

        # Get item data for this row
        ids = self._unwrap_result_list("ids")
        documents = self._unwrap_result_list("documents")
        metadatas = self._unwrap_result_list("metadatas")
        distances = self._unwrap_result_list("distances")

        if row >= len(ids):
            return

        item_data = {
            "id": ids[row],
            "document": documents[row] if row < len(documents) else "",
            "metadata": metadatas[row] if row < len(metadatas) else {},
            "distance": distances[row] if row < len(distances) else None,
            "rank": row + 1,
        }

        # Show details dialog
        dialog = ItemDetailsDialog(self, item_data=item_data, show_search_info=True)
        dialog.exec()

    def _on_selection_changed(self):
        """Handle table selection changes to update inline details pane."""
        selected_rows = self.results_table.selectionModel().selectedRows()

        if not selected_rows or not self.search_results:
            self.details_pane.update_item(None)
            return

        row = selected_rows[0].row()
        if row < 0 or row >= self.results_table.rowCount():
            return

        # Get item data for this row
        ids = self._unwrap_result_list("ids")
        documents = self._unwrap_result_list("documents")
        metadatas = self._unwrap_result_list("metadatas")
        distances = self._unwrap_result_list("distances")
        embeddings = self._unwrap_result_list("embeddings")

        if row >= len(ids):
            return

        item_data = {
            "id": ids[row],
            "document": documents[row] if row < len(documents) else "",
            "metadata": metadatas[row] if row < len(metadatas) else {},
            "embedding": embeddings[row] if row < len(embeddings) else None,
            "distance": distances[row] if row < len(distances) else None,
            "rank": row + 1,
        }

        self.details_pane.update_item(item_data)

    def _open_full_details_from_pane(self):
        """Open full details dialog for currently selected row."""
        selected_rows = self.results_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            self._on_row_double_clicked(self.results_table.model().index(row, 0))

    def _save_results_splitter_sizes(self, splitter: QSplitter, settings_service):
        """Save results splitter sizes to settings."""
        sizes = splitter.sizes()
        settings_service.set("search_view_results_splitter_sizes", sizes)

    def _unwrap_result_list(self, key: str) -> list:
        """Safely unwrap nested result lists."""
        if not self.search_results:
            return []
        val = self.search_results.get(key)
        if not val:
            return []
        # If provider returned a list-of-lists (per-query), take first inner list
        if isinstance(val, list) and len(val) > 0:
            first = val[0]
            if isinstance(first, (list, tuple)):
                return list(first)
            # If it's already a flat list, return it
            return val
        return []

    def _copy_vectors_to_json(self, selected_rows: list[int]):
        """Copy vector(s) from selected row(s) to clipboard as JSON."""
        if not self.search_results:
            QMessageBox.warning(
                self,
                "No Vector Data",
                "No vector embeddings available for the selected row(s).",
            )
            return

        # Search results typically don't include embeddings
        # So we need to get them from the connection
        ids = self._unwrap_result_list("ids")

        if not ids:
            QMessageBox.warning(
                self,
                "No Data",
                "No search results available.",
            )
            return

        # Collect vectors for selected rows
        vectors_data = []
        for row in selected_rows:
            if row < len(ids):
                item_id = ids[row]

                # Try to get the full item with embedding from the collection
                try:
                    item_data = self.connection.get_all_items(
                        self.current_collection,
                        ids=[item_id],
                        include=["embeddings", "documents"],
                    )

                    if item_data and item_data.get("embeddings") and len(item_data["embeddings"]) > 0:
                        vector = item_data["embeddings"][0]
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
            QMessageBox.information(
                self,
                "No Vectors",
                "Could not retrieve vector embeddings for the selected item(s). "
                "Some vector databases may not return embeddings in search results.",
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
                self,
                "Success",
                f"Copied {count} {item_text} to clipboard as JSON.",
            )
        except Exception as e:
            log_info("Error copying vectors to JSON: %s", e)
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to copy vector data: {e}",
            )

    def _show_context_menu(self, position):
        """Show context menu for results table rows."""
        # Get the item at the position
        item = self.results_table.itemAt(position)
        if not item:
            return

        row = item.row()
        if row < 0 or row >= self.results_table.rowCount():
            return

        # Create context menu
        menu = QMenu(self)

        # Add standard "View Details" action
        view_action = menu.addAction("👁️ View Details")
        view_action.triggered.connect(lambda: self._on_row_double_clicked(self.results_table.model().index(row, 0)))

        # Add "Copy vector to JSON" action
        selected_rows = [index.row() for index in self.results_table.selectionModel().selectedRows()]
        if not selected_rows:
            selected_rows = [row]

        copy_vector_action = menu.addAction("📋 Copy vector to JSON")
        copy_vector_action.triggered.connect(lambda: self._copy_vectors_to_json(selected_rows))

        # Add separator before extension items
        menu.addSeparator()

        # Call extension hooks to add custom menu items (for Vector Studio, etc.)
        try:
            from vector_inspector.extensions import table_context_menu_hook

            table_context_menu_hook.trigger(
                menu=menu,
                table=self.results_table,
                row=row,
                data={
                    "current_data": self.search_results,
                    "collection_name": self.current_collection,
                    "database_name": self.current_database,
                    "connection": self.connection,
                    "view_type": "search",
                },
            )
        except Exception as e:
            log_info("Extension hook error: %s", e)

        # Only show menu if it has items
        if not menu.isEmpty():
            menu.exec(self.results_table.viewport().mapToGlobal(position))

    def _display_results(self, results: dict[str, Any]):
        """Display search results in table."""

        # Safely unwrap nested result lists (providers may return [] or [[]])
        def _unwrap(key: str) -> list:
            val = results.get(key)
            if not val:
                return []
            # If provider returned a list-of-lists (per-query), take first inner list
            if isinstance(val, list) and len(val) > 0:
                first = val[0]
                if isinstance(first, (list, tuple)):
                    return list(first)
                # If it's already a flat list, return it
                return val
            return []

        ids = _unwrap("ids")
        documents = _unwrap("documents")
        metadatas = _unwrap("metadatas")
        distances = _unwrap("distances")

        if not ids:
            self.results_table.setRowCount(0)
            self.results_status.setText("No results found")
            if hasattr(self, "details_pane"):
                self.details_pane.update_item(None)
            return

        # Determine columns
        columns = ["Rank", "Distance", "ID", "Document"]
        metadata_keys = []
        if metadatas and metadatas[0]:
            metadata_keys = list(metadatas[0].keys())
            columns.extend(metadata_keys)

        # Save current column order (visual indices) before changing column count
        header = self.results_table.horizontalHeader()
        old_column_order: dict[str, int] = {}
        if self.results_table.columnCount() > 0:
            for logical_index in range(self.results_table.columnCount()):
                header_item = self.results_table.horizontalHeaderItem(logical_index)
                if header_item:
                    column_name = header_item.text()
                    visual_index = header.visualIndex(logical_index)
                    old_column_order[column_name] = visual_index

        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)

        # Restore column order if columns match
        if old_column_order:
            # Build mapping of column name to new logical index
            new_logical_indices: dict[str, int] = {}
            for logical_index in range(self.results_table.columnCount()):
                header_item = self.results_table.horizontalHeaderItem(logical_index)
                if header_item:
                    new_logical_indices[header_item.text()] = logical_index

            # Sort columns by their old visual index to restore order
            columns_with_order = []
            for col_name, old_visual in old_column_order.items():
                if col_name in new_logical_indices:
                    columns_with_order.append((col_name, old_visual, new_logical_indices[col_name]))

            # Sort by old visual index
            columns_with_order.sort(key=lambda x: x[1])

            # Move columns to restore order
            for target_visual_index, (col_name, old_visual, logical_index) in enumerate(columns_with_order):
                current_visual = header.visualIndex(logical_index)
                if current_visual != target_visual_index:
                    header.moveSection(current_visual, target_visual_index)

        self.results_table.setRowCount(len(ids))

        # Populate rows
        for row, (id_val, doc, meta, dist) in enumerate(zip(ids, documents, metadatas, distances, strict=True)):
            # Rank
            self.results_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

            # Distance/similarity score
            dist_text = f"{dist:.4f}" if dist is not None else "N/A"
            self.results_table.setItem(row, 1, QTableWidgetItem(dist_text))

            # ID
            self.results_table.setItem(row, 2, QTableWidgetItem(str(id_val)))

            # Document
            doc_text = str(doc) if doc else ""
            if len(doc_text) > 150:
                doc_text = doc_text[:150] + "..."
            self.results_table.setItem(row, 3, QTableWidgetItem(doc_text))

            # Metadata columns
            if meta:
                for col_idx, key in enumerate(metadata_keys, start=4):
                    value = meta.get(key, "")
                    self.results_table.setItem(row, col_idx, QTableWidgetItem(str(value)))

        self.results_table.resizeColumnsToContents()
        self.results_status.setText(f"Found {len(ids)} results")

    def closeEvent(self, event):
        """Save state before closing."""
        if hasattr(self, "details_pane"):
            self.details_pane.save_state()
        super().closeEvent(event)
