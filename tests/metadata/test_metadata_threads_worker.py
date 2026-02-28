"""Tests for metadata_threads background workers."""

from vector_inspector.ui.views.metadata.context import MetadataContext
from vector_inspector.ui.views.metadata.metadata_threads import (
    DataImportThread,
    DataLoadThread,
    ItemUpdateThread,
)


class FakeConnection:
    def __init__(self, data=None, update_success=True):
        self._data = data
        self._update_success = update_success

    def get_all_items(self, collection, limit=None, offset=None, where=None):
        return self._data

    def update_items(self, collection, ids, documents=None, metadatas=None, embeddings=None):
        return self._update_success


# ---------------------------------------------------------------------------
# DataLoadThread
# ---------------------------------------------------------------------------


def test_data_load_thread_emits_finished_on_success(qtbot):
    data = {"ids": ["a"], "documents": ["hello"]}
    conn = FakeConnection(data=data)
    ctx = MetadataContext(connection=conn, current_collection="col")

    thread = DataLoadThread(ctx, req_limit=50, req_offset=0)
    received = {}
    thread.finished.connect(lambda d: received.update(d))

    with qtbot.waitSignal(thread.finished, timeout=3000):
        thread.start()

    assert received.get("ids") == ["a"]


def test_data_load_thread_emits_error_when_no_connection(qtbot):
    ctx = MetadataContext(connection=None, current_collection="col")

    thread = DataLoadThread(ctx, req_limit=50, req_offset=0)
    errors = []
    thread.error.connect(lambda msg: errors.append(msg))

    with qtbot.waitSignal(thread.error, timeout=3000):
        thread.start()

    assert len(errors) == 1
    assert "connection" in errors[0].lower()


def test_data_load_thread_emits_error_when_data_none(qtbot):
    conn = FakeConnection(data=None)
    ctx = MetadataContext(connection=conn, current_collection="col")

    thread = DataLoadThread(ctx, req_limit=50, req_offset=0)
    errors = []
    thread.error.connect(lambda msg: errors.append(msg))

    with qtbot.waitSignal(thread.error, timeout=3000):
        thread.start()

    assert len(errors) == 1


def test_data_load_thread_emits_error_on_exception(qtbot):
    class ErrorConn:
        def get_all_items(self, *a, **k):
            raise RuntimeError("db failure")

    ctx = MetadataContext(connection=ErrorConn(), current_collection="col")
    thread = DataLoadThread(ctx, req_limit=None, req_offset=None)
    errors = []
    thread.error.connect(lambda msg: errors.append(msg))

    with qtbot.waitSignal(thread.error, timeout=3000):
        thread.start()

    assert any("db failure" in e for e in errors)


# ---------------------------------------------------------------------------
# ItemUpdateThread
# ---------------------------------------------------------------------------


def test_item_update_thread_emits_finished_on_success(qtbot):
    conn = FakeConnection(update_success=True)
    item = {"id": "id1", "document": "doc", "metadata": {"k": "v"}}

    thread = ItemUpdateThread(conn, "col", item)
    received = {}
    thread.finished.connect(lambda d: received.update(d))

    with qtbot.waitSignal(thread.finished, timeout=3000):
        thread.start()

    assert received.get("id") == "id1"


def test_item_update_thread_emits_error_on_failure(qtbot):
    conn = FakeConnection(update_success=False)
    item = {"id": "id2", "document": "doc", "metadata": {}}

    thread = ItemUpdateThread(conn, "col", item)
    errors = []
    thread.error.connect(lambda msg: errors.append(msg))

    with qtbot.waitSignal(thread.error, timeout=3000):
        thread.start()

    assert len(errors) == 1


def test_item_update_thread_emits_error_when_no_connection(qtbot):
    item = {"id": "id3", "document": "doc", "metadata": {}}
    thread = ItemUpdateThread(None, "col", item)
    errors = []
    thread.error.connect(lambda msg: errors.append(msg))

    with qtbot.waitSignal(thread.error, timeout=3000):
        thread.start()

    assert len(errors) == 1
    assert "connection" in errors[0].lower()


def test_item_update_thread_with_embeddings_arg(qtbot):
    conn = FakeConnection(update_success=True)
    item = {"id": "id4", "document": "doc", "metadata": {}}
    embeddings = [[0.1, 0.2]]

    thread = ItemUpdateThread(conn, "col", item, embeddings_arg=embeddings)
    received = {}
    thread.finished.connect(lambda d: received.update(d))

    with qtbot.waitSignal(thread.finished, timeout=3000):
        thread.start()

    assert received.get("id") == "id4"


# ---------------------------------------------------------------------------
# DataImportThread
# ---------------------------------------------------------------------------


class FakeImportConnection:
    def __init__(self, add_success=True):
        self._add_success = add_success

    def add_items(self, collection, documents, metadatas=None, ids=None, embeddings=None):
        return self._add_success


class FakeImportExportService:
    def __init__(self, data=None):
        self._data = data

    def import_from_json(self, path):
        return self._data

    def import_from_csv(self, path):
        return self._data

    def import_from_parquet(self, path):
        return self._data


def test_data_import_thread_emits_finished_on_success(qtbot, monkeypatch, tmp_path):
    import sys
    import types

    fake_data = {"ids": ["id1", "id2"], "documents": ["d1", "d2"]}

    fake_svc_mod = types.ModuleType("vector_inspector.services.import_export_service")
    fake_svc_mod.ImportExportService = lambda: FakeImportExportService(data=fake_data)
    monkeypatch.setitem(sys.modules, "vector_inspector.services.import_export_service", fake_svc_mod)

    thread = DataImportThread(
        connection=FakeImportConnection(add_success=True),
        collection_name="col",
        file_path=str(tmp_path / "data.json"),
        format_type="json",
    )

    with qtbot.waitSignal(thread.finished, timeout=5000) as blocker:
        thread.start()

    imported, count = blocker.args
    assert count == 2
    assert imported == fake_data


def test_data_import_thread_emits_error_when_parse_fails(qtbot, monkeypatch, tmp_path):
    import sys
    import types

    fake_svc_mod = types.ModuleType("vector_inspector.services.import_export_service")
    fake_svc_mod.ImportExportService = lambda: FakeImportExportService(data=None)
    monkeypatch.setitem(sys.modules, "vector_inspector.services.import_export_service", fake_svc_mod)

    thread = DataImportThread(
        connection=FakeImportConnection(),
        collection_name="col",
        file_path=str(tmp_path / "data.json"),
        format_type="json",
    )

    with qtbot.waitSignal(thread.error, timeout=5000) as blocker:
        thread.start()

    assert blocker.args[0]  # some error message


def test_data_import_thread_emits_error_when_add_items_fails(qtbot, monkeypatch, tmp_path):
    import sys
    import types

    fake_data = {"ids": ["id1"], "documents": ["d1"]}
    fake_svc_mod = types.ModuleType("vector_inspector.services.import_export_service")
    fake_svc_mod.ImportExportService = lambda: FakeImportExportService(data=fake_data)
    monkeypatch.setitem(sys.modules, "vector_inspector.services.import_export_service", fake_svc_mod)

    thread = DataImportThread(
        connection=FakeImportConnection(add_success=False),
        collection_name="col",
        file_path=str(tmp_path / "data.csv"),
        format_type="csv",
    )

    with qtbot.waitSignal(thread.error, timeout=5000) as blocker:
        thread.start()

    assert "Failed to add" in blocker.args[0]


def test_data_import_thread_emits_error_on_exception(qtbot, tmp_path):
    class ExceptionConnection:
        def add_items(self, *a, **k):
            raise RuntimeError("network gone")

    # Don't monkeypatch; DataImportThread will try to import from a non-existent file
    # and ImportExportService.import_from_json should raise
    thread = DataImportThread(
        connection=ExceptionConnection(),
        collection_name="col",
        file_path=str(tmp_path / "nonexistent.json"),
        format_type="json",
    )

    with qtbot.waitSignal(thread.error, timeout=5000) as blocker:
        thread.start()

    assert blocker.args[0]  # some Import error message


# ---------------------------------------------------------------------------
# Direct run() call tests — cover QThread.run() bodies for coverage.py
# (PySide6's C++ threads aren't traced by coverage; calling run() directly works)
# ---------------------------------------------------------------------------


def test_data_load_thread_run_direct_success():
    data = {"ids": ["x"], "documents": ["doc"]}
    conn = FakeConnection(data=data)
    ctx = MetadataContext(connection=conn, current_collection="col")
    thread = DataLoadThread(ctx, req_limit=None, req_offset=None)

    finished = []
    thread.finished.connect(lambda d: finished.append(d))
    thread.run()

    assert len(finished) == 1
    assert finished[0]["ids"] == ["x"]


def test_data_load_thread_run_direct_no_connection():
    ctx = MetadataContext(connection=None, current_collection="col")
    thread = DataLoadThread(ctx, req_limit=None, req_offset=None)

    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()

    assert errors and "No database connection" in errors[0]


def test_data_load_thread_run_direct_none_data():
    conn = FakeConnection(data=None)
    ctx = MetadataContext(connection=conn, current_collection="col")
    thread = DataLoadThread(ctx, req_limit=None, req_offset=None)

    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()

    assert errors  # "Failed to load data"


def test_data_load_thread_run_direct_exception():
    class ErrorConn:
        def get_all_items(self, *a, **k):
            raise ValueError("db down")

    ctx = MetadataContext(connection=ErrorConn(), current_collection="col")
    thread = DataLoadThread(ctx, req_limit=None, req_offset=None)

    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()

    assert errors and "db down" in errors[0]


def test_item_update_thread_run_direct_success():
    conn = FakeConnection(update_success=True)
    item = {"id": "id1", "document": "doc", "metadata": {}}
    thread = ItemUpdateThread(conn, "col", item)

    finished = []
    thread.finished.connect(lambda d: finished.append(d))
    thread.run()

    assert finished and finished[0]["id"] == "id1"


def test_item_update_thread_run_direct_failure():
    conn = FakeConnection(update_success=False)
    item = {"id": "id2", "document": "doc", "metadata": {}}
    thread = ItemUpdateThread(conn, "col", item)

    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()

    assert errors  # "Failed to update item"


def test_item_update_thread_run_direct_with_embeddings():
    conn = FakeConnection(update_success=True)
    item = {"id": "id3", "document": "doc", "metadata": {}}
    thread = ItemUpdateThread(conn, "col", item, embeddings_arg=[[0.1, 0.2]])

    finished = []
    thread.finished.connect(lambda d: finished.append(d))
    thread.run()

    assert finished and finished[0]["id"] == "id3"


def test_data_import_thread_run_direct_success(monkeypatch, tmp_path):
    import sys
    import types

    fake_data = {"ids": ["id1"], "documents": ["d1"]}
    fake_svc_mod = types.ModuleType("vector_inspector.services.import_export_service")
    fake_svc_mod.ImportExportService = lambda: FakeImportExportService(data=fake_data)
    monkeypatch.setitem(sys.modules, "vector_inspector.services.import_export_service", fake_svc_mod)

    thread = DataImportThread(
        connection=FakeImportConnection(add_success=True),
        collection_name="col",
        file_path=str(tmp_path / "data.json"),
        format_type="json",
    )

    finished = []
    thread.finished.connect(lambda d, c: finished.append((d, c)))
    thread.run()

    assert finished and finished[0][1] == 1


def test_data_import_thread_run_direct_csv(monkeypatch, tmp_path):
    import sys
    import types

    fake_data = {"ids": ["id1"], "documents": ["d1"]}
    fake_svc_mod = types.ModuleType("vector_inspector.services.import_export_service")
    fake_svc_mod.ImportExportService = lambda: FakeImportExportService(data=fake_data)
    monkeypatch.setitem(sys.modules, "vector_inspector.services.import_export_service", fake_svc_mod)

    thread = DataImportThread(
        connection=FakeImportConnection(add_success=True),
        collection_name="col",
        file_path=str(tmp_path / "data.csv"),
        format_type="csv",
    )

    finished = []
    thread.finished.connect(lambda d, c: finished.append((d, c)))
    thread.run()

    assert finished and finished[0][1] == 1


def test_data_import_thread_run_direct_no_connection():
    thread = DataImportThread(
        connection=None,
        collection_name="col",
        file_path="/some/path.json",
        format_type="json",
    )

    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()

    # No connection → ImportExportService is used normally; connection.add_items fails
    # (run() doesn't check connection before importing; it uses connection.add_items)
    assert errors  # some error


# ---------------------------------------------------------------------------
# Additional direct run() tests for uncovered branches
# ---------------------------------------------------------------------------


def test_item_update_thread_run_direct_no_connection():
    """ItemUpdateThread.run() with no connection emits error."""
    item = {"id": "id_x", "document": "doc", "metadata": {}}
    thread = ItemUpdateThread(None, "col", item)

    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()

    assert errors
    assert "connection" in errors[0].lower()


def test_item_update_thread_run_direct_exception():
    """ItemUpdateThread.run() propagates exception as error."""

    class ErrorConn:
        def update_items(self, *a, **k):
            raise RuntimeError("db exploded")

    item = {"id": "id_y", "document": "doc", "metadata": {}}
    thread = ItemUpdateThread(ErrorConn(), "col", item)

    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()

    assert errors
    assert "db exploded" in errors[0]


def test_data_import_thread_run_direct_parquet(monkeypatch, tmp_path):
    """DataImportThread covers parquet branch."""
    import sys
    import types

    fake_data = {"ids": ["id1"], "documents": ["d1"]}
    fake_svc_mod = types.ModuleType("vector_inspector.services.import_export_service")
    fake_svc_mod.ImportExportService = lambda: FakeImportExportService(data=fake_data)
    monkeypatch.setitem(sys.modules, "vector_inspector.services.import_export_service", fake_svc_mod)

    thread = DataImportThread(
        connection=FakeImportConnection(add_success=True),
        collection_name="col",
        file_path=str(tmp_path / "data.parquet"),
        format_type="parquet",
    )

    finished = []
    thread.finished.connect(lambda d, c: finished.append((d, c)))
    thread.run()

    assert finished and finished[0][1] == 1


def test_data_import_thread_run_direct_add_items_fails(monkeypatch, tmp_path):
    """DataImportThread covers add_items failure path."""
    import sys
    import types

    fake_data = {"ids": ["id1"], "documents": ["d1"]}
    fake_svc_mod = types.ModuleType("vector_inspector.services.import_export_service")
    fake_svc_mod.ImportExportService = lambda: FakeImportExportService(data=fake_data)
    monkeypatch.setitem(sys.modules, "vector_inspector.services.import_export_service", fake_svc_mod)

    thread = DataImportThread(
        connection=FakeImportConnection(add_success=False),
        collection_name="col",
        file_path=str(tmp_path / "data.json"),
        format_type="json",
    )

    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()

    assert errors
    assert "Failed to add" in errors[0]


def test_data_import_thread_run_direct_exception(monkeypatch, tmp_path):
    """DataImportThread.run() covers except block."""
    import sys
    import types

    class ExplodingService:
        def import_from_json(self, path):
            raise ConnectionError("network gone")

        def import_from_csv(self, path):
            raise ConnectionError("network gone")

        def import_from_parquet(self, path):
            raise ConnectionError("network gone")

    fake_svc_mod = types.ModuleType("vector_inspector.services.import_export_service")
    fake_svc_mod.ImportExportService = lambda: ExplodingService()
    monkeypatch.setitem(sys.modules, "vector_inspector.services.import_export_service", fake_svc_mod)

    thread = DataImportThread(
        connection=FakeImportConnection(add_success=True),
        collection_name="col",
        file_path=str(tmp_path / "data.json"),
        format_type="json",
    )

    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()

    assert errors
    assert "Import error" in errors[0]
