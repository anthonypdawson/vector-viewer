"""Test that MainWindow defaults to the Profiles (index 1) left-panel tab on launch."""

from PySide6.QtWidgets import QWidget

import vector_inspector.ui.main_window as mw_mod


class _DummySignal:
    """Thin stand-in for a PySide6 Signal — accepts .connect() calls without wiring."""

    def connect(self, *a, **k):
        pass


class _DummyConnMgr:
    """Minimal ConnectionManager stub exposing the signals _connect_signals expects."""

    def __init__(self):
        pass

    active_connection_changed = _DummySignal()
    active_collection_changed = _DummySignal()
    collections_updated = _DummySignal()
    connection_opened = _DummySignal()

    def get_all_profiles(self):
        return []

    def close_all_connections(self):
        pass


class _DummyProfileService:
    """Minimal ProfileService stub."""

    def __init__(self):
        pass

    def get_all_profiles(self):
        return []


class _DummyConnPanel(QWidget):
    """Lightweight ConnectionManagerPanel replacement."""

    def __init__(self, conn_mgr, parent=None):
        super().__init__(parent)

    # Signals / UI controls accessed by MainWindow._connect_signals
    collection_selected = _DummySignal()
    add_connection_btn = type("_Btn", (), {"clicked": _DummySignal()})()


class _DummyProfilePanel(QWidget):
    """Lightweight ProfileManagerPanel replacement."""

    def __init__(self, svc, parent=None):
        super().__init__(parent)

    # Both signals are accessed in _connect_signals (connect_profile unconditionally)
    connect_profile = _DummySignal()
    profile_selected = _DummySignal()


class _DummyConnectionController:
    """Lightweight ConnectionController replacement."""

    def __init__(self, conn_mgr, profile_svc, parent=None):
        self.connection_completed = _DummySignal()

    def cleanup(self):
        """Called by MainWindow.closeEvent — must exist."""
        pass


def test_saved_profiles_is_default_selected_tab(qtbot, monkeypatch):
    """MainWindow should display the Profiles panel (index=1) as the default selected tab."""
    monkeypatch.setattr(mw_mod, "ConnectionManager", _DummyConnMgr)
    monkeypatch.setattr(mw_mod, "ProfileService", _DummyProfileService)
    monkeypatch.setattr(mw_mod, "ConnectionManagerPanel", _DummyConnPanel)
    monkeypatch.setattr(mw_mod, "ProfileManagerPanel", _DummyProfilePanel)
    monkeypatch.setattr(mw_mod, "ConnectionController", _DummyConnectionController)
    # Prevent the splash window from blocking/timing out in headless test runs
    monkeypatch.setattr(mw_mod.MainWindow, "_maybe_show_splash", lambda self: None)

    win = mw_mod.MainWindow()
    qtbot.addWidget(win)

    assert win.left_tabs.count() >= 2, "Expected at least two left-panel tabs"
    assert win.left_tabs.currentIndex() == 1, "Profiles tab (index 1) should be selected by default"
    assert win.left_tabs.tabText(1) == "Profiles", "Second tab should be labelled 'Profiles'"
