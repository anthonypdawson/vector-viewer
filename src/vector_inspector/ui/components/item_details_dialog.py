"""Dialog for viewing item details (read-only)."""

import json
from datetime import UTC, datetime
from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from vector_inspector.utils import has_embedding


class ItemDetailsDialog(QDialog):
    """Dialog for viewing vector item details (read-only)."""

    item_data: dict[str, Any]
    id_label: QLabel
    document_display: QTextEdit
    metadata_display: QTextEdit
    distance_label: Optional[QLabel]
    rank_label: Optional[QLabel]
    vector_display: Optional[QTextEdit]
    created_label: Optional[QLabel]
    updated_label: Optional[QLabel]
    dimension_label: Optional[QLabel]
    cluster_label: Optional[QLabel]
    dot_product_label: Optional[QLabel]
    cosine_label: Optional[QLabel]

    def __init__(
        self,
        parent=None,
        item_data: Optional[dict[str, Any]] = None,
        show_search_info: bool = False,
    ):
        """Initialize the details dialog.

        Args:
            parent: Parent widget
            item_data: Dictionary containing item data with keys:
                - id: Item ID
                - document: Document text
                - metadata: Metadata dictionary
                - distance: (optional) Search distance/similarity score
                - rank: (optional) Search result rank
                - embedding: (optional) Vector embedding
            show_search_info: If True, show distance and rank fields
        """
        super().__init__(parent)
        self.item_data = item_data or {}
        self.show_search_info = show_search_info
        self.setWindowTitle("Item Details")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self._setup_ui()
        self._populate_fields()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        # Form layout
        form_layout = QFormLayout()

        # ID field
        self.id_label = QLabel()
        self.id_label.setStyleSheet("font-weight: bold;")
        form_layout.addRow("ID:", self.id_label)

        # Extract timestamp and cluster info from metadata
        metadata = self.item_data.get("metadata", {})
        created_at = self._extract_timestamp(metadata, ["created_at", "created", "createdAt"])
        updated_at = self._extract_timestamp(
            metadata, ["updated_at", "updated", "updatedAt", "modified", "modified_at"]
        )
        cluster = self._extract_cluster(metadata)

        # Timestamp fields
        if created_at:
            self.created_label = QLabel()
            form_layout.addRow("Created:", self.created_label)
        else:
            self.created_label = None

        if updated_at:
            self.updated_label = QLabel()
            form_layout.addRow("Updated:", self.updated_label)
        else:
            self.updated_label = None

        # Embedding dimension
        embedding = self.item_data.get("embedding")
        if has_embedding(embedding):
            self.dimension_label = QLabel()
            form_layout.addRow("Embedding Dimension:", self.dimension_label)
        else:
            self.dimension_label = None

        # Cluster assignment
        if cluster is not None:
            self.cluster_label = QLabel()
            form_layout.addRow("Cluster:", self.cluster_label)
        else:
            self.cluster_label = None

        # Search-specific fields (if applicable)
        if self.show_search_info:
            self.rank_label = QLabel()
            form_layout.addRow("Rank:", self.rank_label)

            self.distance_label = QLabel()
            form_layout.addRow("Distance:", self.distance_label)

            # Additional similarity metrics (if available)
            if self.item_data.get("dot_product") is not None:
                self.dot_product_label = QLabel()
                form_layout.addRow("Dot Product:", self.dot_product_label)
            else:
                self.dot_product_label = None

            if self.item_data.get("cosine_similarity") is not None:
                self.cosine_label = QLabel()
                form_layout.addRow("Cosine Similarity:", self.cosine_label)
            else:
                self.cosine_label = None
        else:
            self.dot_product_label = None
            self.cosine_label = None

        # Document field
        form_layout.addRow("Document:", QLabel(""))
        self.document_display = QTextEdit()
        self.document_display.setReadOnly(True)
        self.document_display.setMaximumHeight(150)
        form_layout.addRow(self.document_display)

        # Metadata field
        form_layout.addRow("Metadata:", QLabel(""))
        self.metadata_display = QTextEdit()
        self.metadata_display.setReadOnly(True)
        self.metadata_display.setMaximumHeight(150)
        form_layout.addRow(self.metadata_display)

        # Vector embedding field (collapsible)
        # Use safe check to avoid "ambiguous truth value" error with arrays
        embedding = self.item_data.get("embedding")
        if has_embedding(embedding):
            form_layout.addRow("Vector Embedding:", QLabel(""))
            self.vector_display = QTextEdit()
            self.vector_display.setReadOnly(True)
            self.vector_display.setMaximumHeight(100)
            form_layout.addRow(self.vector_display)
        else:
            self.vector_display = None

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setDefault(True)

        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _populate_fields(self):
        """Populate fields with item data."""
        # ID
        self.id_label.setText(str(self.item_data.get("id", "")))

        # Timestamps
        metadata = self.item_data.get("metadata", {})
        if self.created_label:
            created_at = self._extract_timestamp(metadata, ["created_at", "created", "createdAt"])
            if created_at:
                self.created_label.setText(self._format_timestamp(created_at))

        if self.updated_label:
            updated_at = self._extract_timestamp(
                metadata, ["updated_at", "updated", "updatedAt", "modified", "modified_at"]
            )
            if updated_at:
                self.updated_label.setText(self._format_timestamp(updated_at))

        # Embedding dimension
        if self.dimension_label:
            embedding = self.item_data.get("embedding")
            if has_embedding(embedding):
                try:
                    dimension = len(
                        embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                    )
                    self.dimension_label.setText(str(dimension))
                except Exception:
                    self.dimension_label.setText("N/A")

        # Cluster assignment
        if self.cluster_label:
            cluster = self._extract_cluster(metadata)
            if cluster is not None:
                self.cluster_label.setText(str(cluster))

        # Search-specific fields
        if self.show_search_info:
            if hasattr(self, "rank_label") and self.rank_label:
                rank = self.item_data.get("rank", "")
                self.rank_label.setText(str(rank) if rank else "N/A")

            if hasattr(self, "distance_label") and self.distance_label:
                distance = self.item_data.get("distance", "")
                if distance is not None and distance != "":
                    self.distance_label.setText(f"{distance:.4f}")
                else:
                    self.distance_label.setText("N/A")

            if self.dot_product_label:
                dot_product = self.item_data.get("dot_product")
                if dot_product is not None:
                    self.dot_product_label.setText(f"{dot_product:.4f}")

            if self.cosine_label:
                cosine_similarity = self.item_data.get("cosine_similarity")
                if cosine_similarity is not None:
                    self.cosine_label.setText(f"{cosine_similarity:.4f}")

        # Document
        document = self.item_data.get("document", "")
        self.document_display.setPlainText(str(document) if document else "(No document)")

        # Metadata - filter out the fields we've already shown separately
        if metadata:
            filtered_metadata = self._filter_metadata_for_display(metadata)
            if filtered_metadata:
                metadata_text = json.dumps(filtered_metadata, indent=2)
                self.metadata_display.setPlainText(metadata_text)
            else:
                self.metadata_display.setPlainText("(All metadata fields shown above)")
        else:
            self.metadata_display.setPlainText("(No metadata)")

        # Vector embedding
        if self.vector_display:
            embedding = self.item_data.get("embedding")
            # Safe check: avoid "ambiguous truth value" error with numpy arrays
            if has_embedding(embedding):
                try:
                    # Handle different vector types
                    vector_list = (
                        embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                    )
                    dimension = len(vector_list)

                    # Show first few and last few dimensions
                    if dimension > 10:
                        preview = [*vector_list[:5], "...", *vector_list[-5:]]
                        preview_text = f"Dimension: {dimension}\n{preview}"
                    else:
                        preview_text = f"Dimension: {dimension}\n{vector_list}"

                    self.vector_display.setPlainText(preview_text)
                except Exception as e:
                    self.vector_display.setPlainText(f"(Error displaying vector: {e})")
            else:
                self.vector_display.setPlainText("(No embedding)")

    def _extract_timestamp(self, metadata: dict[str, Any], field_names: list[str]) -> Optional[Any]:
        """Extract timestamp from metadata using common field names.

        Args:
            metadata: Metadata dictionary
            field_names: List of possible field names to check

        Returns:
            Timestamp value if found, None otherwise
        """
        for field_name in field_names:
            if field_name in metadata:
                value = metadata[field_name]
                if value:
                    return value
        return None

    def _format_timestamp(self, timestamp: Any) -> str:
        """Format timestamp for display.

        Args:
            timestamp: Timestamp value (string, int, float, or datetime)

        Returns:
            Formatted timestamp string
        """
        try:
            # Handle different timestamp formats
            if isinstance(timestamp, str):
                # Try parsing ISO format
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    return timestamp
            elif isinstance(timestamp, (int, float)):
                # Assume Unix timestamp
                dt = datetime.fromtimestamp(timestamp, tz=UTC)
                return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            elif isinstance(timestamp, datetime):
                return timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                return str(timestamp)
        except Exception:
            return str(timestamp)

    def _extract_cluster(self, metadata: dict[str, Any]) -> Optional[Any]:
        """Extract cluster assignment from metadata.

        Args:
            metadata: Metadata dictionary

        Returns:
            Cluster value if found, None otherwise
        """
        cluster_fields = ["cluster", "cluster_id", "cluster_label", "clusterLabel", "clusterID"]
        for field_name in cluster_fields:
            if field_name in metadata:
                value = metadata[field_name]
                if value is not None:
                    return value
        return None

    def _filter_metadata_for_display(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Filter metadata to exclude fields already shown separately.

        Args:
            metadata: Original metadata dictionary

        Returns:
            Filtered metadata dictionary
        """
        # Fields that are shown separately in the UI
        excluded_fields = {
            "created_at",
            "created",
            "createdAt",
            "updated_at",
            "updated",
            "updatedAt",
            "modified",
            "modified_at",
            "cluster",
            "cluster_id",
            "cluster_label",
            "clusterLabel",
            "clusterID",
        }

        return {k: v for k, v in metadata.items() if k not in excluded_fields}
