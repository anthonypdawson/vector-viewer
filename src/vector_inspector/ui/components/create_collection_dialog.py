"""Dialog for creating collections with optional sample data."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from vector_inspector.core.model_registry import get_model_registry
from vector_inspector.core.sample_data import SampleDataType


class CreateCollectionDialog(QDialog):
    """Dialog for creating a new collection with optional sample data."""

    name_input: QLineEdit
    add_sample_check: QCheckBox
    count_spin: QSpinBox

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Collection")
        self.setMinimumWidth(450)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)

        # Collection settings
        collection_group = QGroupBox("Collection Settings")
        collection_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., test_collection")
        collection_layout.addRow("Collection Name:", self.name_input)

        collection_group.setLayout(collection_layout)
        layout.addWidget(collection_group)

        # Sample data settings
        sample_group = QGroupBox("Sample Data (Optional)")
        sample_layout = QVBoxLayout()

        self.add_sample_check = QCheckBox("Add sample data")
        self.add_sample_check.setChecked(False)
        sample_layout.addWidget(self.add_sample_check)

        # Sample data options (initially disabled)
        options_layout = QFormLayout()

        self.count_spin = QSpinBox()
        self.count_spin.setMinimum(10)
        self.count_spin.setMaximum(10000)
        self.count_spin.setValue(100)
        self.count_spin.setSingleStep(10)
        self.count_spin.setEnabled(False)
        options_layout.addRow("Number of Items:", self.count_spin)

        self.data_type_combo = QComboBox()
        self.data_type_combo.addItem("Plain Text", SampleDataType.TEXT.value)
        self.data_type_combo.addItem("Markdown", SampleDataType.MARKDOWN.value)
        self.data_type_combo.addItem("Structured (JSON-like)", SampleDataType.JSON.value)
        self.data_type_combo.setEnabled(False)
        options_layout.addRow("Data Type:", self.data_type_combo)

        self.model_combo = QComboBox()
        self._populate_models()
        self.model_combo.setEnabled(False)
        options_layout.addRow("Embedding Model:", self.model_combo)

        sample_layout.addLayout(options_layout)

        # Info label
        self.info_label = QLabel(
            "Sample data will be automatically embedded and inserted into the collection."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: gray; font-size: 11px; padding: 5px;")
        sample_layout.addWidget(self.info_label)

        sample_group.setLayout(sample_layout)
        layout.addWidget(sample_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.create_button = QPushButton("Create")
        self.create_button.clicked.connect(self.accept)
        self.create_button.setDefault(True)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.create_button)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def _populate_models(self):
        """Populate the model dropdown with available embedding models."""
        registry = get_model_registry()

        # Get models suitable for text embedding
        # Prioritize smaller, faster models for sample data
        preferred_models = [
            ("all-MiniLM-L6-v2", "sentence-transformer", "384 dims - Fast & compact"),
            ("all-MiniLM-L12-v2", "sentence-transformer", "384 dims - Balanced"),
            ("all-mpnet-base-v2", "sentence-transformer", "768 dims - High quality"),
            ("paraphrase-MiniLM-L6-v2", "sentence-transformer", "384 dims - Paraphrase"),
        ]

        for model_name, model_type, description in preferred_models:
            model_info = registry.get_model_by_name(model_name)
            if model_info:
                display_text = f"{model_name} ({description})"
                self.model_combo.addItem(display_text, (model_name, model_type))

        # Add a separator and additional models if desired
        if self.model_combo.count() > 0:
            self.model_combo.insertSeparator(self.model_combo.count())

        # Add other text models from registry
        for model in registry.get_models_by_type("sentence-transformer"):
            model_name = model.name
            # Skip if already added
            if any(
                model_name in self.model_combo.itemText(i) for i in range(self.model_combo.count())
            ):
                continue
            display_text = f"{model_name} ({model.dimension} dims)"
            self.model_combo.addItem(display_text, (model_name, "sentence-transformer"))

        # Set default to first item if available
        if self.model_combo.count() > 0:
            self.model_combo.setCurrentIndex(0)

    def _connect_signals(self):
        """Connect UI signals."""
        self.add_sample_check.toggled.connect(self._on_sample_toggle)

    def _on_sample_toggle(self, checked: bool):
        """Handle sample data checkbox toggle."""
        self.count_spin.setEnabled(checked)
        self.data_type_combo.setEnabled(checked)
        self.model_combo.setEnabled(checked)

    def get_configuration(self) -> dict:
        """Get the dialog configuration.

        Returns:
            Dictionary with collection configuration
        """
        config = {
            "name": self.name_input.text().strip(),
            "add_sample": self.add_sample_check.isChecked(),
        }

        if config["add_sample"]:
            model_data = self.model_combo.currentData()
            config["count"] = self.count_spin.value()
            config["data_type"] = self.data_type_combo.currentData()
            config["embedder_name"] = model_data[0] if model_data else None
            config["embedder_type"] = model_data[1] if model_data else None

        return config

    def accept(self):
        """Validate and accept the dialog."""
        name = self.name_input.text().strip()

        if not name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a collection name.")
            return

        # Validate collection name format
        if not name.replace("_", "").replace("-", "").isalnum():
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Collection name must contain only letters, numbers, hyphens, and underscores.",
            )
            return

        # If adding sample data, validate model selection
        if self.add_sample_check.isChecked():
            if self.model_combo.currentData() is None:
                QMessageBox.warning(
                    self, "Invalid Input", "Please select an embedding model for sample data."
                )
                return

        super().accept()
