from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
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

        # Model cache section
        cache_group = QGroupBox("Embedding Model Cache")
        cache_layout = QVBoxLayout()

        self.cache_enabled_checkbox = QCheckBox("Enable disk caching for embedding models")
        cache_layout.addWidget(self.cache_enabled_checkbox)

        # Cache info display
        self.cache_info_label = QLabel("Cache info loading...")
        self.cache_info_label.setWordWrap(True)
        cache_layout.addWidget(self.cache_info_label)

        # Cache controls
        cache_btn_layout = QHBoxLayout()
        self.clear_cache_btn = QPushButton("Clear Cache")
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        self.refresh_cache_info_btn = QPushButton("Refresh Info")
        self.refresh_cache_info_btn.clicked.connect(self._update_cache_info)
        cache_btn_layout.addWidget(self.clear_cache_btn)
        cache_btn_layout.addWidget(self.refresh_cache_info_btn)
        cache_btn_layout.addStretch()
        cache_layout.addLayout(cache_btn_layout)

        cache_group.setLayout(cache_layout)
        layout.addWidget(cache_group)

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
        self.cache_enabled_checkbox.stateChanged.connect(
            lambda s: self.settings.set_embedding_cache_enabled(bool(s))
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
        self.cache_enabled_checkbox.setChecked(self.settings.get_embedding_cache_enabled())
        self._update_cache_info()

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

    def _update_cache_info(self):
        """Update the cache information display."""
        try:
            from vector_inspector.core.model_cache import get_cache_info

            info = get_cache_info()

            if not info["enabled"]:
                self.cache_info_label.setText("Cache is disabled")
                return

            if not info["exists"]:
                self.cache_info_label.setText(f"Location: {info['location']}\nNo cached models yet")
                return

            self.cache_info_label.setText(
                f"Location: {info['location']}\n"
                f"Cached models: {info['model_count']}\n"
                f"Total size: {info['total_size_mb']} MB"
            )
        except Exception as e:
            self.cache_info_label.setText(f"Error getting cache info: {e}")

    def _clear_cache(self):
        """Clear the embedding model cache."""
        reply = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to clear all cached embedding models?\n"
            "This will free up disk space but models will need to be re-downloaded on next use.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                from vector_inspector.core.model_cache import clear_cache

                if clear_cache():
                    QMessageBox.information(
                        self, "Cache Cleared", "Successfully cleared embedding model cache."
                    )
                    self._update_cache_info()
                else:
                    QMessageBox.warning(
                        self, "Clear Failed", "Failed to clear cache. See logs for details."
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error clearing cache: {e}")
