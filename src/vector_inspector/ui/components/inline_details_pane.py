"""Inline details pane for displaying selected row information."""

import json
from datetime import datetime
from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.services.settings_service import SettingsService


class CollapsibleSection(QWidget):
    """A collapsible section widget."""

    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._collapsed = True
        self._setup_ui(title)

    def _setup_ui(self, title: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header button
        self.toggle_button = QPushButton(f"▶ {title}")
        self.toggle_button.setFlat(True)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 6px 8px;
                border: none;
                background: #2d2d30;
                color: #e0e0e0;
                font-weight: bold;
                border-bottom: 1px solid #3e3e42;
            }
            QPushButton:hover {
                background: #3e3e42;
            }
        """)
        self.toggle_button.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_button)

        # Content container
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 4, 8, 4)
        self.content_widget.setVisible(False)
        layout.addWidget(self.content_widget)

    def _toggle(self):
        self._collapsed = not self._collapsed
        self.content_widget.setVisible(not self._collapsed)
        arrow = "▼" if not self._collapsed else "▶"
        current_text = self.toggle_button.text()
        self.toggle_button.setText(arrow + current_text[1:])

    def set_collapsed(self, collapsed: bool):
        """Set collapsed state."""
        if self._collapsed != collapsed:
            self._toggle()

    def is_collapsed(self) -> bool:
        """Check if section is collapsed."""
        return self._collapsed

    def add_widget(self, widget: QWidget):
        """Add a widget to the content area."""
        self.content_layout.addWidget(widget)


class InlineDetailsPane(QWidget):
    """Inline details pane showing selected row information."""

    open_full_details = Signal()  # Emitted when user clicks "Open full details"

    def __init__(self, view_mode: str = "data_browser", parent: Optional[QWidget] = None):
        """
        Initialize the inline details pane.

        Args:
            view_mode: Either "data_browser" or "search"
            parent: Parent widget
        """
        super().__init__(parent)
        self.view_mode = view_mode
        self.settings_service = SettingsService()
        self._current_item: Optional[dict[str, Any]] = None
        self._setup_ui()
        self._load_state()
        # Start hidden if in search mode (will show on first selection)
        if view_mode == "search":
            self.setVisible(False)

    def _setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area for all content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll)

        # Content widget
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(content)

        # Header bar
        self._create_header_bar(content_layout)

        # Document preview
        self._create_document_preview(content_layout)

        # Metadata section
        self._create_metadata_section(content_layout)

        # Vector section
        self._create_vector_section(content_layout)

        content_layout.addStretch()

    def _create_header_bar(self, parent_layout: QVBoxLayout):
        """Create the header bar."""
        header = QFrame()
        header.setStyleSheet("background: #2d2d30; border-bottom: 1px solid #3e3e42;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)

        # Left side: info labels
        info_layout = QHBoxLayout()
        info_layout.setSpacing(12)

        self.id_label = QLabel("No selection")
        font = self.id_label.font()
        font.setBold(True)
        self.id_label.setFont(font)
        info_layout.addWidget(self.id_label)

        self.timestamp_label = QLabel("")
        self.timestamp_label.setStyleSheet("color: #a0a0a0;")
        info_layout.addWidget(self.timestamp_label)

        self.dimension_label = QLabel("")
        self.dimension_label.setStyleSheet("color: #a0a0a0;")
        info_layout.addWidget(self.dimension_label)

        self.cluster_label = QLabel("")
        self.cluster_label.setStyleSheet("color: #a0a0a0;")
        info_layout.addWidget(self.cluster_label)

        # Search-specific labels
        if self.view_mode == "search":
            self.rank_label = QLabel("")
            self.rank_label.setStyleSheet("color: #4fc3f7; font-weight: bold;")
            info_layout.addWidget(self.rank_label)

            self.similarity_label = QLabel("")
            self.similarity_label.setStyleSheet("color: #66bb6a;")
            info_layout.addWidget(self.similarity_label)

        info_layout.addStretch()
        header_layout.addLayout(info_layout)

        # Right side: open full details button
        self.full_details_btn = QPushButton("Open full details...")
        self.full_details_btn.clicked.connect(self.open_full_details.emit)
        header_layout.addWidget(self.full_details_btn)

        parent_layout.addWidget(header)

    def _create_document_preview(self, parent_layout: QVBoxLayout):
        """Create document preview section."""
        label = QLabel("Document Preview")
        label.setStyleSheet("font-weight: bold; margin-top: 8px; color: #e0e0e0;")
        parent_layout.addWidget(label)

        self.document_preview = QTextEdit()
        self.document_preview.setReadOnly(True)
        self.document_preview.setMaximumHeight(100)
        self.document_preview.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                padding: 8px;
                color: #d4d4d4;
                font-size: 10pt;
            }
        """)
        parent_layout.addWidget(self.document_preview)

    def _create_metadata_section(self, parent_layout: QVBoxLayout):
        """Create collapsible metadata section."""
        self.metadata_section = CollapsibleSection("Metadata")

        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setMaximumHeight(150)
        font = QFont("Courier New", 9)
        self.metadata_text.setFont(font)
        self.metadata_text.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                color: #d4d4d4;
            }
        """)

        self.metadata_section.add_widget(self.metadata_text)
        parent_layout.addWidget(self.metadata_section)

    def _create_vector_section(self, parent_layout: QVBoxLayout):
        """Create collapsible vector section."""
        self.vector_section = CollapsibleSection("Embedding Vector")

        # Vector display
        self.vector_text = QTextEdit()
        self.vector_text.setReadOnly(True)
        self.vector_text.setMaximumHeight(150)
        font = QFont("Courier New", 9)
        self.vector_text.setFont(font)
        self.vector_text.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                border: 1px solid #3e3e42;
                border-radius: 4px;
                color: #d4d4d4;
            }
        """)
        self.vector_section.add_widget(self.vector_text)

        # Copy buttons
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 4, 0, 0)

        copy_vector_btn = QPushButton("Copy vector")
        copy_vector_btn.clicked.connect(self._copy_vector)
        button_layout.addWidget(copy_vector_btn)

        copy_json_btn = QPushButton("Copy as JSON")
        copy_json_btn.clicked.connect(self._copy_vector_json)
        button_layout.addWidget(copy_json_btn)

        button_layout.addStretch()

        button_container = QWidget()
        button_container.setLayout(button_layout)
        self.vector_section.add_widget(button_container)

        parent_layout.addWidget(self.vector_section)

    def update_item(self, item_data: Optional[dict[str, Any]]):
        """
        Update the pane with new item data.

        Args:
            item_data: Dictionary with keys: id, document, metadata, embedding,
                      and optionally (for search): rank, distance
        """
        self._current_item = item_data

        if not item_data:
            self._clear_display()
            # Hide pane in search mode when no selection
            if self.view_mode == "search":
                self.setVisible(False)
            return

        # Show pane when we have data
        if not self.isVisible():
            self.setVisible(True)

        # Update header
        self.id_label.setText(f"ID: {item_data.get('id', 'N/A')}")

        # Timestamp
        metadata = item_data.get("metadata", {}) or {}
        timestamp = metadata.get("updated_at") or metadata.get("created_at", "")
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                self.timestamp_label.setText(dt.strftime("%Y-%m-%d %H:%M"))
            except Exception:
                self.timestamp_label.setText(timestamp[:16] if len(timestamp) > 16 else timestamp)
        else:
            self.timestamp_label.setText("")

        # Dimensions
        embedding = item_data.get("embedding")
        if embedding is not None:
            try:
                dim = len(embedding)
                self.dimension_label.setText(f"{dim}D")
            except Exception:
                self.dimension_label.setText("")
        else:
            self.dimension_label.setText("")

        # Cluster
        cluster = metadata.get("cluster", metadata.get("cluster_id", ""))
        if cluster:
            self.cluster_label.setText(f"Cluster: {cluster}")
        else:
            self.cluster_label.setText("")

        # Search-specific metrics
        if self.view_mode == "search":
            rank = item_data.get("rank")
            if rank is not None:
                self.rank_label.setText(f"Rank: {rank}")
            else:
                self.rank_label.setText("")

            distance = item_data.get("distance")
            if distance is not None:
                similarity = 1 - distance if distance <= 1 else 0
                self.similarity_label.setText(f"Similarity: {similarity:.3f}")
            else:
                self.similarity_label.setText("")

        # Document preview
        document = item_data.get("document", "")
        if document:
            preview = str(document)[:500]  # Cap at 500 chars
            if len(str(document)) > 500:
                preview += "..."
            self.document_preview.setText(preview)
        else:
            self.document_preview.setText("(No document text)")

        # Metadata (filter out already-displayed fields)
        filtered_metadata = {
            k: v
            for k, v in metadata.items()
            if k not in ["updated_at", "created_at", "cluster", "cluster_id", "embedding_dimension"]
        }
        if filtered_metadata:
            self.metadata_text.setText(json.dumps(filtered_metadata, indent=2))
        else:
            self.metadata_text.setText("(No metadata)")

        # Vector
        if embedding is not None:
            try:
                vector_list = (
                    embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                )
                self.vector_text.setText(str(vector_list))
                # Update section title with dimension
                self.vector_section.toggle_button.setText(
                    f"▶ Embedding Vector ({len(vector_list)}-dim)"
                )
            except Exception:
                self.vector_text.setText("(Unable to display vector)")
        else:
            self.vector_text.setText("(No embedding)")

    def _clear_display(self):
        """Clear all displayed information."""
        self.id_label.setText("No selection")
        self.timestamp_label.setText("")
        self.dimension_label.setText("")
        self.cluster_label.setText("")

        if self.view_mode == "search":
            self.rank_label.setText("")
            self.similarity_label.setText("")

        self.document_preview.setText("")
        self.metadata_text.setText("")
        self.vector_text.setText("")

    def _copy_vector(self):
        """Copy vector values to clipboard."""
        if not self._current_item:
            return

        embedding = self._current_item.get("embedding")
        if embedding is not None:
            try:
                vector_list = (
                    embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                )
                vector_str = ", ".join(str(v) for v in vector_list)
                QApplication.clipboard().setText(vector_str)
            except Exception:
                pass

    def _copy_vector_json(self):
        """Copy vector as JSON to clipboard."""
        if not self._current_item:
            return

        embedding = self._current_item.get("embedding")
        if embedding is not None:
            try:
                vector_list = (
                    embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)
                )
                json_str = json.dumps(
                    {
                        "id": self._current_item.get("id"),
                        "vector": vector_list,
                        "dimension": len(vector_list),
                    },
                    indent=2,
                )
                QApplication.clipboard().setText(json_str)
            except Exception:
                pass

    def _load_state(self):
        """Load pane state from settings."""
        key_prefix = f"inline_details_{self.view_mode}"

        # Load section states
        metadata_collapsed = self.settings_service.get(f"{key_prefix}_metadata_collapsed", False)
        self.metadata_section.set_collapsed(metadata_collapsed)

        vector_collapsed = self.settings_service.get(f"{key_prefix}_vector_collapsed", True)
        self.vector_section.set_collapsed(vector_collapsed)

    def save_state(self):
        """Save pane state to settings."""
        key_prefix = f"inline_details_{self.view_mode}"

        self.settings_service.set(
            f"{key_prefix}_metadata_collapsed", self.metadata_section.is_collapsed()
        )
        self.settings_service.set(
            f"{key_prefix}_vector_collapsed", self.vector_section.is_collapsed()
        )
