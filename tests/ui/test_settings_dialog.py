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
