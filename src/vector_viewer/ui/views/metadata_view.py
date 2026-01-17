"""Metadata browsing and data view."""

from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QSpinBox,
    QLineEdit, QComboBox, QGroupBox, QHeaderView, QMessageBox, QDialog
)
from PySide6.QtCore import Qt

from vector_viewer.core.connections.chroma_connection import ChromaDBConnection
from vector_viewer.ui.components.item_dialog import ItemDialog


class MetadataView(QWidget):
    """View for browsing collection data and metadata."""
    
    def __init__(self, connection: ChromaDBConnection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.current_collection: str = ""
        self.current_data: Optional[Dict[str, Any]] = None
        self.page_size = 50
        self.current_page = 0
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup widget UI."""
        layout = QVBoxLayout(self)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        # Pagination controls
        controls_layout.addWidget(QLabel("Page:"))
        
        self.prev_button = QPushButton("◀ Previous")
        self.prev_button.clicked.connect(self._previous_page)
        self.prev_button.setEnabled(False)
        controls_layout.addWidget(self.prev_button)
        
        self.page_label = QLabel("0 / 0")
        controls_layout.addWidget(self.page_label)
        
        self.next_button = QPushButton("Next ▶")
        self.next_button.clicked.connect(self._next_page)
        self.next_button.setEnabled(False)
        controls_layout.addWidget(self.next_button)
        
        controls_layout.addWidget(QLabel("  Items per page:"))
        
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setMinimum(10)
        self.page_size_spin.setMaximum(500)
        self.page_size_spin.setValue(50)
        self.page_size_spin.setSingleStep(10)
        self.page_size_spin.valueChanged.connect(self._on_page_size_changed)
        controls_layout.addWidget(self.page_size_spin)
        
        controls_layout.addStretch()
        
        # Refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._load_data)
        controls_layout.addWidget(self.refresh_button)
        
        # Add/Delete buttons
        self.add_button = QPushButton("Add Item")
        self.add_button.clicked.connect(self._add_item)
        controls_layout.addWidget(self.add_button)
        
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self._delete_selected)
        controls_layout.addWidget(self.delete_button)
        
        layout.addLayout(controls_layout)
        
        # Data table
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        
        # Status bar
        self.status_label = QLabel("No collection selected")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)
        
    def set_collection(self, collection_name: str):
        """Set the current collection to display."""
        self.current_collection = collection_name
        self.current_page = 0
        self._load_data()
        
    def _load_data(self):
        """Load data from current collection."""
        if not self.current_collection:
            self.status_label.setText("No collection selected")
            self.table.setRowCount(0)
            return
            
        offset = self.current_page * self.page_size
        
        data = self.connection.get_all_items(
            self.current_collection,
            limit=self.page_size,
            offset=offset
        )
        
        if not data:
            self.status_label.setText("Failed to load data")
            self.table.setRowCount(0)
            return
            
        self.current_data = data
        self._populate_table(data)
        self._update_pagination_controls()
        
    def _populate_table(self, data: Dict[str, Any]):
        """Populate table with data."""
        ids = data.get("ids", [])
        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])
        
        if not ids:
            self.table.setRowCount(0)
            self.status_label.setText("No data in collection")
            return
            
        # Determine columns
        columns = ["ID", "Document"]
        if metadatas and metadatas[0]:
            metadata_keys = list(metadatas[0].keys())
            columns.extend(metadata_keys)
            
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(ids))
        
        # Populate rows
        for row, (id_val, doc, meta) in enumerate(zip(ids, documents, metadatas)):
            # ID column
            self.table.setItem(row, 0, QTableWidgetItem(str(id_val)))
            
            # Document column
            doc_text = str(doc) if doc else ""
            if len(doc_text) > 100:
                doc_text = doc_text[:100] + "..."
            self.table.setItem(row, 1, QTableWidgetItem(doc_text))
            
            # Metadata columns
            if meta:
                for col_idx, key in enumerate(metadata_keys, start=2):
                    value = meta.get(key, "")
                    self.table.setItem(row, col_idx, QTableWidgetItem(str(value)))
                    
        self.table.resizeColumnsToContents()
        self.status_label.setText(f"Showing {len(ids)} items")
        
    def _update_pagination_controls(self):
        """Update pagination button states."""
        if not self.current_data:
            return
            
        item_count = len(self.current_data.get("ids", []))
        has_more = item_count == self.page_size
        
        self.prev_button.setEnabled(self.current_page > 0)
        self.next_button.setEnabled(has_more)
        
        # Update page label (approximate since ChromaDB doesn't give total count easily)
        self.page_label.setText(f"{self.current_page + 1}")
        
    def _previous_page(self):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            self._load_data()
            
    def _next_page(self):
        """Go to next page."""
        self.current_page += 1
        self._load_data()
        
    def _on_page_size_changed(self, value: int):
        """Handle page size change."""
        self.page_size = value
        self.current_page = 0
        self._load_data()
        
    def _add_item(self):
        """Add a new item to the collection."""
        if not self.current_collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first.")
            return
            
        dialog = ItemDialog(self)
        
        if dialog.exec() == QDialog.Accepted:
            item_data = dialog.get_item_data()
            if not item_data:
                return
                
            # Add item to collection
            success = self.connection.add_items(
                self.current_collection,
                documents=[item_data["document"]],
                metadatas=[item_data["metadata"]] if item_data["metadata"] else None,
                ids=[item_data["id"]] if item_data["id"] else None
            )
            
            if success:
                QMessageBox.information(self, "Success", "Item added successfully.")
                self._load_data()
            else:
                QMessageBox.warning(self, "Error", "Failed to add item.")
        
    def _delete_selected(self):
        """Delete selected items."""
        if not self.current_collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first.")
            return
            
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select items to delete.")
            return
            
        # Get IDs of selected items
        ids_to_delete = []
        for row in selected_rows:
            id_item = self.table.item(row.row(), 0)
            if id_item:
                ids_to_delete.append(id_item.text())
                
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Delete {len(ids_to_delete)} item(s)?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success = self.connection.delete_items(self.current_collection, ids=ids_to_delete)
            if success:
                QMessageBox.information(self, "Success", "Items deleted successfully.")
                self._load_data()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete items.")
