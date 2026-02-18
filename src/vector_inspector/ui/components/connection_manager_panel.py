"""Connection manager panel showing multiple active connections."""

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.connection_manager import (
    ConnectionManager,
    ConnectionState,
)
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.ui.components.connection_manager_threads import (
    DeleteCollectionThread,
    RefreshCollectionsThread,
)
from vector_inspector.ui.components.loading_dialog import LoadingDialog


class ConnectionManagerPanel(QWidget):
    """Panel for managing multiple database connections.

    Signals:
        connection_selected: Emitted when a connection is clicked (connection_id)
        collection_selected: Emitted when a collection is clicked (connection_id, collection_name)
    """

    connection_selected = Signal(str)  # connection_id
    collection_selected = Signal(str, str)  # connection_id, collection_name

    connection_manager: ConnectionManager
    connection_tree: QTreeWidget
    add_connection_btn: QPushButton
    _connection_items: dict

    def __init__(self, connection_manager: ConnectionManager, parent=None):
        """
        Initialize connection manager panel.

        Args:
            connection_manager: The ConnectionManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.connection_manager = connection_manager
        self._connection_items = {}  # Map connection_id to tree item

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Connections")
        header_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        # Add connection button
        self.add_connection_btn = QPushButton("+")
        self.add_connection_btn.setMaximumWidth(30)
        self.add_connection_btn.setToolTip("Add new connection")
        header_layout.addWidget(self.add_connection_btn)

        layout.addLayout(header_layout)

        # Connection tree
        self.connection_tree = QTreeWidget()
        self.connection_tree.setHeaderHidden(True)
        # Use the correct enum for PySide6
        self.connection_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.connection_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.connection_tree.itemClicked.connect(self._on_item_clicked)
        self.connection_tree.itemExpanded.connect(self._on_item_expanded)
        # Match QListWidget selection style - use subtle highlight
        self.connection_tree.setStyleSheet("""
            QTreeWidget::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
        """)
        layout.addWidget(self.connection_tree)

    def _connect_signals(self):
        """Connect to connection manager signals."""
        self.connection_manager.connection_opened.connect(self._on_connection_opened)
        self.connection_manager.connection_closed.connect(self._on_connection_closed)
        self.connection_manager.connection_state_changed.connect(self._on_connection_state_changed)
        self.connection_manager.active_connection_changed.connect(
            self._on_active_connection_changed
        )
        self.connection_manager.active_collection_changed.connect(
            self._on_active_collection_changed
        )
        self.connection_manager.collections_updated.connect(self._on_collections_updated)

    def _on_connection_opened(self, connection_id: str):
        """Handle new connection opened (after successful connection)."""
        instance = self.connection_manager.get_connection(connection_id)
        if not instance:
            return

        # Only show if not already shown
        if connection_id in self._connection_items:
            return

        # Create tree item for connection
        item = QTreeWidgetItem(self.connection_tree)
        item.setText(0, instance.get_display_name())
        item.setData(
            0, Qt.ItemDataRole.UserRole, {"type": "connection", "connection_id": connection_id}
        )

        # Set icon/indicator based on state
        self._update_connection_indicator(item, instance.state)

        self._connection_items[connection_id] = item

        # Expand by default to show collections
        item.setExpanded(True)

        # Select if active
        if self.connection_manager.get_active_connection_id() == connection_id:
            self.connection_tree.setCurrentItem(item)

    def _on_connection_closed(self, connection_id: str):
        """Handle connection closed."""
        item = self._connection_items.pop(connection_id, None)
        if item:
            index = self.connection_tree.indexOfTopLevelItem(item)
            if index >= 0:
                self.connection_tree.takeTopLevelItem(index)

    def _on_connection_state_changed(self, connection_id: str, state: ConnectionState):
        """Handle connection state change."""
        item = self._connection_items.get(connection_id)
        if item:
            self._update_connection_indicator(item, state)

    def _on_active_connection_changed(self, connection_id):
        """Handle active connection change."""
        # Select the active connection item in the tree
        if connection_id:
            item = self._connection_items.get(connection_id)
            if item:
                self.connection_tree.setCurrentItem(item)

    def _on_active_collection_changed(self, connection_id: str, collection_name):
        """Handle active collection change."""
        item = self._connection_items.get(connection_id)
        if not item:
            return

        # Select the active collection in the tree
        if collection_name:
            for i in range(item.childCount()):
                child = item.child(i)
                data = child.data(0, Qt.ItemDataRole.UserRole)
                if data and data.get("collection_name") == collection_name:
                    self.connection_tree.setCurrentItem(child)
                    break

    def _on_collections_updated(self, connection_id: str, collections: list):
        """Handle collections list updated."""
        item = self._connection_items.get(connection_id)
        if not item:
            return

        # Remove existing collection items
        while item.childCount() > 0:
            item.removeChild(item.child(0))

        # Add new collection items
        for collection_name in collections:
            child = QTreeWidgetItem(item)
            child.setText(0, collection_name)
            child.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {
                    "type": "collection",
                    "connection_id": connection_id,
                    "collection_name": collection_name,
                },
            )

    def _update_connection_indicator(self, item: QTreeWidgetItem, state: ConnectionState):
        """Update visual indicator for connection state."""
        if state == ConnectionState.CONNECTED:
            indicator = "🟢"
        elif state == ConnectionState.CONNECTING:
            indicator = "🟡"
        elif state == ConnectionState.ERROR:
            indicator = "🔴"
        else:
            indicator = "⚪"

        data = item.data(0, Qt.ItemDataRole.UserRole)
        connection_id = data.get("connection_id")
        instance = self.connection_manager.get_connection(connection_id)

        if instance:
            item.setText(0, f"{indicator} {instance.get_display_name()}")

    def _on_item_clicked(self, item: QTreeWidgetItem):
        """Handle tree item click."""
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        item_type = data.get("type")
        connection_id = data.get("connection_id")

        if item_type == "connection":
            # Set as active connection
            self.connection_manager.set_active_connection(connection_id)
            self.connection_selected.emit(connection_id)
        elif item_type == "collection":
            # Set active connection first (if different)
            if connection_id != self.connection_manager.get_active_connection_id():
                self.connection_manager.set_active_connection(connection_id)

            # Then set as active collection
            collection_name = data.get("collection_name")
            self.connection_manager.set_active_collection(connection_id, collection_name)
            self.collection_selected.emit(connection_id, collection_name)

    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Handle tree item expansion."""
        # Could trigger lazy loading of collections here if needed
        pass

    def _show_context_menu(self, pos):
        """Show context menu for connection/collection."""
        item = self.connection_tree.itemAt(pos)
        if not item:
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        menu = QMenu(self)
        item_type = data.get("type")
        connection_id = data.get("connection_id")

        if item_type == "connection":
            # Connection context menu
            set_active_action = menu.addAction("Set as Active")
            set_active_action.triggered.connect(
                lambda: self.connection_manager.set_active_connection(connection_id)
            )

            menu.addSeparator()

            rename_action = menu.addAction("Rename...")
            rename_action.triggered.connect(lambda: self._rename_connection(connection_id))

            refresh_action = menu.addAction("Refresh Collections")
            refresh_action.triggered.connect(lambda: self._refresh_collections(connection_id))

            menu.addSeparator()

            disconnect_action = menu.addAction("Disconnect")
            disconnect_action.triggered.connect(lambda: self._disconnect_connection(connection_id))

        elif item_type == "collection":
            # Collection context menu
            collection_name = data.get("collection_name")

            select_action = menu.addAction("Select Collection")
            select_action.triggered.connect(
                lambda: self.connection_manager.set_active_collection(
                    connection_id, collection_name
                )
            )

            menu.addSeparator()

            info_action = menu.addAction("View Info")
            info_action.triggered.connect(
                lambda: self._view_collection_info(connection_id, collection_name)
            )

            menu.addSeparator()

            delete_action = menu.addAction("Delete Collection...")
            delete_action.triggered.connect(
                lambda: self._delete_collection(connection_id, collection_name)
            )
            # Make delete action red/warning style
            delete_action.setIcon(QIcon())  # Could add warning icon
            font = delete_action.font()
            font.setBold(True)
            delete_action.setFont(font)

        menu.exec(self.connection_tree.mapToGlobal(pos))

    def _rename_connection(self, connection_id: str):
        """Rename a connection."""
        instance = self.connection_manager.get_connection(connection_id)
        if not instance:
            return

        new_name, ok = QInputDialog.getText(
            self, "Rename Connection", "Enter new name:", text=instance.name
        )

        if ok and new_name and self.connection_manager.rename_connection(connection_id, new_name):
            # Update tree item
            item = self._connection_items.get(connection_id)
            if item:
                self._update_connection_indicator(item, instance.state)

    def _refresh_collections(self, connection_id: str):
        """Refresh collections for a connection."""
        instance = self.connection_manager.get_connection(connection_id)
        if not instance or not instance.is_connected:
            return

        # Show loading while refreshing
        loading = LoadingDialog("Refreshing collections...", self)
        loading.show_loading("Refreshing collections...")

        # Cancel any existing refresh thread
        if (
            hasattr(self, "_refresh_thread")
            and self._refresh_thread
            and self._refresh_thread.isRunning()
        ):
            self._refresh_thread.quit()
            self._refresh_thread.wait()

        # Create and start refresh thread
        self._refresh_thread = RefreshCollectionsThread(instance, parent=self)
        self._refresh_thread.finished.connect(
            lambda collections: self._on_refresh_finished(connection_id, collections, loading)
        )
        self._refresh_thread.error.connect(lambda error: self._on_refresh_error(error, loading))
        self._refresh_thread.start()

    def _on_refresh_finished(
        self, connection_id: str, collections: list, loading: LoadingDialog
    ) -> None:
        """Handle successful collections refresh."""
        loading.hide_loading()
        self.connection_manager.update_collections(connection_id, collections)

    def _on_refresh_error(self, error_message: str, loading: LoadingDialog) -> None:
        """Handle refresh error."""
        loading.hide_loading()
        QMessageBox.warning(self, "Error", f"Failed to refresh collections: {error_message}")

    def _disconnect_connection(self, connection_id: str):
        """Disconnect a connection."""
        instance = self.connection_manager.get_connection(connection_id)
        if not instance:
            return

        reply = QMessageBox.question(
            self,
            "Disconnect",
            f"Disconnect from '{instance.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.connection_manager.close_connection(connection_id)

    def _view_collection_info(self, connection_id: str, collection_name: str):
        """View collection info."""
        # This would trigger showing collection details
        # For now, just select it
        self.connection_manager.set_active_collection(connection_id, collection_name)
        self.collection_selected.emit(connection_id, collection_name)

    def _delete_collection(self, connection_id: str, collection_name: str):
        """Delete a collection with strict warning."""
        instance = self.connection_manager.get_connection(connection_id)
        if not instance:
            return

        # Get collection info for warning
        try:
            col_info = instance.get_collection_info(collection_name)
            item_count = col_info.get("count", 0) if col_info else 0
        except Exception:
            item_count = 0

        # Create a very strict warning dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("⚠️ DELETE Collection - WARNING")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)

        # Warning header
        warning_label = QLabel("⚠️ PERMANENT DELETION WARNING ⚠️")
        warning_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #d32f2f; padding: 10px;"
        )
        warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(warning_label)

        # Details
        details_text = (
            f"You are about to PERMANENTLY DELETE the collection:\n\n"
            f"Collection: {collection_name}\n"
            f"Connection: {instance.name}\n"
            f"Items: {item_count:,}\n\n"
            f"⛔ THIS ACTION CANNOT BE UNDONE ⛔\n\n"
            f"All vectors, documents, metadata, and embeddings in this collection\n"
            f"will be PERMANENTLY DELETED from the database.\n\n"
            f"If you have not created a backup, you will LOSE ALL DATA."
        )
        details_label = QLabel(details_text)
        details_label.setWordWrap(True)
        details_label.setStyleSheet("padding: 10px; border-radius: 5px;")
        layout.addWidget(details_label)

        # Confirmation checkbox
        confirm_checkbox = QCheckBox(
            f"I understand this will PERMANENTLY DELETE '{collection_name}' "
            f"and all {item_count:,} items"
        )
        confirm_checkbox.setStyleSheet("font-weight: bold; color: #d32f2f; padding: 10px;")
        layout.addWidget(confirm_checkbox)

        # Type collection name to confirm
        type_confirm_label = QLabel(
            f"Type the collection name to confirm: <b>{collection_name}</b>"
        )
        layout.addWidget(type_confirm_label)

        name_input = QLineEdit()
        name_input.setPlaceholderText(f"Type '{collection_name}' here")
        layout.addWidget(name_input)

        # Buttons
        button_box = QDialogButtonBox()
        delete_button = button_box.addButton(
            "DELETE PERMANENTLY", QDialogButtonBox.ButtonRole.DestructiveRole
        )
        delete_button.setEnabled(False)  # Disabled until confirmed
        delete_button.setStyleSheet(
            "QPushButton { background-color: #d32f2f; color: white; font-weight: bold; "
            "padding: 8px 16px; } "
            "QPushButton:disabled { background-color: #cccccc; }"
        )
        cancel_button = button_box.addButton(QDialogButtonBox.StandardButton.Cancel)

        # Enable delete button only when both confirmations are met
        def check_confirmations():
            checkbox_ok = confirm_checkbox.isChecked()
            name_ok = name_input.text().strip() == collection_name
            delete_button.setEnabled(checkbox_ok and name_ok)

        confirm_checkbox.stateChanged.connect(check_confirmations)
        name_input.textChanged.connect(check_confirmations)

        delete_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        layout.addWidget(button_box)

        # Show dialog
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Perform deletion
        loading = LoadingDialog("Deleting collection...", self)
        loading.show_loading(f"Deleting collection '{collection_name}'...")

        # Cancel any existing delete thread
        if (
            hasattr(self, "_delete_thread")
            and self._delete_thread
            and self._delete_thread.isRunning()
        ):
            self._delete_thread.quit()
            self._delete_thread.wait()

        # Create and start delete thread
        self._delete_thread = DeleteCollectionThread(
            instance,
            collection_name,
            instance.name,
            parent=self,
        )
        self._delete_thread.finished.connect(
            lambda collections: self._on_delete_finished(
                connection_id, collection_name, collections, loading, instance
            )
        )
        self._delete_thread.error.connect(
            lambda error: self._on_delete_error(collection_name, error, loading)
        )
        self._delete_thread.start()

    def _on_delete_finished(
        self,
        connection_id: str,
        collection_name: str,
        collections: list,
        loading: LoadingDialog,
        instance: Any,
    ) -> None:
        """Handle successful collection deletion."""
        loading.hide_loading()

        # Remove embedding model info from settings
        profile_name = instance.name
        SettingsService().remove_embedding_model(profile_name, collection_name)

        # Update collections list
        self.connection_manager.update_collections(connection_id, collections)

        # Clear active collection if it was this one
        if instance.active_collection == collection_name:
            self.connection_manager.set_active_collection(connection_id, None)

        QMessageBox.information(
            self,
            "Collection Deleted",
            f"Collection '{collection_name}' has been permanently deleted.",
        )

    def _on_delete_error(
        self, collection_name: str, error_message: str, loading: LoadingDialog
    ) -> None:
        """Handle delete error."""
        loading.hide_loading()
        QMessageBox.critical(
            self,
            "Deletion Error",
            f"Error deleting collection '{collection_name}': {error_message}",
        )
