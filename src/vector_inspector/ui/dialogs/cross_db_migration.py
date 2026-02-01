"""Cross-database operations for migrating data between vector databases."""

from typing import Optional, List, Dict, Any
from pathlib import Path
import tempfile
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QGroupBox,
    QFormLayout,
    QSpinBox,
    QCheckBox,
    QMessageBox,
)
from PySide6.QtCore import QThread, Signal

from vector_inspector.core.connection_manager import ConnectionManager, ConnectionInstance
from vector_inspector.services.backup_restore_service import BackupRestoreService
from vector_inspector.core.logging import log_info, log_error


class MigrationThread(QThread):
    """Background thread for migrating data between databases using backup/restore."""

    progress = Signal(int, str)  # progress percentage, status message
    finished = Signal(bool, str)  # success, message

    def __init__(
        self,
        source_conn: ConnectionInstance,
        target_conn: ConnectionInstance,
        source_collection: str,
        target_collection: str,
        include_embeddings: bool,
    ):
        super().__init__()
        self.source_conn = source_conn
        self.target_conn = target_conn
        self.source_collection = source_collection
        self.target_collection = target_collection
        self.include_embeddings = include_embeddings
        self._cancelled = False
        self.backup_service = BackupRestoreService()

    def cancel(self):
        """Cancel the migration."""
        self._cancelled = True

    def run(self):
        """Run the migration using backup and restore."""
        temp_backup_path = None
        try:
            if self._cancelled:
                self.finished.emit(False, "Migration cancelled by user.")
                return

            # Ensure connections are active
            if not self.source_conn.is_connected:
                self.finished.emit(False, "Source connection is not active.")
                return

            if not self.target_conn.is_connected:
                self.finished.emit(False, "Target connection is not active.")
                return

            # Create temporary directory for backup
            temp_dir = tempfile.mkdtemp(prefix="vector_migration_")

            # Step 1: Create backup of source collection
            self.progress.emit(10, f"Creating backup of {self.source_collection}...")

            temp_backup_path = self.backup_service.backup_collection(
                self.source_conn.connection,
                self.source_collection,
                temp_dir,
                include_embeddings=self.include_embeddings,
                connection_id=self.source_conn.id,
            )

            if not temp_backup_path:
                self.finished.emit(False, "Failed to create backup.")
                return

            if self._cancelled:
                self.finished.emit(False, "Migration cancelled by user.")
                return

            # Step 2: Restore to target collection
            self.progress.emit(50, f"Restoring to {self.target_collection}...")

            # Verify target connection before restore
            if not self.target_conn.is_connected:
                # Try to reconnect
                if not self.target_conn.connect():
                    self.finished.emit(False, "Target connection lost. Please try again.")
                    return

            # Check if target collection exists
            target_exists = self.target_collection in self.target_conn.collections

            success = self.backup_service.restore_collection(
                self.target_conn.connection,
                temp_backup_path,
                collection_name=self.target_collection,
                overwrite=target_exists,
                connection_id=self.target_conn.id,
            )

            if self._cancelled:
                self.finished.emit(False, "Migration cancelled by user.")
                return

            if success:
                self.progress.emit(100, f"Migration complete!")
                self.finished.emit(
                    True,
                    f"Successfully migrated {self.source_collection} to {self.target_collection}",
                )
            else:
                # Clean up target collection on failure
                try:
                    if self.target_collection in self.target_conn.list_collections():
                        self.progress.emit(90, "Cleaning up failed migration...")
                        log_info(
                            "Cleaning up failed migration: deleting target collection '%s'",
                            self.target_collection,
                        )
                        self.target_conn.delete_collection(self.target_collection)
                except Exception as cleanup_error:
                    log_error("Warning: Failed to clean up target collection: %s", cleanup_error)

                self.finished.emit(
                    False, "Failed to restore to target collection. Target collection cleaned up."
                )

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            log_error("Migration error details:\n%s", error_details)

            # Clean up target collection on exception
            try:
                if self.target_conn and self.target_conn.is_connected:
                    if self.target_collection in self.target_conn.list_collections():
                        log_info(
                            "Cleaning up failed migration: deleting target collection '%s'",
                            self.target_collection,
                        )
                        self.target_conn.delete_collection(self.target_collection)
            except Exception as cleanup_error:
                log_error("Warning: Failed to clean up target collection: %s", cleanup_error)

            self.finished.emit(False, f"Migration error: {str(e)}")

        finally:
            # Clean up temporary backup file
            if temp_backup_path:
                try:
                    Path(temp_backup_path).unlink()
                    # Also remove temp directory if empty
                    temp_dir = Path(temp_backup_path).parent
                    if temp_dir.exists() and not list(temp_dir.iterdir()):
                        temp_dir.rmdir()
                except Exception:
                    pass  # Ignore cleanup errors


class CrossDatabaseMigrationDialog(QDialog):
    """Dialog for migrating data between vector databases."""

    def __init__(self, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self.connection_manager = connection_manager
        self.migration_thread: Optional[MigrationThread] = None

        self.setWindowTitle("Cross-Database Migration")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self._setup_ui()
        self._populate_connections()

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Source section
        source_group = QGroupBox("Source")
        source_layout = QFormLayout()

        self.source_connection_combo = QComboBox()
        self.source_connection_combo.currentIndexChanged.connect(self._on_source_connection_changed)
        source_layout.addRow("Connection:", self.source_connection_combo)

        self.source_collection_combo = QComboBox()
        source_layout.addRow("Collection:", self.source_collection_combo)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # Target section
        target_group = QGroupBox("Target")
        target_layout = QFormLayout()

        self.target_connection_combo = QComboBox()
        self.target_connection_combo.currentIndexChanged.connect(self._on_target_connection_changed)
        target_layout.addRow("Connection:", self.target_connection_combo)

        self.target_collection_combo = QComboBox()
        self.target_collection_combo.setEditable(True)
        target_layout.addRow("Collection:", self.target_collection_combo)

        self.create_new_check = QCheckBox("Create new collection if it doesn't exist")
        self.create_new_check.setChecked(True)
        target_layout.addRow("", self.create_new_check)

        target_group.setLayout(target_layout)
        layout.addWidget(target_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QFormLayout()

        self.include_embeddings_check = QCheckBox("Include Embeddings")
        self.include_embeddings_check.setChecked(True)
        options_layout.addRow("", self.include_embeddings_check)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Progress section
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        layout.addWidget(self.status_text)

        # Buttons
        button_layout = QHBoxLayout()

        self.start_button = QPushButton("Start Migration")
        self.start_button.clicked.connect(self._start_migration)
        button_layout.addWidget(self.start_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_migration)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def _populate_connections(self):
        """Populate connection dropdowns."""
        connections = self.connection_manager.get_all_connections()

        self.source_connection_combo.clear()
        self.target_connection_combo.clear()

        for conn in connections:
            self.source_connection_combo.addItem(conn.get_display_name(), conn.id)
            self.target_connection_combo.addItem(conn.get_display_name(), conn.id)

        # Populate collections for first connection
        if connections:
            self._on_source_connection_changed(0)
            self._on_target_connection_changed(0)

    def _on_source_connection_changed(self, index: int):
        """Handle source connection change."""
        connection_id = self.source_connection_combo.currentData()
        if connection_id:
            instance = self.connection_manager.get_connection(connection_id)
            if instance:
                self.source_collection_combo.clear()
                self.source_collection_combo.addItems(instance.collections)

    def _on_target_connection_changed(self, index: int):
        """Handle target connection change."""
        connection_id = self.target_connection_combo.currentData()
        if connection_id:
            instance = self.connection_manager.get_connection(connection_id)
            if instance:
                self.target_collection_combo.clear()
                self.target_collection_combo.addItems(instance.collections)

    def _start_migration(self):
        """Start the migration."""
        # Validate selection
        source_conn_id = self.source_connection_combo.currentData()
        target_conn_id = self.target_connection_combo.currentData()

        if not source_conn_id or not target_conn_id:
            QMessageBox.warning(
                self, "Invalid Selection", "Please select both source and target connections."
            )
            return

        if source_conn_id == target_conn_id:
            source_coll = self.source_collection_combo.currentText()
            target_coll = self.target_collection_combo.currentText()
            if source_coll == target_coll:
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    "Source and target cannot be the same collection in the same connection.",
                )
                return

        source_conn = self.connection_manager.get_connection(source_conn_id)
        target_conn = self.connection_manager.get_connection(target_conn_id)

        if not source_conn or not target_conn:
            QMessageBox.warning(self, "Error", "Failed to get connection instances.")
            return

        source_collection = self.source_collection_combo.currentText()
        target_collection = self.target_collection_combo.currentText().strip()

        if not source_collection or not target_collection:
            QMessageBox.warning(
                self, "Invalid Selection", "Please select both source and target collections."
            )
            return

        # Check if target collection exists
        target_exists = target_collection in target_conn.collections

        # If target doesn't exist and we're not set to create, warn user
        if not target_exists and not self.create_new_check.isChecked():
            QMessageBox.warning(
                self,
                "Collection Does Not Exist",
                f"Target collection '{target_collection}' does not exist.\n"
                "Please check 'Create new collection' to allow automatic creation during migration.",
            )
            return

        # Confirm
        action = "create and migrate" if not target_exists else "migrate"
        reply = QMessageBox.question(
            self,
            "Confirm Migration",
            f"Migrate data from:\n  {source_conn.name}/{source_collection}\n"
            f"to:\n  {target_conn.name}/{target_collection}\n\n"
            f"This will {action} all data. Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        # Start migration thread
        self.migration_thread = MigrationThread(
            source_conn=source_conn,
            target_conn=target_conn,
            source_collection=source_collection,
            target_collection=target_collection,
            include_embeddings=self.include_embeddings_check.isChecked(),
        )

        self.migration_thread.progress.connect(self._on_migration_progress)
        self.migration_thread.finished.connect(self._on_migration_finished)

        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.close_button.setEnabled(False)

        self.status_text.clear()
        self.progress_bar.setValue(0)

        self.migration_thread.start()

    def _cancel_migration(self):
        """Cancel the migration."""
        if self.migration_thread:
            self.migration_thread.cancel()
            self.status_text.append("Cancelling migration...")

    def _on_migration_progress(self, progress: int, message: str):
        """Handle migration progress update."""
        self.progress_bar.setValue(progress)
        self.status_text.append(message)

    def _on_migration_finished(self, success: bool, message: str):
        """Handle migration completion."""
        self.status_text.append(message)

        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.warning(self, "Failed", message)

        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)
        self.migration_thread = None
