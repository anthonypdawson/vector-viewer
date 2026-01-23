"""Profile management UI for saved connection profiles."""

from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QMenu, QMessageBox, QLabel, QDialog, QFormLayout,
    QLineEdit, QComboBox, QRadioButton, QButtonGroup, QGroupBox,
    QFileDialog, QCheckBox, QProgressDialog
)
from PySide6.QtCore import Qt, Signal

from vector_inspector.services.profile_service import ProfileService, ConnectionProfile


class ProfileManagerPanel(QWidget):
    """Panel for managing saved connection profiles.
    
    Signals:
        connect_profile: Emitted when user wants to connect to a profile (profile_id)
    """
    
    connect_profile = Signal(str)  # profile_id
    
    def __init__(self, profile_service: ProfileService, parent=None):
        """
        Initialize profile manager panel.
        
        Args:
            profile_service: The ProfileService instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.profile_service = profile_service
        
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
        self.profile_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.profile_list.customContextMenuRequested.connect(self._show_context_menu)
        self.profile_list.itemDoubleClicked.connect(self._on_profile_double_clicked)
        layout.addWidget(self.profile_list)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._connect_selected_profile)
        button_layout.addWidget(self.connect_btn)
        
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_selected_profile)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected_profile)
        button_layout.addWidget(self.delete_btn)
        
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """Connect to profile service signals."""
        self.profile_service.profile_added.connect(self._refresh_profiles)
        self.profile_service.profile_updated.connect(self._refresh_profiles)
        self.profile_service.profile_deleted.connect(self._refresh_profiles)
    
    def _refresh_profiles(self):
        """Refresh the profile list."""
        self.profile_list.clear()
        
        profiles = self.profile_service.get_all_profiles()
        for profile in profiles:
            item = QListWidgetItem(f"{profile.name} ({profile.provider})")
            item.setData(Qt.UserRole, profile.id)
            self.profile_list.addItem(item)
    
    def _on_profile_double_clicked(self, item: QListWidgetItem):
        """Handle profile double-click to connect."""
        profile_id = item.data(Qt.UserRole)
        if profile_id:
            self.connect_profile.emit(profile_id)
    
    def _connect_selected_profile(self):
        """Connect to the selected profile."""
        current_item = self.profile_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a profile to connect.")
            return
        
        profile_id = current_item.data(Qt.UserRole)
        self.connect_profile.emit(profile_id)
    
    def _edit_selected_profile(self):
        """Edit the selected profile."""
        current_item = self.profile_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a profile to edit.")
            return
        
        profile_id = current_item.data(Qt.UserRole)
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
        
        profile_id = current_item.data(Qt.UserRole)
        profile = self.profile_service.get_profile(profile_id)
        if not profile:
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{profile.name}'?\n\nThis will also delete any saved credentials.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
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
        
        profile_id = item.data(Qt.UserRole)
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
        
        menu.exec_(self.profile_list.mapToGlobal(pos))
    
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
            text=f"{profile.name} (Copy)"
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
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.profile_service.delete_profile(profile_id)


class ProfileEditorDialog(QDialog):
    """Dialog for creating/editing connection profiles."""
    
    def __init__(self, profile_service: ProfileService, profile: Optional[ConnectionProfile] = None, parent=None):
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
        
        # Provider
        self.provider_combo = QComboBox()
        self.provider_combo.addItem("ChromaDB", "chromadb")
        self.provider_combo.addItem("Qdrant", "qdrant")
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
        
        layout.addWidget(type_group)
        
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
        self.api_key_input.setEchoMode(QLineEdit.Password)
        details_layout.addRow("API Key:", self.api_key_input)
        
        details_group.setLayout(details_layout)
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
        self._on_type_changed()
    
    def _on_provider_changed(self):
        """Handle provider change."""
        provider = self.provider_combo.currentData()
        
        # Update default port
        if provider == "qdrant":
            if self.port_input.text() == "8000":
                self.port_input.setText("6333")
        elif provider == "chromadb":
            if self.port_input.text() == "6333":
                self.port_input.setText("8000")
        
        # Show/hide API key field
        is_http = self.http_radio.isChecked()
        self.api_key_input.setEnabled(is_http and provider == "qdrant")
    
    def _on_type_changed(self):
        """Handle connection type change."""
        is_persistent = self.persistent_radio.isChecked()
        is_http = self.http_radio.isChecked()
        
        # Show/hide relevant fields
        self.path_input.setEnabled(is_persistent)
        self.path_browse_btn.setEnabled(is_persistent)
        self.host_input.setEnabled(is_http)
        self.port_input.setEnabled(is_http)
        
        provider = self.provider_combo.currentData()
        self.api_key_input.setEnabled(is_http and provider == "qdrant")
    
    def _browse_for_path(self):
        """Browse for persistent storage path."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Select Database Directory",
            self.path_input.text()
        )
        if path:
            self.path_input.setText(path)
    
    def _load_profile_data(self):
        """Load existing profile data into form."""
        if not self.profile:
            return
        
        # Get profile with credentials
        profile_data = self.profile_service.get_profile_with_credentials(self.profile.id)
        if not profile_data:
            return
        
        self.name_input.setText(profile_data["name"])
        
        # Set provider
        index = self.provider_combo.findData(profile_data["provider"])
        if index >= 0:
            self.provider_combo.setCurrentIndex(index)
        
        config = profile_data.get("config", {})
        conn_type = config.get("type", "persistent")
        
        # Set connection type
        if conn_type == "persistent":
            self.persistent_radio.setChecked(True)
            self.path_input.setText(config.get("path", ""))
        elif conn_type == "http":
            self.http_radio.setChecked(True)
            self.host_input.setText(config.get("host", "localhost"))
            self.port_input.setText(str(config.get("port", "8000")))
        else:
            self.ephemeral_radio.setChecked(True)
        
        # Load credentials
        credentials = profile_data.get("credentials", {})
        if "api_key" in credentials:
            self.api_key_input.setText(credentials["api_key"])
    
    def _test_connection(self):
        """Test the connection with current settings."""
        # Get config
        config = self._get_config()
        provider = self.provider_combo.currentData()
        
        # Create connection
        from vector_inspector.core.connections.chroma_connection import ChromaDBConnection
        from vector_inspector.core.connections.qdrant_connection import QdrantConnection
        
        try:
            if provider == "chromadb":
                conn = ChromaDBConnection(**self._get_connection_kwargs(config))
            else:
                conn = QdrantConnection(**self._get_connection_kwargs(config))
            
            # Test connection
            progress = QProgressDialog("Testing connection...", None, 0, 0, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()
            
            success = conn.connect()
            progress.close()
            
            if success:
                QMessageBox.information(self, "Success", "Connection test successful!")
                conn.disconnect()
            else:
                QMessageBox.warning(self, "Failed", "Connection test failed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection test error: {e}")
    
    def _get_config(self) -> dict:
        """Get configuration from form."""
        config = {}
        
        if self.persistent_radio.isChecked():
            config["type"] = "persistent"
            config["path"] = self.path_input.text()
        elif self.http_radio.isChecked():
            config["type"] = "http"
            config["host"] = self.host_input.text()
            config["port"] = int(self.port_input.text())
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
        if self.api_key_input.text() and self.http_radio.isChecked():
            credentials["api_key"] = self.api_key_input.text()
        
        if self.is_edit_mode:
            # Update existing profile
            self.profile_service.update_profile(
                self.profile.id,
                name=name,
                config=config,
                credentials=credentials if credentials else None
            )
        else:
            # Create new profile
            self.profile_service.create_profile(
                name=name,
                provider=provider,
                config=config,
                credentials=credentials if credentials else None
            )
        
        self.accept()

