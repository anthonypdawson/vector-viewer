from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from vector_inspector.ui.dialogs.settings_dialog import SettingsDialog


class FakeSettingsForAppearance:
    def __init__(self):
        self._store = {}
        self._store["default_n_results"] = 10
        self._store["auto_generate_embeddings"] = True
        self._store["window_restore_geometry"] = True
        self._store["hide_loading_screen"] = False
        self._store["embedding_cache_enabled"] = False
        # default highlight colors
        self._store["ui.highlight_color"] = "rgba(1,2,3,1)"
        self._store["ui.highlight_color_bg"] = "rgba(4,5,6,0.5)"
        self._use_accent = False
        self.saved = False

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

    def get_highlight_color(self):
        return self._store.get("ui.highlight_color")

    def get_highlight_color_bg(self):
        return self._store.get("ui.highlight_color_bg")

    def set_highlight_color(self, color):
        self._store["ui.highlight_color"] = color

    def set_highlight_color_bg(self, color):
        self._store["ui.highlight_color_bg"] = color

    def get_use_accent_enabled(self) -> bool:
        return bool(self._use_accent)

    def set_use_accent_enabled(self, enabled: bool):
        self._use_accent = bool(enabled)

    def _save_settings(self):
        self.saved = True

    # Setter methods used by SettingsDialog signal handlers
    def set_default_n_results(self, v):
        self._store["default_n_results"] = v

    def set_auto_generate_embeddings(self, v):
        self._store["auto_generate_embeddings"] = bool(v)

    def set_window_restore_geometry(self, v):
        self._store["window_restore_geometry"] = bool(v)

    def set(self, key, val):
        self._store[key] = val

    def set_embedding_cache_enabled(self, v):
        self._store["embedding_cache_enabled"] = bool(v)


def _monkeypatch_qcolordialog_accept(monkeypatch, color=None):
    """Monkeypatch QColorDialog so exec() returns Accepted and currentColor() returns `color`."""
    if color is None:
        color = QColor(7, 8, 9, 255)

    class _FakeDlg:
        def __init__(self, *a, **k):
            self._color = color

        def setOption(self, *a, **k):
            pass

        def setCurrentColor(self, c):
            self._color = c

        def exec(self):
            return QDialog.DialogCode.Accepted

        def currentColor(self):
            return self._color

    # Patch the QColorDialog symbol used by the settings dialog module
    monkeypatch.setattr("vector_inspector.ui.dialogs.settings_dialog.QColorDialog", _FakeDlg)


def test_color_picker_updates_settings(qtbot, monkeypatch):
    fake = FakeSettingsForAppearance()
    # prevent message boxes
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    _monkeypatch_qcolordialog_accept(monkeypatch, QColor(10, 20, 30, 255))

    dlg = SettingsDialog(settings_service=fake)
    qtbot.addWidget(dlg)

    # Use apply_preset which sets the colors synchronously and updates settings
    dlg._apply_preset("rgba(10,20,30,1)", "rgba(0,0,0,0.12)")

    # Settings should be updated to the new rgba string (check prefix)
    assert "rgba(10,20,30" in fake.get_highlight_color()


def test_accent_checkbox_toggles_global_stylesheet(qtbot, monkeypatch):
    fake = FakeSettingsForAppearance()
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    app = QApplication.instance()
    assert app is not None
    # Ensure a clean slate regardless of test execution order
    app.setStyleSheet("")

    dlg = SettingsDialog(settings_service=fake)
    qtbot.addWidget(dlg)

    # Initially disabled
    assert not fake.get_use_accent_enabled()
    assert app.styleSheet() == ""

    # Enable via checkbox
    dlg.use_accent_checkbox.setChecked(True)
    # Settings flag should update and app stylesheet should be non-empty
    assert fake.get_use_accent_enabled() is True
    assert app.styleSheet() != ""

    # Disable via checkbox
    dlg.use_accent_checkbox.setChecked(False)
    assert fake.get_use_accent_enabled() is False
    assert app.styleSheet() == ""


def test_reset_button_restores_defaults_and_saves(qtbot, monkeypatch):
    fake = FakeSettingsForAppearance()
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    # Change values away from defaults
    fake._store["default_n_results"] = 42
    fake._store["auto_generate_embeddings"] = False

    dlg = SettingsDialog(settings_service=fake)
    qtbot.addWidget(dlg)

    # Call reset and assert UI changed to recommended defaults
    dlg._reset_defaults()
    assert dlg.default_results.value() == 10
    assert dlg.auto_embed_checkbox.isChecked() is True
    # Ensure underlying settings save was invoked
    assert fake.saved is True


def test_loads_saved_color_values_on_init(qtbot, monkeypatch):
    fake = FakeSettingsForAppearance()
    # set specific color values
    fake._store["ui.highlight_color"] = "rgba(123,45,67,0.80)"
    fake._store["ui.highlight_color_bg"] = "rgba(222,222,222,0.12)"
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    dlg = SettingsDialog(settings_service=fake)
    qtbot.addWidget(dlg)

    # Button style sheets should include the provided color strings
    assert "rgba(123,45,67" in dlg.highlight_btn.styleSheet()
    assert "rgba(222,222,222" in dlg.highlight_bg_btn.styleSheet()
