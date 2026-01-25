"""Updated main window with multi-database support."""

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTabWidget,
    QStatusBar,
    QToolBar,
    QMessageBox,
    QInputDialog,
    QLabel,
    QDockWidget,
    QApplication,
    QDialog,
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QAction

from vector_inspector.core.connection_manager import ConnectionManager, ConnectionState
from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.connections.chroma_connection import ChromaDBConnection
from vector_inspector.core.connections.qdrant_connection import QdrantConnection
from vector_inspector.core.connections.pinecone_connection import PineconeConnection
from vector_inspector.services.profile_service import ProfileService
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.ui.components.connection_manager_panel import ConnectionManagerPanel
from vector_inspector.ui.components.profile_manager_panel import ProfileManagerPanel
from vector_inspector.ui.views.info_panel import InfoPanel
from vector_inspector.ui.views.metadata_view import MetadataView
from vector_inspector.ui.views.search_view import SearchView
from vector_inspector.ui.components.loading_dialog import LoadingDialog


class ConnectionThread(QThread):
    """Background thread for connecting to database."""

    finished = Signal(bool, list, str)  # success, collections, error_message

    def __init__(self, connection):
        super().__init__()
        self.connection = connection

    def run(self):
        """Connect to database and get collections."""
        try:
            success = self.connection.connect()
            if success:
                collections = self.connection.list_collections()
                self.finished.emit(True, collections, "")
            else:
                self.finished.emit(False, [], "Connection failed")
        except Exception as e:
            self.finished.emit(False, [], str(e))


class MainWindow(QMainWindow):
    """Main application window with multi-database support."""

    def __init__(self):
        super().__init__()

        # Core services
        self.connection_manager = ConnectionManager()
        self.profile_service = ProfileService()
        self.settings_service = SettingsService()
        self.loading_dialog = LoadingDialog("Loading...", self)

        # State
        self.visualization_view = None
        self._connection_threads = {}  # Track connection threads

        self.setWindowTitle("Vector Inspector")
        self.setGeometry(100, 100, 1600, 900)

        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        self._restore_session()

    def _setup_ui(self):
        """Setup the main UI layout."""
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Main splitter (left panel | right tabs)
        main_splitter = QSplitter(Qt.Horizontal)

        # Left panel - Connections and Profiles
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget for connections and profiles
        self.left_tabs = QTabWidget()

        # Connection manager panel
        self.connection_panel = ConnectionManagerPanel(self.connection_manager)
        self.left_tabs.addTab(self.connection_panel, "Active")

        # Profile manager panel
        self.profile_panel = ProfileManagerPanel(self.profile_service)
        self.left_tabs.addTab(self.profile_panel, "Profiles")

        left_layout.addWidget(self.left_tabs)

        # Right panel - Tabbed views
        self.tab_widget = QTabWidget()

        # Create views (they'll be updated when collection changes)
        self.info_panel = InfoPanel(None)  # Will be set later
        self.metadata_view = MetadataView(None)  # Will be set later
        self.search_view = SearchView(None)  # Will be set later

        self.tab_widget.addTab(self.info_panel, "Info")
        self.tab_widget.addTab(self.metadata_view, "Data Browser")
        self.tab_widget.addTab(self.search_view, "Search")
        self.tab_widget.addTab(QWidget(), "Visualization")  # Placeholder

        # Set Info tab as default
        self.tab_widget.setCurrentIndex(0)

        # Connect to tab change to lazy load visualization
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Add panels to splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(self.tab_widget)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 4)

        layout.addWidget(main_splitter)

    def _setup_menu_bar(self):
        """Setup application menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_connection_action = QAction("&New Connection...", self)
        new_connection_action.setShortcut("Ctrl+N")
        new_connection_action.triggered.connect(self._new_connection_from_profile)
        file_menu.addAction(new_connection_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Connection menu
        connection_menu = menubar.addMenu("&Connection")

        new_profile_action = QAction("New &Profile...", self)
        new_profile_action.triggered.connect(self._show_profile_editor)
        connection_menu.addAction(new_profile_action)

        connection_menu.addSeparator()

        refresh_action = QAction("&Refresh Collections", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_active_connection)
        connection_menu.addAction(refresh_action)

        connection_menu.addSeparator()

        backup_action = QAction("&Backup/Restore...", self)
        backup_action.triggered.connect(self._show_backup_restore_dialog)
        connection_menu.addAction(backup_action)

        migrate_action = QAction("&Migrate Data...", self)
        migrate_action.triggered.connect(self._show_migration_dialog)
        connection_menu.addAction(migrate_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self.cache_action = QAction("Enable &Caching", self)
        self.cache_action.setCheckable(True)
        self.cache_action.setChecked(self.settings_service.get_cache_enabled())
        self.cache_action.triggered.connect(self._toggle_cache)
        view_menu.addAction(self.cache_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _setup_toolbar(self):
        """Setup application toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_connection_action = QAction("New Connection", self)
        new_connection_action.triggered.connect(self._new_connection_from_profile)
        toolbar.addAction(new_connection_action)

        toolbar.addSeparator()

        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._refresh_active_connection)
        toolbar.addAction(refresh_action)

    def _setup_statusbar(self):
        """Setup status bar with connection breadcrumb."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Breadcrumb label
        self.breadcrumb_label = QLabel("No active connection")
        self.statusBar().addPermanentWidget(self.breadcrumb_label)

        self.statusBar().showMessage("Ready")

    def _connect_signals(self):
        """Connect signals between components."""
        # Connection manager signals
        self.connection_manager.active_connection_changed.connect(
            self._on_active_connection_changed
        )
        self.connection_manager.active_collection_changed.connect(
            self._on_active_collection_changed
        )
        self.connection_manager.collections_updated.connect(self._on_collections_updated)
        self.connection_manager.connection_opened.connect(self._on_connection_opened)

        # Connection panel signals
        self.connection_panel.collection_selected.connect(self._on_collection_selected_from_panel)
        self.connection_panel.add_connection_btn.clicked.connect(self._new_connection_from_profile)

        # Profile panel signals
        self.profile_panel.connect_profile.connect(self._connect_to_profile)

    def _on_tab_changed(self, index: int):
        """Handle tab change - lazy load visualization tab."""
        if index == 3 and self.visualization_view is None:
            # Lazy load visualization view
            from vector_inspector.ui.views.visualization_view import VisualizationView

            # Get active connection
            active = self.connection_manager.get_active_connection()
            conn = active.connection if active else None

            self.visualization_view = VisualizationView(conn)
            # Replace placeholder with actual view
            self.tab_widget.removeTab(3)
            self.tab_widget.insertTab(3, self.visualization_view, "Visualization")
            self.tab_widget.setCurrentIndex(3)

            # Set collection if one is already selected
            if active and active.active_collection:
                self.visualization_view.set_collection(active.active_collection)

    def _on_active_connection_changed(self, connection_id):
        """Handle active connection change."""
        if connection_id:
            instance = self.connection_manager.get_connection(connection_id)
            if instance:
                # Update breadcrumb
                self.breadcrumb_label.setText(instance.get_breadcrumb())

                # Update all views with new connection
                self._update_views_with_connection(instance.connection)

                # If there's an active collection, update views with it
                if instance.active_collection:
                    self._update_views_for_collection(instance.active_collection)
            else:
                self.breadcrumb_label.setText("No active connection")
                self._update_views_with_connection(None)
        else:
            self.breadcrumb_label.setText("No active connection")
            self._update_views_with_connection(None)

    def _on_active_collection_changed(self, connection_id: str, collection_name):
        """Handle active collection change."""
        instance = self.connection_manager.get_connection(connection_id)
        if instance:
            # Update breadcrumb
            self.breadcrumb_label.setText(instance.get_breadcrumb())

            # Update views if this is the active connection
            if connection_id == self.connection_manager.get_active_connection_id():
                # Show loading immediately when collection changes
                if collection_name:
                    self.loading_dialog.show_loading(f"Loading collection '{collection_name}'...")
                    QApplication.processEvents()
                    try:
                        self._update_views_for_collection(collection_name)
                    finally:
                        self.loading_dialog.hide_loading()
                else:
                    # Clear collection from views
                    self.loading_dialog.show_loading("Clearing collection...")
                    QApplication.processEvents()
                    try:
                        self._update_views_for_collection(None)
                    finally:
                        self.loading_dialog.hide_loading()

    def _on_collections_updated(self, connection_id: str, collections: list):
        """Handle collections list updated."""
        # UI automatically updates via connection_manager_panel
        pass

    def _on_connection_opened(self, connection_id: str):
        """Handle connection successfully opened."""
        # If this is the active connection, refresh the info panel
        if connection_id == self.connection_manager.get_active_connection_id():
            instance = self.connection_manager.get_connection(connection_id)
            if instance and instance.connection:
                self.info_panel.refresh_database_info()

    def _on_collection_selected_from_panel(self, connection_id: str, collection_name: str):
        """Handle collection selection from connection panel."""
        # Show loading dialog while switching collections
        self.loading_dialog.show_loading(f"Loading collection '{collection_name}'...")
        QApplication.processEvents()

        try:
            # The connection manager already handled setting active collection
            # Just update the views
            self._update_views_for_collection(collection_name)
        finally:
            self.loading_dialog.hide_loading()

    def _update_views_with_connection(self, connection: VectorDBConnection):
        """Update all views with a new connection."""
        # Clear current collection when switching connections
        self.info_panel.current_collection = None
        self.metadata_view.current_collection = None
        self.search_view.current_collection = None
        if self.visualization_view is not None:
            self.visualization_view.current_collection = None

        # Update connection references
        self.info_panel.connection = connection
        self.metadata_view.connection = connection
        self.search_view.connection = connection

        if self.visualization_view is not None:
            self.visualization_view.connection = connection

        # Refresh info panel (will show no collection selected)
        if connection:
            self.info_panel.refresh_database_info()

    def _update_views_for_collection(self, collection_name: str):
        """Update all views with the selected collection."""
        if collection_name:
            # Get active connection ID to use as database identifier
            active = self.connection_manager.get_active_connection()
            database_name = active.id if active else ""

            self.info_panel.set_collection(collection_name, database_name)
            self.metadata_view.set_collection(collection_name, database_name)
            self.search_view.set_collection(collection_name, database_name)

            if self.visualization_view is not None:
                self.visualization_view.set_collection(collection_name)

    def _new_connection_from_profile(self):
        """Show dialog to create new connection (switches to Profiles tab)."""
        self.left_tabs.setCurrentIndex(1)  # Switch to Profiles tab
        QMessageBox.information(
            self,
            "Connect to Profile",
            "Select a profile from the list and click 'Connect', or click '+' to create a new profile.",
        )

    def _show_profile_editor(self):
        """Show profile editor to create new profile."""
        self.left_tabs.setCurrentIndex(1)  # Switch to Profiles tab
        self.profile_panel._create_profile()

    def _connect_to_profile(self, profile_id: str):
        """Connect to a profile."""
        profile_data = self.profile_service.get_profile_with_credentials(profile_id)
        if not profile_data:
            QMessageBox.warning(self, "Error", "Profile not found.")
            return

        # Check connection limit
        if self.connection_manager.get_connection_count() >= ConnectionManager.MAX_CONNECTIONS:
            QMessageBox.warning(
                self,
                "Connection Limit",
                f"Maximum number of connections ({ConnectionManager.MAX_CONNECTIONS}) reached. "
                "Please close a connection first.",
            )
            return

        # Create connection
        provider = profile_data["provider"]
        config = profile_data["config"]
        credentials = profile_data.get("credentials", {})

        try:
            # Create connection object
            if provider == "chromadb":
                connection = self._create_chroma_connection(config, credentials)
            elif provider == "qdrant":
                connection = self._create_qdrant_connection(config, credentials)
            elif provider == "pinecone":
                connection = self._create_pinecone_connection(config, credentials)
            else:
                QMessageBox.warning(self, "Error", f"Unsupported provider: {provider}")
                return

            # Register with connection manager, using profile_id as connection_id for persistence
            connection_id = self.connection_manager.create_connection(
                name=profile_data["name"],
                provider=provider,
                connection=connection,
                config=config,
                connection_id=profile_data["id"],
            )

            # Update state to connecting
            self.connection_manager.update_connection_state(
                connection_id, ConnectionState.CONNECTING
            )

            # Connect in background thread
            thread = ConnectionThread(connection)
            thread.finished.connect(
                lambda success, collections, error: self._on_connection_finished(
                    connection_id, success, collections, error
                )
            )
            self._connection_threads[connection_id] = thread
            thread.start()

            # Show loading dialog
            self.loading_dialog.show_loading(f"Connecting to {profile_data['name']}...")

        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to create connection: {e}")

    def _create_chroma_connection(self, config: dict, credentials: dict) -> ChromaDBConnection:
        """Create a ChromaDB connection."""
        conn_type = config.get("type")

        if conn_type == "persistent":
            return ChromaDBConnection(path=config.get("path"))
        elif conn_type == "http":
            return ChromaDBConnection(host=config.get("host"), port=config.get("port"))
        else:  # ephemeral
            return ChromaDBConnection()

    def _create_qdrant_connection(self, config: dict, credentials: dict) -> QdrantConnection:
        """Create a Qdrant connection."""
        conn_type = config.get("type")
        api_key = credentials.get("api_key")

        if conn_type == "persistent":
            return QdrantConnection(path=config.get("path"))
        elif conn_type == "http":
            return QdrantConnection(
                host=config.get("host"), port=config.get("port"), api_key=api_key
            )
        else:  # ephemeral
            return QdrantConnection()

    def _create_pinecone_connection(self, config: dict, credentials: dict) -> PineconeConnection:
        """Create a Pinecone connection."""
        api_key = credentials.get("api_key")
        if not api_key:
            raise ValueError("Pinecone requires an API key")

        return PineconeConnection(api_key=api_key)

    def _on_connection_finished(
        self, connection_id: str, success: bool, collections: list, error: str
    ):
        """Handle connection thread completion."""
        self.loading_dialog.hide_loading()

        # Clean up thread
        thread = self._connection_threads.pop(connection_id, None)
        if thread:
            thread.wait()  # Wait for thread to fully finish
            thread.deleteLater()

        if success:
            # Update state to connected
            self.connection_manager.update_connection_state(
                connection_id, ConnectionState.CONNECTED
            )

            # Mark connection as opened first (will show in UI)
            self.connection_manager.mark_connection_opened(connection_id)

            # Then update collections (UI item now exists to receive them)
            self.connection_manager.update_collections(connection_id, collections)

            # Switch to Active connections tab
            self.left_tabs.setCurrentIndex(0)

            self.statusBar().showMessage(
                f"Connected successfully ({len(collections)} collections)", 5000
            )
        else:
            # Update state to error
            self.connection_manager.update_connection_state(
                connection_id, ConnectionState.ERROR, error
            )

            QMessageBox.warning(self, "Connection Failed", f"Failed to connect: {error}")

            # Remove the failed connection
            self.connection_manager.close_connection(connection_id)

    def _refresh_active_connection(self):
        """Refresh collections for the active connection."""
        active = self.connection_manager.get_active_connection()
        if not active or not active.connection.is_connected:
            QMessageBox.information(self, "No Connection", "No active connection to refresh.")
            return

        try:
            collections = active.connection.list_collections()
            self.connection_manager.update_collections(active.id, collections)
            self.statusBar().showMessage(f"Refreshed collections ({len(collections)} found)", 3000)

            # Also refresh info panel
            self.info_panel.refresh_database_info()
        except Exception as e:
            QMessageBox.warning(self, "Refresh Failed", f"Failed to refresh collections: {e}")

    def _restore_session(self):
        """Restore previously active connections on startup."""
        # TODO: Implement session restore
        # For now, we'll just show a message if there are saved profiles
        profiles = self.profile_service.get_all_profiles()
        if profiles:
            self.statusBar().showMessage(
                f"{len(profiles)} saved profile(s) available. Switch to Profiles tab to connect.",
                10000,
            )

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Vector Inspector",
            "<h2>Vector Inspector 0.3.0</h2>"
            "<p>A comprehensive desktop application for visualizing, "
            "querying, and managing multiple vector databases simultaneously.</p>"
            '<p><a href="https://github.com/anthonypdawson/vector-inspector" style="color:#2980b9;">GitHub Project Page</a></p>'
            "<hr />"
            "<p>Built with PySide6, ChromaDB, and Qdrant</p>"
            "<p><b>New:</b> Multi-database support with saved connection profiles</p>",
        )

    def _toggle_cache(self, checked: bool):
        """Toggle caching on/off."""
        self.settings_service.set_cache_enabled(checked)
        status = "enabled" if checked else "disabled"
        self.statusBar().showMessage(f"Caching {status}", 3000)

    def _show_migration_dialog(self):
        """Show cross-database migration dialog."""
        if self.connection_manager.get_connection_count() < 2:
            QMessageBox.information(
                self,
                "Insufficient Connections",
                "You need at least 2 active connections to migrate data.\n"
                "Please connect to additional databases first.",
            )
            return

        from vector_inspector.ui.dialogs.cross_db_migration import CrossDatabaseMigrationDialog

        dialog = CrossDatabaseMigrationDialog(self.connection_manager, self)
        dialog.exec()

    def _show_backup_restore_dialog(self):
        """Show backup/restore dialog for the active collection."""
        # Check if there's an active connection
        connection = self.connection_manager.get_active_connection()
        if not connection:
            QMessageBox.information(self, "No Connection", "Please connect to a database first.")
            return

        # Get active collection
        collection_name = self.connection_manager.get_active_collection()
        if not collection_name:
            # Allow opening dialog without a collection selected (for restore-only)
            QMessageBox.information(
                self,
                "No Collection Selected",
                "You can restore backups without a collection selected.\n"
                "To create a backup, please select a collection first.",
            )

        from vector_inspector.ui.components.backup_restore_dialog import BackupRestoreDialog

        dialog = BackupRestoreDialog(connection, collection_name or "", self)
        if dialog.exec() == QDialog.Accepted:
            # Refresh collections after restore
            self._refresh_active_connection()

    def closeEvent(self, event):
        """Handle application close."""
        # Wait for all connection threads to finish
        for thread in list(self._connection_threads.values()):
            if thread.isRunning():
                thread.quit()
                thread.wait(1000)  # Wait up to 1 second

        # Clean up temp HTML files from visualization view
        if self.visualization_view is not None:
            try:
                self.visualization_view.cleanup_temp_html()
            except Exception:
                pass
        # Close all connections
        self.connection_manager.close_all_connections()

        event.accept()
