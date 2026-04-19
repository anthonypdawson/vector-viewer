from __future__ import annotations

import warnings

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.extensions import settings_panel_hook
from vector_inspector.services.settings_service import SettingsService


class _FeatureUninstallThread(QThread):
    """Background thread that runs pip uninstall for a feature group."""

    done = Signal(int, str)  # returncode, combined_output

    def __init__(self, feature_id: str, parent=None):
        super().__init__(parent)
        self._feature_id = feature_id

    def run(self):
        from vector_inspector.services.provider_install_service import uninstall_feature

        returncode, output = uninstall_feature(self._feature_id)
        self.done.emit(returncode, output)


class _ProviderUninstallThread(QThread):
    """Background thread that runs pip uninstall for a database provider."""

    done = Signal(int, str)  # returncode, combined_output

    def __init__(self, provider_id: str, parent=None):
        super().__init__(parent)
        self._provider_id = provider_id

    def run(self):
        from vector_inspector.services.provider_install_service import uninstall_provider

        returncode, output = uninstall_provider(self._provider_id)
        self.done.emit(returncode, output)


class _StatusCheckThread(QThread):
    """Background thread that checks availability of feature/provider packages.

    Emits ``result(id, available)`` for each item as soon as its check
    completes, so the UI can update one row at a time rather than waiting
    for all checks to finish.
    """

    result = Signal(str, bool)  # id, available
    all_done = Signal()

    def __init__(self, checks: dict, parent=None):
        super().__init__(parent)
        self._checks: dict = checks

    def run(self):
        for item_id, check in self._checks.items():
            try:
                available = check()
            except Exception:
                available = False
            self.result.emit(item_id, available)
        self.all_done.emit()


def _deps_tooltip(specs: list[str]) -> str:
    """Return an HTML tooltip string listing versioned package specs."""
    if not specs:
        return ""
    bullets = "".join(f"<br>&nbsp;&nbsp;&bull;&nbsp;{s}" for s in specs)
    return f"<b>Packages:</b>{bullets}"


class SettingsDialog(QDialog):
    """Modal settings dialog backed by SettingsService."""

    def __init__(self, settings_service: SettingsService = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.settings = settings_service or SettingsService()
        self._init_ui()
        self._load_values()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)

        # Central tab widget
        self._tabs = QTabWidget()
        outer_layout.addWidget(self._tabs)

        # Internal registry: tab name -> (QWidget, QVBoxLayout)
        self._tab_widgets: dict[str, tuple[QWidget, QVBoxLayout]] = {}

        # Build the core tabs in display order
        self._create_general_tab()
        self._create_embeddings_tab()
        self._create_appearance_tab()
        self._create_llm_tab()
        self._create_features_tab()
        self._create_providers_tab()

        # Allow extensions to inject into tabs.
        # General tab layout is passed as parent_layout for backward-compatible
        # handlers (e.g. telemetry).  Tab-aware handlers use dialog.get_tab_layout().
        try:
            settings_panel_hook.trigger(self.get_tab_layout("General"), self.settings, self)
        except Exception:
            pass

        # Action buttons live outside the tab widget
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
        outer_layout.addLayout(btn_layout)

        # Signals
        self.apply_btn.clicked.connect(self._apply)
        self.ok_btn.clicked.connect(self._ok)
        self.cancel_btn.clicked.connect(self.reject)
        self.reset_btn.clicked.connect(self._reset_defaults)

        # Container for programmatic sections
        self._extra_sections = []

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _create_general_tab(self):
        layout = self.get_tab_layout("General")

        # Search defaults
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Default results:"))
        self.default_results = QSpinBox()
        self.default_results.setMinimum(1)
        self.default_results.setMaximum(1000)
        search_layout.addWidget(self.default_results)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # Embeddings auto-generate
        self.auto_embed_checkbox = QCheckBox("Auto-generate embeddings for new text")
        layout.addWidget(self.auto_embed_checkbox)

        # Window geometry
        self.restore_geometry_checkbox = QCheckBox("Restore window size/position on startup")
        layout.addWidget(self.restore_geometry_checkbox)

        # Loading screen
        self.hide_splash_checkbox = QCheckBox("Hide loading screen on startup")
        layout.addWidget(self.hide_splash_checkbox)

        # Status bar message duration
        status_group = QGroupBox("Status Bar")
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Message duration:"))
        self.status_timeout_spin = QSpinBox()
        self.status_timeout_spin.setMinimum(0)
        self.status_timeout_spin.setMaximum(30)
        self.status_timeout_spin.setSuffix(" s")
        self.status_timeout_spin.setSpecialValueText("Permanent")
        self.status_timeout_spin.setToolTip(
            "How long status bar messages stay visible.\n0 = permanent (until the next message replaces it)."
        )
        status_layout.addWidget(self.status_timeout_spin)
        status_layout.addStretch()
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        layout.addStretch()

        # Signals — immediate apply on change
        self.default_results.valueChanged.connect(lambda v: self.settings.set_default_n_results(v))
        self.auto_embed_checkbox.stateChanged.connect(lambda s: self.settings.set_auto_generate_embeddings(bool(s)))
        self.restore_geometry_checkbox.stateChanged.connect(
            lambda s: self.settings.set_window_restore_geometry(bool(s))
        )
        self.hide_splash_checkbox.stateChanged.connect(lambda s: self.settings.set("hide_loading_screen", bool(s)))
        self.status_timeout_spin.valueChanged.connect(lambda v: self.settings.set_status_timeout_ms(v * 1000))

    def _create_embeddings_tab(self):
        layout = self.get_tab_layout("Embeddings")

        cache_group = QGroupBox("Embedding Model Cache")
        cache_layout = QVBoxLayout()

        self.cache_enabled_checkbox = QCheckBox("Enable disk caching for embedding models")
        cache_layout.addWidget(self.cache_enabled_checkbox)

        self.cache_info_label = QLabel("Cache info loading...")
        self.cache_info_label.setWordWrap(True)
        cache_layout.addWidget(self.cache_info_label)

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
        layout.addStretch()

        self.cache_enabled_checkbox.stateChanged.connect(lambda s: self.settings.set_embedding_cache_enabled(bool(s)))

    def _create_appearance_tab(self):
        layout = self.get_tab_layout("Appearance")

        appearance_group = QGroupBox("Highlight Colors")
        appearance_layout = QVBoxLayout()

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Highlight color:"))
        self.highlight_btn = QPushButton()
        self.highlight_btn.setFixedSize(40, 22)
        top_row.addWidget(self.highlight_btn)

        top_row.addWidget(QLabel("Highlight background:"))
        self.highlight_bg_btn = QPushButton()
        self.highlight_bg_btn.setFixedSize(40, 22)
        top_row.addWidget(self.highlight_bg_btn)
        top_row.addStretch()
        appearance_layout.addLayout(top_row)

        self.use_accent_checkbox = QCheckBox("Enable accent/highlight colors")
        appearance_layout.addWidget(self.use_accent_checkbox)

        reset_row = QHBoxLayout()
        self.reset_highlight_btn = QPushButton("Reset highlight to default")
        reset_row.addWidget(self.reset_highlight_btn)
        reset_row.addStretch()
        self.reset_highlight_btn.clicked.connect(self._reset_highlight_defaults)
        appearance_layout.addLayout(reset_row)

        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)
        layout.addStretch()

        self.highlight_btn.clicked.connect(lambda: self._pick_color("ui.highlight_color", self.highlight_btn))
        self.highlight_bg_btn.clicked.connect(lambda: self._pick_color("ui.highlight_color_bg", self.highlight_bg_btn))
        self.use_accent_checkbox.stateChanged.connect(self._on_use_accent_changed)

    def _create_llm_tab(self):
        # Pre-create the tab so it appears in the correct position.
        # Content is injected by llm_settings_panel via the settings_panel_hook
        # using dialog.get_tab_layout("LLM").
        self.get_tab_layout("LLM")

    def _create_features_tab(self):
        """Build the 'Features' tab — rows are populated immediately from static
        metadata, availability is checked in the background."""
        from vector_inspector.core.provider_detection import get_all_feature_metadata
        from vector_inspector.services.provider_install_service import _FEATURE_PACKAGE_SPECS

        layout = self.get_tab_layout("Features")

        group = QGroupBox("Optional Feature Groups")
        group_layout = QVBoxLayout()
        group_layout.setSpacing(6)

        intro = QLabel(
            "Optional feature packs extend Vector Inspector with additional capabilities. "
            "Hover over a row to see which packages will be installed."
        )
        intro.setWordWrap(True)
        group_layout.addWidget(intro)

        self._feature_rows: dict[str, dict] = {}
        self._uninstall_threads: list[_FeatureUninstallThread] = []
        self._features_checked: bool = False
        self._feature_check_thread: _StatusCheckThread | None = None

        for info in get_all_feature_metadata():
            tooltip = _deps_tooltip(_FEATURE_PACKAGE_SPECS.get(info.id, []))

            row_widget = QWidget()
            row_widget.setToolTip(tooltip)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 4, 0, 4)

            status_lbl = QLabel()
            status_lbl.setFixedWidth(18)
            row_layout.addWidget(status_lbl)

            text_layout = QVBoxLayout()
            text_layout.setSpacing(1)
            name_lbl = QLabel(f"<b>{info.name}</b>")
            name_lbl.setToolTip(tooltip)
            desc_lbl = QLabel(info.description)
            desc_lbl.setStyleSheet("color: #888888; font-size: 11px;")
            text_layout.addWidget(name_lbl)
            text_layout.addWidget(desc_lbl)
            row_layout.addLayout(text_layout, stretch=1)

            action_btn = QPushButton()
            action_btn.setFixedWidth(100)
            action_btn.setToolTip(tooltip)
            row_layout.addWidget(action_btn)

            status_msg = QLabel()
            status_msg.setMinimumWidth(130)
            row_layout.addWidget(status_msg)

            group_layout.addWidget(row_widget)

            widgets = {
                "status_lbl": status_lbl,
                "action_btn": action_btn,
                "status_msg": status_msg,
            }
            self._feature_rows[info.id] = widgets
            self._set_row_pending(widgets)

        group.setLayout(group_layout)
        layout.addWidget(group)

        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.clicked.connect(self._refresh_feature_statuses)
        refresh_layout.addStretch()
        refresh_layout.addWidget(refresh_btn)
        layout.addLayout(refresh_layout)
        layout.addStretch()

        self._start_feature_status_check()

    def _create_providers_tab(self):
        """Build the 'Providers' tab — rows are populated immediately from static
        metadata, availability is checked in the background."""
        from vector_inspector.core.provider_detection import get_all_provider_metadata
        from vector_inspector.services.provider_install_service import _PROVIDER_PACKAGE_SPECS

        layout = self.get_tab_layout("Providers")

        group = QGroupBox("Database Providers")
        group_layout = QVBoxLayout()
        group_layout.setSpacing(6)

        intro = QLabel(
            "Database provider packages connect Vector Inspector to vector databases. "
            "Hover over a row to see which packages will be installed."
        )
        intro.setWordWrap(True)
        group_layout.addWidget(intro)

        self._provider_rows: dict[str, dict] = {}
        self._provider_uninstall_threads: list[_ProviderUninstallThread] = []
        self._providers_checked: bool = False
        self._provider_check_thread: _StatusCheckThread | None = None

        for pinfo in get_all_provider_metadata():
            tooltip = _deps_tooltip(_PROVIDER_PACKAGE_SPECS.get(pinfo.id, []))

            row_widget = QWidget()
            row_widget.setToolTip(tooltip)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 4, 0, 4)

            status_lbl = QLabel()
            status_lbl.setFixedWidth(18)
            row_layout.addWidget(status_lbl)

            text_layout = QVBoxLayout()
            text_layout.setSpacing(1)
            name_lbl = QLabel(f"<b>{pinfo.name}</b>")
            name_lbl.setToolTip(tooltip)
            desc_lbl = QLabel(pinfo.description)
            desc_lbl.setStyleSheet("color: #888888; font-size: 11px;")
            text_layout.addWidget(name_lbl)
            text_layout.addWidget(desc_lbl)
            row_layout.addLayout(text_layout, stretch=1)

            action_btn = QPushButton()
            action_btn.setFixedWidth(100)
            action_btn.setToolTip(tooltip)
            row_layout.addWidget(action_btn)

            status_msg = QLabel()
            status_msg.setMinimumWidth(130)
            row_layout.addWidget(status_msg)

            group_layout.addWidget(row_widget)

            widgets = {
                "status_lbl": status_lbl,
                "action_btn": action_btn,
                "status_msg": status_msg,
            }
            self._provider_rows[pinfo.id] = widgets
            self._set_row_pending(widgets)

        group.setLayout(group_layout)
        layout.addWidget(group)

        refresh_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Status")
        refresh_btn.clicked.connect(self._refresh_provider_statuses)
        refresh_layout.addStretch()
        refresh_layout.addWidget(refresh_btn)
        layout.addLayout(refresh_layout)
        layout.addStretch()

        self._start_provider_status_check()

    # ------------------------------------------------------------------
    # Row state helpers
    # ------------------------------------------------------------------

    def _set_row_pending(self, widgets: dict) -> None:
        """Render a row in the 'Checking\u2026' greyed-out state."""
        widgets["status_lbl"].setText("\u22ef")  # ⋯
        widgets["status_lbl"].setStyleSheet("color: #888888;")
        widgets["action_btn"].setText("Checking\u2026")
        widgets["action_btn"].setEnabled(False)
        widgets["status_msg"].setText("")

    def _apply_row_result(
        self,
        widgets: dict,
        available: bool,
        *,
        on_install,
        on_uninstall,
    ) -> None:
        """Apply an availability check result to a row's widgets.

        Does not touch ``status_msg`` \u2014 callers set that independently.
        """
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                widgets["action_btn"].clicked.disconnect()
        except RuntimeError:
            pass

        if available:
            widgets["status_lbl"].setText("\u2714")  # ✔
            widgets["status_lbl"].setStyleSheet("color: #4caf50; font-weight: bold;")
            widgets["action_btn"].setText("Uninstall")
            widgets["action_btn"].clicked.connect(on_uninstall)
        else:
            widgets["status_lbl"].setText("\u2718")  # ✘
            widgets["status_lbl"].setStyleSheet("color: #f44336; font-weight: bold;")
            widgets["action_btn"].setText("Install")
            widgets["action_btn"].clicked.connect(on_install)
        widgets["action_btn"].setEnabled(True)

    # ------------------------------------------------------------------
    # Background status checks \u2014 features
    # ------------------------------------------------------------------

    def _start_feature_status_check(self) -> None:
        """Set all feature rows to pending and kick off a background check."""
        from vector_inspector.core.provider_detection import get_feature_availability_checks

        for widgets in self._feature_rows.values():
            self._set_row_pending(widgets)
        self._features_checked = False

        thread = _StatusCheckThread(get_feature_availability_checks(), parent=self)
        thread.result.connect(self._on_feature_status_result)
        thread.all_done.connect(self._on_feature_checks_done)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._feature_check_thread = thread

    def _on_feature_status_result(self, feature_id: str, available: bool) -> None:
        widgets = self._feature_rows.get(feature_id)
        if widgets is None:
            return
        self._apply_row_result(
            widgets,
            available,
            on_install=lambda fid=feature_id: self._on_install_clicked(fid),
            on_uninstall=lambda fid=feature_id: self._on_uninstall_clicked(fid),
        )

    def _on_feature_checks_done(self) -> None:
        self._features_checked = True

    def _refresh_feature_statuses(self) -> None:
        """Kick off an async re-check of all feature group statuses."""
        self._start_feature_status_check()

    # ------------------------------------------------------------------
    # Background status checks \u2014 providers
    # ------------------------------------------------------------------

    def _start_provider_status_check(self) -> None:
        """Set all provider rows to pending and kick off a background check."""
        from vector_inspector.core.provider_detection import get_provider_availability_checks

        for widgets in self._provider_rows.values():
            self._set_row_pending(widgets)
        self._providers_checked = False

        thread = _StatusCheckThread(get_provider_availability_checks(), parent=self)
        thread.result.connect(self._on_provider_status_result)
        thread.all_done.connect(self._on_provider_checks_done)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._provider_check_thread = thread

    def _on_provider_status_result(self, provider_id: str, available: bool) -> None:
        widgets = self._provider_rows.get(provider_id)
        if widgets is None:
            return
        self._apply_row_result(
            widgets,
            available,
            on_install=lambda pid=provider_id: self._on_provider_install_clicked(pid),
            on_uninstall=lambda pid=provider_id: self._on_provider_uninstall_clicked(pid),
        )

    def _on_provider_checks_done(self) -> None:
        self._providers_checked = True

    def _refresh_provider_statuses(self) -> None:
        """Kick off an async re-check of all provider statuses."""
        self._start_provider_status_check()

    def _refresh_all_statuses(self) -> None:
        self._start_feature_status_check()
        self._start_provider_status_check()

    # ------------------------------------------------------------------
    # Install / uninstall action handlers
    # ------------------------------------------------------------------

    def _on_install_clicked(self, feature_id: str) -> None:
        from vector_inspector.core.provider_detection import get_feature_static_info
        from vector_inspector.ui.dialogs.provider_install_dialog import ProviderInstallDialog

        info = get_feature_static_info(feature_id)
        if info is None:
            return
        dlg = ProviderInstallDialog(info, parent=self)
        dlg.exec()
        # Re-check in background after user closes the install dialog.
        self._start_feature_status_check()

    def _on_uninstall_clicked(self, feature_id: str) -> None:
        from vector_inspector.core.provider_detection import get_feature_static_info

        info = get_feature_static_info(feature_id)
        if info is None:
            return

        reply = QMessageBox.question(
            self,
            "Uninstall Feature",
            f"Uninstall '{info.name}'?\nThis will remove its Python packages.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        row = self._feature_rows[feature_id]
        row["action_btn"].setEnabled(False)
        row["status_msg"].setText("Uninstalling\u2026")

        thread = _FeatureUninstallThread(feature_id, parent=self)
        thread.done.connect(lambda rc, out, fid=feature_id: self._on_uninstall_done(fid, rc, out))
        thread.done.connect(thread.deleteLater)
        thread.start()
        self._uninstall_threads.append(thread)

    def _on_uninstall_done(self, feature_id: str, returncode: int, output: str) -> None:
        from vector_inspector.core.logging import log_error

        row = self._feature_rows[feature_id]
        if returncode == 0:
            # Known state: now uninstalled.  Apply directly \u2014 no re-check needed.
            self._apply_row_result(
                row,
                available=False,
                on_install=lambda fid=feature_id: self._on_install_clicked(fid),
                on_uninstall=lambda fid=feature_id: self._on_uninstall_clicked(fid),
            )
            row["status_msg"].setText("Removed")
        else:
            # Uninstall failed \u2014 package is still present; keep existing state.
            row["status_msg"].setText("Failed \u2014 see logs")
            log_error("Uninstall of feature '%s' failed (rc=%d): %s", feature_id, returncode, output)

    def _on_provider_install_clicked(self, provider_id: str) -> None:
        from vector_inspector.core.provider_detection import get_provider_static_info
        from vector_inspector.ui.dialogs.provider_install_dialog import ProviderInstallDialog

        info = get_provider_static_info(provider_id)
        if info is None:
            return
        dlg = ProviderInstallDialog(info, parent=self)
        dlg.exec()
        self._start_provider_status_check()

    def _on_provider_uninstall_clicked(self, provider_id: str) -> None:
        from vector_inspector.core.provider_detection import get_provider_static_info

        info = get_provider_static_info(provider_id)
        if info is None:
            return

        reply = QMessageBox.question(
            self,
            "Uninstall Provider",
            f"Uninstall '{info.name}'?\nThis will remove its Python packages.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        row = self._provider_rows[provider_id]
        row["action_btn"].setEnabled(False)
        row["status_msg"].setText("Uninstalling\u2026")

        thread = _ProviderUninstallThread(provider_id, parent=self)
        thread.done.connect(lambda rc, out, pid=provider_id: self._on_provider_uninstall_done(pid, rc, out))
        thread.done.connect(thread.deleteLater)
        thread.start()
        self._provider_uninstall_threads.append(thread)

    def _on_provider_uninstall_done(self, provider_id: str, returncode: int, output: str) -> None:
        from vector_inspector.core.logging import log_error

        row = self._provider_rows[provider_id]
        if returncode == 0:
            self._apply_row_result(
                row,
                available=False,
                on_install=lambda pid=provider_id: self._on_provider_install_clicked(pid),
                on_uninstall=lambda pid=provider_id: self._on_provider_uninstall_clicked(pid),
            )
            row["status_msg"].setText("Removed")
        else:
            row["status_msg"].setText("Failed \u2014 see logs")
            log_error("Uninstall of provider '%s' failed (rc=%d): %s", provider_id, returncode, output)

    # ------------------------------------------------------------------
    # Tab access API
    # ------------------------------------------------------------------

    def get_tab_layout(self, tab_name: str) -> QVBoxLayout:
        """Return the QVBoxLayout for the named tab, creating the tab if needed.

        Extensions can use this to target a specific tab::

            dialog.get_tab_layout("LLM").addWidget(my_group)
        """
        if tab_name in self._tab_widgets:
            return self._tab_widgets[tab_name][1]
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self._tabs.addTab(widget, tab_name)
        self._tab_widgets[tab_name] = (widget, layout)
        return layout

    def add_section(self, widget_or_layout, tab: str = "General"):
        """Add a section (widget or layout) to the specified tab.

        Args:
            widget_or_layout: A QWidget or QLayout to add.
            tab: Name of the destination tab (default ``'General'``).  If the
                named tab does not exist it will be created automatically.
        """
        try:
            layout = self.get_tab_layout(tab)
            if hasattr(widget_or_layout, "setParent"):
                layout.addWidget(widget_or_layout)
            else:
                layout.addLayout(widget_or_layout)
            self._extra_sections.append(widget_or_layout)
        except Exception:
            pass

    def _load_values(self):
        # Breadcrumb controls are not present in core dialog.
        self.default_results.setValue(self.settings.get_default_n_results())
        self.auto_embed_checkbox.setChecked(self.settings.get_auto_generate_embeddings())
        self.restore_geometry_checkbox.setChecked(self.settings.get_window_restore_geometry())
        self.hide_splash_checkbox.setChecked(self.settings.get("hide_loading_screen", False))
        timeout_ms = self.settings.get_status_timeout_ms()
        timeout_seconds = (timeout_ms + 500) // 1000
        self.status_timeout_spin.blockSignals(True)
        self.status_timeout_spin.setValue(timeout_seconds)
        self.status_timeout_spin.blockSignals(False)
        self.cache_enabled_checkbox.setChecked(self.settings.get_embedding_cache_enabled())
        self._update_cache_info()
        # Load appearance colors
        try:
            hc = self.settings.get_highlight_color()
            hcbg = self.settings.get_highlight_color_bg()
            self._set_button_color(self.highlight_btn, hc)
            self._set_button_color(self.highlight_bg_btn, hcbg)
            try:
                self.use_accent_checkbox.setChecked(self.settings.get_use_accent_enabled())
            except Exception:
                self.use_accent_checkbox.setChecked(False)
        except Exception:
            pass

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
        self.status_timeout_spin.setValue(0)  # permanent by default
        self._apply()

    def _set_button_color(self, btn: QPushButton, color: str):
        try:
            btn.setStyleSheet(f"background-color: {color}; border: 1px solid #444;")
        except Exception:
            pass

    def _on_use_accent_changed(self, state: int):
        try:
            enabled = bool(state)
            self.settings.set_use_accent_enabled(enabled)
            # Immediately apply or clear the global stylesheet depending on the flag
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None:
                return
            if enabled:
                from vector_inspector.ui.styles import TAB_FONT_SIZE, TAB_FONT_WEIGHT, TAB_PADDING

                highlight = self.settings.get_highlight_color()
                highlight_bg = self.settings.get_highlight_color_bg()
                global_qss = (
                    f"QTabBar::tab {{ font-weight: {TAB_FONT_WEIGHT}; padding: {TAB_PADDING}; font-size: {TAB_FONT_SIZE};}}"
                    f"QTabBar::tab:selected {{ background-color: {highlight_bg}; border-bottom: 2px solid {highlight}; }}"
                    f"QProgressDialog QLabel {{ color: {highlight}; }}"
                )
                app.setStyleSheet(global_qss)
            else:
                app.setStyleSheet("")
        except Exception:
            pass

    def _pick_color(self, key: str, btn: QPushButton):
        try:
            # current color
            if key == "ui.highlight_color":
                current = self.settings.get_highlight_color()
            else:
                current = self.settings.get_highlight_color_bg()
            dlg = QColorDialog(self)
            dlg.setOption(QColorDialog.ShowAlphaChannel, True)
            # try parse existing rgba() into QColor; fallback to default
            try:
                # QColor accepts CSS-style rgba via setNamedColor for hex, for rgba we'll construct
                # Parse numbers
                parts = current.replace("rgba(", "").replace(")", "").split(",")
                if len(parts) >= 3:
                    r = int(parts[0])
                    g = int(parts[1])
                    b = int(parts[2])
                    a = 255
                    if len(parts) == 4:
                        a = int(float(parts[3]) * 255)
                    color = QColor(r, g, b, a)
                    dlg.setCurrentColor(color)
            except Exception:
                pass

            if dlg.exec() == QDialog.DialogCode.Accepted:
                c = dlg.currentColor()
                rgba = f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha() / 255:.2f})"
                if key == "ui.highlight_color":
                    self.settings.set_highlight_color(rgba)
                else:
                    self.settings.set_highlight_color_bg(rgba)
                # update button swatch
                self._set_button_color(btn, rgba)
                # Immediately update global stylesheet
                try:
                    from PySide6.QtWidgets import QApplication

                    from vector_inspector.ui.styles import TAB_FONT_SIZE, TAB_FONT_WEIGHT, TAB_PADDING

                    # Only apply accent stylesheet when the feature is enabled.
                    app = QApplication.instance()
                    if app is not None:
                        if self.settings.get_use_accent_enabled():
                            highlight = self.settings.get_highlight_color()
                            highlight_bg = self.settings.get_highlight_color_bg()
                            global_qss = (
                                f"QTabBar::tab {{ font-weight: {TAB_FONT_WEIGHT}; padding: {TAB_PADDING}; font-size: {TAB_FONT_SIZE};}}"
                                f"QTabBar::tab:selected {{ background-color: {highlight_bg}; border-bottom: 2px solid {highlight}; }}"
                                f"QProgressDialog QLabel {{ color: {highlight}; }}"
                            )
                            app.setStyleSheet(global_qss)
                        else:
                            # Clear any previously applied accent stylesheet
                            app.setStyleSheet("")
                except Exception:
                    pass
        except Exception as e:
            QMessageBox.warning(self, "Color Picker", f"Failed to pick color: {e}")

    def _apply_preset(self, primary: str, bg: str):
        try:
            self.settings.set_highlight_color(primary)
            self.settings.set_highlight_color_bg(bg)
            self._set_button_color(self.highlight_btn, primary)
            self._set_button_color(self.highlight_bg_btn, bg)
            # Apply immediately
            try:
                from PySide6.QtWidgets import QApplication

                from vector_inspector.ui.styles import TAB_FONT_SIZE, TAB_FONT_WEIGHT, TAB_PADDING

                app = QApplication.instance()
                if app is not None:
                    if self.settings.get_use_accent_enabled():
                        highlight = self.settings.get_highlight_color()
                        highlight_bg = self.settings.get_highlight_color_bg()
                        global_qss = (
                            f"QTabBar::tab {{ font-weight: {TAB_FONT_WEIGHT}; padding: {TAB_PADDING}; font-size: {TAB_FONT_SIZE};}}"
                            f"QTabBar::tab:selected {{ background-color: {highlight_bg}; border-bottom: 2px solid {highlight}; }}"
                            f"QProgressDialog QLabel {{ color: {highlight}; }}"
                        )
                        app.setStyleSheet(global_qss)
                    else:
                        app.setStyleSheet("")
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "Apply Preset", f"Failed to apply preset: {e}")

    def _reset_highlight_defaults(self):
        try:
            from vector_inspector.ui.styles import HIGHLIGHT_COLOR, HIGHLIGHT_COLOR_BG

            self._apply_preset(HIGHLIGHT_COLOR, HIGHLIGHT_COLOR_BG)
        except Exception as e:
            QMessageBox.warning(self, "Reset Highlight", f"Failed to reset highlight: {e}")

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
                    QMessageBox.information(self, "Cache Cleared", "Successfully cleared embedding model cache.")
                    self._update_cache_info()
                else:
                    QMessageBox.warning(self, "Clear Failed", "Failed to clear cache. See logs for details.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error clearing cache: {e}")
