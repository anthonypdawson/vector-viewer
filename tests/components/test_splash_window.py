"""Tests for SplashWindow component."""

from vector_inspector.ui.components.splash_window import SplashWindow


def test_splash_window_instantiates(qtbot):
    dlg = SplashWindow()
    qtbot.addWidget(dlg)
    assert dlg is not None


def test_splash_window_title(qtbot):
    dlg = SplashWindow()
    qtbot.addWidget(dlg)
    assert "Vector Inspector" in dlg.windowTitle()


def test_splash_window_should_hide_defaults_false(qtbot):
    dlg = SplashWindow()
    qtbot.addWidget(dlg)
    assert dlg.should_hide() is False


def test_splash_window_should_hide_when_checked(qtbot):
    dlg = SplashWindow()
    qtbot.addWidget(dlg)
    dlg.hide_checkbox.setChecked(True)
    assert dlg.should_hide() is True


def test_splash_window_has_hide_checkbox(qtbot):
    dlg = SplashWindow()
    qtbot.addWidget(dlg)
    assert hasattr(dlg, "hide_checkbox")


def test_splash_window_accept_closes(qtbot):
    dlg = SplashWindow()
    qtbot.addWidget(dlg)
    dlg.accept()
    from PySide6.QtWidgets import QDialog

    assert dlg.result() == QDialog.DialogCode.Accepted
