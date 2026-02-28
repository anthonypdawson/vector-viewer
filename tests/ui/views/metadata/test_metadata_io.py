from PySide6.QtWidgets import QMessageBox, QWidget

from vector_inspector.ui.views.metadata.metadata_io import (
    export_data,
    import_data,
)


class DummyCtx:
    def __init__(self):
        self.current_collection = None
        self.current_data = None
        self.connection = None


def test_export_no_collection(monkeypatch, qtbot):
    ctx = DummyCtx()
    parent = QWidget()
    qtbot.addWidget(parent)

    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    assert export_data(parent, ctx, "json") is False


def test_export_no_data(monkeypatch, qtbot):
    ctx = DummyCtx()
    ctx.current_collection = "col1"
    ctx.current_data = {"ids": []}
    parent = QWidget()
    qtbot.addWidget(parent)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    assert export_data(parent, ctx, "json") is False


def test_export_success_json(monkeypatch, tmp_path, qtbot):
    ctx = DummyCtx()
    ctx.current_collection = "col1"
    ctx.current_data = {"ids": ["id1"], "documents": ["d1"]}

    # Patch file dialog to return a path
    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(tmp_path / "out.json"), ""),
    )

    class FakeService:
        def export_to_json(self, data, path):
            return True

    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.ImportExportService",
        lambda: FakeService(),
    )

    # Patch SettingsService.set to capture directory
    class FakeSettings:
        def __init__(self):
            self._store = {}

        def get(self, key, default=None):
            return ""

        def set(self, key, val):
            self._store[key] = val

    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.SettingsService",
        lambda: FakeSettings(),
    )

    # Ensure message boxes don't block
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    parent = QWidget()
    qtbot.addWidget(parent)
    assert export_data(parent, ctx, "json") is True


def test_import_no_collection(monkeypatch, qtbot):
    ctx = DummyCtx()
    parent = QWidget()
    loading = type("L", (), {"show_loading": lambda *a, **k: None, "hide_loading": lambda *a, **k: None})()
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    qtbot.addWidget(parent)
    assert import_data(parent, ctx, "json", loading) is None


def test_import_success(monkeypatch, tmp_path, qtbot):
    ctx = DummyCtx()
    ctx.current_collection = "col1"

    # Fake connection that records add_items call
    class FakeConn:
        def __init__(self):
            self.added = None

        def add_items(self, collection, documents, metadatas=None, ids=None, embeddings=None):
            self.added = (collection, documents)
            return True

    ctx.connection = FakeConn()

    # Patch file dialog to return a path
    p = tmp_path / "in.json"
    p.write_text('{"ids":["id1"], "documents":["d1"]}')
    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.QFileDialog.getOpenFileName", lambda *a, **k: (str(p), "")
    )

    class FakeService:
        def import_from_json(self, path):
            return {"ids": ["id1"], "documents": ["d1"]}

    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.ImportExportService", lambda: FakeService())

    # Patch SettingsService to provide get/set
    class FakeSettings2:
        def __init__(self):
            self._store = {}

        def get(self, key, default=None):
            return ""

        def set(self, key, val):
            self._store[key] = val

    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.SettingsService", lambda: FakeSettings2())

    # Prevent message boxes from showing during tests
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    loading = type("L", (), {"show_loading": lambda *a, **k: None, "hide_loading": lambda *a, **k: None})()
    parent = QWidget()
    qtbot.addWidget(parent)
    res = import_data(parent, ctx, "json", loading)
    assert res is not None
    assert ctx.connection.added[0] == "col1"


# ---------------------------------------------------------------------------
# Additional export coverage
# ---------------------------------------------------------------------------


def _fake_settings():
    class _FS:
        def get(self, key, default=None):
            return ""

        def set(self, key, val):
            pass

    return _FS()


def test_export_no_file_selected_returns_false(monkeypatch, qtbot):
    ctx = DummyCtx()
    ctx.current_collection = "col1"
    ctx.current_data = {"ids": ["id1"], "documents": ["d1"]}
    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.QFileDialog.getSaveFileName",
        lambda *a, **k: ("", ""),
    )
    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.SettingsService", _fake_settings)
    parent = QWidget()
    qtbot.addWidget(parent)
    assert export_data(parent, ctx, "json") is False


def test_export_csv_format(monkeypatch, tmp_path, qtbot):
    ctx = DummyCtx()
    ctx.current_collection = "col1"
    ctx.current_data = {"ids": ["id1"], "documents": ["d1"]}
    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(tmp_path / "out.csv"), ""),
    )

    class FakeSvc:
        def export_to_csv(self, data, path):
            return True

    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.ImportExportService", lambda: FakeSvc())
    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.SettingsService", _fake_settings)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    parent = QWidget()
    qtbot.addWidget(parent)
    assert export_data(parent, ctx, "csv") is True


def test_export_failure_path(monkeypatch, tmp_path, qtbot):
    ctx = DummyCtx()
    ctx.current_collection = "col1"
    ctx.current_data = {"ids": ["id1"], "documents": ["d1"]}
    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(tmp_path / "out.json"), ""),
    )

    class FailSvc:
        def export_to_json(self, data, path):
            return False

    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.ImportExportService", lambda: FailSvc())
    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.SettingsService", _fake_settings)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    parent = QWidget()
    qtbot.addWidget(parent)
    assert export_data(parent, ctx, "json") is False


def test_export_with_selected_rows(monkeypatch, tmp_path, qtbot):
    from PySide6.QtWidgets import QAbstractItemView, QTableWidget, QTableWidgetItem

    ctx = DummyCtx()
    ctx.current_collection = "col1"
    ctx.current_data = {
        "ids": ["id1", "id2"],
        "documents": ["d1", "d2"],
        "metadatas": [{"k": "v1"}, {"k": "v2"}],
        "embeddings": [[0.1], [0.2]],
    }

    table = QTableWidget(2, 2)
    qtbot.addWidget(table)
    table.setItem(0, 0, QTableWidgetItem("id1"))
    table.setItem(1, 0, QTableWidgetItem("id2"))
    table.setSelectionMode(QAbstractItemView.MultiSelection)
    table.selectRow(0)  # select only first row

    saved_data = {}

    class FakeSvc:
        def export_to_json(self, data, path):
            saved_data["data"] = data
            return True

    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.ImportExportService", lambda: FakeSvc())
    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.SettingsService", _fake_settings)
    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(tmp_path / "sel.json"), ""),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    parent = QWidget()
    qtbot.addWidget(parent)

    result = export_data(parent, ctx, "json", table=table)
    assert result is True
    assert saved_data["data"]["ids"] == ["id1"]


# ---------------------------------------------------------------------------
# Additional import coverage
# ---------------------------------------------------------------------------


def test_import_no_file_selected_returns_none(monkeypatch, qtbot):
    ctx = DummyCtx()
    ctx.current_collection = "col1"
    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.QFileDialog.getOpenFileName",
        lambda *a, **k: ("", ""),
    )
    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.SettingsService", _fake_settings)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)

    loading = type("L", (), {"show_loading": lambda *a, **k: None, "hide_loading": lambda *a, **k: None})()
    parent = QWidget()
    qtbot.addWidget(parent)
    assert import_data(parent, ctx, "json", loading) is None


def test_import_parse_fails_returns_none(monkeypatch, tmp_path, qtbot):
    ctx = DummyCtx()
    ctx.current_collection = "col1"

    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(tmp_path / "bad.json"), ""),
    )

    class FakeSvc:
        def import_from_json(self, path):
            return None  # parse failed

    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.ImportExportService", lambda: FakeSvc())
    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.SettingsService", _fake_settings)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    loading = type("L", (), {"show_loading": lambda *a, **k: None, "hide_loading": lambda *a, **k: None})()
    parent = QWidget()
    qtbot.addWidget(parent)
    result = import_data(parent, ctx, "json", loading)
    assert result is None


def test_import_add_items_fails_returns_none(monkeypatch, tmp_path, qtbot):
    ctx = DummyCtx()
    ctx.current_collection = "col1"

    class FailConn:
        def add_items(self, *a, **k):
            return False

    ctx.connection = FailConn()

    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_io.QFileDialog.getOpenFileName",
        lambda *a, **k: (str(tmp_path / "data.json"), ""),
    )

    class FakeSvc:
        def import_from_json(self, path):
            return {"ids": ["id1"], "documents": ["d1"]}

    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.ImportExportService", lambda: FakeSvc())
    monkeypatch.setattr("vector_inspector.ui.views.metadata.metadata_io.SettingsService", _fake_settings)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)

    loading = type("L", (), {"show_loading": lambda *a, **k: None, "hide_loading": lambda *a, **k: None})()
    parent = QWidget()
    qtbot.addWidget(parent)
    result = import_data(parent, ctx, "json", loading)
    assert result is None
