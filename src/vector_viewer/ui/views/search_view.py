"""Search interface for similarity queries."""

from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QLabel, QSpinBox, QTableWidget,
    QTableWidgetItem, QGroupBox, QSplitter
)
from PySide6.QtCore import Qt

from vector_viewer.core.connections.chroma_connection import ChromaDBConnection


class SearchView(QWidget):
    """View for performing similarity searches."""
    
    def __init__(self, connection: ChromaDBConnection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.current_collection: str = ""
        self.search_results: Optional[Dict[str, Any]] = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup widget UI."""
        layout = QVBoxLayout(self)
        
        # Create splitter for query and results
        splitter = QSplitter(Qt.Vertical)
        
        # Query section
        query_widget = QWidget()
        query_layout = QVBoxLayout(query_widget)
        
        query_group = QGroupBox("Search Query")
        query_group_layout = QVBoxLayout()
        
        # Query input
        query_group_layout.addWidget(QLabel("Enter search text:"))
        self.query_input = QTextEdit()
        self.query_input.setMaximumHeight(100)
        self.query_input.setPlaceholderText("Enter text to search for similar vectors...")
        query_group_layout.addWidget(self.query_input)
        
        # Search controls
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Results:"))
        self.n_results_spin = QSpinBox()
        self.n_results_spin.setMinimum(1)
        self.n_results_spin.setMaximum(100)
        self.n_results_spin.setValue(10)
        controls_layout.addWidget(self.n_results_spin)
        
        controls_layout.addStretch()
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self._perform_search)
        self.search_button.setDefault(True)
        controls_layout.addWidget(self.search_button)
        
        query_group_layout.addLayout(controls_layout)
        query_group.setLayout(query_group_layout)
        query_layout.addWidget(query_group)
        
        splitter.addWidget(query_widget)
        
        # Results section
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        results_group = QGroupBox("Search Results")
        results_group_layout = QVBoxLayout()
        
        self.results_table = QTableWidget()
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        results_group_layout.addWidget(self.results_table)
        
        self.results_status = QLabel("No search performed")
        self.results_status.setStyleSheet("color: gray;")
        results_group_layout.addWidget(self.results_status)
        
        results_group.setLayout(results_group_layout)
        results_layout.addWidget(results_group)
        
        splitter.addWidget(results_widget)
        
        # Set splitter proportions
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
    def set_collection(self, collection_name: str):
        """Set the current collection to search."""
        self.current_collection = collection_name
        self.search_results = None
        self.results_table.setRowCount(0)
        self.results_status.setText(f"Collection: {collection_name}")
        
    def _perform_search(self):
        """Perform similarity search."""
        if not self.current_collection:
            self.results_status.setText("No collection selected")
            return
            
        query_text = self.query_input.toPlainText().strip()
        if not query_text:
            self.results_status.setText("Please enter search text")
            return
            
        n_results = self.n_results_spin.value()
        
        # Perform query
        results = self.connection.query_collection(
            self.current_collection,
            query_texts=[query_text],
            n_results=n_results
        )
        
        if not results:
            self.results_status.setText("Search failed")
            self.results_table.setRowCount(0)
            return
            
        self.search_results = results
        self._display_results(results)
        
    def _display_results(self, results: Dict[str, Any]):
        """Display search results in table."""
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        
        if not ids:
            self.results_table.setRowCount(0)
            self.results_status.setText("No results found")
            return
            
        # Determine columns
        columns = ["Rank", "Distance", "ID", "Document"]
        if metadatas and metadatas[0]:
            metadata_keys = list(metadatas[0].keys())
            columns.extend(metadata_keys)
            
        self.results_table.setColumnCount(len(columns))
        self.results_table.setHorizontalHeaderLabels(columns)
        self.results_table.setRowCount(len(ids))
        
        # Populate rows
        for row, (id_val, doc, meta, dist) in enumerate(zip(ids, documents, metadatas, distances)):
            # Rank
            self.results_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            
            # Distance/similarity score
            self.results_table.setItem(row, 1, QTableWidgetItem(f"{dist:.4f}"))
            
            # ID
            self.results_table.setItem(row, 2, QTableWidgetItem(str(id_val)))
            
            # Document
            doc_text = str(doc) if doc else ""
            if len(doc_text) > 150:
                doc_text = doc_text[:150] + "..."
            self.results_table.setItem(row, 3, QTableWidgetItem(doc_text))
            
            # Metadata columns
            if meta:
                for col_idx, key in enumerate(metadata_keys, start=4):
                    value = meta.get(key, "")
                    self.results_table.setItem(row, col_idx, QTableWidgetItem(str(value)))
                    
        self.results_table.resizeColumnsToContents()
        self.results_status.setText(f"Found {len(ids)} results")
