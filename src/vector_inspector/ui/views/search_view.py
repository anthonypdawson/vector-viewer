"""Search interface for similarity queries."""

from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QSplitter,
    QCheckBox,
    QApplication,
)
from PySide6.QtCore import Qt

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.ui.components.filter_builder import FilterBuilder
from vector_inspector.ui.components.loading_dialog import LoadingDialog
from vector_inspector.services.filter_service import apply_client_side_filters
from vector_inspector.core.cache_manager import get_cache_manager, CacheEntry
from vector_inspector.core.logging import log_info


class SearchView(QWidget):
    """View for performing similarity searches."""

    def __init__(self, connection: VectorDBConnection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.current_collection: str = ""
        self.current_database: str = ""
        self.search_results: Optional[Dict[str, Any]] = None
        self.loading_dialog = LoadingDialog("Searching...", self)
        self.cache_manager = get_cache_manager()

        self._setup_ui()

    def _setup_ui(self):
        """Setup widget UI."""
        layout = QVBoxLayout(self)

        # Create splitter for query and results
        splitter = QSplitter(Qt.Vertical)

        # Query section
        query_widget = QWidget()
        query_layout = QVBoxLayout(query_widget)

        query_group = QGroupBox("Search Query")
        query_group_layout = QVBoxLayout()

        # Query input
        query_group_layout.addWidget(QLabel("Enter search text:"))
        self.query_input = QTextEdit()
        self.query_input.setMaximumHeight(100)
        self.query_input.setPlaceholderText("Enter text to search for similar vectors...")
        query_group_layout.addWidget(self.query_input)

        # Search controls
        controls_layout = QHBoxLayout()

        controls_layout.addWidget(QLabel("Results:"))
        self.n_results_spin = QSpinBox()
        self.n_results_spin.setMinimum(1)
        self.n_results_spin.setMaximum(100)
        self.n_results_spin.setValue(10)
        controls_layout.addWidget(self.n_results_spin)

        controls_layout.addStretch()

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._perform_search)
        self.search_button.setDefault(True)
        controls_layout.addWidget(self.search_button)

        query_group_layout.addLayout(controls_layout)
        query_group.setLayout(query_group_layout)
        query_layout.addWidget(query_group)

        # Advanced filters section
        filter_group = QGroupBox("Advanced Metadata Filters")
        filter_group.setCheckable(True)
        filter_group.setChecked(False)
        filter_group_layout = QVBoxLayout()

        # Filter builder
        self.filter_builder = FilterBuilder()
        filter_group_layout.addWidget(self.filter_builder)

        filter_group.setLayout(filter_group_layout)
        query_layout.addWidget(filter_group)
        self.filter_group = filter_group

        splitter.addWidget(query_widget)

        # Results section
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)

        results_group = QGroupBox("Search Results")
        results_group_layout = QVBoxLayout()

        self.results_table = QTableWidget()
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        results_group_layout.addWidget(self.results_table)

        self.results_status = QLabel("No search performed")
        self.results_status.setStyleSheet("color: gray;")
        results_group_layout.addWidget(self.results_status)

        results_group.setLayout(results_group_layout)
        results_layout.addWidget(results_group)

        splitter.addWidget(results_widget)

        # Set splitter proportions
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

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

        # Show loading indicator
        self.loading_dialog.show_loading("Searching for similar vectors...")
        QApplication.processEvents()

        try:
            # Always pass query_texts; provider handles embedding if needed
            results = self.connection.query_collection(
                self.current_collection,
                query_texts=[query_text],
                n_results=n_results,
                where=server_filter,
            )
        finally:
            self.loading_dialog.hide_loading()

        if not results:
            self.results_status.setText("Search failed")
            self.results_table.setRowCount(0)
            return

        # Check if results have the expected structure
        if (
            not results.get("ids")
            or not isinstance(results["ids"], list)
            or len(results["ids"]) == 0
        ):
            self.results_status.setText("No results found or query failed")
            self.results_table.setRowCount(0)
            return

        # Apply client-side filters if any
        if client_filters and results:
            # Restructure results for filtering
            filter_data = {
                "ids": results.get("ids", [[]])[0],
                "documents": results.get("documents", [[]])[0],
                "metadatas": results.get("metadatas", [[]])[0],
            }
            filtered = apply_client_side_filters(filter_data, client_filters)

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
                search_query=query_text,
                search_results=results,
                user_inputs={
                    "n_results": n_results,
                    "filters": self.filter_builder.to_dict()
                    if hasattr(self.filter_builder, "to_dict")
                    else {},
                },
            )

    def _display_results(self, results: Dict[str, Any]):
        """Display search results in table."""
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not ids:
            self.results_table.setRowCount(0)
            self.results_status.setText("No results found")
            return

        # Determine columns
        columns = ["Rank", "Distance", "ID", "Document"]
        if metadatas and metadatas[0]:
            metadata_keys = list(metadatas[0].keys())
            columns.extend(metadata_keys)

        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setRowCount(len(ids))

        # Populate rows
        for row, (id_val, doc, meta, dist) in enumerate(zip(ids, documents, metadatas, distances)):
            # Rank
            self.results_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))

            # Distance/similarity score
            self.results_table.setItem(row, 1, QTableWidgetItem(f"{dist:.4f}"))

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
