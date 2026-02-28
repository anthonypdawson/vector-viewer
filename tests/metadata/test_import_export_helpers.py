"""Tests for import_export_helpers module."""

from PySide6.QtWidgets import QMessageBox, QWidget

from vector_inspector.ui.views.metadata.import_export_helpers import (
    on_import_error,
    on_import_finished,
    start_import,
)


class FakeCtx:
    def __init__(self, collection=None, db="db1"):
        self.current_collection = collection
        self.current_database = db
        self.connection = None
        self.cache_manager = FakeCache()


class FakeCache:
    def __init__(self):
        self.invalidated = []

    def invalidate(self, db, coll):
        self.invalidated.append((db, coll))


class FakeLoadingDialog:
    def __init__(self):
        self.shown = []
        self.hidden = 0

    def show_loading(self, msg):
        self.shown.append(msg)

    def hide_loading(self):
        self.hidden += 1


class FakeSettings:
    def __init__(self):
        self._store = {}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, val):
        self._store[key] = val


# ---------------------------------------------------------------------------
# start_import
# ---------------------------------------------------------------------------


def test_start_import_no_collection_shows_warning(qtbot, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a[1]))

    parent = QWidget()
    qtbot.addWidget(parent)
    ctx = FakeCtx(collection=None)

    start_import(
        parent=parent,
        ctx=ctx,
        format_type="json",
        settings_service=FakeSettings(),
        loading_dialog=FakeLoadingDialog(),
        import_thread_attr="_import_thread",
        finished_callback=lambda **kw: None,
        error_callback=lambda e: None,
        progress_callback=lambda p: None,
    )
    assert any("collection" in w.lower() for w in warnings)


def test_start_import_no_file_selected_does_nothing(qtbot, monkeypatch):
    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.import_export_helpers.QFileDialog.getOpenFileName",
        lambda *a, **k: ("", ""),
    )
    parent = QWidget()
    qtbot.addWidget(parent)
    ctx = FakeCtx(collection="col1")
    loading = FakeLoadingDialog()

    start_import(
        parent=parent,
        ctx=ctx,
        format_type="json",
        settings_service=FakeSettings(),
        loading_dialog=loading,
        import_thread_attr="_import_thread",
        finished_callback=lambda **kw: None,
        error_callback=lambda e: None,
        progress_callback=lambda p: None,
    )
    assert loading.shown == []  # loading was never shown


def test_start_import_starts_thread(qtbot, monkeypatch):
    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.import_export_helpers.QFileDialog.getOpenFileName",
        lambda *a, **k: ("/some/path/data.json", ""),
    )

    threads_started = []

    class FakeSignal:
        def connect(self, fn):
            pass

    class FakeImportThread:
        finished = FakeSignal()
        error = FakeSignal()
        progress = FakeSignal()

        def __init__(self, *a, **k):
            pass

        def isRunning(self):
            return False

        def start(self):
            threads_started.append(True)

    # DataImportThread is lazily imported inside start_import; patch via sys.modules
    import sys
    import types

    fake_mt_mod = types.ModuleType("vector_inspector.ui.views.metadata.metadata_threads")
    fake_mt_mod.DataImportThread = FakeImportThread
    monkeypatch.setitem(sys.modules, "vector_inspector.ui.views.metadata.metadata_threads", fake_mt_mod)

    parent = QWidget()
    qtbot.addWidget(parent)
    ctx = FakeCtx(collection="col1")
    loading = FakeLoadingDialog()

    start_import(
        parent=parent,
        ctx=ctx,
        format_type="json",
        settings_service=FakeSettings(),
        loading_dialog=loading,
        import_thread_attr="_import_thread",
        finished_callback=lambda **kw: None,
        error_callback=lambda e: None,
        progress_callback=lambda p: None,
    )
    assert "Importing" in loading.shown[0]
    assert threads_started == [True]


# ---------------------------------------------------------------------------
# on_import_finished
# ---------------------------------------------------------------------------


def test_on_import_finished_shows_info_and_reloads(qtbot, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda p, t, m: messages.append(m))

    reload_calls = []
    loading = FakeLoadingDialog()
    ctx = FakeCtx(collection="col1", db="db1")

    parent = QWidget()
    qtbot.addWidget(parent)

    on_import_finished(
        parent=parent,
        ctx=ctx,
        settings_service=FakeSettings(),
        loading_dialog=loading,
        reload_callback=lambda: reload_calls.append(True),
        imported_data={"ids": ["id1", "id2"]},
        item_count=2,
        file_path="/some/dir/data.json",
    )

    assert loading.hidden == 1
    assert reload_calls == [True]
    assert ("db1", "col1") in ctx.cache_manager.invalidated
    assert any("2" in m for m in messages)


# ---------------------------------------------------------------------------
# on_import_error
# ---------------------------------------------------------------------------


def test_on_import_error_hides_loading_and_shows_warning(qtbot, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warnings.append(a[2]))

    loading = FakeLoadingDialog()
    parent = QWidget()
    qtbot.addWidget(parent)

    on_import_error(loading_dialog=loading, parent=parent, error_message="parse failed")

    assert loading.hidden == 1
    assert any("parse failed" in w for w in warnings)
