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

    # Add a layout or widget as extra section
    from PySide6.QtWidgets import QGroupBox

    box = QGroupBox("Extra")
    dlg.add_section(box)
    assert box in dlg._extra_sections

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
