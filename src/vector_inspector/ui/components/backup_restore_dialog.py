"""Dialog for backup and restore operations."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.connection_manager import ConnectionInstance
from vector_inspector.services.backup_restore_service import BackupRestoreService
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.ui.components.loading_dialog import LoadingDialog


class BackupRestoreDialog(QDialog):
    """Dialog for managing backups and restores."""

    def __init__(self, connection: ConnectionInstance, collection_name: str = "", parent=None):
        super().__init__(parent)
        # Expects a ConnectionInstance wrapper; services access the underlying
        # raw database connection via `.database` when needed.
        self.connection = connection
        self.collection_name = collection_name
        self.backup_service = BackupRestoreService()
        self.settings_service = SettingsService()

        # Load backup directory from settings or use default
        default_backup_dir = str(Path.home() / "vector-viewer-backups")
        self.backup_dir = self.settings_service.get("backup_directory", default_backup_dir)

        self.loading_dialog = LoadingDialog("Processing...", self)

        self.setWindowTitle("Backup & Restore")
        self.setMinimumSize(600, 500)

        self._setup_ui()
        self._refresh_backups_list()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        # Tabs for backup and restore
        tabs = QTabWidget()

        # Backup tab
        backup_tab = self._create_backup_tab()
        tabs.addTab(backup_tab, "Create Backup")

        # Restore tab
        restore_tab = self._create_restore_tab()
        tabs.addTab(restore_tab, "Restore from Backup")

        layout.addWidget(tabs)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignRight)

    def _create_backup_tab(self) -> QWidget:
        """Create the backup tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Collection selection
        collection_group = QGroupBox("Backup Configuration")
        collection_layout = QFormLayout()

        # Collection name
        collection_layout.addRow(
            "Collection:", QLabel(self.collection_name or "No collection selected")
        )

        # Backup directory
        dir_layout = QHBoxLayout()
        self.backup_dir_input = QLineEdit(self.backup_dir)
        self.backup_dir_input.setReadOnly(True)
        dir_layout.addWidget(self.backup_dir_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._select_backup_dir)
        dir_layout.addWidget(browse_btn)

        collection_layout.addRow("Backup Directory:", dir_layout)

        # Options
        self.include_embeddings_check = QCheckBox("Include embedding vectors (larger file size)")
        self.include_embeddings_check.setChecked(True)
        collection_layout.addRow("Options:", self.include_embeddings_check)

        collection_group.setLayout(collection_layout)
        layout.addWidget(collection_group)

        # Info label
        info_label = QLabel(
            "Backup will create a compressed archive containing all collection data, "
            "metadata, and optionally embedding vectors."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(info_label)

        layout.addStretch()

        # Create backup button
        backup_button = QPushButton("Create Backup")
        backup_button.clicked.connect(self._create_backup)
        backup_button.setStyleSheet("QPushButton { font-weight: bold; padding: 8px; }")
        layout.addWidget(backup_button)

        return widget

    def _create_restore_tab(self) -> QWidget:
        """Create the restore tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Backup list
        layout.addWidget(QLabel("Available Backups:"))

        self.backups_list = QListWidget()
        self.backups_list.itemSelectionChanged.connect(self._on_backup_selected)
        layout.addWidget(self.backups_list)

        # Refresh button
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.clicked.connect(self._refresh_backups_list)
        layout.addWidget(refresh_btn)

        # Restore options
        options_group = QGroupBox("Restore Options")
        options_layout = QVBoxLayout()

        # New collection name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Restore as:"))
        self.restore_name_input = QLineEdit()
        self.restore_name_input.setPlaceholderText("Leave empty to use original name")
        name_layout.addWidget(self.restore_name_input)
        options_layout.addLayout(name_layout)

        # Overwrite checkbox
        self.overwrite_check = QCheckBox("Overwrite if collection exists")
        self.overwrite_check.setChecked(False)
        options_layout.addWidget(self.overwrite_check)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Restore and delete buttons
        button_layout = QHBoxLayout()

        self.restore_button = QPushButton("Restore Selected")
        self.restore_button.clicked.connect(self._restore_backup)
        self.restore_button.setEnabled(False)
        self.restore_button.setStyleSheet("QPushButton { font-weight: bold; padding: 8px; }")
        button_layout.addWidget(self.restore_button)

        self.delete_backup_button = QPushButton("Delete Selected")
        self.delete_backup_button.clicked.connect(self._delete_backup)
        self.delete_backup_button.setEnabled(False)
        button_layout.addWidget(self.delete_backup_button)

        layout.addLayout(button_layout)

        return widget

    def _select_backup_dir(self):
        """Select backup directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Backup Directory", self.backup_dir
        )

        if dir_path:
            self.backup_dir = dir_path
            self.backup_dir_input.setText(dir_path)

            # Save to settings
            self.settings_service.set("backup_directory", dir_path)

            self._refresh_backups_list()

    def _create_backup(self):
        """Create a backup of the current collection."""
        if not self.collection_name:
            QMessageBox.warning(self, "No Collection", "No collection selected for backup.")
            return

        # Create backup
        include_embeddings = self.include_embeddings_check.isChecked()

        self.loading_dialog.show_loading("Creating backup...")
        QApplication.processEvents()

        try:
            backup_path = self.backup_service.backup_collection(
                self.connection.database,
                self.collection_name,
                self.backup_dir,
                include_embeddings=include_embeddings,
                profile_name=self.connection.name,
            )
        finally:
            self.loading_dialog.hide_loading()

        if backup_path:
            QMessageBox.information(
                self, "Backup Successful", f"Backup created successfully:\n{backup_path}"
            )
            self._refresh_backups_list()
        else:
            QMessageBox.warning(self, "Backup Failed", "Failed to create backup.")

    def _refresh_backups_list(self):
        """Refresh the list of available backups."""
        self.backups_list.clear()

        backups = self.backup_service.list_backups(self.backup_dir)

        for backup in backups:
            # Format file size
            size_mb = backup["file_size"] / (1024 * 1024)

            item_text = (
                f"{backup['collection_name']} - {backup['timestamp']}\n"
                f"  Items: {backup['item_count']}, Size: {size_mb:.2f} MB\n"
                f"  File: {backup['file_name']}"
            )

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, backup["file_path"])
            self.backups_list.addItem(item)

        if not backups:
            item = QListWidgetItem("No backups found in directory")
            item.setFlags(Qt.NoItemFlags)
            self.backups_list.addItem(item)

    def _on_backup_selected(self):
        """Handle backup selection."""
        has_selection = len(self.backups_list.selectedItems()) > 0
        self.restore_button.setEnabled(has_selection)
        self.delete_backup_button.setEnabled(has_selection)

    def _restore_backup(self):
        """Restore a backup."""
        selected_items = self.backups_list.selectedItems()
        if not selected_items:
            return

        backup_file = selected_items[0].data(Qt.UserRole)
        if not backup_file:
            return

        # Read backup metadata to get original collection name
        try:
            import json
            import zipfile

            with zipfile.ZipFile(backup_file, "r") as zipf:
                metadata_str = zipf.read("metadata.json").decode("utf-8")
                metadata = json.loads(metadata_str)
                original_name = metadata.get("collection_name", "unknown")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to read backup metadata: {e}")
            return

        # Get restore options
        restore_name = self.restore_name_input.text().strip()
        overwrite = self.overwrite_check.isChecked()

        # Determine final collection name
        final_name = restore_name if restore_name else original_name

        # Build confirmation message
        if restore_name:
            msg = f"Restore backup to NEW collection: '{final_name}'"
        else:
            msg = f"Restore backup to ORIGINAL collection: '{final_name}'"

        # Check if collection exists
        # Extract the underlying database connection from the ConnectionInstance wrapper.
        actual_conn = getattr(self.connection, "database", self.connection)
        if hasattr(actual_conn, "list_collections"):
            try:
                existing_collections = actual_conn.list_collections()
            except Exception:
                existing_collections = getattr(self.connection, "collections", [])
        else:
            existing_collections = getattr(self.connection, "collections", [])
        if final_name in existing_collections:
            if overwrite:
                msg += f"\n\n⚠️  WARNING: This will DELETE and replace the existing collection '{final_name}'!"
            else:
                QMessageBox.warning(
                    self,
                    "Collection Exists",
                    f"Collection '{final_name}' already exists.\n\n"
                    f"Check 'Overwrite existing collection' to replace it, or enter a different name.",
                )
                return

        # Confirm
        reply = QMessageBox.question(self, "Confirm Restore", msg, QMessageBox.Yes | QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        # If the backup included embeddings, ask user how to handle them
        recompute_choice: bool | None = None
        try:
            import json
            import zipfile

            with zipfile.ZipFile(backup_file, "r") as zipf:
                metadata_str = zipf.read("metadata.json").decode("utf-8")
                metadata = json.loads(metadata_str)
                include_embeddings = metadata.get("include_embeddings", False)
                has_model = bool(metadata.get("embedding_model"))
                embedding_model = metadata.get("embedding_model", "unknown")

            if include_embeddings:
                # Present three options: Use stored (default), Recompute, or Omit
                from PySide6.QtWidgets import (
                    QDialog,
                    QHBoxLayout,
                    QLabel,
                    QPushButton,
                    QRadioButton,
                    QVBoxLayout,
                )

                dialog = QDialog(self)
                dialog.setWindowTitle("Restore Embeddings")
                dialog.setMinimumWidth(500)
                layout = QVBoxLayout(dialog)

                # Explanation
                if has_model:
                    info_text = (
                        f"This backup includes {metadata.get('item_count', 0)} embedding vectors.\n"
                        f"Recorded model: {embedding_model}\n\n"
                        "How would you like to handle the embeddings?"
                    )
                else:
                    info_text = (
                        f"This backup includes {metadata.get('item_count', 0)} embedding vectors,\n"
                        "but no embedding model was recorded.\n\n"
                        "How would you like to handle the embeddings?"
                    )

                info_label = QLabel(info_text)
                info_label.setWordWrap(True)
                layout.addWidget(info_label)

                # Radio buttons for options
                use_stored_radio = QRadioButton(
                    "Use stored embeddings (recommended for new collections)"
                )
                use_stored_radio.setChecked(True)  # Default option
                layout.addWidget(use_stored_radio)

                recompute_radio = QRadioButton("Recompute embeddings from documents")
                if has_model:
                    recompute_radio.setToolTip(f"Will use model: {embedding_model}")
                else:
                    recompute_radio.setToolTip(
                        "Will attempt using your current embedding configuration"
                    )
                layout.addWidget(recompute_radio)

                omit_radio = QRadioButton("Omit embeddings (documents and metadata only)")
                layout.addWidget(omit_radio)

                # Buttons
                button_layout = QHBoxLayout()
                ok_button = QPushButton("OK")
                cancel_button = QPushButton("Cancel")
                ok_button.clicked.connect(dialog.accept)
                cancel_button.clicked.connect(dialog.reject)
                button_layout.addStretch()
                button_layout.addWidget(ok_button)
                button_layout.addWidget(cancel_button)
                layout.addLayout(button_layout)

                # Show dialog and get choice
                if dialog.exec() != QDialog.Accepted:
                    return

                if use_stored_radio.isChecked():
                    recompute_choice = None  # Use stored embeddings
                elif recompute_radio.isChecked():
                    recompute_choice = True  # Recompute
                else:  # omit_radio.isChecked()
                    recompute_choice = False  # Omit
        except Exception:
            recompute_choice = None  # Default to using stored embeddings

        self.loading_dialog.show_loading("Restoring backup...")
        QApplication.processEvents()

        try:
            # Restore (pass low-level connection to service)
            success = self.backup_service.restore_collection(
                self.connection.database,
                backup_file,
                collection_name=restore_name if restore_name else None,
                overwrite=overwrite,
                recompute_embeddings=recompute_choice,
                profile_name=self.connection.name,
            )
        finally:
            self.loading_dialog.hide_loading()

        if success:
            QMessageBox.information(
                self,
                "Restore Successful",
                f"Backup restored successfully to collection '{final_name}'.",
            )
        else:
            QMessageBox.warning(self, "Restore Failed", "Failed to restore backup.")

    def _delete_backup(self):
        """Delete a backup file."""
        selected_items = self.backups_list.selectedItems()
        if not selected_items:
            return

        backup_file = selected_items[0].data(Qt.UserRole)
        if not backup_file:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete this backup file?\n{Path(backup_file).name}",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            if self.backup_service.delete_backup(backup_file):
                QMessageBox.information(self, "Deleted", "Backup deleted successfully.")
                self._refresh_backups_list()
            else:
                QMessageBox.warning(self, "Delete Failed", "Failed to delete backup.")
