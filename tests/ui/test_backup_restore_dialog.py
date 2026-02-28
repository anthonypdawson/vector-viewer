import os

from PySide6.QtCore import Qt


class FakeBackupService:
    def __init__(self, backups=None):
        self._backups = backups or []

    def list_backups(self, backup_dir):
        return list(self._backups)

    def delete_backup(self, path):
        # pretend deletion succeeds when path matches one of stored backups
        original_len = len(self._backups)
        self._backups = [b for b in self._backups if b["file_path"] != path]
        return len(self._backups) < original_len


class FakeSettingsService:
    def __init__(self, initial=None):
        self._store = dict(initial or {})
        self.set_calls = []

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self.set_calls.append((key, value))
        self._store[key] = value


class FakeConnection:
    def __init__(self, name="db1", collections=None):
        self.name = name
        self.database = self  # simplified
        self.collections = collections or []

    def list_collections(self):
        return list(self.collections)


def make_dialog(monkeypatch, qtbot, backups=None, settings_initial=None, collection_name=""):
    # Patch BackupRestoreService and SettingsService in module
    import vector_inspector.ui.components.backup_restore_dialog as brd

    fake_backup_service = FakeBackupService(backups=backups)
    fake_settings = FakeSettingsService(initial=settings_initial)

    monkeypatch.setattr(brd, "BackupRestoreService", lambda: fake_backup_service)
    monkeypatch.setattr(brd, "SettingsService", lambda: fake_settings)

    # Patch LoadingDialog to a no-op class to avoid UI blocking
    class NoopLoading:
        def __init__(self, *args, **kwargs):
            pass

        def show_loading(self, *a, **k):
            pass

        def hide_loading(self):
            pass

    monkeypatch.setattr(brd, "LoadingDialog", NoopLoading)

    # Patch QMessageBox to safe no-op defaults to avoid modal popups
    monkeypatch.setattr(brd.QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(brd.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(brd.QMessageBox, "question", lambda *a, **k: brd.QMessageBox.StandardButton.No)

    conn = FakeConnection()
    dlg = brd.BackupRestoreDialog(conn, collection_name=collection_name)
    qtbot.addWidget(dlg)
    return dlg, fake_backup_service, fake_settings


def test_refresh_backups_list_no_backups(monkeypatch, qtbot):
    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[], settings_initial={})
    # After init, backups_list should show the no-backups item
    assert dlg.backups_list.count() == 1
    item = dlg.backups_list.item(0)
    assert "No backups found" in item.text()


def test_refresh_backups_list_with_backups(monkeypatch, qtbot):
    sample = {
        "collection_name": "colA",
        "timestamp": "2026-01-01T00:00:00",
        "item_count": 10,
        "file_name": "colA.zip",
        "file_path": os.path.join(os.getcwd(), "colA.zip"),
        "file_size": 1024 * 1024 * 2,
    }
    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[sample], settings_initial={})
    assert dlg.backups_list.count() == 1
    item = dlg.backups_list.item(0)
    assert "colA" in item.text()
    assert item.data(Qt.ItemDataRole.UserRole) == sample["file_path"]


def test_select_backup_dir_updates_settings_and_refresh(monkeypatch, qtbot):
    # Patch QFileDialog to return a chosen directory
    import vector_inspector.ui.components.backup_restore_dialog as brd

    monkeypatch.setattr(brd.QFileDialog, "getExistingDirectory", lambda *a, **k: os.getcwd())

    dlg, _, settings = make_dialog(monkeypatch, qtbot, backups=[], settings_initial={})
    # Call select backup dir
    dlg._select_backup_dir()
    # backup_dir should be updated to cwd and settings.set called
    assert dlg.backup_dir == os.getcwd()
    assert ("backup_directory", os.getcwd()) in settings.set_calls


def test_create_backup_no_collection_shows_warning(monkeypatch, qtbot):
    # When no collection is selected, creating backup should warn and not start thread
    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[], settings_initial={}, collection_name="")

    called = {}

    def fake_warning(parent, title, msg):
        called["warn"] = (title, msg)

    import vector_inspector.ui.components.backup_restore_dialog as brd

    monkeypatch.setattr(brd.QMessageBox, "warning", lambda *a, **k: fake_warning(*a, **k))

    dlg._create_backup()
    assert "warn" in called
    assert "No collection selected" in called["warn"][1]


def test_on_backup_selected_enables_buttons(monkeypatch, qtbot):
    sample = {
        "collection_name": "colA",
        "timestamp": "2026-01-01T00:00:00",
        "item_count": 1,
        "file_name": "colA.zip",
        "file_path": os.path.join(os.getcwd(), "colA.zip"),
        "file_size": 1024,
    }
    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[sample], settings_initial={})
    # Select the item programmatically
    dlg.backups_list.setCurrentRow(0)
    dlg._on_backup_selected()
    assert dlg.restore_button.isEnabled() is True
    assert dlg.delete_backup_button.isEnabled() is True


# ---------------------------------------------------------------------------
# _on_backup_finished / _on_backup_error
# ---------------------------------------------------------------------------


def test_on_backup_finished_hides_loading_and_shows_info(monkeypatch, qtbot):
    import vector_inspector.ui.components.backup_restore_dialog as brd

    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[], settings_initial={}, collection_name="colA")

    shown = {}
    monkeypatch.setattr(brd.QMessageBox, "information", lambda p, t, m: shown.update({"title": t, "msg": m}))
    monkeypatch.setattr(brd.QMessageBox, "warning", lambda *a, **k: None)

    dlg._on_backup_finished("/tmp/colA.zip")

    assert "title" in shown
    assert "Backup Successful" in shown["title"]
    assert "colA.zip" in shown["msg"]


def test_on_backup_error_hides_loading_and_shows_warning(monkeypatch, qtbot):
    import vector_inspector.ui.components.backup_restore_dialog as brd

    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[], settings_initial={})

    warned = {}
    monkeypatch.setattr(brd.QMessageBox, "warning", lambda p, t, m: warned.update({"title": t, "msg": m}))
    monkeypatch.setattr(brd.QMessageBox, "information", lambda *a, **k: None)

    dlg._on_backup_error("disk full")

    assert "Backup Failed" in warned["title"]
    assert "disk full" in warned["msg"]


# ---------------------------------------------------------------------------
# _on_restore_finished / _on_restore_error
# ---------------------------------------------------------------------------


def test_on_restore_finished_shows_success_message(monkeypatch, qtbot):
    import vector_inspector.ui.components.backup_restore_dialog as brd

    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[], settings_initial={})

    shown = {}
    monkeypatch.setattr(brd.QMessageBox, "information", lambda p, t, m: shown.update({"title": t, "msg": m}))
    monkeypatch.setattr(brd.QMessageBox, "warning", lambda *a, **k: None)

    dlg._on_restore_finished("new_col")

    assert "Restore Successful" in shown["title"]
    assert "new_col" in shown["msg"]


def test_on_restore_error_shows_warning(monkeypatch, qtbot):
    import vector_inspector.ui.components.backup_restore_dialog as brd

    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[], settings_initial={})

    warned = {}
    monkeypatch.setattr(brd.QMessageBox, "warning", lambda p, t, m: warned.update({"title": t, "msg": m}))
    monkeypatch.setattr(brd.QMessageBox, "information", lambda *a, **k: None)

    dlg._on_restore_error("timeout")

    assert "Restore Failed" in warned["title"]
    assert "timeout" in warned["msg"]


# ---------------------------------------------------------------------------
# _delete_backup
# ---------------------------------------------------------------------------


def _make_sample_backup(backup_dir=None):
    import os

    return {
        "collection_name": "colA",
        "timestamp": "2026-01-01T00:00:00",
        "item_count": 5,
        "file_name": "colA.zip",
        "file_path": os.path.join(os.getcwd(), "colA.zip"),
        "file_size": 1024,
    }


def test_delete_backup_no_selection_does_nothing(monkeypatch, qtbot):
    """_delete_backup is a no-op when nothing is selected."""
    import vector_inspector.ui.components.backup_restore_dialog as brd

    called = {}
    monkeypatch.setattr(
        brd.QMessageBox, "question", lambda *a, **k: called.update({"q": True}) or brd.QMessageBox.StandardButton.No
    )

    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[], settings_initial={})
    dlg.backups_list.clearSelection()
    dlg._delete_backup()

    # question dialog should NOT have been shown
    assert "q" not in called


def test_delete_backup_confirm_yes_calls_service(monkeypatch, qtbot):
    import vector_inspector.ui.components.backup_restore_dialog as brd

    sample = _make_sample_backup()
    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[sample], settings_initial={})

    monkeypatch.setattr(
        brd.QMessageBox,
        "question",
        lambda *a, **k: brd.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(brd.QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(brd.QMessageBox, "warning", lambda *a, **k: None)

    dlg.backups_list.setCurrentRow(0)
    dlg._delete_backup()

    # FakeBackupService.delete_backup returns True only when path matches
    # After deletion the list should be refreshed (now showing "No backups found")
    assert dlg.backups_list.count() == 1
    assert "No backups found" in dlg.backups_list.item(0).text()


def test_delete_backup_confirm_no_does_not_delete(monkeypatch, qtbot):
    import vector_inspector.ui.components.backup_restore_dialog as brd

    sample = _make_sample_backup()
    monkeypatch.setattr(
        brd.QMessageBox,
        "question",
        lambda *a, **k: brd.QMessageBox.StandardButton.No,
    )

    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[sample], settings_initial={})
    dlg.backups_list.setCurrentRow(0)
    original_count = dlg.backups_list.count()
    dlg._delete_backup()

    # List should remain unchanged
    assert dlg.backups_list.count() == original_count


def test_create_backup_with_collection_starts_thread(monkeypatch, qtbot):
    """When a collection is set, _create_backup should start a BackupThread."""
    import vector_inspector.ui.components.backup_restore_dialog as brd

    started = {}

    class FakeThread:
        def __init__(self, *args, **kwargs):
            pass

        def isRunning(self):
            return False

        def start(self):
            started["called"] = True

        def finished(self):
            pass

        def error(self):
            pass

        finished = type("S", (), {"connect": lambda self, fn: None})()
        error = type("S", (), {"connect": lambda self, fn: None})()

    monkeypatch.setattr(brd, "BackupThread", FakeThread)

    dlg, *_ = make_dialog(monkeypatch, qtbot, backups=[], settings_initial={}, collection_name="my_col")
    dlg._create_backup()

    assert started.get("called") is True
