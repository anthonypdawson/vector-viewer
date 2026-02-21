"""
Demo view showcasing the new AppState + Services architecture pattern.

This is a working example of how to build UI views using:
- AppState for centralized state management
- ThreadedTaskRunner for background operations
- Service modules for business logic
- Reactive signal-based UI updates

Use this as a template for refactoring other views.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.services import (
    CollectionLoader,
    MetadataLoader,
    ThreadedTaskRunner,
)
from vector_inspector.state import AppState
from vector_inspector.ui.components.loading_dialog import LoadingDialog


class DemoCollectionView(QWidget):
    """
    Demo view showing AppState + Services pattern.

    This view demonstrates:
    - AppState for state management (no local state variables)
    - ThreadedTaskRunner for background tasks (no custom QThread classes)
    - Service modules for business logic (CollectionLoader, MetadataLoader)
    - Reactive UI updates via signal subscriptions
    - Separation of concerns (thin UI, testable services)

    Services used:
        - CollectionLoader: Loads collection data
        - MetadataLoader: Loads metadata details

    AppState subscriptions:
        - provider_changed: Updates services with new connection
        - collection_changed: Loads new collection data
        - vectors_loaded: Updates table display
        - loading_started/finished: Shows/hides loading dialog
        - error_occurred: Displays errors

    Usage:
        app_state = AppState()
        task_runner = ThreadedTaskRunner()
        view = DemoCollectionView(app_state, task_runner)
    """

    def __init__(
        self, app_state: AppState, task_runner: ThreadedTaskRunner, parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize demo collection view.

        Args:
            app_state: Shared application state
            task_runner: Shared task runner for background operations
            parent: Parent widget
        """
        super().__init__(parent)

        # Injected dependencies (no local state!)
        self.app_state = app_state
        self.task_runner = task_runner

        # Services (no connection passed, they get it from app_state)
        self.collection_loader = CollectionLoader()
        self.metadata_loader = MetadataLoader()

        # UI-only components
        self.loading_dialog = LoadingDialog("Loading...", self)

        # UI widgets (to be created)
        self.status_label: QLabel = None
        self.load_button: QPushButton = None
        self.table: QTableWidget = None

        # Setup
        self._setup_ui()
        self._connect_state_signals()

        # Update services with current connection if available
        if self.app_state.provider:
            self._on_provider_changed(self.app_state.provider)
        else:
            # No provider - ensure button is disabled
            self.load_button.setEnabled(False)

    def _setup_ui(self) -> None:
        """Setup widget UI (pure UI construction, no logic)."""
        layout = QVBoxLayout(self)

        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.load_button = QPushButton("Load Collection Data")
        self.load_button.clicked.connect(self._load_data)
        status_layout.addWidget(self.load_button)

        layout.addLayout(status_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Metadata", "Document"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    def _connect_state_signals(self) -> None:
        """Subscribe to AppState changes (declarative reactivity)."""
        # React to connection changes
        self.app_state.provider_changed.connect(self._on_provider_changed)

        # React to collection changes
        self.app_state.collection_changed.connect(self._on_collection_changed)

        # React to data loads
        self.app_state.vectors_loaded.connect(self._on_data_loaded)

        # React to loading state
        self.app_state.loading_started.connect(self._on_loading_started)
        self.app_state.loading_finished.connect(self._on_loading_finished)

        # React to errors
        self.app_state.error_occurred.connect(self._on_error)

    # Signal handlers (reactive UI updates)

    def _on_provider_changed(self, connection) -> None:
        """
        React to provider/connection change.

        Updates services with new connection and clears UI.
        """
        # Update services
        self.collection_loader.set_connection(connection)
        self.metadata_loader.set_connection(connection)

        # Clear UI
        self.table.setRowCount(0)

        # Update status
        if connection:
            self.status_label.setText("Connected - select a collection to load data")
            self.load_button.setEnabled(True)
        else:
            self.status_label.setText("No connection")
            self.load_button.setEnabled(False)

    def _on_collection_changed(self, collection: str) -> None:
        """
        React to collection change.

        Automatically loads data when collection changes.
        """
        if collection:
            self.status_label.setText(f"Collection: {collection}")
            # Auto-load when collection changes
            self._load_data()
        else:
            self.status_label.setText("No collection selected")

    def _on_data_loaded(self, data: dict) -> None:
        """
        React to data being loaded (pure UI update).

        This is called when app_state.set_data() is called,
        either from our load or from another view.
        """
        # Pure UI update - populate table with data
        self._populate_table(data)

        # Update status
        count = len(data.get("ids", []))
        self.status_label.setText(f"Loaded {count} items")

    def _on_loading_started(self, message: str) -> None:
        """React to loading started."""
        self.loading_dialog.show_loading(message)
        self.load_button.setEnabled(False)

    def _on_loading_finished(self) -> None:
        """React to loading finished."""
        self.loading_dialog.hide()
        self.load_button.setEnabled(True)

    def _on_error(self, title: str, message: str) -> None:
        """React to error."""
        QMessageBox.critical(self, title, message)

    # Actions (delegate to services)

    def _load_data(self) -> None:
        """
        Load collection data (delegates to service).

        This demonstrates the pattern:
        1. UI initiates action
        2. TaskRunner runs service method in background
        3. On success, update AppState (triggers UI update via signal)
        4. On error, emit error via AppState
        """
        collection = self.app_state.collection
        if not collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first")
            return

        # Signal loading started
        self.app_state.start_loading(f"Loading {collection}...")

        # Run load task in background
        self.task_runner.run_task(
            self.collection_loader.load_all,
            collection,
            limit=100,  # Limit for demo
            on_finished=self._on_load_complete,
            on_error=self._on_load_failed,
            task_id=f"demo_load_{collection}",
        )

    def _on_load_complete(self, data: dict) -> None:
        """
        Handle successful load.

        Updates AppState, which triggers _on_data_loaded via signal.
        """
        # Update state (emits vectors_loaded signal)
        self.app_state.set_data(data)

        # Signal loading finished
        self.app_state.finish_loading()

    def _on_load_failed(self, error: str) -> None:
        """Handle load failure."""
        self.app_state.finish_loading()
        self.app_state.emit_error("Load Error", f"Failed to load data: {error}")

    # Pure UI methods (no business logic, no state changes)

    def _populate_table(self, data: dict) -> None:
        """
        Populate table with data (pure UI rendering).

        No state changes, no business logic - just render data.
        """
        ids = data.get("ids", [])
        metadatas = data.get("metadatas", [])
        documents = data.get("documents", [])

        self.table.setRowCount(len(ids))

        for row, item_id in enumerate(ids):
            # ID column
            id_item = QTableWidgetItem(str(item_id))
            id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, id_item)

            # Metadata column
            metadata = metadatas[row] if row < len(metadatas) else {}
            metadata_str = str(metadata) if metadata else ""
            metadata_item = QTableWidgetItem(
                metadata_str[:50] + "..." if len(metadata_str) > 50 else metadata_str
            )
            metadata_item.setFlags(metadata_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, metadata_item)

            # Document column
            document = documents[row] if row < len(documents) else ""
            doc_str = str(document) if document else ""
            doc_item = QTableWidgetItem(doc_str[:100] + "..." if len(doc_str) > 100 else doc_str)
            doc_item.setFlags(doc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, doc_item)

        self.table.resizeColumnsToContents()
