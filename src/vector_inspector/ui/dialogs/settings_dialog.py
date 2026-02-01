from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from vector_inspector.extensions import settings_panel_hook
from vector_inspector.services.settings_service import SettingsService


class SettingsDialog(QDialog):
    """Modal settings dialog backed by SettingsService."""

    def __init__(self, settings_service: SettingsService = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.settings = settings_service or SettingsService()
        self._init_ui()
        self._load_values()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Breadcrumb controls are provided by pro extensions (vector-studio)
        # via the settings_panel_hook. Core does not add breadcrumb options.

        # Search defaults
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Default results:"))
        self.default_results = QSpinBox()
        self.default_results.setMinimum(1)
        self.default_results.setMaximum(1000)
        search_layout.addWidget(self.default_results)
        layout.addLayout(search_layout)

        # Embeddings
        self.auto_embed_checkbox = QCheckBox("Auto-generate embeddings for new text")
        layout.addWidget(self.auto_embed_checkbox)

        # Window geometry
        self.restore_geometry_checkbox = QCheckBox("Restore window size/position on startup")
        layout.addWidget(self.restore_geometry_checkbox)

        # Loading screen
        self.hide_splash_checkbox = QCheckBox("Hide loading screen on startup")
        layout.addWidget(self.hide_splash_checkbox)

        # Buttons
        btn_layout = QHBoxLayout()
        self.apply_btn = QPushButton("Apply")
        self.ok_btn = QPushButton("OK")
        self.cancel_btn = QPushButton("Cancel")
        self.reset_btn = QPushButton("Reset to defaults")
        btn_layout.addWidget(self.reset_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.apply_btn)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        # Allow external extensions to add sections before the buttons
        try:
            # Handlers receive (parent_layout, settings_service, dialog)
            settings_panel_hook.trigger(layout, self.settings, self)
        except Exception:
            pass

        layout.addLayout(btn_layout)

        # Signals
        self.apply_btn.clicked.connect(self._apply)
        self.ok_btn.clicked.connect(self._ok)
        self.cancel_btn.clicked.connect(self.reject)
        self.reset_btn.clicked.connect(self._reset_defaults)

        # Immediate apply on change for some controls
        self.default_results.valueChanged.connect(lambda v: self.settings.set_default_n_results(v))
        self.auto_embed_checkbox.stateChanged.connect(
            lambda s: self.settings.set_auto_generate_embeddings(bool(s))
        )
        self.restore_geometry_checkbox.stateChanged.connect(
            lambda s: self.settings.set_window_restore_geometry(bool(s))
        )
        self.hide_splash_checkbox.stateChanged.connect(
            lambda s: self.settings.set("hide_loading_screen", bool(s))
        )

        # Container for programmatic sections
        self._extra_sections = []

    def add_section(self, widget_or_layout):
        """Programmatically add a section (widget or layout) to the dialog.

        `widget_or_layout` can be a QWidget or QLayout. It will be added
        immediately to the dialog's main layout.
        """
        try:
            if hasattr(widget_or_layout, "setParent"):
                # QWidget
                self.layout().addWidget(widget_or_layout)
            else:
                # Assume QLayout
                self.layout().addLayout(widget_or_layout)
            self._extra_sections.append(widget_or_layout)
        except Exception:
            pass

    def _load_values(self):
        # Breadcrumb controls are not present in core dialog.
        self.default_results.setValue(self.settings.get_default_n_results())
        self.auto_embed_checkbox.setChecked(self.settings.get_auto_generate_embeddings())
        self.restore_geometry_checkbox.setChecked(self.settings.get_window_restore_geometry())
        self.hide_splash_checkbox.setChecked(self.settings.get("hide_loading_screen", False))

    def _apply(self):
        # Values are already applied on change; ensure persistence and close
        self.settings._save_settings()

    def _ok(self):
        self._apply()
        self.accept()

    def _reset_defaults(self):
        # Reset to recommended defaults
        self.default_results.setValue(10)
        self.auto_embed_checkbox.setChecked(True)
        self.restore_geometry_checkbox.setChecked(True)
        self.hide_splash_checkbox.setChecked(False)
        self._apply()
