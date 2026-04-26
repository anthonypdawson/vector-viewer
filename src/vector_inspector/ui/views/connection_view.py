"""Connection configuration view."""

from typing import Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.connections import get_connection_class
from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.provider_detection import (
    get_all_providers,
    get_provider_info,
)
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.ui.components.loading_dialog import LoadingDialog


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

        # Provider selection with availability detection
        provider_group = QGroupBox("Database Provider")
        provider_layout = QVBoxLayout()

        # Provider combo + refresh button row
        provider_row = QHBoxLayout()

        self.provider_combo = QComboBox()
        self._populate_providers()
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self.provider_combo, 1)

        # Refresh button to detect newly installed providers
        refresh_btn = QPushButton("🔄")
        refresh_btn.setMaximumWidth(40)
        refresh_btn.setToolTip("Refresh provider list (detects newly installed providers)")
        refresh_btn.clicked.connect(self._refresh_providers)
        provider_row.addWidget(refresh_btn)

        provider_layout.addLayout(provider_row)

        # Help text for installing providers
        self.provider_help_label = QLabel()
        self.provider_help_label.setStyleSheet("color: gray; font-size: 10px;")
        self.provider_help_label.setWordWrap(True)
        self._update_help_text()
        provider_layout.addWidget(self.provider_help_label)

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

    def _populate_providers(self):
        """Populate provider combo box with availability detection."""
        self.provider_combo.clear()

        all_providers = get_all_providers()
        available_count = 0

        for provider in all_providers:
            if provider.available:
                # Available provider - normal display
                self.provider_combo.addItem(provider.name, provider.id)
                available_count += 1
            else:
                # Unavailable provider — shown in gray but still selectable so
                # currentIndexChanged fires and the install dialog is triggered.
                display_name = f"{provider.name} (not installed)"
                self.provider_combo.addItem(display_name, provider.id)
                index = self.provider_combo.count() - 1
                model = self.provider_combo.model()
                item = model.item(index)
                if item:
                    item.setForeground(QColor("gray"))

        # If no providers available, show helpful message
        if available_count == 0:
            self.provider_combo.addItem("(No providers installed)", None)

    def _refresh_providers(self, silent: bool = False):
        """Refresh the provider list to detect newly installed packages."""
        import importlib

        from PySide6.QtWidgets import QMessageBox

        current_provider = self.provider_combo.currentData()

        # Invalidate import caches so newly installed packages can be discovered
        # without unloading modules that may already be in use elsewhere.
        importlib.invalidate_caches()

        # Block signals during repopulation to prevent install dialog from
        # opening when restoring the previous selection.
        self.provider_combo.blockSignals(True)
        try:
            # Repopulate combo
            self._populate_providers()
            self._update_help_text()

            # Try to restore previous selection
            for i in range(self.provider_combo.count()):
                if self.provider_combo.itemData(i) == current_provider:
                    self.provider_combo.setCurrentIndex(i)
                    break
        finally:
            self.provider_combo.blockSignals(False)

        # Show success message (suppressed when called silently after an in-app install)
        if not silent:
            available_providers = [p for p in get_all_providers() if p.available]
            if available_providers:
                provider_names = ", ".join([p.name for p in available_providers])
                QMessageBox.information(
                    self,
                    "Providers Refreshed",
                    f"Available providers: {provider_names}\n\n"
                    f"If you just installed a provider, it should now appear in the list.",
                )
            else:
                QMessageBox.information(
                    self,
                    "No Providers Found",
                    "No database providers are currently installed.\n\n"
                    "Install providers with:\n"
                    "  pip install vector-inspector[recommended]\n\n"
                    "Or install individual providers:\n"
                    "  pip install vector-inspector[chromadb]\n"
                    "  pip install vector-inspector[qdrant]",
                )

    def _update_help_text(self):
        """Update help text based on available providers."""
        providers = get_all_providers()
        available_providers = [p for p in providers if p.available]
        unavailable_count = len(providers) - len(available_providers)

        if not available_providers:
            self.provider_help_label.setText(
                "💡 No providers installed. Install with: pip install vector-inspector[recommended]"
            )
        elif unavailable_count > 0:
            self.provider_help_label.setText(
                f"💡 {len(available_providers)} provider(s) available. "
                f"To install more: pip install vector-inspector[all]"
            )
        else:
            self.provider_help_label.setText(f"✓ All providers installed ({len(available_providers)} available)")

    def _on_provider_changed(self):
        """Handle provider selection change."""
        provider_id = self.provider_combo.currentData()

        # Check if this is a placeholder (no providers installed)
        if provider_id is None:
            return

        # Check if provider is available
        provider_info = get_provider_info(provider_id)
        if provider_info and not provider_info.available:
            # Offer to install the provider in-app
            from vector_inspector.ui.dialogs.provider_install_dialog import ProviderInstallDialog

            dlg = ProviderInstallDialog(provider_info, parent=self)
            # After a successful install, silently refresh the combo so the
            # newly-installed provider shows as available immediately.
            dlg.provider_installed.connect(lambda _pid: self._refresh_providers(silent=True))
            dlg.exec()

            # Switch back to the first available provider if this one is
            # still not installed (user cancelled or install failed).
            fresh_info = get_provider_info(provider_id)
            if fresh_info and not fresh_info.available:
                for i in range(self.provider_combo.count()):
                    check_id = self.provider_combo.itemData(i)
                    check_info = get_provider_info(check_id) if check_id else None
                    if check_info and check_info.available:
                        self.provider_combo.setCurrentIndex(i)
                        return

            # If no available providers, keep selection but don't proceed
            return

        self.provider = provider_id

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

    def _load_last_connection(self):
        """Load and populate the last connection configuration."""
        last_config = self.settings_service.get_last_connection()
        if not last_config:
            return

        # Set provider — block signals so loading a saved provider never
        # triggers the install-dialog prompt. The user can still switch
        # providers manually after the dialog opens.
        provider = last_config.get("provider", "chromadb")
        index = self.provider_combo.findData(provider)
        if index >= 0:
            self.provider_combo.blockSignals(True)
            self.provider_combo.setCurrentIndex(index)
            self.provider_combo.blockSignals(False)
            self.provider = provider

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

    _raw_connection: Optional[VectorDBConnection]
    connection: Optional[VectorDBConnection]
    loading_dialog: LoadingDialog
    settings_service: SettingsService
    connection_thread: Optional[ConnectionThread]

    def __init__(self, connection: Optional[VectorDBConnection] = None, parent=None):
        super().__init__(parent)
        self._raw_connection = None
        self.connection = connection
        self.loading_dialog = LoadingDialog("Connecting to database...", self)
        self.settings_service = SettingsService()
        self.connection_thread = None
        self._setup_ui()
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

                QMessageBox.warning(self, "Missing API Key", "Pinecone requires an API key to connect.")
                return
            # Lazy import connection class
            try:
                ConnectionClass = get_connection_class("pinecone")
                self.connection = ConnectionClass(api_key=api_key)
            except ImportError as e:
                QMessageBox.critical(
                    self,
                    "Provider Not Installed",
                    f"Pinecone provider is not installed.\n\n{e!s}\n\n"
                    f"Install with: pip install vector-inspector[pinecone]",
                )
                return
        elif provider == "qdrant":
            try:
                ConnectionClass = get_connection_class("qdrant")
                if conn_type == "persistent":
                    self.connection = ConnectionClass(path=config.get("path"))
                elif conn_type == "http":
                    self.connection = ConnectionClass(
                        host=config.get("host"),
                        port=config.get("port"),
                        api_key=config.get("api_key"),
                    )
                else:  # ephemeral/memory
                    self.connection = ConnectionClass()
            except ImportError as e:
                QMessageBox.critical(
                    self,
                    "Provider Not Installed",
                    f"Qdrant provider is not installed.\n\n{e!s}\n\nInstall with: pip install vector-inspector[qdrant]",
                )
                return
        elif provider == "pgvector":
            try:
                ConnectionClass = get_connection_class("pgvector")
                self.connection = ConnectionClass(
                    host=config.get("host", "localhost"),
                    port=config.get("port", 5432),
                    database=config.get("database", "subtitles"),
                    user=config.get("user", "postgres"),
                    password=config.get("password", "postgres"),
                )
            except ImportError as e:
                QMessageBox.critical(
                    self,
                    "Provider Not Installed",
                    f"PostgreSQL/pgvector provider is not installed.\n\n{e!s}\n\n"
                    f"Install with: pip install vector-inspector[pgvector]",
                )
                return
        else:  # chromadb
            try:
                ConnectionClass = get_connection_class("chromadb")
                if conn_type == "persistent":
                    self.connection = ConnectionClass(path=config.get("path"))
                elif conn_type == "http":
                    self.connection = ConnectionClass(host=config.get("host"), port=config.get("port"))
                else:  # ephemeral
                    self.connection = ConnectionClass()
            except ImportError as e:
                QMessageBox.critical(
                    self,
                    "Provider Not Installed",
                    f"ChromaDB provider is not installed.\n\n{e!s}\n\n"
                    f"Install with: pip install vector-inspector[chromadb]",
                )
                return

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
