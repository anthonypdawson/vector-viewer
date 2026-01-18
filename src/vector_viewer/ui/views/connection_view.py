"""Connection configuration view."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QDialog, QFormLayout, QLineEdit,
    QRadioButton, QButtonGroup, QGroupBox, QFileDialog, QComboBox, QApplication
)
from PySide6.QtCore import Signal

from vector_viewer.core.connections.base_connection import VectorDBConnection
from vector_viewer.core.connections.chroma_connection import ChromaDBConnection
from vector_viewer.core.connections.qdrant_connection import QdrantConnection
from vector_viewer.ui.components.loading_dialog import LoadingDialog


class ConnectionDialog(QDialog):
    """Dialog for configuring database connection."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Vector Database")
        self.setMinimumWidth(450)
        
        self.provider = "chromadb"
        self.connection_type = "persistent"
        self.path = ""
        self.host = "localhost"
        self.port = "8000"
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)
        
        # Provider selection
        provider_group = QGroupBox("Database Provider")
        provider_layout = QVBoxLayout()
        
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("ChromaDB", "chromadb")
        self.provider_combo.addItem("Qdrant", "qdrant")
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_layout.addWidget(self.provider_combo)
        provider_group.setLayout(provider_layout)
        
        layout.addWidget(provider_group)
        
        # Connection type selection
        type_group = QGroupBox("Connection Type")
        type_layout = QVBoxLayout()
        
        self.button_group = QButtonGroup()
        
        self.persistent_radio = QRadioButton("Persistent (Local File)")
        self.persistent_radio.setChecked(True)
        self.persistent_radio.toggled.connect(self._on_type_changed)
        
        self.http_radio = QRadioButton("HTTP (Remote Server)")
        
        self.ephemeral_radio = QRadioButton("Ephemeral (In-Memory)")
        
        self.button_group.addButton(self.persistent_radio)
        self.button_group.addButton(self.http_radio)
        self.button_group.addButton(self.ephemeral_radio)
        
        type_layout.addWidget(self.persistent_radio)
        type_layout.addWidget(self.http_radio)
        type_layout.addWidget(self.ephemeral_radio)
        type_group.setLayout(type_layout)
        
        layout.addWidget(type_group)
        
        # Connection details
        details_group = QGroupBox("Connection Details")
        form_layout = QFormLayout()
        
        # Path input (for persistent) + Browse button
        self.path_input = QLineEdit()
        # Default to user's test data folder
        self.path_input.setText("./data/chrome_db")
        path_row_widget = QWidget()
        path_row_layout = QHBoxLayout(path_row_widget)
        path_row_layout.setContentsMargins(0, 0, 0, 0)
        path_row_layout.addWidget(self.path_input)
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse_for_path)
        path_row_layout.addWidget(browse_button)
        form_layout.addRow("Data Path:", path_row_widget)
        
        # Host input (for HTTP)
        self.host_input = QLineEdit()
        self.host_input.setText("localhost")
        self.host_input.setEnabled(False)
        form_layout.addRow("Host:", self.host_input)
        
        # Port input (for HTTP)
        self.port_input = QLineEdit()
        self.port_input.setText("8000")
        self.port_input.setEnabled(False)
        form_layout.addRow("Port:", self.port_input)
        
        # API Key input (for Qdrant Cloud)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEnabled(False)
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_row = form_layout.rowCount()
        form_layout.addRow("API Key:", self.api_key_input)
        
        details_group.setLayout(form_layout)
        layout.addWidget(details_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        connect_button = QPushButton("Connect")
        connect_button.clicked.connect(self.accept)
        connect_button.setDefault(True)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(connect_button)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)

        # Resolved absolute path preview
        self.absolute_path_label = QLabel("")
        self.absolute_path_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.absolute_path_label)
        
        # Update preview when inputs change
        self.path_input.textChanged.connect(self._update_absolute_preview)
        self.persistent_radio.toggled.connect(self._update_absolute_preview)
        self._update_absolute_preview()
    
    def _on_provider_changed(self):
        """Handle provider selection change."""
        self.provider = self.provider_combo.currentData()
        
        # Update default port based on provider
        if self.provider == "qdrant":
            if self.port_input.text() == "8000":
                self.port_input.setText("6333")
        elif self.provider == "chromadb":
            if self.port_input.text() == "6333":
                self.port_input.setText("8000")
        
        # Show/hide API key field
        is_http = self.http_radio.isChecked()
        self.api_key_input.setEnabled(is_http and self.provider == "qdrant")
        
    def _on_type_changed(self):
        """Handle connection type change."""
        is_persistent = self.persistent_radio.isChecked()
        is_http = self.http_radio.isChecked()
        
        self.path_input.setEnabled(is_persistent)
        self.host_input.setEnabled(is_http)
        self.port_input.setEnabled(is_http)
        self.api_key_input.setEnabled(is_http and self.provider == "qdrant")

        self._update_absolute_preview()
        
    def get_connection_config(self):
        """Get connection configuration from dialog."""
        config = {"provider": self.provider}
        
        if self.persistent_radio.isChecked():
            config.update({"type": "persistent", "path": self.path_input.text()})
        elif self.http_radio.isChecked():
            config.update({
                "type": "http",
                "host": self.host_input.text(),
                "port": int(self.port_input.text()),
                "api_key": self.api_key_input.text() if self.api_key_input.text() else None
            })
        else:
            config.update({"type": "ephemeral"})
        
        return config

    def _update_absolute_preview(self):
        """Show resolved absolute path for persistent connections."""
        if not self.persistent_radio.isChecked():
            self.absolute_path_label.setText("")
            return
        rel = self.path_input.text().strip() or "."
        # Resolve relative to project root by searching for pyproject.toml
        from pathlib import Path
        current = Path(__file__).resolve()
        abs_path = None
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                abs_path = (parent / rel).resolve()
                break
        if abs_path is None:
            abs_path = Path(rel).resolve()
        self.absolute_path_label.setText(f"Resolved path: {abs_path}")

    def _browse_for_path(self):
        """Open a folder chooser to select persistent storage path."""
        # Suggest current resolved path as starting point
        start_dir = None
        from pathlib import Path
        rel = self.path_input.text().strip() or "."
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                start_dir = str((parent / rel).resolve())
                break
        if start_dir is None:
            start_dir = str(Path(rel).resolve())
        directory = QFileDialog.getExistingDirectory(self, "Select ChromaDB Data Directory", start_dir)
        if directory:
            # Set as relative to project root if within it, else absolute
            proj_root = None
            for parent in current.parents:
                if (parent / "pyproject.toml").exists():
                    proj_root = parent
                    break
            dir_path = Path(directory)
            if proj_root and proj_root in dir_path.parents:
                try:
                    display_path = str(dir_path.relative_to(proj_root))
                except Exception:
                    display_path = str(dir_path)
            else:
                display_path = str(dir_path)
            self.path_input.setText(display_path)
            self._update_absolute_preview()


class ConnectionView(QWidget):
    """Widget for managing database connection."""
    
    connection_changed = Signal(bool)
    connection_created = Signal(VectorDBConnection)  # Signal when new connection is created
    
    def __init__(self, connection: VectorDBConnection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.loading_dialog = LoadingDialog("Connecting to database...", self)
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Connection status group
        group = QGroupBox("Connection")
        group_layout = QVBoxLayout()
        
        self.status_label = QLabel("Status: Not connected")
        group_layout.addWidget(self.status_label)
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.show_connection_dialog)
        group_layout.addWidget(self.connect_button)
        
        group.setLayout(group_layout)
        layout.addWidget(group)
        
    def show_connection_dialog(self):
        """Show connection configuration dialog."""
        dialog = ConnectionDialog(self)
        
        if dialog.exec() == QDialog.Accepted:
            config = dialog.get_connection_config()
            self._connect_with_config(config)
            
    def _connect_with_config(self, config: dict):
        """Connect to database with given configuration."""
        self.loading_dialog.show_loading("Connecting to database...")
        QApplication.processEvents()
        try:
            provider = config.get("provider", "chromadb")
            conn_type = config.get("type")
            
            # Create appropriate connection instance based on provider
            if provider == "qdrant":
                if conn_type == "persistent":
                    self.connection = QdrantConnection(path=config.get("path"))
                elif conn_type == "http":
                    self.connection = QdrantConnection(
                        host=config.get("host"),
                        port=config.get("port"),
                        api_key=config.get("api_key")
                    )
                else:  # ephemeral/memory
                    self.connection = QdrantConnection()
            else:  # chromadb
                if conn_type == "persistent":
                    self.connection = ChromaDBConnection(path=config.get("path"))
                elif conn_type == "http":
                    self.connection = ChromaDBConnection(
                        host=config.get("host"),
                        port=config.get("port")
                    )
                else:  # ephemeral
                    self.connection = ChromaDBConnection()
                    
            # Notify parent that connection instance changed
            self.connection_created.emit(self.connection)
            success = self.connection.connect()
        finally:
            self.loading_dialog.hide_loading()
            
        if success:
            # Show provider, path/host + collection count for clarity
            details = []
            details.append(f"provider: {provider}")
            if hasattr(self.connection, 'path') and self.connection.path:
                details.append(f"path: {self.connection.path}")
            if hasattr(self.connection, 'host') and self.connection.host:
                port = getattr(self.connection, 'port', None)
                details.append(f"host: {self.connection.host}:{port}")
            collections = self.connection.list_collections()
            count_text = f"collections: {len(collections)}"
            info = ", ".join(details)
            self.status_label.setText(f"Status: Connected ({info}, {count_text})")
            self.connect_button.setText("Disconnect")
            self.connect_button.clicked.disconnect()
            self.connect_button.clicked.connect(self._disconnect)
        else:
            self.status_label.setText("Status: Connection failed")
            
        self.connection_changed.emit(success)
        
    def _disconnect(self):
        """Disconnect from database."""
        self.connection.disconnect()
        self.status_label.setText("Status: Not connected")
        self.connect_button.setText("Connect")
        self.connect_button.clicked.disconnect()
        self.connect_button.clicked.connect(self.show_connection_dialog)
        self.connection_changed.emit(False)
