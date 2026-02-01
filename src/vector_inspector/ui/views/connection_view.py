"""Connection configuration view."""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QDialog,
    QFormLayout,
    QLineEdit,
    QRadioButton,
    QButtonGroup,
    QGroupBox,
    QFileDialog,
    QComboBox,
    QApplication,
    QCheckBox,
)
from PySide6.QtCore import Signal, QThread

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.connections.chroma_connection import ChromaDBConnection
from vector_inspector.core.connections.qdrant_connection import QdrantConnection
from vector_inspector.core.connections.pinecone_connection import PineconeConnection
from vector_inspector.core.connections.pgvector_connection import PgVectorConnection
from vector_inspector.ui.components.loading_dialog import LoadingDialog
from vector_inspector.services.settings_service import SettingsService


class ConnectionThread(QThread):
    """Background thread for connecting to database."""

    finished = Signal(bool, list)  # success, collections

    def __init__(self, connection):
        super().__init__()
        self.connection = connection

    def run(self):
        """Connect to database and get collections."""
        try:
            success = self.connection.connect()
            if success:
                collections = self.connection.list_collections()
                self.finished.emit(True, collections)
            else:
                self.finished.emit(False, [])
        except Exception:
            self.finished.emit(False, [])


class ConnectionDialog(QDialog):
    """Dialog for configuring database connection."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connect to Vector Database")
        self.setMinimumWidth(450)

        self.settings_service = SettingsService()

        self.provider = "chromadb"
        self.connection_type = "persistent"
        self.path = ""
        self.host = "localhost"
        self.port = "8000"

        self._setup_ui()
        self._load_last_connection()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        # Provider selection
        provider_group = QGroupBox("Database Provider")
        provider_layout = QVBoxLayout()

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("ChromaDB", "chromadb")
        self.provider_combo.addItem("Qdrant", "qdrant")
        self.provider_combo.addItem("Pinecone", "pinecone")
        self.provider_combo.addItem("PgVector/PostgreSQL", "pgvector")
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

        # Host input (for HTTP/PgVector)
        self.host_input = QLineEdit()
        self.host_input.setText("localhost")
        self.host_input.setEnabled(False)
        form_layout.addRow("Host:", self.host_input)

        # Port input (for HTTP/PgVector)
        self.port_input = QLineEdit()
        self.port_input.setText("8000")
        self.port_input.setEnabled(False)
        form_layout.addRow("Port:", self.port_input)

        # Database input (for PgVector)
        self.database_input = QLineEdit()
        self.database_input.setText("subtitles")
        self.database_input.setEnabled(False)
        form_layout.addRow("Database:", self.database_input)

        # User input (for PgVector)
        self.user_input = QLineEdit()
        self.user_input.setText("postgres")
        self.user_input.setEnabled(False)
        form_layout.addRow("User:", self.user_input)

        # Password input (for PgVector)
        self.password_input = QLineEdit()
        self.password_input.setText("postgres")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setEnabled(False)
        form_layout.addRow("Password:", self.password_input)

        # API Key input (for Qdrant Cloud)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEnabled(False)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_row = form_layout.rowCount()
        form_layout.addRow("API Key:", self.api_key_input)

        details_group.setLayout(form_layout)
        layout.addWidget(details_group)

        # Auto-connect option
        self.auto_connect_check = QCheckBox("Auto-connect on startup")
        self.auto_connect_check.setChecked(False)
        layout.addWidget(self.auto_connect_check)

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
        if self.provider == "qdrant" and self.port_input.text() == "8000":
            self.port_input.setText("6333")
        elif self.provider == "chromadb" and self.port_input.text() == "6333":
            self.port_input.setText("8000")

        # Enable/disable fields for PgVector
        if self.provider == "pgvector":
            self.persistent_radio.setEnabled(False)
            self.http_radio.setEnabled(False)
            self.ephemeral_radio.setEnabled(False)
            self.path_input.setEnabled(False)
            self.host_input.setEnabled(True)
            self.port_input.setEnabled(True)
            self.database_input.setEnabled(True)
            self.user_input.setEnabled(True)
            self.password_input.setEnabled(True)
            self.api_key_input.setEnabled(False)
            # Set default port for PostgreSQL if not set
            if self.port_input.text() in ("8000", "6333"):
                self.port_input.setText("5432")
        elif self.provider == "pinecone":
            self.persistent_radio.setEnabled(False)
            self.http_radio.setEnabled(True)
            self.http_radio.setChecked(True)
            self.ephemeral_radio.setEnabled(False)
            self.path_input.setEnabled(False)
            self.host_input.setEnabled(False)
            self.port_input.setEnabled(False)
            self.api_key_input.setEnabled(True)
            self.database_input.setEnabled(False)
            self.user_input.setEnabled(False)
            self.password_input.setEnabled(False)
        else:
            self.persistent_radio.setEnabled(True)
            self.http_radio.setEnabled(True)
            self.ephemeral_radio.setEnabled(True)
            # Show/hide API key field
            is_http = self.http_radio.isChecked()
            self.api_key_input.setEnabled(is_http and self.provider == "qdrant")
            # Update path/host/port based on connection type
            self._on_type_changed()
            # Disable PgVector fields for other providers
            self.database_input.setEnabled(False)
            self.user_input.setEnabled(False)
            self.password_input.setEnabled(False)

    def _on_type_changed(self):
        """Handle connection type change."""
        is_persistent = self.persistent_radio.isChecked()
        is_http = self.http_radio.isChecked()

        # Pinecone always uses API key, no path/host/port
        if self.provider == "pinecone":
            self.path_input.setEnabled(False)
            self.host_input.setEnabled(False)
            self.port_input.setEnabled(False)
            self.api_key_input.setEnabled(True)
            self.database_input.setEnabled(False)
            self.user_input.setEnabled(False)
            self.password_input.setEnabled(False)
        elif self.provider == "pgvector":
            self.path_input.setEnabled(False)
            self.host_input.setEnabled(True)
            self.port_input.setEnabled(True)
            self.database_input.setEnabled(True)
            self.user_input.setEnabled(True)
            self.password_input.setEnabled(True)
            self.api_key_input.setEnabled(False)
        else:
            self.path_input.setEnabled(is_persistent)
            self.host_input.setEnabled(is_http)
            self.port_input.setEnabled(is_http)
            self.api_key_input.setEnabled(is_http and self.provider == "qdrant")
            self.database_input.setEnabled(False)
            self.user_input.setEnabled(False)
            self.password_input.setEnabled(False)

        self._update_absolute_preview()

    def get_connection_config(self):
        """Get connection configuration from dialog."""
        # Get current provider from combo box to ensure it's up to date
        self.provider = self.provider_combo.currentData()

        config = {"provider": self.provider}

        if self.provider == "pinecone":
            config.update({"type": "cloud", "api_key": self.api_key_input.text()})
        elif self.provider == "pgvector":
            config.update(
                {
                    "type": "pgvector",
                    "host": self.host_input.text(),
                    "port": int(self.port_input.text()),
                    "database": self.database_input.text(),
                    "user": self.user_input.text(),
                    "password": self.password_input.text(),
                }
            )
        elif self.persistent_radio.isChecked():
            config.update({"type": "persistent", "path": self.path_input.text()})
        elif self.http_radio.isChecked():
            config.update(
                {
                    "type": "http",
                    "host": self.host_input.text(),
                    "port": int(self.port_input.text()),
                    "api_key": self.api_key_input.text() if self.api_key_input.text() else None,
                }
            )
        else:
            config.update({"type": "ephemeral"})

        # Save auto-connect preference
        config["auto_connect"] = self.auto_connect_check.isChecked()

        # Save this configuration for next time
        self.settings_service.save_last_connection(config)

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
        directory = QFileDialog.getExistingDirectory(
            self, "Select ChromaDB Data Directory", start_dir
        )
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

    def _load_last_connection(self):
        """Load and populate the last connection configuration."""
        last_config = self.settings_service.get_last_connection()
        if not last_config:
            return

        # Set provider
        provider = last_config.get("provider", "chromadb")
        index = self.provider_combo.findData(provider)
        if index >= 0:
            self.provider_combo.setCurrentIndex(index)

        # Set connection type
        conn_type = last_config.get("type", "persistent")
        if conn_type == "cloud":
            # Pinecone cloud connection
            self.http_radio.setChecked(True)
            api_key = last_config.get("api_key")
            if api_key:
                self.api_key_input.setText(api_key)
        elif conn_type == "pgvector":
            # PgVector connection
            self.host_input.setText(last_config.get("host", "localhost"))
            self.port_input.setText(str(last_config.get("port", "5432")))
            self.database_input.setText(last_config.get("database", "subtitles"))
            self.user_input.setText(last_config.get("user", "postgres"))
            self.password_input.setText(last_config.get("password", "postgres"))
        elif conn_type == "persistent":
            self.persistent_radio.setChecked(True)
            path = last_config.get("path", "")
            if path:
                self.path_input.setText(path)
        elif conn_type == "http":
            self.http_radio.setChecked(True)
            host = last_config.get("host", "localhost")
            port = last_config.get("port", "8000")
            self.host_input.setText(host)
            self.port_input.setText(str(port))
            api_key = last_config.get("api_key")
            if api_key:
                self.api_key_input.setText(api_key)
        elif conn_type == "ephemeral":
            self.ephemeral_radio.setChecked(True)

        # Set auto-connect checkbox
        auto_connect = last_config.get("auto_connect", False)
        self.auto_connect_check.setChecked(auto_connect)


class ConnectionView(QWidget):
    """Widget for managing database connection."""

    connection_changed = Signal(bool)
    connection_created = Signal(VectorDBConnection)  # Signal when new connection is created

    def __init__(self, connection: Optional[VectorDBConnection] = None, parent=None):
        super().__init__(parent)
        # This view may be constructed without an active connection; it manages
        # creation of `VectorDBConnection` instances. Keep `self.connection` as
        # the low-level `VectorDBConnection` when present.
        self._raw_connection = None
        self.connection = connection
        self.loading_dialog = LoadingDialog("Connecting to database...", self)
        self.settings_service = SettingsService()
        self.connection_thread = None
        self._setup_ui()

        # Try to auto-connect if enabled in settings
        self._try_auto_connect()

    def _setup_ui(self):
        """Setup widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Connection status group
        group = QGroupBox("Connection")
        group_layout = QVBoxLayout()

        self.status_label = QLabel("Status: Not connected")
        group_layout.addWidget(self.status_label)

        # Button layout with both connect and disconnect
        button_layout = QHBoxLayout()

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.show_connection_dialog)
        button_layout.addWidget(self.connect_button)

        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self._disconnect)
        self.disconnect_button.setEnabled(False)
        button_layout.addWidget(self.disconnect_button)

        group_layout.addLayout(button_layout)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def show_connection_dialog(self):
        """Show connection configuration dialog."""
        dialog = ConnectionDialog(self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_connection_config()
            self._connect_with_config(config)

    def _connect_with_config(self, config: dict):
        """Connect to database with given configuration."""
        self.loading_dialog.show_loading("Connecting to database...")

        provider = config.get("provider", "chromadb")
        conn_type = config.get("type")

        # Create appropriate connection instance based on provider
        if provider == "pinecone":
            api_key = config.get("api_key")
            if not api_key:
                self.loading_dialog.hide_loading()
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self, "Missing API Key", "Pinecone requires an API key to connect."
                )
                return
            self.connection = PineconeConnection(api_key=api_key)
        elif provider == "qdrant":
            if conn_type == "persistent":
                self.connection = QdrantConnection(path=config.get("path"))
            elif conn_type == "http":
                self.connection = QdrantConnection(
                    host=config.get("host"), port=config.get("port"), api_key=config.get("api_key")
                )
            else:  # ephemeral/memory
                self.connection = QdrantConnection()
        elif provider == "pgvector":
            self.connection = PgVectorConnection(
                host=config.get("host", "localhost"),
                port=config.get("port", 5432),
                database=config.get("database", "subtitles"),
                user=config.get("user", "postgres"),
                password=config.get("password", "postgres"),
            )
        else:  # chromadb
            if conn_type == "persistent":
                self.connection = ChromaDBConnection(path=config.get("path"))
            elif conn_type == "http":
                self.connection = ChromaDBConnection(
                    host=config.get("host"), port=config.get("port")
                )
            else:  # ephemeral
                self.connection = ChromaDBConnection()

        # Store config for later use
        self._pending_config = config

        # Notify parent that connection instance changed
        self.connection_created.emit(self.connection)

        # Start background thread to connect
        self.connection_thread = ConnectionThread(self.connection)
        self.connection_thread.finished.connect(self._on_connection_finished)
        self.connection_thread.start()

    def _on_connection_finished(self, success: bool, collections: list):
        """Handle connection thread completion."""
        self.loading_dialog.hide_loading()

        if success:
            config = self._pending_config
            provider = config.get("provider", "chromadb")

            # Show provider, path/host + collection count for clarity
            details = [f"provider: {provider}"]
            # Show path for persistent ChromaDB/Qdrant
            if provider in ("chromadb", "qdrant") and hasattr(self.connection, "path"):
                path = getattr(self.connection, "path", None)
                if path:
                    details.append(f"path: {path}")
            # Show host/port for HTTP or PgVector
            if provider in ("qdrant", "chromadb", "pgvector") and hasattr(self.connection, "host"):
                host = getattr(self.connection, "host", None)
                port = getattr(self.connection, "port", None)
                if host:
                    details.append(f"host: {host}:{port}")
            count_text = f"collections: {len(collections)}"
            info = ", ".join(details)
            self.status_label.setText(f"Status: Connected ({info}, {count_text})")

            # Enable disconnect, disable connect
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)

            # Emit signal which triggers collection browser refresh
            self.connection_changed.emit(True)

            # Process events to ensure collection browser is updated
            QApplication.processEvents()
        else:
            self.status_label.setText("Status: Connection failed")
            # Enable connect, disable disconnect
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(False)
            self.connection_changed.emit(False)

    def _disconnect(self):
        """Disconnect from database."""
        self.connection.disconnect()
        self.status_label.setText("Status: Not connected")

        # Enable connect, disable disconnect
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)

        self.connection_changed.emit(False)

    def _try_auto_connect(self):
        """Try to automatically connect if auto-connect is enabled."""
        last_config = self.settings_service.get_last_connection()
        if last_config and last_config.get("auto_connect", False):
            # Auto-connect is enabled
            self._connect_with_config(last_config)
