"""Information panel for displaying database and collection metadata."""

from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, QObject

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.connections.chroma_connection import ChromaDBConnection
from vector_inspector.core.connections.qdrant_connection import QdrantConnection


class InfoPanel(QWidget):
    """Panel for displaying database and collection information."""
    
    def __init__(self, connection: VectorDBConnection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.current_collection: str = ""
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup widget UI."""
        layout = QVBoxLayout(self)
        
        # Create scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Container for all info sections
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(10)
        
        # Database Information Section
        self.db_group = QGroupBox("Database Information")
        db_layout = QVBoxLayout()
        
        self.provider_label = self._create_info_row("Provider:", "Not connected")
        self.connection_type_label = self._create_info_row("Connection Type:", "N/A")
        self.endpoint_label = self._create_info_row("Endpoint:", "N/A")
        self.api_key_label = self._create_info_row("API Key:", "N/A")
        self.status_label = self._create_info_row("Status:", "Disconnected")
        self.collections_count_label = self._create_info_row("Total Collections:", "0")
        
        db_layout.addWidget(self.provider_label)
        db_layout.addWidget(self.connection_type_label)
        db_layout.addWidget(self.endpoint_label)
        db_layout.addWidget(self.api_key_label)
        db_layout.addWidget(self.status_label)
        db_layout.addWidget(self.collections_count_label)
        
        self.db_group.setLayout(db_layout)
        container_layout.addWidget(self.db_group)
        
        # Collections List Section
        self.collections_group = QGroupBox("Available Collections")
        collections_layout = QVBoxLayout()
        
        self.collections_list_label = QLabel("No collections")
        self.collections_list_label.setWordWrap(True)
        self.collections_list_label.setStyleSheet("color: gray; padding: 10px;")
        collections_layout.addWidget(self.collections_list_label)
        
        self.collections_group.setLayout(collections_layout)
        container_layout.addWidget(self.collections_group)
        
        # Collection Information Section
        self.collection_group = QGroupBox("Collection Information")
        collection_layout = QVBoxLayout()
        
        self.collection_name_label = self._create_info_row("Name:", "No collection selected")
        self.vector_dim_label = self._create_info_row("Vector Dimension:", "N/A")
        self.distance_metric_label = self._create_info_row("Distance Metric:", "N/A")
        self.total_points_label = self._create_info_row("Total Points:", "0")
        
        collection_layout.addWidget(self.collection_name_label)
        collection_layout.addWidget(self.vector_dim_label)
        collection_layout.addWidget(self.distance_metric_label)
        collection_layout.addWidget(self.total_points_label)
        
        # Payload Schema subsection
        schema_label = QLabel("<b>Payload Schema:</b>")
        collection_layout.addWidget(schema_label)
        
        self.schema_label = QLabel("N/A")
        self.schema_label.setWordWrap(True)
        self.schema_label.setStyleSheet("color: gray; padding-left: 20px;")
        collection_layout.addWidget(self.schema_label)
        
        # Provider-specific details
        provider_details_label = QLabel("<b>Provider-Specific Details:</b>")
        collection_layout.addWidget(provider_details_label)
        
        self.provider_details_label = QLabel("N/A")
        self.provider_details_label.setWordWrap(True)
        self.provider_details_label.setStyleSheet("color: gray; padding-left: 20px;")
        collection_layout.addWidget(self.provider_details_label)
        
        self.collection_group.setLayout(collection_layout)
        container_layout.addWidget(self.collection_group)
        
        # Add stretch to push content to top
        container_layout.addStretch()
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        # Initial state
        self.refresh_database_info()
        
    def _create_info_row(self, label: str, value: str) -> QWidget:
        """Create a row with label and value."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)
        
        label_widget = QLabel(f"<b>{label}</b>")
        label_widget.setMinimumWidth(150)
        row_layout.addWidget(label_widget)
        
        value_widget = QLabel(value)
        value_widget.setWordWrap(True)
        value_widget.setStyleSheet("color: white;")
        row_layout.addWidget(value_widget, stretch=1)
        
        # Store value widget for later updates (use setProperty for type safety)
        row.setProperty("value_label", value_widget)
        
        return row
        
    def refresh_database_info(self):
        """Refresh database connection information."""
        if not self.connection or not self.connection.is_connected:
            self._update_label(self.provider_label, "Not connected")
            self._update_label(self.connection_type_label, "N/A")
            self._update_label(self.endpoint_label, "N/A")
            self._update_label(self.api_key_label, "N/A")
            self._update_label(self.status_label, "Disconnected")
            self._update_label(self.collections_count_label, "0")
            self.collections_list_label.setText("No collections")
            self.collections_list_label.setStyleSheet("color: gray; padding: 10px;")
            # Also clear collection info
            self._update_label(self.collection_name_label, "No collection selected")
            self._update_label(self.vector_dim_label, "N/A")
            self._update_label(self.distance_metric_label, "N/A")
            self._update_label(self.total_points_label, "0")
            self.schema_label.setText("N/A")
            self.provider_details_label.setText("N/A")
            return
            
        # Get provider name
        provider_name = self.connection.__class__.__name__.replace("Connection", "")
        self._update_label(self.provider_label, provider_name)
        
        # Get connection details
        if isinstance(self.connection, ChromaDBConnection):
            if self.connection.path:
                self._update_label(self.connection_type_label, "Persistent (Local)")
                self._update_label(self.endpoint_label, self.connection.path)
            elif self.connection.host and self.connection.port:
                self._update_label(self.connection_type_label, "HTTP (Remote)")
                self._update_label(self.endpoint_label, f"{self.connection.host}:{self.connection.port}")
            else:
                self._update_label(self.connection_type_label, "Ephemeral (In-Memory)")
                self._update_label(self.endpoint_label, "N/A")
            self._update_label(self.api_key_label, "Not required")
            
        elif isinstance(self.connection, QdrantConnection):
            if self.connection.path:
                self._update_label(self.connection_type_label, "Embedded (Local)")
                self._update_label(self.endpoint_label, self.connection.path)
            elif self.connection.url:
                self._update_label(self.connection_type_label, "Remote (URL)")
                self._update_label(self.endpoint_label, self.connection.url)
            elif self.connection.host:
                self._update_label(self.connection_type_label, "Remote (Host)")
                self._update_label(self.endpoint_label, f"{self.connection.host}:{self.connection.port}")
            else:
                self._update_label(self.connection_type_label, "In-Memory")
                self._update_label(self.endpoint_label, "N/A")
                
            if self.connection.api_key:
                self._update_label(self.api_key_label, "Present (hidden)")
            else:
                self._update_label(self.api_key_label, "Not configured")
        else:
            self._update_label(self.connection_type_label, "Unknown")
            self._update_label(self.endpoint_label, "N/A")
            self._update_label(self.api_key_label, "Unknown")
        
        # Status
        self._update_label(self.status_label, "Connected" if self.connection.is_connected else "Disconnected")
        
        # List collections
        try:
            collections = self.connection.list_collections()
            self._update_label(self.collections_count_label, str(len(collections)))
            
            if collections:
                collections_text = "\n".join([f"• {name}" for name in sorted(collections)])
                self.collections_list_label.setText(collections_text)
                self.collections_list_label.setStyleSheet("color: white; padding: 10px; font-family: monospace;")
            else:
                self.collections_list_label.setText("No collections found")
                self.collections_list_label.setStyleSheet("color: gray; padding: 10px;")
        except Exception as e:
            self._update_label(self.collections_count_label, "Error")
            self.collections_list_label.setText(f"Error loading collections: {str(e)}")
            self.collections_list_label.setStyleSheet("color: red; padding: 10px;")
    
    def refresh_collection_info(self):
        """Refresh collection-specific information."""
        if not self.current_collection or not self.connection or not self.connection.is_connected:
            self._update_label(self.collection_name_label, "No collection selected")
            self._update_label(self.vector_dim_label, "N/A")
            self._update_label(self.distance_metric_label, "N/A")
            self._update_label(self.total_points_label, "0")
            self.schema_label.setText("N/A")
            self.provider_details_label.setText("N/A")
            return
            
        try:
            # Get collection info
            collection_info = self.connection.get_collection_info(self.current_collection)
            
            if not collection_info:
                self._update_label(self.collection_name_label, self.current_collection)
                self._update_label(self.vector_dim_label, "Unable to retrieve")
                self._update_label(self.distance_metric_label, "Unable to retrieve")
                self._update_label(self.total_points_label, "Unable to retrieve")
                self.schema_label.setText("Unable to retrieve collection info")
                self.provider_details_label.setText("N/A")
                return
            
            # Update basic info
            self._update_label(self.collection_name_label, self.current_collection)
            
            # Vector dimension
            vector_dim = collection_info.get("vector_dimension", "Unknown")
            self._update_label(self.vector_dim_label, str(vector_dim))
            
            # Distance metric
            distance = collection_info.get("distance_metric", "Unknown")
            self._update_label(self.distance_metric_label, distance)
            
            # Total points
            count = collection_info.get("count", 0)
            self._update_label(self.total_points_label, f"{count:,}")
            
            # Metadata schema
            metadata_fields = collection_info.get("metadata_fields", [])
            if metadata_fields:
                schema_text = "\n".join([f"• {field}" for field in sorted(metadata_fields)])
                self.schema_label.setText(schema_text)
                self.schema_label.setStyleSheet("color: white; padding-left: 20px; font-family: monospace;")
            else:
                self.schema_label.setText("No metadata fields found")
                self.schema_label.setStyleSheet("color: gray; padding-left: 20px;")
            
            # Provider-specific details
            details_list = []
            
            if isinstance(self.connection, ChromaDBConnection):
                details_list.append("• Provider: ChromaDB")
                details_list.append("• Supports: Documents, Metadata, Embeddings")
                details_list.append("• Default embedding: all-MiniLM-L6-v2")
                
            elif isinstance(self.connection, QdrantConnection):
                details_list.append("• Provider: Qdrant")
                details_list.append("• Supports: Points, Payload, Vectors")
                # Get additional Qdrant-specific info if available
                if "config" in collection_info:
                    config = collection_info["config"]
                    if "hnsw_config" in config:
                        hnsw = config["hnsw_config"]
                        details_list.append(f"• HNSW M: {hnsw.get('m', 'N/A')}")
                        details_list.append(f"• HNSW ef_construct: {hnsw.get('ef_construct', 'N/A')}")
                    if "optimizer_config" in config:
                        opt = config["optimizer_config"]
                        details_list.append(f"• Indexing threshold: {opt.get('indexing_threshold', 'N/A')}")
            
            if details_list:
                self.provider_details_label.setText("\n".join(details_list))
                self.provider_details_label.setStyleSheet("color: white; padding-left: 20px; font-family: monospace;")
            else:
                self.provider_details_label.setText("No additional details available")
                self.provider_details_label.setStyleSheet("color: gray; padding-left: 20px;")
                
        except Exception as e:
            self._update_label(self.collection_name_label, self.current_collection)
            self._update_label(self.vector_dim_label, "Error")
            self._update_label(self.distance_metric_label, "Error")
            self._update_label(self.total_points_label, "Error")
            self.schema_label.setText(f"Error: {str(e)}")
            self.schema_label.setStyleSheet("color: red; padding-left: 20px;")
            self.provider_details_label.setText("N/A")
    
    def set_collection(self, collection_name: str):
        """Set the current collection and refresh its information."""
        self.current_collection = collection_name
        self.refresh_collection_info()
    
    def _update_label(self, row_widget: QWidget, value: str):
        """Update the value label in an info row."""
        value_label = row_widget.property("value_label")
        if value_label and isinstance(value_label, QLabel):
            value_label.setText(value)
