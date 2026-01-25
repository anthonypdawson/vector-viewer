"""Information panel for displaying database and collection metadata."""

from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QScrollArea,
    QFrame,
    QPushButton,
)
from PySide6.QtCore import Qt, QObject
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import QApplication

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.connections.chroma_connection import ChromaDBConnection
from vector_inspector.core.connections.qdrant_connection import QdrantConnection
from vector_inspector.core.connections.pinecone_connection import PineconeConnection
from vector_inspector.core.cache_manager import get_cache_manager
from vector_inspector.core.logging import log_info


class InfoPanel(QWidget):
    """Panel for displaying database and collection information."""

    def __init__(self, connection: VectorDBConnection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.connection_id: str = ""  # Will be set when collection is set
        self.current_collection: str = ""
        self.current_database: str = ""
        self.cache_manager = get_cache_manager()
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

        # Collection Information Section
        self.collection_group = QGroupBox("Collection Information")
        collection_layout = QVBoxLayout()

        self.collection_name_label = self._create_info_row("Name:", "No collection selected")
        self.vector_dim_label = self._create_info_row("Vector Dimension:", "N/A")
        self.distance_metric_label = self._create_info_row("Distance Metric:", "N/A")
        self.total_points_label = self._create_info_row("Total Points:", "0")

        # Embedding model row with configure button
        embedding_row = QWidget()
        embedding_layout = QHBoxLayout(embedding_row)
        embedding_layout.setContentsMargins(0, 2, 0, 2)

        embedding_label = QLabel("<b>Embedding Model:</b>")
        embedding_label.setMinimumWidth(150)
        self.embedding_model_label = QLabel("Auto-detect")
        self.embedding_model_label.setStyleSheet("color: gray;")
        self.embedding_model_label.setWordWrap(True)

        self.configure_embedding_btn = QPushButton("Configure...")
        self.configure_embedding_btn.setMaximumWidth(100)
        self.configure_embedding_btn.clicked.connect(self._configure_embedding_model)
        self.configure_embedding_btn.setEnabled(False)

        self.clear_embedding_btn = QPushButton("Reset to Auto-Detect")
        self.clear_embedding_btn.setMaximumWidth(140)
        self.clear_embedding_btn.setToolTip(
            "Remove custom embedding model and use automatic detection based on collection dimension."
        )
        self.clear_embedding_btn.clicked.connect(self._clear_embedding_model)
        self.clear_embedding_btn.setEnabled(False)

        embedding_layout.addWidget(embedding_label)
        embedding_layout.addWidget(self.embedding_model_label, 1)
        embedding_layout.addWidget(self.configure_embedding_btn)
        embedding_layout.addWidget(self.clear_embedding_btn)

        # Add the embedding row and other collection info widgets to the collection layout
        collection_layout.addWidget(self.collection_name_label)
        collection_layout.addWidget(self.vector_dim_label)
        collection_layout.addWidget(self.distance_metric_label)
        collection_layout.addWidget(self.total_points_label)
        collection_layout.addWidget(embedding_row)

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

    def _clear_embedding_model(self):
        """Clear the embedding model configuration for this collection (reset to autodetect)."""
        from ...services.settings_service import SettingsService

        settings = SettingsService()
        settings.remove_embedding_model(self.connection_id, self.current_collection)
        # Refresh display (force reload collection info)
        if self.current_collection:
            self.set_collection(self.current_collection, self.current_database)
        log_info(
            "✓ Cleared embedding model configuration for '%s' (via info panel button)",
            self.current_collection,
        )

    def _update_clear_button_state(self):
        """Update the clear button state based on current configuration."""
        from ...services.settings_service import SettingsService

        if not self.connection_id or not self.current_collection:
            self.clear_embedding_btn.setEnabled(False)
            return

        # Check if there's a user-configured model in settings
        settings = SettingsService()
        model_info = settings.get_embedding_model(self.connection_id, self.current_collection)

        # Enable button if there's a user-configured model
        self.clear_embedding_btn.setEnabled(model_info is not None)

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
                self._update_label(
                    self.endpoint_label, f"{self.connection.host}:{self.connection.port}"
                )
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
                self._update_label(
                    self.endpoint_label, f"{self.connection.host}:{self.connection.port}"
                )
            else:
                self._update_label(self.connection_type_label, "In-Memory")
                self._update_label(self.endpoint_label, "N/A")

            if self.connection.api_key:
                self._update_label(self.api_key_label, "Present (hidden)")
            else:
                self._update_label(self.api_key_label, "Not configured")

        elif isinstance(self.connection, PineconeConnection):
            self._update_label(self.connection_type_label, "Cloud")
            self._update_label(self.endpoint_label, "Pinecone Cloud")

            if self.connection.api_key:
                self._update_label(self.api_key_label, "Present (hidden)")
            else:
                self._update_label(self.api_key_label, "Not configured")
        else:
            self._update_label(self.connection_type_label, "Unknown")
            self._update_label(self.endpoint_label, "N/A")
            self._update_label(self.api_key_label, "Unknown")

        # Status
        self._update_label(
            self.status_label, "Connected" if self.connection.is_connected else "Disconnected"
        )

        # Count collections
        try:
            collections = self.connection.list_collections()
            self._update_label(self.collections_count_label, str(len(collections)))
        except Exception as e:
            self._update_label(self.collections_count_label, "Error")

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
            # Get collection info from database
            collection_info = self.connection.get_collection_info(self.current_collection)

            if not collection_info:
                self._update_label(self.collection_name_label, self.current_collection)
                self._update_label(self.vector_dim_label, "Unable to retrieve")
                self._update_label(self.distance_metric_label, "Unable to retrieve")
                self._update_label(self.total_points_label, "Unable to retrieve")
                self.schema_label.setText("Unable to retrieve collection info")
                self.provider_details_label.setText("N/A")
                return

            # Display the info
            self._display_collection_info(collection_info)

            # Save to cache
            if self.current_database and self.current_collection:
                log_info(
                    "[InfoPanel] Saving collection info to cache: db='%s', coll='%s'",
                    self.current_database,
                    self.current_collection,
                )
                self.cache_manager.update(
                    self.current_database,
                    self.current_collection,
                    user_inputs={"collection_info": collection_info},
                )
                log_info("[InfoPanel] ✓ Saved collection info to cache.")

        except Exception as e:
            self._update_label(self.collection_name_label, self.current_collection)
            self._update_label(self.vector_dim_label, "Error")
            self._update_label(self.distance_metric_label, "Error")
            self._update_label(self.total_points_label, "Error")
            self.schema_label.setText(f"Error: {str(e)}")
            self.schema_label.setStyleSheet("color: red; padding-left: 20px;")
            self.provider_details_label.setText("N/A")

    def _display_collection_info(self, collection_info: Dict[str, Any]):
        """Display collection information (from cache or fresh query)."""
        # Update basic info
        self._update_label(self.collection_name_label, self.current_collection)

        # Vector dimension
        vector_dim = collection_info.get("vector_dimension", "Unknown")
        self._update_label(self.vector_dim_label, str(vector_dim))

        # Enable configure button if we have a valid dimension
        self.configure_embedding_btn.setEnabled(
            vector_dim != "Unknown" and isinstance(vector_dim, int)
        )

        # Update embedding model display
        self._update_embedding_model_display(collection_info)

        # Update clear button state
        self._update_clear_button_state()

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
            self.schema_label.setStyleSheet(
                "color: white; padding-left: 20px; font-family: monospace;"
            )
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
                    details_list.append(
                        f"• Indexing threshold: {opt.get('indexing_threshold', 'N/A')}"
                    )

        elif isinstance(self.connection, PineconeConnection):
            details_list.append("• Provider: Pinecone")
            details_list.append("• Supports: Vectors, Metadata")
            details_list.append("• Cloud-hosted vector database")
            # Add Pinecone-specific info if available
            if "host" in collection_info:
                details_list.append(f"• Host: {collection_info['host']}")
            if "status" in collection_info:
                details_list.append(f"• Status: {collection_info['status']}")
            if "spec" in collection_info:
                details_list.append(f"• Spec: {collection_info['spec']}")

        if details_list:
            self.provider_details_label.setText("\n".join(details_list))
            self.provider_details_label.setStyleSheet(
                "color: white; padding-left: 20px; font-family: monospace;"
            )
        else:
            self.provider_details_label.setText("No additional details available")
            self.provider_details_label.setStyleSheet("color: gray; padding-left: 20px;")

    def set_collection(self, collection_name: str, database_name: str = ""):
        """Set the current collection and refresh its information."""
        self.current_collection = collection_name
        # Always update database_name if provided
        if database_name:
            self.current_database = database_name
            self.connection_id = database_name  # database_name is the connection ID

        log_info(
            "[InfoPanel] Setting collection: db='%s', coll='%s'",
            self.current_database,
            collection_name,
        )

        # Check cache first for collection info
        cached = self.cache_manager.get(self.current_database, self.current_collection)
        if cached and hasattr(cached, "user_inputs") and cached.user_inputs.get("collection_info"):
            log_info("[InfoPanel] ✓ Cache HIT! Loading collection info from cache.")
            collection_info = cached.user_inputs["collection_info"]
            self._display_collection_info(collection_info)
            return

        log_info("[InfoPanel] ✗ Cache MISS. Loading collection info from database...")
        self.refresh_collection_info()

    def _update_label(self, row_widget: QWidget, value: str):
        """Update the value label in an info row."""
        value_label = row_widget.property("value_label")
        if value_label and isinstance(value_label, QLabel):
            value_label.setText(value)

    def _update_embedding_model_display(self, collection_info: Dict[str, Any]):
        """Update the embedding model label based on current configuration."""
        from ...services.settings_service import SettingsService

        # Check if stored in collection metadata
        # Default: disable clear button
        self.clear_embedding_btn.setEnabled(False)

        if "embedding_model" in collection_info:
            model_name = collection_info["embedding_model"]
            model_type = collection_info.get("embedding_model_type", "stored")
            self.embedding_model_label.setText(f"{model_name} ({model_type})")
            self.embedding_model_label.setStyleSheet("color: lightgreen;")
            self.clear_embedding_btn.setEnabled(True)
            return

        # Try to get from connection using the helper method
        if self.connection and self.current_collection:
            detected_model = self.connection.get_embedding_model(
                self.current_collection, self.connection_id
            )
            if detected_model:
                self.embedding_model_label.setText(f"{detected_model} (detected)")
                self.embedding_model_label.setStyleSheet("color: lightgreen;")
                self.clear_embedding_btn.setEnabled(False)
                return

        # Check user settings
        settings = SettingsService()
        model_info = settings.get_embedding_model(self.connection_id, self.current_collection)

        if model_info:
            model_name = model_info["model"]
            model_type = model_info.get("type", "unknown")
            self.embedding_model_label.setText(f"{model_name} ({model_type})")
            self.embedding_model_label.setStyleSheet("color: lightblue;")
            self.clear_embedding_btn.setEnabled(True)
            return

        # No configuration - using auto-detect
        self.embedding_model_label.setText("Auto-detect (dimension-based)")
        self.embedding_model_label.setStyleSheet("color: orange;")
        self.clear_embedding_btn.setEnabled(False)

    def _configure_embedding_model(self):
        """Open dialog to configure embedding model for current collection."""
        if not self.current_collection:
            return

        # Show loading immediately; preparing can touch DB/registry
        from ..components.loading_dialog import LoadingDialog

        loading = LoadingDialog("Preparing model configuration...", self)
        loading.show_loading("Preparing model configuration...")
        QApplication.processEvents()

        from ..dialogs import ProviderTypeDialog, EmbeddingConfigDialog
        from ...services.settings_service import SettingsService

        # Get current collection info
        try:
            collection_info = self.connection.get_collection_info(self.current_collection)
        finally:
            # Hide loading before presenting dialogs
            loading.hide_loading()
        if not collection_info:
            return

        vector_dim = collection_info.get("vector_dimension")
        if not vector_dim or vector_dim == "Unknown":
            return

        # Get current configuration if any
        settings = SettingsService()

        current_model = None
        current_type = None

        # Check metadata first
        if "embedding_model" in collection_info:
            current_model = collection_info["embedding_model"]
            current_type = collection_info.get("embedding_model_type", "stored")
        # Then check settings
        else:
            model_info = settings.get_embedding_model(self.connection_id, self.current_collection)
            if model_info:
                current_model = model_info.get("model")
                current_type = model_info.get("type")

        # Step 1: Provider Type Selection
        type_dialog = ProviderTypeDialog(self.current_collection, vector_dim, self)

        type_result = type_dialog.exec()
        if type_result != QDialog.DialogCode.Accepted:
            return  # User cancelled

        provider_type = type_dialog.get_selected_type()
        if not provider_type:
            return

        # Step 2: Model Selection (filtered by provider type)
        model_dialog = EmbeddingConfigDialog(
            self.current_collection, vector_dim, provider_type, current_model, current_type, self
        )

        # Optionally show brief loading while populating models
        # (dialog itself handles content; only show if provider lists are large)
        result = model_dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            # Save the configuration using the new SettingsService method
            selection = model_dialog.get_selection()
            if selection:
                model_name, model_type = selection
                settings.save_embedding_model(
                    self.connection_id, self.current_collection, model_name, model_type
                )

                # Update the display immediately to show new model
                self.embedding_model_label.setText(f"{model_name} ({model_type})")
                self.embedding_model_label.setStyleSheet("color: lightblue;")

                # Enable the clear button
                self._update_clear_button_state()

                log_info(
                    "✓ Configured embedding model for '%s': %s (%s)",
                    self.current_collection,
                    model_name,
                    model_type,
                )

        elif result == 2:  # Clear configuration
            # Remove from settings using the new SettingsService method
            settings.remove_embedding_model(self.connection_id, self.current_collection)

            # Refresh display
            self._update_embedding_model_display(collection_info)

            log_info("✓ Cleared embedding model configuration for '%s'", self.current_collection)
