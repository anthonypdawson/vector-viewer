"""Metadata browsing and data view."""

from typing import Optional, Dict, Any, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QLabel, QSpinBox,
    QLineEdit, QComboBox, QGroupBox, QHeaderView, QMessageBox, QDialog,
    QFileDialog, QMenu
)
from PySide6.QtCore import Qt, QTimer

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.ui.components.item_dialog import ItemDialog
from vector_inspector.ui.components.loading_dialog import LoadingDialog
from vector_inspector.ui.components.filter_builder import FilterBuilder
from vector_inspector.services.import_export_service import ImportExportService
from vector_inspector.services.filter_service import apply_client_side_filters
from vector_inspector.services.settings_service import SettingsService
from PySide6.QtWidgets import QApplication


class MetadataView(QWidget):
    """View for browsing collection data and metadata."""
    
    def __init__(self, connection: VectorDBConnection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.current_collection: str = ""
        self.current_data: Optional[Dict[str, Any]] = None
        self.page_size = 50
        self.current_page = 0
        self.loading_dialog = LoadingDialog("Loading data...", self)
        self.settings_service = SettingsService()
        
        # Debounce timer for filter changes
        self.filter_reload_timer = QTimer()
        self.filter_reload_timer.setSingleShot(True)
        self.filter_reload_timer.timeout.connect(self._reload_with_filters)
        
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
        
        # Export button with menu
        self.export_button = QPushButton("Export...")
        self.export_button.setStyleSheet("QPushButton::menu-indicator { width: 0px; }")
        export_menu = QMenu(self)
        export_menu.addAction("Export to JSON", lambda: self._export_data("json"))
        export_menu.addAction("Export to CSV", lambda: self._export_data("csv"))
        export_menu.addAction("Export to Parquet", lambda: self._export_data("parquet"))
        self.export_button.setMenu(export_menu)
        controls_layout.addWidget(self.export_button)
        
        # Import button with menu
        self.import_button = QPushButton("Import...")
        self.import_button.setStyleSheet("QPushButton::menu-indicator { width: 0px; }")
        import_menu = QMenu(self)
        import_menu.addAction("Import from JSON", lambda: self._import_data("json"))
        import_menu.addAction("Import from CSV", lambda: self._import_data("csv"))
        import_menu.addAction("Import from Parquet", lambda: self._import_data("parquet"))
        self.import_button.setMenu(import_menu)
        controls_layout.addWidget(self.import_button)
        
        layout.addLayout(controls_layout)
        
        # Filter section
        filter_group = QGroupBox("Metadata Filters")
        filter_group.setCheckable(True)
        filter_group.setChecked(False)
        filter_group_layout = QVBoxLayout()
        
        self.filter_builder = FilterBuilder()
        # Remove auto-reload on filter changes - only reload when user clicks Refresh
        # self.filter_builder.filter_changed.connect(self._on_filter_changed)
        # But DO reload when user presses Enter or clicks away from value input
        self.filter_builder.apply_filters.connect(self._apply_filters)
        filter_group_layout.addWidget(self.filter_builder)
        
        filter_group.setLayout(filter_group_layout)
        layout.addWidget(filter_group)
        self.filter_group = filter_group
        
        # Data table
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)
        
        # Status bar
        self.status_label = QLabel("No collection selected")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)
        
    def set_collection(self, collection_name: str):
        """Set the current collection to display."""
        self.current_collection = collection_name
        self.current_page = 0
        
        # Show loading dialog at the start
        self.loading_dialog.show_loading("Loading collection data...")
        QApplication.processEvents()
        
        try:
            # Update filter builder with supported operators
            operators = self.connection.get_supported_filter_operators()
            self.filter_builder.set_operators(operators)
            
            self._load_data_internal()
            
            # Ensure UI is fully updated before hiding loading dialog
            QApplication.processEvents()
        finally:
            self.loading_dialog.hide_loading()
        
    def _load_data(self):
        """Load data from current collection (with loading dialog)."""
        if not self.current_collection:
            self.status_label.setText("No collection selected")
            self.table.setRowCount(0)
            return
            
        self.loading_dialog.show_loading("Loading data from collection...")
        QApplication.processEvents()
        try:
            self._load_data_internal()
        finally:
            self.loading_dialog.hide_loading()
    
    def _load_data_internal(self):
        """Internal method to load data without managing loading dialog."""
        if not self.current_collection:
            self.status_label.setText("No collection selected")
            self.table.setRowCount(0)
            return
        
        offset = self.current_page * self.page_size
        
        # Get filters split into server-side and client-side
        server_filter = None
        client_filters = []
        if self.filter_group.isChecked() and self.filter_builder.has_filters():
            server_filter, client_filters = self.filter_builder.get_filters_split()
        
        data = self.connection.get_all_items(
            self.current_collection,
            limit=self.page_size,
            offset=offset,
            where=server_filter
        )
        
        # Apply client-side filters if any
        if client_filters and data:
            data = apply_client_side_filters(data, client_filters)
        
        if not data:
            self.status_label.setText("Failed to load data")
            self.table.setRowCount(0)
            return
        self.current_data = data
        self._populate_table(data)
        self._update_pagination_controls()
        
        # Update filter builder with available metadata fields
        self._update_filter_fields(data)
        
    def _update_filter_fields(self, data: Dict[str, Any]):
        """Update filter builder with available metadata field names."""
        field_names = []
        
        # Add 'document' field if documents exist
        documents = data.get("documents", [])
        if documents and any(doc for doc in documents if doc):
            field_names.append("document")
        
        # Add metadata fields
        metadatas = data.get("metadatas", [])
        if metadatas and len(metadatas) > 0 and metadatas[0]:
            # Get all unique metadata keys from the first item
            metadata_keys = sorted(metadatas[0].keys())
            field_names.extend(metadata_keys)
        
        if field_names:
            self.filter_builder.set_available_fields(field_names)
        
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
    
    def _on_filter_changed(self):
        """Handle filter changes - debounce and reload data."""
        if self.filter_group.isChecked():
            # Restart the timer - will only fire 500ms after last change
            self.filter_reload_timer.stop()
            self.filter_reload_timer.start(500)  # 500ms debounce
    
    def _reload_with_filters(self):
        """Reload data with current filters (called after debounce)."""
        self.current_page = 0
        self._load_data()
    
    def _apply_filters(self):
        """Apply filters when user presses Enter or clicks away."""
        if self.filter_group.isChecked() and self.current_collection:
            self.current_page = 0
            self._load_data()
    
    def _on_row_double_clicked(self, index):
        """Handle double-click on a row to edit item."""
        if not self.current_collection or not self.current_data:
            return
            
        row = index.row()
        if row < 0 or row >= self.table.rowCount():
            return
            
        # Get item data for this row
        ids = self.current_data.get("ids", [])
        documents = self.current_data.get("documents", [])
        metadatas = self.current_data.get("metadatas", [])
        
        if row >= len(ids):
            return
            
        item_data = {
            "id": ids[row],
            "document": documents[row] if row < len(documents) else "",
            "metadata": metadatas[row] if row < len(metadatas) else {}
        }
        
        # Open edit dialog
        dialog = ItemDialog(self, item_data=item_data)
        
        if dialog.exec() == QDialog.Accepted:
            updated_data = dialog.get_item_data()
            if not updated_data:
                return
                
            # Update item in collection
            success = self.connection.update_items(
                self.current_collection,
                ids=[updated_data["id"]],
                documents=[updated_data["document"]] if updated_data["document"] else None,
                metadatas=[updated_data["metadata"]] if updated_data["metadata"] else None
            )
            
            if success:
                QMessageBox.information(self, "Success", "Item updated successfully.")
                self._load_data()
            else:
                QMessageBox.warning(self, "Error", "Failed to update item.")
    
    def _export_data(self, format_type: str):
        """Export current table data to file (visible rows or selected rows)."""
        if not self.current_collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first.")
            return
        
        if not self.current_data or not self.current_data.get("ids"):
            QMessageBox.warning(self, "No Data", "No data to export.")
            return
        
        # Check if there are selected rows
        selected_rows = self.table.selectionModel().selectedRows()
        
        if selected_rows:
            # Export only selected rows
            export_data = {
                "ids": [],
                "documents": [],
                "metadatas": [],
                "embeddings": []
            }
            
            for index in selected_rows:
                row = index.row()
                if row < len(self.current_data["ids"]):
                    export_data["ids"].append(self.current_data["ids"][row])
                    if "documents" in self.current_data and row < len(self.current_data["documents"]):
                        export_data["documents"].append(self.current_data["documents"][row])
                    if "metadatas" in self.current_data and row < len(self.current_data["metadatas"]):
                        export_data["metadatas"].append(self.current_data["metadatas"][row])
                    if "embeddings" in self.current_data and row < len(self.current_data["embeddings"]):
                        export_data["embeddings"].append(self.current_data["embeddings"][row])
        else:
            # Export all visible data from current table
            export_data = self.current_data
        
        # Select file path
        file_filters = {
            "json": "JSON Files (*.json)",
            "csv": "CSV Files (*.csv)",
            "parquet": "Parquet Files (*.parquet)"
        }
        
        # Get last used directory from settings
        last_dir = self.settings_service.get("last_import_export_dir", "")
        default_path = f"{last_dir}/{self.current_collection}.{format_type}" if last_dir else f"{self.current_collection}.{format_type}"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export to {format_type.upper()}",
            default_path,
            file_filters[format_type]
        )
        
        if not file_path:
            return
            
        # Export
        service = ImportExportService()
        success = False
        
        if format_type == "json":
            success = service.export_to_json(export_data, file_path)
        elif format_type == "csv":
            success = service.export_to_csv(export_data, file_path)
        elif format_type == "parquet":
            success = service.export_to_parquet(export_data, file_path)
            
        if success:
            # Save the directory for next time
            from pathlib import Path
            self.settings_service.set("last_import_export_dir", str(Path(file_path).parent))
            
            QMessageBox.information(
                self,
                "Export Successful",
                f"Exported {len(export_data['ids'])} items to {file_path}"
            )
        else:
            QMessageBox.warning(self, "Export Failed", "Failed to export data.")
    
    def _import_data(self, format_type: str):
        """Import data from file into collection."""
        if not self.current_collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first.")
            return
            
        # Select file to import
        file_filters = {
            "json": "JSON Files (*.json)",
            "csv": "CSV Files (*.csv)",
            "parquet": "Parquet Files (*.parquet)"
        }
        
        # Get last used directory from settings
        last_dir = self.settings_service.get("last_import_export_dir", "")
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Import from {format_type.upper()}",
            last_dir,
            file_filters[format_type]
        )
        
        if not file_path:
            return
            
        # Import
        self.loading_dialog.show_loading("Importing data...")
        QApplication.processEvents()
        
        try:
            service = ImportExportService()
            imported_data = None
            
            if format_type == "json":
                imported_data = service.import_from_json(file_path)
            elif format_type == "csv":
                imported_data = service.import_from_csv(file_path)
            elif format_type == "parquet":
                imported_data = service.import_from_parquet(file_path)
                
            if not imported_data:
                QMessageBox.warning(self, "Import Failed", "Failed to parse import file.")
                return
            
            # Handle Qdrant-specific requirements (similar to backup/restore)
            from vector_inspector.core.connections.qdrant_connection import QdrantConnection
            if isinstance(self.connection, QdrantConnection):
                # Check if embeddings are missing and need to be generated
                if not imported_data.get("embeddings"):
                    self.loading_dialog.setLabelText("Generating embeddings for Qdrant...")
                    QApplication.processEvents()
                    try:
                        from sentence_transformers import SentenceTransformer
                        model = SentenceTransformer("all-MiniLM-L6-v2")
                        documents = imported_data.get("documents", [])
                        imported_data["embeddings"] = model.encode(documents, show_progress_bar=False).tolist()
                    except Exception as e:
                        QMessageBox.warning(self, "Import Failed", 
                                          f"Qdrant requires embeddings. Failed to generate: {e}")
                        return
                
                # Convert IDs to Qdrant-compatible format (integers or UUIDs)
                # Store original IDs in metadata
                original_ids = imported_data.get("ids", [])
                qdrant_ids = []
                metadatas = imported_data.get("metadatas", [])
                
                for i, orig_id in enumerate(original_ids):
                    # Try to convert to integer, otherwise use index
                    try:
                        # If it's like "doc_123", extract the number
                        if isinstance(orig_id, str) and "_" in orig_id:
                            qdrant_id = int(orig_id.split("_")[-1])
                        else:
                            qdrant_id = int(orig_id)
                    except (ValueError, AttributeError):
                        # Use index as ID if can't convert
                        qdrant_id = i
                    
                    qdrant_ids.append(qdrant_id)
                    
                    # Store original ID in metadata
                    if i < len(metadatas):
                        if metadatas[i] is None:
                            metadatas[i] = {}
                        metadatas[i]["original_id"] = orig_id
                    else:
                        metadatas.append({"original_id": orig_id})
                
                imported_data["ids"] = qdrant_ids
                imported_data["metadatas"] = metadatas
                
            # Add items to collection
            success = self.connection.add_items(
                self.current_collection,
                documents=imported_data["documents"],
                metadatas=imported_data.get("metadatas"),
                ids=imported_data.get("ids"),
                embeddings=imported_data.get("embeddings")
            )
        finally:
            self.loading_dialog.hide_loading()
            
        if success:
            # Save the directory for next time
            from pathlib import Path
            self.settings_service.set("last_import_export_dir", str(Path(file_path).parent))
            
            QMessageBox.information(
                self,
                "Import Successful",
                f"Imported {len(imported_data['ids'])} items."
            )
            self._load_data()
        else:
            QMessageBox.warning(self, "Import Failed", "Failed to import data.")

