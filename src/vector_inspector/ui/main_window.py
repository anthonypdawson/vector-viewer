"""Main application window."""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QSplitter, QTabWidget, QStatusBar, QToolBar,
    QMessageBox, QInputDialog, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.connections.chroma_connection import ChromaDBConnection
from vector_inspector.ui.views.connection_view import ConnectionView
from vector_inspector.ui.views.collection_browser import CollectionBrowser
from vector_inspector.ui.views.metadata_view import MetadataView
from vector_inspector.ui.views.search_view import SearchView
from vector_inspector.ui.views.visualization_view import VisualizationView
from vector_inspector.ui.components.backup_restore_dialog import BackupRestoreDialog


class MainWindow(QMainWindow):
    """Main application window with all views and controls."""
    
    connection_changed = Signal(bool)  # Emits True when connected, False when disconnected
    
    def __init__(self):
        super().__init__()
        self.connection: VectorDBConnection = ChromaDBConnection()
        self.current_collection: str = ""
        
        self.setWindowTitle("Vector Inspector")
        self.setGeometry(100, 100, 1400, 900)
        
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_statusbar()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup the main UI layout."""
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Main splitter (left panel | right tabs)
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Connection and Collections
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.connection_view = ConnectionView(self.connection)
        self.collection_browser = CollectionBrowser(self.connection)
        
        left_layout.addWidget(self.connection_view)
        left_layout.addWidget(self.collection_browser)
        
        # Right panel - Tabbed views
        self.tab_widget = QTabWidget()
        
        self.metadata_view = MetadataView(self.connection)
        self.search_view = SearchView(self.connection)
        self.visualization_view = VisualizationView(self.connection)
        
        self.tab_widget.addTab(self.metadata_view, "Data Browser")
        self.tab_widget.addTab(self.search_view, "Search")
        self.tab_widget.addTab(self.visualization_view, "Visualization")
        
        # Add panels to splitter
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(self.tab_widget)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 3)
        
        layout.addWidget(main_splitter)
        
    def _setup_menu_bar(self):
        """Setup application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        connect_action = QAction("&Connect to Database...", self)
        connect_action.setShortcut("Ctrl+O")
        connect_action.triggered.connect(self._on_connect)
        file_menu.addAction(connect_action)
        
        disconnect_action = QAction("&Disconnect", self)
        disconnect_action.triggered.connect(self._on_disconnect)
        file_menu.addAction(disconnect_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Collection menu
        collection_menu = menubar.addMenu("&Collection")
        
        new_collection_action = QAction("&New Collection...", self)
        new_collection_action.setShortcut("Ctrl+N")
        new_collection_action.triggered.connect(self._on_new_collection)
        collection_menu.addAction(new_collection_action)
        
        refresh_action = QAction("&Refresh Collections", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._on_refresh_collections)
        collection_menu.addAction(refresh_action)
        
        collection_menu.addSeparator()
        
        backup_action = QAction("&Backup/Restore...", self)
        backup_action.setShortcut("Ctrl+B")
        backup_action.triggered.connect(self._on_backup_restore)
        collection_menu.addAction(backup_action)
        
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
        
        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self._on_connect)
        toolbar.addAction(connect_action)
        
        disconnect_action = QAction("Disconnect", self)
        disconnect_action.triggered.connect(self._on_disconnect)
        toolbar.addAction(disconnect_action)
        toolbar.addSeparator()
        
        backup_action = QAction("Backup/Restore", self)
        backup_action.triggered.connect(self._on_backup_restore)
        toolbar.addAction(backup_action)
        
        
        toolbar.addSeparator()
        
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self._on_refresh_collections)
        toolbar.addAction(refresh_action)
        
    def _setup_statusbar(self):
        """Setup status bar."""
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Not connected")
        
    def _connect_signals(self):
        """Connect signals between components."""
        self.connection_view.connection_changed.connect(self._on_connection_status_changed)
        self.connection_view.connection_created.connect(self._on_connection_created)
        self.collection_browser.collection_selected.connect(self._on_collection_selected)
    
    def _on_connection_created(self, new_connection: VectorDBConnection):
        """Handle when a new connection instance is created."""
        self.connection = new_connection
        # Update all views with new connection
        self.collection_browser.connection = new_connection
        self.metadata_view.connection = new_connection
        self.search_view.connection = new_connection
        self.visualization_view.connection = new_connection
        
    def _on_connect(self):
        """Handle connect action."""
        self.connection_view.show_connection_dialog()
        
    def _on_disconnect(self):
        """Handle disconnect action."""
        if self.connection.is_connected:
            self.connection.disconnect()
            self.statusBar.showMessage("Disconnected")
            self.connection_changed.emit(False)
            self.collection_browser.clear()
            
    def _on_connection_status_changed(self, connected: bool):
        """Handle connection status change."""
        if connected:
            self.statusBar.showMessage("Connected")
            self.connection_changed.emit(True)
            self._on_refresh_collections()
        else:
            self.statusBar.showMessage("Connection failed")
            self.connection_changed.emit(False)
            
    def _on_collection_selected(self, collection_name: str):
        """Handle collection selection."""
        self.current_collection = collection_name
        self.statusBar.showMessage(f"Collection: {collection_name}")
        
        # Update all views with new collection
        self.metadata_view.set_collection(collection_name)
        self.search_view.set_collection(collection_name)
        self.visualization_view.set_collection(collection_name)
        
    def _on_refresh_collections(self):
        """Refresh collection list."""
        if self.connection.is_connected:
            self.collection_browser.refresh()
            
    def _on_new_collection(self):
        """Create a new collection."""
        if not self.connection.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a database first.")
            return
        
        from vector_inspector.core.connections.chroma_connection import ChromaDBConnection
        from vector_inspector.core.connections.qdrant_connection import QdrantConnection
        
        name, ok = QInputDialog.getText(
            self, "New Collection", "Enter collection name:"
        )
        
        if ok and name:
            success = False
            
            # Handle ChromaDB
            if isinstance(self.connection, ChromaDBConnection):
                collection = self.connection.get_collection(name)
                success = collection is not None
            
            # Handle Qdrant
            elif isinstance(self.connection, QdrantConnection):
                # Ask for vector size (required for Qdrant)
                vector_size, ok = QInputDialog.getInt(
                    self, 
                    "Vector Size", 
                    "Enter vector dimension size:",
                    value=384,  # Default for sentence transformers
                    min=1,
                    max=10000
                )
                if ok:
                    success = self.connection.create_collection(name, vector_size)
            
            if success:
                QMessageBox.information(
                    self, "Success", f"Collection '{name}' created successfully."
                )
                self._on_refresh_collections()
            else:
                QMessageBox.warning(
                    self, "Error", f"Failed to create collection '{name}'."
                )
    
    def _on_backup_restore(self):
        """Open backup/restore dialog."""
        if not self.connection.is_connected:
            QMessageBox.warning(self, "Not Connected", "Please connect to a database first.")
            return
            
        dialog = BackupRestoreDialog(
            self.connection,
            self.current_collection,
            self
        )
        dialog.exec()
        
        # Refresh collections after dialog closes (in case something was restored)
        self._on_refresh_collections()
                
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Vector Inspector",
            "<h2>Vector Inspector 0.1.0</h2>"
            "<p>A comprehensive desktop application for visualizing, "
            "querying, and managing vector database data.</p>"
            '<p><a href="https://github.com/anthonypdawson/vector-viewer" style="color:#2980b9;">GitHub Project Page</a></p>'
            "<hr />"
            "<p>Built with PySide6 and ChromaDB</p>"
        )
