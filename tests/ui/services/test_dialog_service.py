"""Tests for DialogService."""

from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from vector_inspector.ui.services.dialog_service import DialogService

# ---------------------------------------------------------------------------
# show_about
# ---------------------------------------------------------------------------


def test_show_about_calls_about(qtbot, monkeypatch):
    called = []
    monkeypatch.setattr(QMessageBox, "about", lambda p, t, m: called.append((t, m)))
    parent = QWidget()
    qtbot.addWidget(parent)
    DialogService.show_about(parent)
    assert len(called) == 1
    title, text = called[0]
    assert "Vector Inspector" in title
    assert "Vector Inspector" in text


# ---------------------------------------------------------------------------
# show_backup_restore_dialog
# ---------------------------------------------------------------------------


def test_show_backup_restore_no_connection_returns_rejected(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    parent = QWidget()
    qtbot.addWidget(parent)
    result = DialogService.show_backup_restore_dialog(None, "col", parent)
    assert result == QDialog.Rejected


def test_show_backup_restore_no_collection_shows_info(qtbot, monkeypatch):
    """When collection_name is empty, shows an informational message."""
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda p, t, m: messages.append(m))

    class FakeDialogClass:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Accepted

    # Patch in the actual submodule where BackupRestoreDialog lives
    import sys
    import types

    fake_mod = types.ModuleType("vector_inspector.ui.components.backup_restore_dialog")
    fake_mod.BackupRestoreDialog = FakeDialogClass
    monkeypatch.setitem(sys.modules, "vector_inspector.ui.components.backup_restore_dialog", fake_mod)

    parent = QWidget()
    qtbot.addWidget(parent)

    class FakeConn:
        pass

    result = DialogService.show_backup_restore_dialog(FakeConn(), "", parent)
    # Information was shown about needing a collection
    assert any("collection" in m.lower() for m in messages)
    assert result == QDialog.Accepted


# ---------------------------------------------------------------------------
# show_migration_dialog
# ---------------------------------------------------------------------------


def test_show_migration_insufficient_connections_returns_rejected(qtbot, monkeypatch):
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    class FakeConnectionManager:
        def get_connection_count(self):
            return 1

    parent = QWidget()
    qtbot.addWidget(parent)
    result = DialogService.show_migration_dialog(FakeConnectionManager(), parent)
    assert result == QDialog.Rejected


# ---------------------------------------------------------------------------
# show_profile_editor_prompt
# ---------------------------------------------------------------------------


def test_show_profile_editor_prompt(qtbot, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda p, t, m: messages.append(m))
    parent = QWidget()
    qtbot.addWidget(parent)
    DialogService.show_profile_editor_prompt(parent)
    assert len(messages) == 1
    assert "profile" in messages[0].lower()


# ---------------------------------------------------------------------------
# show_update_details
# ---------------------------------------------------------------------------


def test_show_update_details(qtbot, monkeypatch):
    executions = []

    class FakeUpdateDialog:
        def __init__(self, version, notes, pip_cmd, github_url, parent=None):
            pass

        def exec(self):
            executions.append(True)

    class FakeUpdateService:
        @staticmethod
        def get_update_instructions():
            return {"pip": "pip install -U vector-inspector", "github": "https://github.com/..."}

    import sys
    import types

    fake_dialog_mod = types.ModuleType("vector_inspector.ui.components.update_details_dialog")
    fake_dialog_mod.UpdateDetailsDialog = FakeUpdateDialog
    monkeypatch.setitem(sys.modules, "vector_inspector.ui.components.update_details_dialog", fake_dialog_mod)

    fake_svc_mod = types.ModuleType("vector_inspector.services.update_service")
    fake_svc_mod.UpdateService = FakeUpdateService
    monkeypatch.setitem(sys.modules, "vector_inspector.services.update_service", fake_svc_mod)

    parent = QWidget()
    qtbot.addWidget(parent)
    DialogService.show_update_details({"tag_name": "v1.0.0", "body": "notes"}, parent)
    assert executions == [True]
