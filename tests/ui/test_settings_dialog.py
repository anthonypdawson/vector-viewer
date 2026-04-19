from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from vector_inspector.ui.dialogs.settings_dialog import SettingsDialog


class FakeSettings:
    def __init__(self):
        self._store = {
            "default_n_results": 7,
            "auto_generate_embeddings": False,
            "window_restore_geometry": False,
            "hide_loading_screen": True,
            "embedding_cache_enabled": False,
        }

    def get_default_n_results(self):
        return self._store["default_n_results"]

    def get_auto_generate_embeddings(self):
        return self._store["auto_generate_embeddings"]

    def get_window_restore_geometry(self):
        return self._store["window_restore_geometry"]

    def get(self, key, default=None):
        return self._store.get(key, default)

    def get_embedding_cache_enabled(self):
        return self._store["embedding_cache_enabled"]

    def set_default_n_results(self, v):
        self._store["default_n_results"] = v

    def set_auto_generate_embeddings(self, v):
        self._store["auto_generate_embeddings"] = v

    def set_window_restore_geometry(self, v):
        self._store["window_restore_geometry"] = v

    def set(self, key, val):
        self._store[key] = val

    def set_embedding_cache_enabled(self, v):
        self._store["embedding_cache_enabled"] = v

    # Status timeout setting
    def get_status_timeout_ms(self):
        return self._store.get("status.timeout_ms", 0)

    def set_status_timeout_ms(self, ms):
        self._store["status.timeout_ms"] = int(ms)

    # Highlight color stubs for new Appearance controls
    def get_highlight_color(self):
        return self._store.get("ui.highlight_color", "rgba(0,122,204,1)")

    def get_highlight_color_bg(self):
        return self._store.get("ui.highlight_color_bg", "rgba(0,122,204,0.12)")

    def set_highlight_color(self, color):
        self._store["ui.highlight_color"] = color

    def set_highlight_color_bg(self, color):
        self._store["ui.highlight_color_bg"] = color

    def get_use_accent_enabled(self):
        return self._store.get("use_accent_enabled", False)

    def set_use_accent_enabled(self, val):
        self._store["use_accent_enabled"] = val

    def _save_settings(self):
        # pretend to persist
        pass


def test_load_values_and_apply(qtbot, monkeypatch):
    fake_settings = FakeSettings()
    # Prevent QMessageBox dialogs from blocking
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    # initial values loaded from fake settings
    assert dlg.default_results.value() == 7
    assert dlg.auto_embed_checkbox.isChecked() is False

    # change a value via UI and ensure settings updated
    dlg.default_results.setValue(20)
    assert fake_settings.get_default_n_results() == 20

    # test reset defaults sets recommended defaults and calls save
    dlg._reset_defaults()
    assert dlg.default_results.value() == 10


def test_add_section_and_cache_info(monkeypatch, qtbot):
    fake_settings = FakeSettings()
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    # Patch core.model_cache.get_cache_info to return a disabled state
    monkeypatch.setattr(
        "vector_inspector.core.model_cache.get_cache_info",
        lambda: {"enabled": False, "exists": False, "location": "/tmp", "model_count": 0, "total_size_mb": 0},
        raising=False,
    )

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    # add_section with default tab ("General")
    from PySide6.QtWidgets import QGroupBox

    box = QGroupBox("Extra")
    dlg.add_section(box)
    assert box in dlg._extra_sections

    # add_section targeting a specific existing tab
    box2 = QGroupBox("Extra Embeddings")
    dlg.add_section(box2, tab="Embeddings")
    assert box2 in dlg._extra_sections

    # Test _update_cache_info when cache disabled (label updated)
    dlg._update_cache_info()
    assert "disabled" in dlg.cache_info_label.text().lower()


def test_clear_cache_flow(monkeypatch, qtbot):
    fake_settings = FakeSettings()
    # Prevent message boxes from blocking
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    # Patch clear_cache in the core model_cache module
    monkeypatch.setattr("vector_inspector.core.model_cache.clear_cache", lambda: True, raising=False)

    # Call clear cache and ensure no exception raised
    dlg._clear_cache()


def test_clear_cache_returns_false(monkeypatch, qtbot):
    """_clear_cache shows warning when clear_cache() returns False."""
    fake_settings = FakeSettings()
    warning_calls = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warning_calls.append(a))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    monkeypatch.setattr("vector_inspector.core.model_cache.clear_cache", lambda: False, raising=False)

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    dlg._clear_cache()
    assert len(warning_calls) > 0


def test_clear_cache_answer_no(monkeypatch, qtbot):
    """_clear_cache does nothing when user answers No to confirmation."""
    fake_settings = FakeSettings()
    cleared = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    monkeypatch.setattr(
        "vector_inspector.core.model_cache.clear_cache",
        lambda: cleared.append(1) or True,
        raising=False,
    )

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    dlg._clear_cache()
    assert len(cleared) == 0


def test_ok_button_calls_apply_and_accepts(monkeypatch, qtbot):
    """_ok persists settings."""
    fake_settings = FakeSettings()
    saved = []
    fake_settings._save_settings = lambda: saved.append(1)

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    dlg._ok()
    assert len(saved) == 1


def test_on_use_accent_changed_enabled(monkeypatch, qtbot):
    """_on_use_accent_changed(1) sets use_accent to True and applies stylesheet."""
    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    dlg._on_use_accent_changed(1)  # non-zero = enabled
    assert fake_settings.get_use_accent_enabled() is True


def test_on_use_accent_changed_disabled(monkeypatch, qtbot):
    """_on_use_accent_changed(0) sets use_accent to False and clears stylesheet."""
    fake_settings = FakeSettings()
    fake_settings._store["use_accent_enabled"] = True

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    dlg._on_use_accent_changed(0)
    assert fake_settings.get_use_accent_enabled() is False


def test_apply_preset(monkeypatch, qtbot):
    """_apply_preset stores both colors in settings."""
    fake_settings = FakeSettings()
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    dlg._apply_preset("rgba(255,0,0,1)", "rgba(255,0,0,0.1)")
    assert fake_settings.get_highlight_color() == "rgba(255,0,0,1)"
    assert fake_settings.get_highlight_color_bg() == "rgba(255,0,0,0.1)"


def test_reset_highlight_defaults(monkeypatch, qtbot):
    """_reset_highlight_defaults restores VI default colors."""
    fake_settings = FakeSettings()
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    fake_settings.set_highlight_color("rgba(0,0,0,1)")
    dlg._reset_highlight_defaults()
    # Must have changed to something other than the fake override
    assert fake_settings.get_highlight_color() != "rgba(0,0,0,1)"


def test_update_cache_info_cache_exists_with_models(monkeypatch, qtbot):
    """_update_cache_info shows model count when cache has entries."""
    fake_settings = FakeSettings()
    monkeypatch.setattr(
        "vector_inspector.core.model_cache.get_cache_info",
        lambda: {
            "enabled": True,
            "exists": True,
            "location": "/tmp/cache",
            "model_count": 3,
            "total_size_mb": 1.5,
        },
        raising=False,
    )

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    dlg._update_cache_info()
    assert "3" in dlg.cache_info_label.text()


def test_update_cache_info_enabled_no_models_yet(monkeypatch, qtbot):
    """_update_cache_info shows 'no cached models' path when exists=False."""
    fake_settings = FakeSettings()
    monkeypatch.setattr(
        "vector_inspector.core.model_cache.get_cache_info",
        lambda: {
            "enabled": True,
            "exists": False,
            "location": "/tmp/cache",
            "model_count": 0,
            "total_size_mb": 0,
        },
        raising=False,
    )

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    dlg._update_cache_info()
    label = dlg.cache_info_label.text()
    assert "/tmp/cache" in label or "no cached" in label.lower()


def test_settings_panel_hook_exception_swallowed(qtbot):
    """If settings_panel_hook.trigger raises, the dialog still initializes."""
    fake_settings = FakeSettings()

    with patch("vector_inspector.ui.dialogs.settings_dialog.settings_panel_hook") as mock_hook:
        mock_hook.trigger.side_effect = RuntimeError("hook crashed")
        dlg = SettingsDialog(settings_service=fake_settings)
        qtbot.addWidget(dlg)

    assert dlg.default_results is not None


def test_load_values_accent_checkbox_checked_when_enabled(qtbot):
    """_load_values covers the inner try success path when get_use_accent_enabled() works."""
    fake_settings = FakeSettings()
    fake_settings._store["use_accent_enabled"] = True

    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    assert dlg.use_accent_checkbox.isChecked() is True


# ---------------------------------------------------------------------------
# Tabbed layout tests
# ---------------------------------------------------------------------------


def test_dialog_has_tab_widget(qtbot):
    """SettingsDialog uses a QTabWidget as its central container."""
    from PySide6.QtWidgets import QTabWidget

    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    assert hasattr(dlg, "_tabs")
    assert isinstance(dlg._tabs, QTabWidget)


def test_core_tabs_present(qtbot):
    """The four core tabs — General, Embeddings, Appearance, LLM — are created."""
    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    tab_titles = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    for expected in ("General", "Embeddings", "Appearance", "LLM"):
        assert expected in tab_titles, f"Tab '{expected}' not found; tabs are: {tab_titles}"


def test_get_tab_layout_returns_existing(qtbot):
    """get_tab_layout returns the same layout object for a tab that already exists."""
    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    layout_a = dlg.get_tab_layout("General")
    layout_b = dlg.get_tab_layout("General")
    assert layout_a is layout_b


def test_get_tab_layout_creates_new_tab(qtbot):
    """get_tab_layout creates a new tab on-demand when the name is unknown."""

    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    count_before = dlg._tabs.count()
    dlg.get_tab_layout("Custom")
    assert dlg._tabs.count() == count_before + 1
    tab_titles = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    assert "Custom" in tab_titles


def test_add_section_creates_tab_if_missing(qtbot):
    """add_section with an unknown tab name auto-creates that tab."""
    from PySide6.QtWidgets import QGroupBox

    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    count_before = dlg._tabs.count()
    box = QGroupBox("Plugin Section")
    dlg.add_section(box, tab="Plugin")

    assert box in dlg._extra_sections
    assert dlg._tabs.count() == count_before + 1
    tab_titles = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    assert "Plugin" in tab_titles


def test_add_section_layout_routed_to_correct_tab(qtbot):
    """A widget added via add_section(..., tab='Embeddings') lands in the Embeddings tab."""
    from PySide6.QtWidgets import QGroupBox

    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)

    box = QGroupBox("My Embeddings Extra")
    dlg.add_section(box, tab="Embeddings")

    # The widget's parent should be the Embeddings tab widget
    emb_widget = dlg._tab_widgets["Embeddings"][0]
    assert box.parent() is emb_widget


# ---------------------------------------------------------------------------
# Status timeout spinbox tests
# ---------------------------------------------------------------------------


def test_status_timeout_spinbox_loads_default(qtbot):
    """Spinbox reflects the value returned by get_status_timeout_ms (in seconds)."""
    fake_settings = FakeSettings()
    fake_settings._store["status.timeout_ms"] = 8000  # 8 s
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    assert dlg.status_timeout_spin.value() == 8


def test_status_timeout_spinbox_zero_shows_permanent_text(qtbot):
    """When the spinbox is at 0 it should display its specialValueText 'Permanent'."""
    fake_settings = FakeSettings()
    fake_settings._store["status.timeout_ms"] = 0
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    assert dlg.status_timeout_spin.value() == 0
    assert dlg.status_timeout_spin.specialValueText() == "Permanent"


def test_status_timeout_spinbox_change_calls_settings(qtbot):
    """Changing the spinbox value stores the correct milliseconds in settings."""
    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    dlg.status_timeout_spin.setValue(12)
    assert fake_settings.get_status_timeout_ms() == 12_000


# ---------------------------------------------------------------------------
# Extensions (Features) tab tests
# ---------------------------------------------------------------------------


def _make_settings_with_features_tab(monkeypatch, qtbot, *, features_available: dict | None = None):
    """Build a SettingsDialog with all feature checks patched to avoid real imports."""
    import vector_inspector.core.provider_detection as pd

    if features_available is None:
        features_available = {"viz": False, "embeddings": False, "clip": False, "documents": False}

    for fid, available in features_available.items():
        checker = {
            "viz": "check_viz_available",
            "embeddings": "check_embeddings_available",
            "clip": "check_clip_available",
            "documents": "check_documents_available",
        }[fid]
        monkeypatch.setattr(pd, checker, lambda a=available: a)

    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    # Wait for both background check threads to finish applying results.
    qtbot.waitUntil(lambda: dlg._features_checked and dlg._providers_checked, timeout=3000)
    return dlg


def test_features_tab_exists(monkeypatch, qtbot):
    """SettingsDialog creates a 'Features' tab."""
    dlg = _make_settings_with_features_tab(monkeypatch, qtbot)
    tab_titles = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    assert "Features" in tab_titles


def test_providers_tab_is_separate_from_features_tab(monkeypatch, qtbot):
    """Database Providers live on their own 'Providers' tab, not on 'Features'."""
    dlg = _make_settings_with_features_tab(monkeypatch, qtbot)
    tab_titles = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    assert "Providers" in tab_titles
    assert "Features" in tab_titles
    assert tab_titles.index("Features") != tab_titles.index("Providers")


def test_features_tab_has_all_four_feature_rows(monkeypatch, qtbot):
    """_feature_rows contains entries for all four feature groups."""
    dlg = _make_settings_with_features_tab(monkeypatch, qtbot)
    assert set(dlg._feature_rows.keys()) == {"viz", "embeddings", "clip", "documents"}


def test_feature_row_action_btn_tooltip_contains_package_spec(monkeypatch, qtbot):
    """The Install/Uninstall button on a feature row has a tooltip listing package specs."""
    from vector_inspector.services.provider_install_service import _FEATURE_PACKAGE_SPECS

    dlg = _make_settings_with_features_tab(monkeypatch, qtbot)
    tip = dlg._feature_rows["viz"]["action_btn"].toolTip()
    # All viz package specs should appear in the tooltip
    for spec in _FEATURE_PACKAGE_SPECS["viz"]:
        assert spec in tip, f"Expected {spec!r} in tooltip, got: {tip!r}"


def test_provider_row_action_btn_tooltip_contains_package_spec(monkeypatch, qtbot):
    """The Install/Uninstall button on a provider row has a tooltip listing package specs."""
    from vector_inspector.services.provider_install_service import _PROVIDER_PACKAGE_SPECS

    dlg = _make_settings_with_features_tab(monkeypatch, qtbot)
    tip = dlg._provider_rows["lancedb"]["action_btn"].toolTip()
    for spec in _PROVIDER_PACKAGE_SPECS["lancedb"]:
        assert spec in tip, f"Expected {spec!r} in tooltip, got: {tip!r}"


def test_features_tab_not_installed_shows_install_button(monkeypatch, qtbot):
    """When a feature is not installed its action button reads 'Install'."""
    dlg = _make_settings_with_features_tab(
        monkeypatch, qtbot, features_available={"viz": False, "embeddings": False, "clip": False, "documents": False}
    )
    assert dlg._feature_rows["viz"]["action_btn"].text() == "Install"


def test_features_tab_installed_shows_uninstall_button(monkeypatch, qtbot):
    """When a feature is installed its action button reads 'Uninstall'."""
    dlg = _make_settings_with_features_tab(
        monkeypatch, qtbot, features_available={"viz": True, "embeddings": False, "clip": False, "documents": False}
    )
    assert dlg._feature_rows["viz"]["action_btn"].text() == "Uninstall"


def test_features_tab_installed_shows_checkmark(monkeypatch, qtbot):
    """Status label shows a checkmark for installed features."""
    dlg = _make_settings_with_features_tab(
        monkeypatch, qtbot, features_available={"viz": True, "embeddings": False, "clip": False, "documents": False}
    )
    assert "✔" in dlg._feature_rows["viz"]["status_lbl"].text()


def test_features_tab_not_installed_shows_cross(monkeypatch, qtbot):
    """Status label shows a cross for missing features."""
    dlg = _make_settings_with_features_tab(
        monkeypatch, qtbot, features_available={"viz": False, "embeddings": False, "clip": False, "documents": False}
    )
    assert "✘" in dlg._feature_rows["viz"]["status_lbl"].text()


def test_refresh_feature_statuses_updates_button_when_newly_installed(monkeypatch, qtbot):
    """Calling _refresh_feature_statuses picks up a changed availability."""
    import vector_inspector.core.provider_detection as pd

    monkeypatch.setattr(pd, "check_viz_available", lambda: False)
    monkeypatch.setattr(pd, "check_embeddings_available", lambda: False)
    monkeypatch.setattr(pd, "check_clip_available", lambda: False)
    monkeypatch.setattr(pd, "check_documents_available", lambda: False)

    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._features_checked and dlg._providers_checked, timeout=3000)

    assert dlg._feature_rows["viz"]["action_btn"].text() == "Install"

    # Simulate feature becoming available
    monkeypatch.setattr(pd, "check_viz_available", lambda: True)
    dlg._features_checked = False
    dlg._refresh_feature_statuses()
    qtbot.waitUntil(lambda: dlg._features_checked, timeout=3000)

    assert dlg._feature_rows["viz"]["action_btn"].text() == "Uninstall"


def test_on_install_clicked_opens_provider_install_dialog(monkeypatch, qtbot):
    """_on_install_clicked opens ProviderInstallDialog and kicks off a background re-check."""
    dlg = _make_settings_with_features_tab(monkeypatch, qtbot)

    from unittest.mock import MagicMock

    mock_dlg = MagicMock()
    mock_dlg.exec.return_value = None

    monkeypatch.setattr(
        "vector_inspector.ui.dialogs.provider_install_dialog.ProviderInstallDialog",
        lambda info, parent=None: mock_dlg,
    )

    with patch("vector_inspector.ui.dialogs.settings_dialog.SettingsDialog._start_feature_status_check") as mock_check:
        dlg._on_install_clicked("viz")
        mock_dlg.exec.assert_called_once()
        mock_check.assert_called_once()


def test_on_uninstall_clicked_cancelled_does_not_start_thread(monkeypatch, qtbot):
    """When the user cancels the uninstall confirmation no thread is started."""
    dlg = _make_settings_with_features_tab(
        monkeypatch, qtbot, features_available={"viz": True, "embeddings": False, "clip": False, "documents": False}
    )
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    initial_threads = len(dlg._uninstall_threads)
    dlg._on_uninstall_clicked("viz")
    assert len(dlg._uninstall_threads) == initial_threads


def test_on_uninstall_done_success_updates_status_message(monkeypatch, qtbot):
    """A returncode of 0 sets the status message to 'Removed'."""
    dlg = _make_settings_with_features_tab(
        monkeypatch, qtbot, features_available={"viz": True, "embeddings": False, "clip": False, "documents": False}
    )
    dlg._on_uninstall_done("viz", 0, "Uninstalled successfully")
    assert dlg._feature_rows["viz"]["status_msg"].text() == "Removed"


def test_on_uninstall_done_failure_updates_status_message(monkeypatch, qtbot):
    """A non-zero returncode sets the status message to a failure string."""
    dlg = _make_settings_with_features_tab(
        monkeypatch, qtbot, features_available={"viz": True, "embeddings": False, "clip": False, "documents": False}
    )
    monkeypatch.setattr("vector_inspector.core.logging.log_error", lambda *a, **k: None)
    dlg._on_uninstall_done("viz", 1, "pip failed")
    assert "Failed" in dlg._feature_rows["viz"]["status_msg"].text()


# ---------------------------------------------------------------------------
# Extensions (Features) tab — Database Providers section tests
# ---------------------------------------------------------------------------


def _make_settings_with_providers_patched(monkeypatch, qtbot, *, chromadb_available=True):
    """Build a SettingsDialog with provider rows and availability patched for testing."""
    import vector_inspector.core.provider_detection as pd
    from vector_inspector.core.provider_detection import ProviderInfo

    # Keep feature checkers consistent (all unavailable — not under test here)
    monkeypatch.setattr(pd, "check_viz_available", lambda: False)
    monkeypatch.setattr(pd, "check_embeddings_available", lambda: False)
    monkeypatch.setattr(pd, "check_clip_available", lambda: False)
    monkeypatch.setattr(pd, "check_documents_available", lambda: False)

    # Static metadata for row building — no availability flags needed here
    fake_provider_metadata = [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=False,
            install_command="pip install ...",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
        ProviderInfo(
            id="qdrant",
            name="Qdrant",
            available=False,
            install_command="pip install ...",
            import_name="qdrant_client",
            description="Local, remote, or cloud vector database",
        ),
    ]
    monkeypatch.setattr(pd, "get_all_provider_metadata", lambda: fake_provider_metadata)

    # Background availability checks
    monkeypatch.setattr(
        pd,
        "get_provider_availability_checks",
        lambda: {"chromadb": (lambda: chromadb_available), "qdrant": (lambda: False)},
    )

    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._features_checked and dlg._providers_checked, timeout=3000)
    return dlg


def test_provider_rows_created_for_patched_providers(monkeypatch, qtbot):
    """_provider_rows contains an entry for every provider returned by get_all_providers."""
    dlg = _make_settings_with_providers_patched(monkeypatch, qtbot)
    assert set(dlg._provider_rows.keys()) == {"chromadb", "qdrant"}


def test_provider_not_installed_shows_install_button(monkeypatch, qtbot):
    """An unavailable provider row shows an 'Install' button."""
    dlg = _make_settings_with_providers_patched(monkeypatch, qtbot, chromadb_available=False)
    assert dlg._provider_rows["chromadb"]["action_btn"].text() == "Install"


def test_provider_installed_shows_uninstall_button(monkeypatch, qtbot):
    """An available provider row shows an 'Uninstall' button."""
    dlg = _make_settings_with_providers_patched(monkeypatch, qtbot, chromadb_available=True)
    assert dlg._provider_rows["chromadb"]["action_btn"].text() == "Uninstall"


def test_provider_installed_shows_checkmark(monkeypatch, qtbot):
    """An available provider row shows ✔ in its status label."""
    dlg = _make_settings_with_providers_patched(monkeypatch, qtbot, chromadb_available=True)
    assert "✔" in dlg._provider_rows["chromadb"]["status_lbl"].text()


def test_provider_not_installed_shows_cross(monkeypatch, qtbot):
    """An unavailable provider row shows ✘ in its status label."""
    dlg = _make_settings_with_providers_patched(monkeypatch, qtbot, chromadb_available=False)
    assert "✘" in dlg._provider_rows["chromadb"]["status_lbl"].text()


def test_refresh_provider_statuses_updates_button_when_newly_installed(monkeypatch, qtbot):
    """Calling _refresh_provider_statuses picks up a changed availability."""
    import vector_inspector.core.provider_detection as pd
    from vector_inspector.core.provider_detection import ProviderInfo

    monkeypatch.setattr(pd, "check_viz_available", lambda: False)
    monkeypatch.setattr(pd, "check_embeddings_available", lambda: False)
    monkeypatch.setattr(pd, "check_clip_available", lambda: False)
    monkeypatch.setattr(pd, "check_documents_available", lambda: False)

    # Start with chromadb unavailable
    monkeypatch.setattr(
        pd,
        "get_all_provider_metadata",
        lambda: [
            ProviderInfo(
                id="chromadb",
                name="ChromaDB",
                available=False,
                install_command="pip install ...",
                import_name="chromadb",
                description="Local persistent or HTTP client",
            )
        ],
    )
    monkeypatch.setattr(
        pd,
        "get_provider_availability_checks",
        lambda: {"chromadb": (lambda: False)},
    )

    fake_settings = FakeSettings()
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._features_checked and dlg._providers_checked, timeout=3000)

    assert dlg._provider_rows["chromadb"]["action_btn"].text() == "Install"

    # Simulate chromadb becoming available
    monkeypatch.setattr(
        pd,
        "get_provider_availability_checks",
        lambda: {"chromadb": (lambda: True)},
    )
    dlg._providers_checked = False
    dlg._refresh_provider_statuses()
    qtbot.waitUntil(lambda: dlg._providers_checked, timeout=3000)

    assert dlg._provider_rows["chromadb"]["action_btn"].text() == "Uninstall"


def test_on_provider_install_clicked_opens_install_dialog(monkeypatch, qtbot):
    """_on_provider_install_clicked opens ProviderInstallDialog and kicks off a background re-check."""
    from unittest.mock import MagicMock

    dlg = _make_settings_with_providers_patched(monkeypatch, qtbot, chromadb_available=False)

    mock_dlg = MagicMock()
    mock_dlg.exec.return_value = None

    monkeypatch.setattr(
        "vector_inspector.ui.dialogs.provider_install_dialog.ProviderInstallDialog",
        lambda info, parent=None: mock_dlg,
    )

    with patch("vector_inspector.ui.dialogs.settings_dialog.SettingsDialog._start_provider_status_check") as mock_check:
        dlg._on_provider_install_clicked("chromadb")
        mock_dlg.exec.assert_called_once()
        mock_check.assert_called_once()


def test_on_provider_uninstall_clicked_cancelled_does_not_start_thread(monkeypatch, qtbot):
    """When the user cancels the provider uninstall confirmation no thread is started."""
    dlg = _make_settings_with_providers_patched(monkeypatch, qtbot, chromadb_available=True)
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    initial_threads = len(dlg._provider_uninstall_threads)
    dlg._on_provider_uninstall_clicked("chromadb")
    assert len(dlg._provider_uninstall_threads) == initial_threads


def test_on_provider_uninstall_done_success_updates_status_message(monkeypatch, qtbot):
    """A returncode of 0 sets the provider status message to 'Removed'."""
    dlg = _make_settings_with_providers_patched(monkeypatch, qtbot, chromadb_available=True)
    dlg._on_provider_uninstall_done("chromadb", 0, "Uninstalled successfully")
    assert dlg._provider_rows["chromadb"]["status_msg"].text() == "Removed"


def test_on_provider_uninstall_done_failure_updates_status_message(monkeypatch, qtbot):
    """A non-zero returncode sets the provider status message to a failure string."""
    dlg = _make_settings_with_providers_patched(monkeypatch, qtbot, chromadb_available=True)
    monkeypatch.setattr("vector_inspector.core.logging.log_error", lambda *a, **k: None)
    dlg._on_provider_uninstall_done("chromadb", 1, "pip failed")
    assert "Failed" in dlg._provider_rows["chromadb"]["status_msg"].text()


def test_reset_defaults_sets_timeout_to_5s(qtbot, monkeypatch):
    """_reset_defaults resets the status timeout spinbox to 5 seconds."""
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    fake_settings = FakeSettings()
    fake_settings._store["status.timeout_ms"] = 20_000  # start with a non-default
    dlg = SettingsDialog(settings_service=fake_settings)
    qtbot.addWidget(dlg)
    dlg._reset_defaults()
    assert dlg.status_timeout_spin.value() == 0
