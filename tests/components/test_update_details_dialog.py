"""Tests for UpdateDetailsDialog component."""

from vector_inspector.ui.components.update_details_dialog import UpdateDetailsDialog


def test_update_details_dialog_instantiates(qtbot):
    dlg = UpdateDetailsDialog(
        version="1.2.3",
        release_notes="Bug fixes and improvements.",
        pip_command="pip install --upgrade vector-inspector",
        github_url="https://github.com/example/repo",
    )
    qtbot.addWidget(dlg)
    assert dlg is not None


def test_update_details_dialog_title(qtbot):
    dlg = UpdateDetailsDialog(
        version="2.0.0",
        release_notes="Major update.",
        pip_command="pip install vector-inspector==2.0.0",
        github_url="https://github.com/example/repo",
    )
    qtbot.addWidget(dlg)
    assert "2.0.0" in dlg.windowTitle()


def test_update_details_dialog_stores_fields(qtbot):
    dlg = UpdateDetailsDialog(
        version="0.5.1",
        release_notes="Fix crash on startup.",
        pip_command="pip install -U vector-inspector",
        github_url="https://github.com/example/repo/releases",
    )
    qtbot.addWidget(dlg)
    assert dlg.version == "0.5.1"
    assert dlg.release_notes == "Fix crash on startup."
    assert dlg.pip_command == "pip install -U vector-inspector"
    assert dlg.github_url == "https://github.com/example/repo/releases"


def test_update_details_dialog_accept(qtbot):
    dlg = UpdateDetailsDialog(
        version="1.0.0",
        release_notes="Initial release.",
        pip_command="pip install vector-inspector",
        github_url="https://github.com/example/repo",
    )
    qtbot.addWidget(dlg)
    dlg.accept()
    from PySide6.QtWidgets import QDialog

    assert dlg.result() == QDialog.DialogCode.Accepted
