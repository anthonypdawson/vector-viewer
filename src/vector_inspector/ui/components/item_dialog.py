"""Dialog for adding/editing items in a collection."""

from typing import Any, Optional

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class ItemDialog(QDialog):
    """Dialog for adding or editing a vector item."""

    item_data: Optional[dict[str, Any]]
    is_edit_mode: bool
    id_input: QLineEdit
    document_input: QTextEdit
    metadata_input: QTextEdit

    def __init__(self, parent=None, item_data: Optional[dict[str, Any]] = None):
        super().__init__(parent)
        self.item_data = item_data
        self.is_edit_mode = item_data is not None
        self.setWindowTitle("Edit Item" if self.is_edit_mode else "Add Item")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self._setup_ui()
        if self.is_edit_mode:
            self._populate_fields()

    def _setup_ui(self):
        """Setup dialog UI."""
        layout = QVBoxLayout(self)

        # Form layout
        form_layout = QFormLayout()

        # ID field
        self.id_input = QLineEdit()
        if self.is_edit_mode:
            self.id_input.setReadOnly(True)
        form_layout.addRow("ID:", self.id_input)

        # Document field
        form_layout.addRow("Document:", QLabel(""))
        self.document_input = QTextEdit()
        self.document_input.setMaximumHeight(150)
        form_layout.addRow(self.document_input)

        # Metadata field
        form_layout.addRow("Metadata (JSON):", QLabel(""))
        self.metadata_input = QTextEdit()
        self.metadata_input.setMaximumHeight(150)
        self.metadata_input.setPlaceholderText(
            '{"key": "value", "category": "example"}'
        )
        form_layout.addRow(self.metadata_input)

        layout.addLayout(form_layout)

        # Note about embeddings
        note_label = QLabel(
            "Note: Embeddings will be automatically generated from the document text."
        )
        note_label.setStyleSheet("color: gray; font-style: italic;")
        note_label.setWordWrap(True)
        layout.addWidget(note_label)

        # Buttons
        button_layout = QHBoxLayout()

        save_button = QPushButton("Save" if self.is_edit_mode else "Add")
        save_button.clicked.connect(self.accept)
        save_button.setDefault(True)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

    def _populate_fields(self):
        """Populate fields with existing item data."""
        if not self.item_data:
            return

        self.id_input.setText(str(self.item_data.get("id", "")))
        self.document_input.setPlainText(str(self.item_data.get("document", "")))

        metadata = self.item_data.get("metadata", {})
        if metadata:
            import json

            self.metadata_input.setPlainText(json.dumps(metadata, indent=2))

    def get_item_data(self) -> Optional[dict[str, Any]]:
        """Get item data from dialog fields."""
        import json

        item_id = self.id_input.text().strip()
        document = self.document_input.toPlainText().strip()

        # Parse metadata
        metadata = {}
        metadata_text = self.metadata_input.toPlainText().strip()
        if metadata_text:
            try:
                metadata = json.loads(metadata_text)
            except json.JSONDecodeError:
                QMessageBox.warning(
                    self, "Invalid Metadata", "Metadata must be valid JSON format."
                )
                return None

        return {"id": item_id, "document": document, "metadata": metadata}
