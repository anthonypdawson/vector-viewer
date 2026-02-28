"""Tests for CrossDatabaseMigrationDialog and MigrationThread."""

from unittest.mock import MagicMock

from PySide6.QtWidgets import QMessageBox

import vector_inspector.ui.dialogs.cross_db_migration as migration_module
from vector_inspector.ui.dialogs.cross_db_migration import (
    CrossDatabaseMigrationDialog,
    MigrationThread,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeConnectionInstance:
    def __init__(self, conn_id, name, collections=None):
        self.id = conn_id
        self.name = name
        self.collections = collections or ["col_a", "col_b"]
        self.is_connected = True

    def get_display_name(self):
        return self.name

    def list_collections(self):
        return self.collections


class FakeConnectionManager:
    def __init__(self, conns=None):
        self._conns = {c.id: c for c in (conns or [])}

    def get_all_connections(self):
        return list(self._conns.values())

    def get_connection(self, conn_id):
        return self._conns.get(conn_id)


class FakeBackupService:
    def backup_collection(self, conn, collection, temp_dir, include_embeddings, connection_id):
        return "/tmp/backup.json"

    def restore_collection(self, conn, backup_path, collection_name, overwrite, connection_id):
        return True


class FailingBackupService:
    def backup_collection(self, conn, collection, temp_dir, include_embeddings, connection_id):
        return None  # simulate failure

    def restore_collection(self, conn, backup_path, collection_name, overwrite, connection_id):
        return False


# ---------------------------------------------------------------------------
# CrossDatabaseMigrationDialog tests
# ---------------------------------------------------------------------------


def test_dialog_instantiates_with_connections(qtbot):
    mgr = FakeConnectionManager(
        [
            FakeConnectionInstance("c1", "DB1"),
            FakeConnectionInstance("c2", "DB2"),
        ]
    )
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)
    assert dlg is not None
    assert dlg.source_connection_combo.count() == 2
    assert dlg.target_connection_combo.count() == 2


def test_dialog_instantiates_with_no_connections(qtbot):
    mgr = FakeConnectionManager([])
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)
    assert dlg.source_connection_combo.count() == 0


def test_dialog_populates_collections_on_source_change(qtbot):
    conn1 = FakeConnectionInstance("c1", "DB1", collections=["alpha", "beta"])
    conn2 = FakeConnectionInstance("c2", "DB2", collections=["gamma"])
    mgr = FakeConnectionManager([conn1, conn2])
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)
    # Select second connection
    dlg.source_connection_combo.setCurrentIndex(1)
    assert dlg.source_collection_combo.count() == 1
    assert dlg.source_collection_combo.itemText(0) == "gamma"


def test_dialog_populates_collections_on_target_change(qtbot):
    conn1 = FakeConnectionInstance("c1", "DB1", collections=["alpha"])
    conn2 = FakeConnectionInstance("c2", "DB2", collections=["x", "y", "z"])
    mgr = FakeConnectionManager([conn1, conn2])
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)
    dlg.target_connection_combo.setCurrentIndex(1)
    assert dlg.target_collection_combo.count() == 3


def test_start_migration_no_connections_shows_warning(qtbot, monkeypatch):
    mgr = FakeConnectionManager([])
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)

    warnings = []
    monkeypatch.setattr(migration_module.QMessageBox, "warning", staticmethod(lambda *a, **kw: warnings.append(True)))

    dlg._start_migration()
    assert warnings


def test_start_migration_same_conn_same_coll_warns(qtbot, monkeypatch):
    conn = FakeConnectionInstance("c1", "DB1", collections=["my_col"])
    mgr = FakeConnectionManager([conn])
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)

    # Both combos point to same connection and same collection
    assert dlg.source_connection_combo.count() == 1
    assert dlg.target_connection_combo.count() == 1

    warnings = []
    monkeypatch.setattr(migration_module.QMessageBox, "warning", staticmethod(lambda *a, **kw: warnings.append(True)))

    dlg._start_migration()
    assert warnings


def test_cancel_migration_no_thread(qtbot):
    """Cancel when no thread running should do nothing."""
    mgr = FakeConnectionManager([])
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)
    dlg._cancel_migration()  # Should not raise


def test_on_migration_progress_updates_bar(qtbot):
    mgr = FakeConnectionManager([])
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)
    dlg._on_migration_progress(42, "Working…")
    assert dlg.progress_bar.value() == 42


def test_on_migration_finished_success(qtbot, monkeypatch):
    mgr = FakeConnectionManager([])
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)

    shown = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: shown.append("info"))

    dlg._on_migration_finished(True, "Done!")
    assert "info" in shown
    assert dlg.start_button.isEnabled()


def test_on_migration_finished_failure(qtbot, monkeypatch):
    mgr = FakeConnectionManager([])
    dlg = CrossDatabaseMigrationDialog(connection_manager=mgr)
    qtbot.addWidget(dlg)

    shown = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: shown.append("warn"))

    dlg._on_migration_finished(False, "Failed!")
    assert "warn" in shown


# ---------------------------------------------------------------------------
# MigrationThread direct run() tests
# ---------------------------------------------------------------------------


def test_migration_thread_run_direct_not_connected(monkeypatch):
    """Emits finished(False) when source not connected."""
    source = MagicMock()
    source.is_connected = False
    target = MagicMock()
    target.is_connected = True

    thread = MigrationThread(
        source_conn=source,
        target_conn=target,
        source_collection="src_col",
        target_collection="tgt_col",
        include_embeddings=True,
    )
    results = []
    thread.finished.connect(lambda s, m: results.append((s, m)))
    thread.run()

    assert results and results[0][0] is False
    assert "not active" in results[0][1].lower()


def test_migration_thread_run_direct_target_not_connected(monkeypatch):
    source = MagicMock()
    source.is_connected = True
    target = MagicMock()
    target.is_connected = False

    thread = MigrationThread(
        source_conn=source,
        target_conn=target,
        source_collection="src_col",
        target_collection="tgt_col",
        include_embeddings=True,
    )
    results = []
    thread.finished.connect(lambda s, m: results.append((s, m)))
    thread.run()

    assert results and results[0][0] is False


def test_migration_thread_run_direct_success(monkeypatch):
    source = MagicMock()
    source.is_connected = True
    source.connection = MagicMock()
    target = MagicMock()
    target.is_connected = True
    target.connection = MagicMock()
    target.collections = []

    fake_svc = FakeBackupService()
    monkeypatch.setattr(migration_module, "BackupRestoreService", lambda: fake_svc)

    thread = MigrationThread(
        source_conn=source,
        target_conn=target,
        source_collection="src_col",
        target_collection="tgt_col",
        include_embeddings=True,
    )
    results = []
    thread.finished.connect(lambda s, m: results.append((s, m)))
    thread.run()

    assert results and results[0][0] is True


def test_migration_thread_run_direct_backup_fails(monkeypatch):
    source = MagicMock()
    source.is_connected = True
    source.connection = MagicMock()
    target = MagicMock()
    target.is_connected = True
    target.connection = MagicMock()
    target.collections = []

    fake_svc = FailingBackupService()
    monkeypatch.setattr(migration_module, "BackupRestoreService", lambda: fake_svc)

    thread = MigrationThread(
        source_conn=source,
        target_conn=target,
        source_collection="src_col",
        target_collection="tgt_col",
        include_embeddings=False,
    )
    results = []
    thread.finished.connect(lambda s, m: results.append((s, m)))
    thread.run()

    assert results and results[0][0] is False


def test_migration_thread_cancel(monkeypatch):
    source = MagicMock()
    source.is_connected = True
    target = MagicMock()
    target.is_connected = True

    thread = MigrationThread(
        source_conn=source,
        target_conn=target,
        source_collection="src_col",
        target_collection="tgt_col",
        include_embeddings=True,
    )
    thread.cancel()
    results = []
    thread.finished.connect(lambda s, m: results.append((s, m)))
    thread.run()

    assert results and results[0][0] is False
    assert "cancel" in results[0][1].lower()
