"""Action buttons for metadata view operations."""

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QWidget,
)

from vector_inspector.services.settings_service import SettingsService


class MetadataActionButtons(QWidget):
    """
    Reusable action buttons for metadata operations.

    Signals:
        refresh_clicked: Emitted when refresh button clicked
        add_clicked: Emitted when add button clicked
        delete_clicked: Emitted when delete button clicked
        export_requested: Emitted when export requested (format_type)
        import_requested: Emitted when import requested (format_type)
        generate_on_edit_changed: Emitted when generate embeddings checkbox toggled (checked)
    """

    refresh_clicked = Signal()
    add_clicked = Signal()
    delete_clicked = Signal()
    export_requested = Signal(str)  # format_type
    import_requested = Signal(str)  # format_type
    generate_on_edit_changed = Signal(bool)  # checked

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.settings_service = SettingsService()
        self._setup_ui()

    def _setup_ui(self):
        """Setup UI controls."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Refresh button
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self.refresh_clicked.emit)
        self.refresh_button.setToolTip("Refresh data and clear cache")
        layout.addWidget(self.refresh_button)

        # Add button
        self.add_button = QPushButton("Add Item")
        self.add_button.clicked.connect(self.add_clicked.emit)
        layout.addWidget(self.add_button)

        # Delete button
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_clicked.emit)
        layout.addWidget(self.delete_button)

        # Generate embeddings checkbox
        self.generate_on_edit_checkbox = QCheckBox("Generate embeddings on edit")
        try:
            pref = bool(self.settings_service.get("generate_embeddings_on_edit", False))
        except Exception:
            pref = False
        self.generate_on_edit_checkbox.setChecked(pref)
        self.generate_on_edit_checkbox.toggled.connect(self._on_generate_toggled)
        layout.addWidget(self.generate_on_edit_checkbox)

        # Export button with menu
        self.export_button = QPushButton("Export...")
        self.export_button.setStyleSheet("QPushButton::menu-indicator { width: 0px; }")
        export_menu = QMenu(self)
        export_menu.addAction("Export to JSON", lambda: self.export_requested.emit("json"))
        export_menu.addAction("Export to CSV", lambda: self.export_requested.emit("csv"))
        export_menu.addAction("Export to Parquet", lambda: self.export_requested.emit("parquet"))
        self.export_button.setMenu(export_menu)
        layout.addWidget(self.export_button)

        # Import button with menu
        self.import_button = QPushButton("Import...")
        self.import_button.setStyleSheet("QPushButton::menu-indicator { width: 0px; }")
        import_menu = QMenu(self)
        import_menu.addAction("Import from JSON", lambda: self.import_requested.emit("json"))
        import_menu.addAction("Import from CSV", lambda: self.import_requested.emit("csv"))
        import_menu.addAction("Import from Parquet", lambda: self.import_requested.emit("parquet"))
        self.import_button.setMenu(import_menu)
        layout.addWidget(self.import_button)

        layout.addStretch()

    def _on_generate_toggled(self, checked: bool):
        """Handle generate embeddings checkbox toggle."""
        self.settings_service.set("generate_embeddings_on_edit", bool(checked))
        self.generate_on_edit_changed.emit(checked)

    def set_enabled(self, enabled: bool):
        """Enable/disable all buttons."""
        self.refresh_button.setEnabled(enabled)
        self.add_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)
        self.export_button.setEnabled(enabled)
        self.import_button.setEnabled(enabled)
