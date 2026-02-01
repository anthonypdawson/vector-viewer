"""Collection browser for listing and selecting collections."""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QLabel,
    QMenu,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QAction

from vector_inspector.core.connection_manager import ConnectionInstance


class CollectionBrowser(QWidget):
    """Widget for browsing and selecting collections."""

    collection_selected = Signal(str)

    def __init__(self, connection: Optional[ConnectionInstance] = None, parent=None):
        super().__init__(parent)
        # Expects a ConnectionInstance wrapper.
        self.connection = connection
        self._setup_ui()

    def _setup_ui(self):
        """Setup widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Collections")
        group_layout = QVBoxLayout()

        self.collection_list = QListWidget()
        self.collection_list.itemClicked.connect(self._on_collection_clicked)
        self.collection_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.collection_list.customContextMenuRequested.connect(self._show_context_menu)

        group_layout.addWidget(self.collection_list)

        self.info_label = QLabel("No collections")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: gray; font-size: 10px;")
        group_layout.addWidget(self.info_label)

        group.setLayout(group_layout)
        layout.addWidget(group)

    def refresh(self):
        """Refresh collection list."""
        self.collection_list.clear()

        if not self.connection.is_connected:
            self.info_label.setText("Not connected")
            return

        collections = self.connection.list_collections()

        if not collections:
            # Show more context for persistent connections
            if self.connection.path:
                self.info_label.setText(f"No collections found at {self.connection.path}")
            else:
                self.info_label.setText("No collections found")
            return

        for collection_name in collections:
            item = QListWidgetItem(collection_name)
            self.collection_list.addItem(item)

        self.info_label.setText(f"{len(collections)} collection(s)")

    def clear(self):
        """Clear collection list."""
        self.collection_list.clear()
        self.info_label.setText("No collections")

    def _on_collection_clicked(self, item: QListWidgetItem):
        """Handle collection selection."""
        collection_name = item.text()
        self.collection_selected.emit(collection_name)

        # Show collection info
        info = self.connection.get_collection_info(collection_name)
        if info:
            count = info.get("count", 0)
            fields = info.get("metadata_fields", [])
            fields_str = ", ".join(fields[:3])
            if len(fields) > 3:
                fields_str += "..."
            self.info_label.setText(f"{count} items | Fields: {fields_str if fields else 'None'}")

    def _show_context_menu(self, position):
        """Show context menu for collections."""
        item = self.collection_list.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        delete_action = QAction("Delete Collection", self)
        delete_action.triggered.connect(lambda: self._delete_collection(item.text()))
        menu.addAction(delete_action)

        menu.exec(self.collection_list.mapToGlobal(position))

    def _delete_collection(self, collection_name: str):
        """Delete a collection."""
        # TODO: Add confirmation dialog
        if self.connection.delete_collection(collection_name):
            self.refresh()
