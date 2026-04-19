"""Profile management UI for saved connection profiles."""

import contextlib
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.provider_detection import get_all_providers, get_provider_info
from vector_inspector.services.profile_service import ConnectionProfile, ProfileService


class TestConnectionThread(QThread):
    """Background thread for testing database connections."""

    finished = Signal(bool, str)  # success, message
    error = Signal(str)  # error_message

    def __init__(self, connection, provider: str, parent=None):
        """
        Initialize test connection thread.

        Args:
            connection: The VectorDBConnection instance to test
            provider: Provider name (for database fetching)
            parent: Parent QObject
        """
        super().__init__(parent)
        self.connection = connection
        self.provider = provider

    def run(self):
        """Run the connection test in background."""
        try:
            success = self.connection.connect()
            if success:
                self.finished.emit(True, "Connection test successful!")
            else:
                self.finished.emit(False, "Connection test failed.")
        except Exception as e:
            self.error.emit(f"Connection test error: {e}")


class ProfileManagerPanel(QWidget):
    """Panel for managing saved connection profiles.

    Signals:
        connect_profile: Emitted when user wants to connect to a profile (profile_id)
        profile_selected: Emitted when a profile is selected in the list (profile_id)
    """

    connect_profile = Signal(str)  # profile_id
    profile_selected = Signal(str)  # profile_id

    profile_service: ProfileService
    profile_list: QListWidget
    new_profile_btn: QPushButton
    connect_btn: QPushButton
    edit_btn: QPushButton
    delete_btn: QPushButton
    test_thread: Optional[TestConnectionThread]

    def __init__(self, profile_service: ProfileService, parent=None):
        """
        Initialize profile manager panel.

        Args:
            profile_service: The ProfileService instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.profile_service = profile_service
        self.test_thread = None

        self._setup_ui()
        self._connect_signals()
        self._refresh_profiles()

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Saved Profiles")
        header_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        # New profile button
        self.new_profile_btn = QPushButton("+")
        self.new_profile_btn.setMaximumWidth(30)
        self.new_profile_btn.setToolTip("Create new profile")
        self.new_profile_btn.clicked.connect(self._create_profile)
        header_layout.addWidget(self.new_profile_btn)

        layout.addLayout(header_layout)

        # Profile list
        self.profile_list = QListWidget()
        self.profile_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.profile_list.customContextMenuRequested.connect(self._show_context_menu)
        self.profile_list.itemDoubleClicked.connect(self._on_profile_double_clicked)
        layout.addWidget(self.profile_list)

        # Action buttons
        button_layout = QHBoxLayout()

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self._connect_selected_profile)
        button_layout.addWidget(self.connect_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setEnabled(False)
        self.edit_btn.clicked.connect(self._edit_selected_profile)
        button_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._delete_selected_profile)
        button_layout.addWidget(self.delete_btn)

        layout.addLayout(button_layout)

    def _connect_signals(self):
        """Connect to profile service signals and UI events."""
        self.profile_service.profile_added.connect(self._refresh_profiles)
        self.profile_service.profile_updated.connect(self._refresh_profiles)
        self.profile_service.profile_deleted.connect(self._refresh_profiles)
        self.profile_list.currentItemChanged.connect(self._on_profile_selection_changed)

    def _on_profile_selection_changed(self, current, _):
        has_selection = current is not None
        self.connect_btn.setEnabled(has_selection)
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        # Emit profile_selected for single-click selection so other views can preview
        if has_selection:
            try:
                profile_id = current.data(Qt.ItemDataRole.UserRole)
                if profile_id:
                    self.profile_selected.emit(profile_id)
            except Exception:
                pass

    def _refresh_profiles(self):
        """Refresh the profile list."""
        self.profile_list.clear()

        profiles = self.profile_service.get_all_profiles()
        for profile in profiles:
            item = QListWidgetItem(f"{profile.name} ({profile.provider})")
            item.setData(Qt.ItemDataRole.UserRole, profile.id)
            self.profile_list.addItem(item)
        if self.profile_list.currentItem() is None:
            self.connect_btn.setEnabled(False)
            self.edit_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)

    def _on_profile_double_clicked(self, item: QListWidgetItem):
        """Handle profile double-click to connect."""
        profile_id = item.data(Qt.ItemDataRole.UserRole)
        if profile_id:
            self.connect_profile.emit(profile_id)

    def _connect_selected_profile(self):
        """Connect to the selected profile."""
        current_item = self.profile_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a profile to connect.")
            return

        profile_id = current_item.data(Qt.ItemDataRole.UserRole)
        self.connect_profile.emit(profile_id)

    def _edit_selected_profile(self):
        """Edit the selected profile."""
        current_item = self.profile_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a profile to edit.")
            return

        profile_id = current_item.data(Qt.ItemDataRole.UserRole)
        profile = self.profile_service.get_profile(profile_id)
        if not profile:
            return

        dialog = ProfileEditorDialog(self.profile_service, profile, parent=self)
        dialog.exec()

    def _delete_selected_profile(self):
        """Delete the selected profile."""
        current_item = self.profile_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a profile to delete.")
            return

        profile_id = current_item.data(Qt.ItemDataRole.UserRole)
        profile = self.profile_service.get_profile(profile_id)
        if not profile:
            return

        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{profile.name}'?\n\nThis will also delete any saved credentials.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.profile_service.delete_profile(profile_id)

    def _create_profile(self):
        """Create a new profile."""
        dialog = ProfileEditorDialog(self.profile_service, parent=self)
        dialog.exec()

    def _show_context_menu(self, pos):
        """Show context menu for profile."""
        item = self.profile_list.itemAt(pos)
        if not item:
            return

        profile_id = item.data(Qt.ItemDataRole.UserRole)
        profile = self.profile_service.get_profile(profile_id)
        if not profile:
            return

        menu = QMenu(self)

        connect_action = menu.addAction("Connect")
        connect_action.triggered.connect(lambda: self.connect_profile.emit(profile_id))

        menu.addSeparator()

        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(lambda: self._edit_profile(profile_id))

        duplicate_action = menu.addAction("Duplicate")
        duplicate_action.triggered.connect(lambda: self._duplicate_profile(profile_id))

        menu.addSeparator()

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self._delete_profile(profile_id))

        menu.exec(self.profile_list.mapToGlobal(pos))

    def _edit_profile(self, profile_id: str):
        """Edit a profile."""
        profile = self.profile_service.get_profile(profile_id)
        if profile:
            dialog = ProfileEditorDialog(self.profile_service, profile, parent=self)
            dialog.exec()

    def _duplicate_profile(self, profile_id: str):
        """Duplicate a profile."""
        profile = self.profile_service.get_profile(profile_id)
        if not profile:
            return

        from PySide6.QtWidgets import QInputDialog

        new_name, ok = QInputDialog.getText(
            self,
            "Duplicate Profile",
            "Enter name for duplicated profile:",
            text=f"{profile.name} (Copy)",
        )

        if ok and new_name:
            self.profile_service.duplicate_profile(profile_id, new_name)

    def _delete_profile(self, profile_id: str):
        """Delete a profile."""
        profile = self.profile_service.get_profile(profile_id)
        if not profile:
            return

        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{profile.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.profile_service.delete_profile(profile_id)


class DatabaseFetchThread(QThread):
    """Background thread to fetch database names using PgVectorConnection."""

    finished = Signal(list, str)  # (databases, error)

    def __init__(self, host: str, port: int, user: str, password: str, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def run(self):
        try:
            from vector_inspector.core.connections.pgvector_connection import PgVectorConnection

            conn = PgVectorConnection(
                host=self.host,
                port=int(self.port),
                database="postgres",
                user=self.user,
                password=self.password,
            )
            if not conn.connect():
                self.finished.emit([], "Failed to connect to server")
                return

            dbs = conn.list_databases()
            conn.disconnect()
            self.finished.emit(dbs or [], "")
        except Exception as e:
            self.finished.emit([], str(e))


class ProfileEditorDialog(QDialog):
    """Dialog for creating/editing connection profiles."""

    def __init__(
        self,
        profile_service: ProfileService,
        profile: Optional[ConnectionProfile] = None,
        parent=None,
    ):
        """
        Initialize profile editor dialog.

        Args:
            profile_service: The ProfileService instance
            profile: Existing profile to edit (None for new profile)
            parent: Parent widget
        """
        super().__init__(parent)
        self.profile_service = profile_service
        self.profile = profile
        self.is_edit_mode = profile is not None
        self.test_thread = None

        self.setWindowTitle("Edit Profile" if self.is_edit_mode else "New Profile")
        self.setMinimumWidth(500)

        self._setup_ui()

        if self.is_edit_mode:
            self._load_profile_data()

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Profile name
        self.name_input = QLineEdit()
        form_layout.addRow("Profile Name:", self.name_input)

        # Provider — populated with availability detection
        self.provider_combo = QComboBox()
        self._populate_providers()
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form_layout.addRow("Provider:", self.provider_combo)

        layout.addLayout(form_layout)

        # Connection type group
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

        # Ensure the Connection Type group hugs the top and doesn't get
        # pushed around when other form rows are hidden or shown.
        type_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(type_group)
        layout.setAlignment(type_group, Qt.AlignTop)

        # Connection details
        details_group = QGroupBox("Connection Details")
        details_layout = QFormLayout()

        # Persistent path
        self.path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_browse_btn = QPushButton("Browse...")
        self.path_browse_btn.clicked.connect(self._browse_for_path)
        self.path_layout.addWidget(self.path_input)
        self.path_layout.addWidget(self.path_browse_btn)
        details_layout.addRow("Path:", self.path_layout)

        # HTTP settings
        self.host_input = QLineEdit("localhost")
        details_layout.addRow("Host:", self.host_input)

        self.port_input = QLineEdit("8000")
        details_layout.addRow("Port:", self.port_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        details_layout.addRow("API Key:", self.api_key_input)

        # gRPC toggle (Weaviate only)
        self.grpc_checkbox = QCheckBox("Use gRPC (Weaviate only)")
        self.grpc_checkbox.setChecked(True)
        details_layout.addRow("gRPC:", self.grpc_checkbox)

        # Weaviate cloud selector (only for Weaviate provider)
        self.weaviate_cloud_checkbox = QCheckBox("Weaviate Cloud (WCD)")
        self.weaviate_cloud_checkbox.setToolTip("When checked, use a cloud cluster URL (no port) and API key.")
        self.weaviate_cloud_checkbox.setChecked(False)
        self.weaviate_cloud_checkbox.toggled.connect(self._on_weaviate_cloud_toggled)
        details_layout.addRow("Cloud:", self.weaviate_cloud_checkbox)

        # (Database field moved to end of form)

        self.user_input = QLineEdit()
        details_layout.addRow("User:", self.user_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        details_layout.addRow("Password:", self.password_input)

        # PgVector/Postgres specific: editable combo + refresh (placed last)
        self.database_input = QComboBox()
        self.database_input.setEditable(True)
        db_layout = QHBoxLayout()
        db_layout.addWidget(self.database_input)
        self.db_refresh_btn = QPushButton("⟳")
        self.db_refresh_btn.setToolTip("Refresh database list")
        self.db_refresh_btn.setMaximumWidth(30)
        self.db_refresh_btn.clicked.connect(lambda: self._fetch_databases())
        db_layout.addWidget(self.db_refresh_btn)
        self.db_status_label = QLabel("")
        self.db_status_label.setStyleSheet("color: gray; padding-left: 6px;")
        db_layout.addWidget(self.db_status_label)
        # Provide a clear hint: user should click "Test Connection" to fetch DB list
        line = self.database_input.lineEdit()
        if line is not None:
            line.setPlaceholderText("Click 'Test Connection' to fetch databases")
        # Disable the refresh button until a fetch has occurred
        self.db_refresh_btn.setEnabled(False)
        # Small hint in the status label
        self.db_status_label.setText("Click 'Test Connection' to load databases")
        details_layout.addRow("Database:", db_layout)
        # Keep reference to the details layout so we can toggle labels too
        self.db_layout = db_layout

        details_group.setLayout(details_layout)
        self.details_layout = details_layout
        layout.addWidget(details_group)

        # Test connection button
        self.test_btn = QPushButton("Test Connection")
        self.test_btn.clicked.connect(self._test_connection)
        layout.addWidget(self.test_btn)

        # Buttons
        button_layout = QHBoxLayout()

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_profile)
        button_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        # Initial state
        # Ensure provider-specific visibility and type state are applied
        self._on_provider_changed()
        self._on_type_changed()
        # Make details_group expand so the Connection Type group remains
        # anchored to the top when rows are hidden or shown.
        try:
            details_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            layout.setStretch(layout.indexOf(type_group), 0)
            layout.setStretch(layout.indexOf(details_group), 1)
        except Exception:
            pass

    def _populate_providers(self) -> None:
        """Populate provider combo with availability-aware items."""
        self.provider_combo.clear()
        available_count = 0
        display_names = {
            "chromadb": "ChromaDB",
            "qdrant": "Qdrant",
            "pgvector": "PgVector/PostgreSQL",
            "pinecone": "Pinecone",
            "lancedb": "LanceDB",
            "weaviate": "Weaviate",
            "milvus": "Milvus",
        }
        for provider in get_all_providers():
            label = display_names.get(provider.id, provider.name)
            if provider.available:
                self.provider_combo.addItem(label, provider.id)
                available_count += 1
            else:
                self.provider_combo.addItem(f"{label} (not installed)", provider.id)
                index = self.provider_combo.count() - 1
                item = self.provider_combo.model().item(index)
                if item:
                    item.setForeground(QColor("gray"))
        if available_count == 0:
            self.provider_combo.addItem("(No providers installed)", None)

    def _on_provider_changed(self):
        """Handle provider change."""
        provider = self.provider_combo.currentData()

        # If the selected provider is not installed, open the install dialog.
        provider_info = get_provider_info(provider) if provider else None
        if provider_info and not provider_info.available:
            from vector_inspector.ui.dialogs.provider_install_dialog import ProviderInstallDialog

            dlg = ProviderInstallDialog(provider_info, parent=self)
            dlg.provider_installed.connect(lambda _pid: self._populate_providers())
            dlg.exec()
            # If still not installed after dialog closes, fall back to first available.
            fresh = get_provider_info(provider)
            if fresh and not fresh.available:
                for i in range(self.provider_combo.count()):
                    check_id = self.provider_combo.itemData(i)
                    check_info = get_provider_info(check_id) if check_id else None
                    if check_info and check_info.available:
                        self.provider_combo.blockSignals(True)
                        self.provider_combo.setCurrentIndex(i)
                        self.provider_combo.blockSignals(False)
                        provider = check_id
                        break
                else:
                    return

        # ---------------------------------------------------------------
        # Original provider-change logic below
        # ---------------------------------------------------------------

        # Set a conservative baseline: hide controls that are only relevant to
        # specific providers. Each branch will make the controls visible as
        # required so the form shows only what's needed.
        with contextlib.suppress(Exception):
            self._set_field_and_label_visible(self.path_layout, False)
            self._set_field_and_label_visible(self.host_input, False)
            self._set_field_and_label_visible(self.port_input, False)
            self._set_field_and_label_visible(self.api_key_input, False)
            self._set_field_and_label_visible(self.db_layout, False)
            self._set_field_and_label_visible(self.user_input, False)
            self._set_field_and_label_visible(self.password_input, False)
            self._set_field_and_label_visible(self.grpc_checkbox, False)
            self._set_field_and_label_visible(self.weaviate_cloud_checkbox, False)
            # gRPC and WCD are handled above

        # Reset persistent radio button text (may be changed for specific providers)
        self.persistent_radio.setText("Persistent (Local File)")

        # Update default port
        if provider == "qdrant":
            if self.port_input.text() == "8000":
                self.port_input.setText("6333")
        elif provider == "chromadb":
            if self.port_input.text() == "6333":
                self.port_input.setText("8000")
        elif provider == "pgvector" and self.port_input.text() in ("8000", "6333"):
            self.port_input.setText("5432")
        elif provider == "weaviate" and self.port_input.text() in ("8000", "6333", "5432"):
            self.port_input.setText("8080")

        if provider == "lancedb":
            self.persistent_radio.setEnabled(True)
            self.persistent_radio.setChecked(True)
            self.http_radio.setEnabled(False)
            self.ephemeral_radio.setEnabled(False)
            # Visible: path controls only
            with contextlib.suppress(Exception):
                self._set_field_and_label_visible(self.path_layout, True)
                self.path_input.setEnabled(True)
                self.path_browse_btn.setEnabled(True)
        elif provider == "pinecone":
            self.persistent_radio.setEnabled(False)
            self.http_radio.setEnabled(True)
            self.http_radio.setChecked(True)
            self.ephemeral_radio.setEnabled(False)
            # Pinecone uses cloud API key flow; show API key only
            with contextlib.suppress(Exception):
                self._set_field_and_label_visible(self.api_key_input, True)
                self.api_key_input.setEnabled(True)
                self._set_field_and_label_visible(self.path_layout, False)
                self._set_field_and_label_visible(self.host_input, False)
                self._set_field_and_label_visible(self.port_input, False)
        elif provider == "weaviate":
            # Weaviate supports HTTP (local/cloud) and Persistent (embedded)
            self.persistent_radio.setEnabled(True)
            self.persistent_radio.setText("Embedded (In-Process)")
            self.http_radio.setEnabled(True)
            self.ephemeral_radio.setEnabled(False)
            # Weaviate may use path (embedded) or host/port/api_key (HTTP/cloud).
            # Show all Weaviate-relevant controls; the type handlers will
            # enable/disable them according to connection type.
            with contextlib.suppress(Exception):
                self._set_field_and_label_visible(self.path_layout, True)
                self._set_field_and_label_visible(self.host_input, True)
                self._set_field_and_label_visible(self.port_input, True)
                self._set_field_and_label_visible(self.api_key_input, True)
                self.grpc_checkbox.setVisible(True)
                self.weaviate_cloud_checkbox.setVisible(True)

            is_persistent = self.persistent_radio.isChecked()
            if is_persistent:
                # Embedded mode: enable path for persistence directory
                self.path_input.setEnabled(True)
                self.path_browse_btn.setEnabled(True)
                self.host_input.setEnabled(False)
                self.port_input.setEnabled(False)
                self.api_key_input.setEnabled(False)
                # disable gRPC and cloud selector when embedded
                try:
                    self.grpc_checkbox.setEnabled(False)
                except Exception:
                    pass
                try:
                    self.weaviate_cloud_checkbox.setEnabled(False)
                except Exception:
                    pass
            else:
                # HTTP mode: enable host/port/api_key
                self.path_input.setEnabled(False)
                self.path_browse_btn.setEnabled(False)
                self.host_input.setEnabled(True)
                self.port_input.setEnabled(True)
                self.api_key_input.setEnabled(True)
                # enable gRPC for HTTP mode
                try:
                    self.grpc_checkbox.setEnabled(True)
                except Exception:
                    pass
                try:
                    self.weaviate_cloud_checkbox.setEnabled(True)
                except Exception:
                    pass

            self.database_input.setEnabled(False)
            self.user_input.setEnabled(False)
            self.password_input.setEnabled(False)
            # Hide DB fetch UI for Weaviate
            with contextlib.suppress(Exception):
                self._set_field_and_label_visible(self.db_layout, False)
        elif provider == "pgvector":
            self.persistent_radio.setEnabled(False)
            self.http_radio.setEnabled(True)
            self.http_radio.setChecked(True)
            self.ephemeral_radio.setEnabled(False)
            self.path_input.setEnabled(False)
            self.path_browse_btn.setEnabled(False)
            self.host_input.setEnabled(True)
            self.port_input.setEnabled(True)
            self.api_key_input.setEnabled(False)
            self.database_input.setEnabled(True)
            self.user_input.setEnabled(True)
            self.password_input.setEnabled(True)
            # Show Postgres-related controls
            with contextlib.suppress(Exception):
                self._set_field_and_label_visible(self.host_input, True)
                self._set_field_and_label_visible(self.port_input, True)
                self._set_field_and_label_visible(self.db_layout, True)
                self._set_field_and_label_visible(self.user_input, True)
                self._set_field_and_label_visible(self.password_input, True)
                self._set_field_and_label_visible(self.api_key_input, False)
                self._set_field_and_label_visible(self.path_layout, False)
        else:
            self.persistent_radio.setEnabled(True)
            self.http_radio.setEnabled(True)
            self.ephemeral_radio.setEnabled(True)
            is_http = self.http_radio.isChecked()
            # Default: show host/port and API key only when relevant
            with contextlib.suppress(Exception):
                self._set_field_and_label_visible(self.host_input, True)
                self._set_field_and_label_visible(self.port_input, True)
                self._set_field_and_label_visible(self.api_key_input, provider == "qdrant")
                if provider == "qdrant":
                    self.api_key_input.setEnabled(is_http)
                # Hide DB-related controls for generic providers
                self._set_field_and_label_visible(self.db_layout, False)
                self._set_field_and_label_visible(self.user_input, False)
                self._set_field_and_label_visible(self.password_input, False)
            self._on_type_changed()

    def _on_type_changed(self):
        """Handle connection type change."""
        is_persistent = self.persistent_radio.isChecked()
        is_http = self.http_radio.isChecked()

        provider = self.provider_combo.currentData()

        if provider == "lancedb":
            self.path_input.setEnabled(True)
            self.path_browse_btn.setEnabled(True)
            self.host_input.setEnabled(False)
            self.port_input.setEnabled(False)
            self.api_key_input.setEnabled(False)
            self.database_input.setEnabled(False)
            self.user_input.setEnabled(False)
            self.password_input.setEnabled(False)
        elif provider == "pinecone":
            self.path_input.setEnabled(False)
            self.path_browse_btn.setEnabled(False)
            self.host_input.setEnabled(False)
            self.port_input.setEnabled(False)
            self.api_key_input.setEnabled(True)
        elif provider == "weaviate":
            # Embedded mode uses path, HTTP mode uses host/port/api_key
            self.path_input.setEnabled(is_persistent)
            self.path_browse_btn.setEnabled(is_persistent)
            self.host_input.setEnabled(is_http)
            self.port_input.setEnabled(is_http)
            self.api_key_input.setEnabled(is_http)
            # gRPC checkbox enabled only when HTTP selected
            try:
                self.grpc_checkbox.setEnabled(is_http)
            except Exception:
                pass
            try:
                self.weaviate_cloud_checkbox.setEnabled(is_http)
            except Exception:
                pass
            self.database_input.setEnabled(False)
            self.user_input.setEnabled(False)
            self.password_input.setEnabled(False)
        elif provider == "pgvector":
            self.path_input.setEnabled(False)
            self.path_browse_btn.setEnabled(False)
            self.host_input.setEnabled(is_http)
            self.port_input.setEnabled(is_http)
            self.api_key_input.setEnabled(False)
            self.database_input.setEnabled(is_http)
            self.user_input.setEnabled(is_http)
            self.password_input.setEnabled(is_http)
        else:
            self.path_input.setEnabled(is_persistent)
            self.path_browse_btn.setEnabled(is_persistent)
            self.host_input.setEnabled(is_http)
            self.port_input.setEnabled(is_http)
            self.api_key_input.setEnabled(is_http and provider == "qdrant")

    def _set_field_and_label_visible(self, field_obj, visible: bool):
        """Show/hide a form field (widget or layout) and its label in the details layout.

        This covers rows where the field is a QWidget (e.g. QLineEdit) or a
        QLayout (e.g. HBox containing multiple widgets). If the row cannot be
        found the method will fall back to setting visibility on the object
        itself.
        """
        with contextlib.suppress(Exception):
            layout = getattr(self, "details_layout", None)
            if layout is None:
                # fallback
                try:
                    field_obj.setVisible(visible)
                except Exception:
                    pass
                return

            # iterate rows to find matching field
            rows = layout.rowCount()
            for row in range(rows):
                field_item = layout.itemAt(row, QFormLayout.FieldRole)
                label_item = layout.itemAt(row, QFormLayout.LabelRole)
                if field_item is None:
                    continue
                # widget field
                w = field_item.widget()
                if w is not None:
                    if w is field_obj:
                        w.setVisible(visible)
                        if label_item and label_item.widget():
                            label_item.widget().setVisible(visible)
                        return
                    # if field_obj is a child widget inside this widget
                    if isinstance(w, QWidget):
                        # check children
                        if field_obj in w.findChildren(QWidget):
                            w.setVisible(visible)
                            if label_item and label_item.widget():
                                label_item.widget().setVisible(visible)
                            return
                else:
                    # layout field
                    sub_layout = field_item.layout()
                    if sub_layout is None:
                        continue
                    if sub_layout is field_obj:
                        # toggle all child widgets in the layout
                        for i in range(sub_layout.count()):
                            it = sub_layout.itemAt(i)
                            try:
                                child = it.widget()
                                if child:
                                    child.setVisible(visible)
                            except Exception:
                                pass
                        if label_item and label_item.widget():
                            label_item.widget().setVisible(visible)
                        return
                    # check children of sub_layout
                    for i in range(sub_layout.count()):
                        it = sub_layout.itemAt(i)
                        try:
                            child = it.widget()
                            if child is field_obj:
                                # toggle all children so row looks consistent
                                for j in range(sub_layout.count()):
                                    c = sub_layout.itemAt(j).widget()
                                    if c:
                                        c.setVisible(visible)
                                if label_item and label_item.widget():
                                    label_item.widget().setVisible(visible)
                                return
                        except Exception:
                            pass

            # fallback: try setting visibility directly
            try:
                field_obj.setVisible(visible)
            except Exception:
                pass

    def _browse_for_path(self):
        """Browse for persistent storage path."""
        path = QFileDialog.getExistingDirectory(self, "Select Database Directory", self.path_input.text())
        if path:
            self.path_input.setText(path)

    def _on_weaviate_cloud_toggled(self, is_cloud: bool):
        """Handle Weaviate cloud checkbox toggle.

        When cloud mode is enabled:
        - Disable port field (cloud URLs don't use ports)
        - Disable gRPC checkbox (client automatically infers gRPC for cloud)
        - Update host field placeholder to show cloud URL format
        """
        if self.provider_combo.currentData() == "weaviate" and self.http_radio.isChecked():
            if is_cloud:
                # Cloud mode: disable port and gRPC (automatically handled by client)
                self.port_input.setEnabled(False)
                self.port_input.setText("")  # Clear port
                try:
                    self.grpc_checkbox.setEnabled(False)
                    self.grpc_checkbox.setToolTip(
                        "gRPC is automatically inferred by the Weaviate client for cloud connections"
                    )
                except Exception:
                    pass
                # Update host field placeholder
                self.host_input.setPlaceholderText("cluster-id.weaviate.cloud")
            else:
                # Local/self-hosted mode: enable port and gRPC
                self.port_input.setEnabled(True)
                if not self.port_input.text():
                    self.port_input.setText("8080")  # Restore default port
                try:
                    self.grpc_checkbox.setEnabled(True)
                    self.grpc_checkbox.setToolTip("Use gRPC (Weaviate only)")
                except Exception:
                    pass
                self.host_input.setPlaceholderText("localhost")

    def _load_profile_data(self):
        """Load existing profile data into form."""
        if not self.profile:
            return

        # Get profile with credentials
        profile_data = self.profile_service.get_profile_with_credentials(self.profile.id)
        if not profile_data:
            return

        self.name_input.setText(profile_data["name"])

        # Set provider — block signals so loading a saved profile never
        # triggers the install-dialog prompt.
        index = self.provider_combo.findData(profile_data["provider"])
        if index >= 0:
            self.provider_combo.blockSignals(True)
            self.provider_combo.setCurrentIndex(index)
            self.provider_combo.blockSignals(False)

        config = profile_data.get("config", {})
        conn_type = config.get("type", "persistent")

        # Set connection type
        if conn_type == "cloud":
            # Cloud connection. For Pinecone this is a cloud API key flow.
            # For Weaviate cloud (WCD) we treat it as an HTTP/cloud URL.
            self.http_radio.setChecked(True)
            if profile_data.get("provider") == "weaviate":
                try:
                    self.weaviate_cloud_checkbox.setChecked(True)
                    # Store full cluster URL in host input for editing
                    self.host_input.setText(config.get("url", ""))
                    # Port is not used for cloud URLs
                    self.port_input.setText("")
                    # Restore gRPC preference
                    self.grpc_checkbox.setChecked(bool(config.get("use_grpc", True)))
                except Exception:
                    pass
        elif conn_type == "persistent":
            self.persistent_radio.setChecked(True)
            self.path_input.setText(config.get("path", ""))
        elif conn_type == "http":
            self.http_radio.setChecked(True)
            self.host_input.setText(config.get("host", "localhost"))
            # If port was not set in config, keep the input empty
            port_val = config.get("port")
            self.port_input.setText(str(port_val) if port_val is not None else "")
            # restore gRPC preference if present
            try:
                self.grpc_checkbox.setChecked(bool(config.get("use_grpc", True)))
            except Exception:
                pass
            # Ensure weaviate cloud checkbox is unchecked for regular HTTP mode
            if profile_data.get("provider") == "weaviate":
                try:
                    self.weaviate_cloud_checkbox.setChecked(False)
                except Exception:
                    pass
            # PgVector HTTP-style config may include DB credentials
            self.database_input.setCurrentText(config.get("database", ""))
            self.user_input.setText(config.get("user", ""))
        else:
            self.ephemeral_radio.setChecked(True)

        # Load credentials
        credentials = profile_data.get("credentials", {})
        if "api_key" in credentials:
            self.api_key_input.setText(credentials["api_key"])
        # pgvector may store password in credentials
        if "password" in credentials:
            self.password_input.setText(credentials["password"])

    def _test_connection(self):
        """Test the connection with current settings."""
        # Get config
        config = self._get_config()
        provider = self.provider_combo.currentData()

        # Create connection
        from vector_inspector.core.connections.chroma_connection import ChromaDBConnection
        from vector_inspector.core.connections.lancedb_connection import LanceDBConnection
        from vector_inspector.core.connections.pgvector_connection import PgVectorConnection
        from vector_inspector.core.connections.pinecone_connection import PineconeConnection
        from vector_inspector.core.connections.qdrant_connection import QdrantConnection
        from vector_inspector.core.connections.weaviate_connection import WeaviateConnection

        try:
            if provider == "pinecone":
                api_key = self.api_key_input.text()
                if not api_key:
                    QMessageBox.warning(self, "Missing API Key", "Pinecone requires an API key.")
                    return
                conn = PineconeConnection(api_key=api_key)
            elif provider == "chromadb":
                conn = ChromaDBConnection(**self._get_connection_kwargs(config))
            elif provider == "pgvector":
                # Use parsed config values to avoid int() on empty port
                conn = PgVectorConnection(
                    host=config.get("host"),
                    port=config.get("port"),
                    database=config.get("database"),
                    user=config.get("user"),
                    password=self.password_input.text(),
                )
            elif provider == "lancedb":
                conn = LanceDBConnection(uri=self.path_input.text())
            elif provider == "weaviate":
                # Build Weaviate connection parameters
                config_type = config.get("type")
                if config_type == "persistent":
                    # Embedded mode
                    conn = WeaviateConnection(
                        mode="embedded",
                        persistence_directory=self.path_input.text(),
                    )
                else:
                    # HTTP mode (local or cloud) - use config values (port may be None)
                    if config_type == "cloud":
                        # For cloud, use the cluster URL (host_input holds URL)
                        conn = WeaviateConnection(
                            url=config.get("url") or self.host_input.text(),
                            api_key=self.api_key_input.text() if self.api_key_input.text() else None,
                            use_grpc=self.grpc_checkbox.isChecked() if hasattr(self, "grpc_checkbox") else True,
                        )
                    else:
                        conn = WeaviateConnection(
                            host=config.get("host") if config_type == "http" else None,
                            port=config.get("port") if config_type == "http" else None,
                            url=config.get("url"),
                            api_key=self.api_key_input.text() if self.api_key_input.text() else None,
                            use_grpc=self.grpc_checkbox.isChecked() if hasattr(self, "grpc_checkbox") else True,
                        )
            else:
                conn = QdrantConnection(**self._get_connection_kwargs(config))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create connection: {e}")
            return

        # Cancel any existing test thread
        if self.test_thread and self.test_thread.isRunning():
            self.test_thread.quit()
            self.test_thread.wait()

        # Show progress dialog
        progress = QProgressDialog("Testing connection...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        # Create and start test thread
        self.test_thread = TestConnectionThread(conn, provider, self)
        self.test_thread.finished.connect(
            lambda success, msg: self._on_test_finished(success, msg, conn, provider, progress)
        )
        self.test_thread.error.connect(lambda err: self._on_test_error(err, progress))
        self.test_thread.start()

    def _on_test_finished(self, success: bool, message: str, conn, provider: str, progress: QProgressDialog) -> None:
        """Handle test connection completion."""
        progress.close()

        if success:
            QMessageBox.information(self, "Success", message)
            # For pgvector, populate database suggestions after a successful connect
            if provider == "pgvector":
                with contextlib.suppress(Exception):
                    self._fetch_databases()
            # Disconnect after successful test
            with contextlib.suppress(Exception):
                conn.disconnect()
        else:
            QMessageBox.warning(self, "Failed", message)

    def _on_test_error(self, error_message: str, progress: QProgressDialog) -> None:
        """Handle test connection error."""
        progress.close()
        QMessageBox.critical(self, "Error", error_message)

    def _get_config(self) -> dict:
        """Get configuration from form."""
        config = {}
        provider = self.provider_combo.currentData()

        # Pinecone uses cloud connection type
        if provider == "pinecone":
            config["type"] = "cloud"
        elif provider == "lancedb" or self.persistent_radio.isChecked():
            config["type"] = "persistent"
            config["path"] = self.path_input.text()
        elif self.http_radio.isChecked():
            config["type"] = "http"
            config["host"] = self.host_input.text()
            # Allow empty port (some Weaviate configs use URL without port)
            port_text = self.port_input.text().strip()
            if port_text:
                try:
                    config["port"] = int(port_text)
                except ValueError:
                    # Leave out invalid port to allow using URL-only connections
                    pass
            # If provider is Weaviate and cloud checkbox checked, mark as cloud
            if provider == "weaviate":
                try:
                    if self.weaviate_cloud_checkbox.isChecked():
                        config["type"] = "cloud"
                        # store cluster URL instead of host/port
                        config["url"] = self.host_input.text()
                        # ensure port not included
                        config.pop("port", None)
                except Exception:
                    pass
            if self.database_input.currentText():
                config["database"] = self.database_input.currentText()
            if self.user_input.text():
                config["user"] = self.user_input.text()
        # include gRPC preference for Weaviate regardless of http/cloud/persistent
        if provider == "weaviate":
            try:
                config["use_grpc"] = bool(self.grpc_checkbox.isChecked())
            except Exception:
                pass
        else:
            config["type"] = "ephemeral"

        return config

    def _get_connection_kwargs(self, config: dict) -> dict:
        """Get kwargs for creating connection."""
        kwargs = {}

        if config["type"] == "persistent":
            kwargs["path"] = config["path"]
        elif config["type"] == "http":
            kwargs["host"] = config["host"]
            kwargs["port"] = config["port"]
            if self.api_key_input.text():
                kwargs["api_key"] = self.api_key_input.text()
            # Include DB credentials if present (pgvector)
            if config.get("database"):
                kwargs["database"] = config.get("database")
            if config.get("user"):
                kwargs["user"] = config.get("user")
            if self.password_input.text():
                kwargs["password"] = self.password_input.text()

        return kwargs

    def _save_profile(self):
        """Save the profile."""
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a profile name.")
            return

        provider = self.provider_combo.currentData()
        config = self._get_config()

        # Get credentials
        credentials = {}
        if provider == "pinecone":
            # Pinecone always requires API key
            if self.api_key_input.text():
                credentials["api_key"] = self.api_key_input.text()
            else:
                QMessageBox.warning(self, "Missing API Key", "Pinecone requires an API key.")
                return
        elif self.api_key_input.text() and self.http_radio.isChecked():
            credentials["api_key"] = self.api_key_input.text()
        elif provider == "pgvector" and self.password_input.text() and self.http_radio.isChecked():
            credentials["password"] = self.password_input.text()

        if self.is_edit_mode:
            # Update existing profile
            self.profile_service.update_profile(
                self.profile.id,
                name=name,
                config=config,
                credentials=credentials if credentials else None,
            )
        else:
            # Create new profile
            self.profile_service.create_profile(
                name=name,
                provider=provider,
                config=config,
                credentials=credentials if credentials else None,
            )

        self.accept()

    def _fetch_databases(self):
        """Start background fetch of database names."""
        host = self.host_input.text()
        try:
            port = int(self.port_input.text())
        except Exception:
            port = 5432
        user = self.user_input.text()
        password = self.password_input.text()

        # Disable refresh while fetching
        with contextlib.suppress(Exception):
            self.db_refresh_btn.setEnabled(False)
            self.db_status_label.setText("Fetching…")

        self._db_thread = DatabaseFetchThread(host=host, port=port, user=user, password=password)
        self._db_thread.finished.connect(self._on_databases_fetched)
        self._db_thread.start()

    def _on_databases_fetched(self, dbs: list, error: str):
        with contextlib.suppress(Exception):
            self.db_refresh_btn.setEnabled(True)

        if dbs:
            # Preserve current text if set
            current = self.database_input.currentText() if hasattr(self.database_input, "currentText") else ""
            self.database_input.clear()
            self.database_input.addItems(dbs)
            if current:
                self.database_input.setCurrentText(current)
            self.db_status_label.setText(f"Loaded {len(dbs)} databases")
        else:
            # If fetch failed and we have an error, show a non-blocking warning
            if error:
                self.db_status_label.setText("Failed to fetch databases")
                QMessageBox.warning(self, "Database List", f"Could not fetch databases: {error}")
            else:
                self.db_status_label.setText("")
