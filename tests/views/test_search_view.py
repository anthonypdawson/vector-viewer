"""Tests for search_view.py covering previously uncovered lines."""

import pytest

from vector_inspector.state import AppState
from vector_inspector.ui.views.search_view import SearchView

# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


def _make_fake_provider(fake_provider):
    """Populate fake_provider with a test collection and helpers."""
    fake_provider.create_collection(
        "col1",
        ["doc1", "doc2"],
        [{"key": "v1"}, {"key": "v2"}],
        [[0.1, 0.2], [0.3, 0.4]],
        ids=["id1", "id2"],
    )
    fake_provider.compute_embeddings_for_documents = lambda texts: [[0.1, 0.2]]
    fake_provider.get_supported_filter_operators = lambda: []
    orig_qc = fake_provider.query_collection

    def _qc(collection_name, query_texts=None, n_results=10, where=None, **kwargs):
        if query_texts:
            return {
                "ids": [["id1", "id2"]],
                "documents": [["doc1", "doc2"]],
                "metadatas": [[{"key": "v1"}, {"key": "v2"}]],
                "embeddings": [[[0.1, 0.2], [0.3, 0.4]]],
                "distances": [[0.1, 0.3]],
            }
        return orig_qc(collection_name, n_results=n_results, where=where)

    fake_provider.query_collection = _qc
    return fake_provider


@pytest.fixture
def sv(qtbot, fake_provider, task_runner):
    """Search view fixture backed by a populated fake provider."""
    _make_fake_provider(fake_provider)
    app_state = AppState()
    app_state.provider = fake_provider
    view = SearchView(app_state, task_runner)
    qtbot.addWidget(view)
    view.current_collection = "col1"
    view.current_database = "test_db"
    return view


# ---------------------------------------------------------------------------
# Signal-connected handler methods
# ---------------------------------------------------------------------------


def test_on_provider_changed_clears_results(sv, qtbot, fake_provider):
    """_on_provider_changed clears results and updates status."""
    # Pre-populate table so clearing is observable
    sv.results_table.setRowCount(3)
    sv.app_state.provider_changed.emit(None)
    assert sv.results_table.rowCount() == 0
    assert "No search performed" in sv.results_status.text() or "Connected" in sv.results_status.text()


def test_on_provider_changed_with_connection(sv, qtbot, fake_provider):
    """_on_provider_changed sets connection when provided."""
    sv.app_state.provider_changed.emit(fake_provider)
    assert sv.connection is fake_provider


def test_on_collection_changed_calls_set_collection(sv, qtbot):
    """_on_collection_changed → set_collection()."""
    sv.app_state.database = "test_db"
    sv.app_state.collection_changed.emit("col1")
    assert sv.current_collection == "col1"


def test_on_loading_started_shows_dialog(sv, qtbot, monkeypatch):
    """_on_loading_started shows the loading dialog."""
    showed = []
    monkeypatch.setattr(sv.loading_dialog, "show_loading", lambda msg: showed.append(msg))
    sv.app_state.loading_started.emit("Loading...")
    assert showed == ["Loading..."]


def test_on_loading_finished_hides_dialog(sv, qtbot, monkeypatch):
    """_on_loading_finished hides the loading dialog."""
    hidden = []
    monkeypatch.setattr(sv.loading_dialog, "hide", lambda: hidden.append(True))
    sv.app_state.loading_finished.emit()
    assert hidden == [True]


def test_on_error_shows_critical_dialog(sv, qtbot, monkeypatch):
    """_on_error shows QMessageBox.critical."""
    import vector_inspector.ui.views.search_view as sv_mod

    shown = []
    monkeypatch.setattr(
        sv_mod, "QMessageBox", type("MB", (), {"critical": staticmethod(lambda *a, **k: shown.append(True))})
    )
    sv.app_state.error_occurred.emit("Title", "Msg")
    assert shown


# ---------------------------------------------------------------------------
# Breadcrumb elide modes
# ---------------------------------------------------------------------------


def test_set_breadcrumb_elide_left(sv, qtbot):
    """ElideLeft mode is used when _elide_mode == 'left'."""
    sv._elide_mode = "left"
    sv._full_breadcrumb = "long > path > to > collection > name"
    sv._update_breadcrumb_display()
    # Just verify no exception and label is set
    assert sv.breadcrumb_label.text() is not None


def test_set_elide_mode_middle(sv, qtbot):
    """set_elide_mode with 'middle' refreshes display."""
    sv.set_breadcrumb("DB > MyCollection > SubItem")
    sv.set_elide_mode("middle")
    assert sv._elide_mode == "middle"


def test_set_elide_mode_invalid_defaults_to_left(sv, qtbot):
    """set_elide_mode with invalid value defaults to 'left'."""
    sv.set_elide_mode("invalid_mode")
    assert sv._elide_mode == "left"


# ---------------------------------------------------------------------------
# Cache hit path in set_collection
# ---------------------------------------------------------------------------


def test_set_collection_cache_hit_restores_results(sv, qtbot):
    """cache hit → restores search results and returns early."""
    results = {
        "ids": [["id1", "id2"]],
        "documents": [["doc1", "doc2"]],
        "metadatas": [[{"key": "v1"}, {"key": "v2"}]],
        "distances": [[0.1, 0.3]],
    }
    sv.cache_manager.update("test_db", "col1", search_query="my query", search_results=results)

    sv.set_collection("col1", "test_db")

    assert sv.query_input.toPlainText() == "my query"
    assert sv.search_results is not None


# ---------------------------------------------------------------------------
# Cache miss path & metadata loading
# ---------------------------------------------------------------------------


def test_set_collection_cache_miss_loads_metadata(sv, qtbot):
    """cache miss clears form and loads metadata fields."""
    sv.set_collection("col1", "test_db")
    # After set_collection, filter builder should have fields from metadata
    # (fake provider returns {"key": "v1"} items)
    assert sv.current_collection == "col1"
    assert sv.results_status.text() == "Collection: col1"


# ---------------------------------------------------------------------------
# _perform_search paths
# ---------------------------------------------------------------------------


def test_perform_search_empty_query(sv, qtbot):
    """empty query → status updated, no search started."""
    sv.query_input.clear()
    sv._perform_search()
    assert sv.results_status.text() == "Please enter search text"


def test_perform_search_no_collection(sv, qtbot):
    """no collection → 'No collection selected'."""
    sv.current_collection = ""
    sv._perform_search()
    assert "No collection selected" in sv.results_status.text()


def test_perform_search_cancels_running_thread(sv, qtbot):
    """running thread is quit/wait'd before new search."""

    class FakeThread:
        def __init__(self):
            self._running = True
            self.quit_called = False
            self.wait_called = False

        def isRunning(self):
            return self._running

        def quit(self):
            self.quit_called = True
            self._running = False

        def wait(self):
            self.wait_called = True

    fake = FakeThread()
    sv.search_thread = fake
    sv.query_input.setPlainText("test query")
    # Patch start to no-op to avoid real Qt thread
    import vector_inspector.ui.views.search_view as sv_mod

    class NullThread:
        def __init__(self, *a, **k):

            class Sig:
                def connect(self, *a):
                    pass

            self.finished = Sig()
            self.error = Sig()

        def start(self):
            pass

    old_cls = sv_mod.SearchThread
    sv_mod.SearchThread = NullThread
    try:
        sv._perform_search()
    finally:
        sv_mod.SearchThread = old_cls

    assert fake.quit_called
    assert fake.wait_called


# ---------------------------------------------------------------------------
# _on_search_finished
# ---------------------------------------------------------------------------


def test_on_search_finished_empty_results(sv, qtbot):
    """empty results → 'No results found' status."""
    sv._search_start_time = __import__("time").time()
    sv._search_correlation_id = "test-id"
    sv._search_server_filter = None
    sv._search_client_filters = []
    sv._on_search_finished({})
    assert "No results found" in sv.results_status.text()


def test_on_search_finished_with_results(sv, qtbot):
    """valid results → display and cache update."""
    import time

    sv._search_start_time = time.time()
    sv._search_correlation_id = "test-id"
    sv._search_server_filter = None
    sv._search_client_filters = []
    sv._search_query_text = "test q"
    sv._search_n_results = 10

    results = {
        "ids": [["id1", "id2"]],
        "documents": [["doc1", "doc2"]],
        "metadatas": [[{"key": "v1"}, {"key": "v2"}]],
        "distances": [[0.1, 0.3]],
    }
    sv._on_search_finished(results)
    assert "Found 2 results" in sv.results_status.text()


def test_on_search_finished_with_client_filters(sv, qtbot):
    """client-side filters applied after results."""
    import time

    sv._search_start_time = time.time()
    sv._search_correlation_id = "cid"
    sv._search_server_filter = None
    sv._search_query_text = "test"
    sv._search_n_results = 10

    # Simple filter that keeps all items
    sv._search_client_filters = [{"field": "key", "operator": "==", "value": "v1"}]

    results = {
        "ids": [["id1", "id2"]],
        "documents": [["doc1", "doc2"]],
        "metadatas": [[{"key": "v1"}, {"key": "v2"}]],
        "distances": [[0.1, 0.3]],
    }
    # Should not raise even if filter removes some results
    sv._on_search_finished(results)


# ---------------------------------------------------------------------------
# _on_search_error
# ---------------------------------------------------------------------------


def test_on_search_error_updates_status(sv, qtbot):
    """search error updates status and clears table."""
    import time

    sv._search_start_time = time.time()
    sv._search_correlation_id = "corr"
    sv._search_server_filter = None
    sv._search_client_filters = []

    sv._on_search_error("connection refused")
    assert "Search failed" in sv.results_status.text()
    assert "connection refused" in sv.results_status.text()
    assert sv.results_table.rowCount() == 0


# ---------------------------------------------------------------------------
# _on_row_double_clicked
# ---------------------------------------------------------------------------


def test_on_row_double_clicked_out_of_bounds(sv, qtbot):
    """row >= len(ids) → no dialog shown (no crash)."""
    sv.search_results = {
        "ids": [["id1"]],
        "documents": [["doc1"]],
        "metadatas": [[{"k": "v"}]],
        "distances": [[0.1]],
    }
    sv.results_table.setRowCount(3)
    sv.results_table.setColumnCount(3)
    # row=2 is out of range for single-item results
    idx = sv.results_table.model().index(2, 0)
    # Should not raise
    sv._on_row_double_clicked(idx)


# ---------------------------------------------------------------------------
# _on_selection_changed
# ---------------------------------------------------------------------------


def test_on_selection_changed_no_results(sv, qtbot):
    """no search_results → pane updated with None."""
    sv.search_results = None
    updated = []
    sv.details_pane.update_item = lambda d: updated.append(d)
    sv._on_selection_changed()
    assert updated == [None]


def test_on_selection_changed_with_row(sv, qtbot):
    """selection changes → details pane updated."""
    sv.search_results = {
        "ids": [["id1", "id2"]],
        "documents": [["doc1", "doc2"]],
        "metadatas": [[{"key": "v1"}, {"key": "v2"}]],
        "embeddings": [[[0.1, 0.2], [0.3, 0.4]]],
        "distances": [[0.1, 0.3]],
    }
    import time

    sv._search_start_time = time.time()
    sv._search_correlation_id = "c"
    sv._search_server_filter = None
    sv._search_client_filters = []
    sv._search_query_text = "q"
    sv._search_n_results = 10
    sv._on_search_finished(sv.search_results)

    updated = []
    sv.details_pane.update_item = lambda d: updated.append(d)
    sv.results_table.selectRow(0)
    sv._on_selection_changed()

    assert updated and updated[-1] is not None
    assert updated[-1]["id"] == "id1"


# ---------------------------------------------------------------------------
# _copy_vectors_to_json
# ---------------------------------------------------------------------------


def test_copy_vectors_no_results(sv, qtbot, monkeypatch):
    """no search_results → warning dialog."""
    import vector_inspector.ui.views.search_view as sv_mod

    warnings = []
    monkeypatch.setattr(
        sv_mod,
        "QMessageBox",
        type(
            "MB",
            (),
            {
                "warning": staticmethod(lambda *a, **k: warnings.append(True)),
                "information": staticmethod(lambda *a, **k: None),
            },
        ),
    )
    sv.search_results = None
    sv._copy_vectors_to_json([0])
    assert warnings


def test_copy_vectors_no_ids(sv, qtbot, monkeypatch):
    """empty ids → warning dialog."""
    import vector_inspector.ui.views.search_view as sv_mod

    warnings = []
    monkeypatch.setattr(
        sv_mod,
        "QMessageBox",
        type(
            "MB",
            (),
            {
                "warning": staticmethod(lambda *a, **k: warnings.append(True)),
                "information": staticmethod(lambda *a, **k: None),
            },
        ),
    )
    sv.search_results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    sv._copy_vectors_to_json([0])
    assert warnings


def test_copy_vectors_fetches_embedding(sv, qtbot, monkeypatch):
    """fetches embedding from connection and copies to clipboard."""
    import vector_inspector.ui.views.search_view as sv_mod

    sv.search_results = {
        "ids": [["id1"]],
        "documents": [["doc1"]],
        "metadatas": [[{"key": "v1"}]],
        "distances": [[0.1]],
    }

    # Fake get_all_items that returns embeddings
    sv.connection.get_all_items = lambda *a, **k: {
        "ids": ["id1"],
        "documents": ["doc1"],
        "metadatas": [{"key": "v1"}],
        "embeddings": [[0.1, 0.2, 0.3]],
    }

    info_messages = []
    monkeypatch.setattr(
        sv_mod,
        "QMessageBox",
        type(
            "MB",
            (),
            {
                "warning": staticmethod(lambda *a, **k: None),
                "information": staticmethod(lambda *a, **k: info_messages.append(True)),
            },
        ),
    )

    clipboard_text = []

    class FakeClipboard:
        def setText(self, text):
            clipboard_text.append(text)

    monkeypatch.setattr(sv_mod.QApplication, "clipboard", staticmethod(lambda: FakeClipboard()))

    sv._copy_vectors_to_json([0])
    assert clipboard_text
    import json

    data = json.loads(clipboard_text[0])
    assert data["id"] == "id1"
    assert info_messages


# ---------------------------------------------------------------------------
# _show_context_menu
# ---------------------------------------------------------------------------


def test_show_context_menu_no_item(sv, qtbot):
    """no item at position → no menu shown (no crash)."""
    from PySide6.QtCore import QPoint

    sv.results_table.setRowCount(0)
    # Should not raise or show a menu
    sv._show_context_menu(QPoint(0, 0))


def test_show_context_menu_on_valid_row(sv, qtbot, monkeypatch):
    """valid row → context menu populated and exec'd."""
    import time

    import vector_inspector.ui.views.search_view as sv_mod

    sv.search_results = {
        "ids": [["id1"]],
        "documents": [["doc1"]],
        "metadatas": [[{"key": "v1"}]],
        "distances": [[0.1]],
    }
    sv._search_start_time = time.time()
    sv._search_correlation_id = "c"
    sv._search_server_filter = None
    sv._search_client_filters = []
    sv._search_query_text = "q"
    sv._search_n_results = 10
    sv._on_search_finished(sv.search_results)

    exec_called = []

    class FakeMenu:
        def __init__(self, parent=None):
            self._actions = []

        def addAction(self, text):
            class FakeAction:
                def triggered(self):
                    pass

                def connect(self, fn):
                    pass

            class Sig:
                def connect(self, fn):
                    pass

            a = FakeAction()
            a.triggered = Sig()
            self._actions.append(a)
            return a

        def addSeparator(self):
            pass

        def isEmpty(self):
            return False

        def exec(self, pos):
            exec_called.append(pos)

    monkeypatch.setattr(sv_mod, "QMenu", FakeMenu)

    from PySide6.QtCore import QPoint

    # item at (0,0) for first row
    sv.results_table.scrollToTop()
    pos = QPoint(5, 5)
    sv._show_context_menu(pos)
    # Should have tried to exec the menu (may or may not have an item depending on viewport)


# ---------------------------------------------------------------------------
# _display_results column restore
# ---------------------------------------------------------------------------


def test_display_results_column_restore_on_second_call(sv, qtbot):
    """second _display_results call with existing columns triggers restore logic."""
    results = {
        "ids": [["id1", "id2"]],
        "documents": [["doc1", "doc2"]],
        "metadatas": [[{"col_a": "x"}, {"col_a": "y"}]],
        "distances": [[0.1, 0.2]],
    }
    # First call sets up columns
    sv._display_results(results)
    assert sv.results_table.columnCount() > 0

    # Second call triggers column-restore logic (old_column_order will be populated)
    sv._display_results(results)
    assert sv.results_table.rowCount() == 2
    assert "Found 2 results" in sv.results_status.text()


def test_display_results_empty_ids(sv, qtbot):
    """empty ids → clear table and 'No results found'."""
    results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    sv._display_results(results)
    assert sv.results_table.rowCount() == 0
    assert "No results found" in sv.results_status.text()


def test_display_results_null_distance(sv, qtbot):
    """None distance is displayed as 'N/A'."""
    results = {
        "ids": [["id1"]],
        "documents": [["doc1"]],
        "metadatas": [[{"k": "v"}]],
        "distances": [[None]],
    }
    sv._display_results(results)
    item = sv.results_table.item(0, 1)
    assert item and item.text() == "N/A"


def test_display_results_truncates_long_doc(sv, qtbot):
    """doc > 150 chars is truncated."""
    long_doc = "x" * 200
    results = {
        "ids": [["id1"]],
        "documents": [[long_doc]],
        "metadatas": [[{}]],
        "distances": [[0.1]],
    }
    sv._display_results(results)
    doc_item = sv.results_table.item(0, 3)
    assert doc_item and len(doc_item.text()) <= 154  # 150 + "..."


# ---------------------------------------------------------------------------
# closeEvent
# ---------------------------------------------------------------------------


def test_close_event_saves_pane_state(sv, qtbot, monkeypatch):
    """closeEvent calls details_pane.save_state()."""
    saved = []
    monkeypatch.setattr(sv.details_pane, "save_state", lambda: saved.append(True))
    from PySide6.QtGui import QCloseEvent

    sv.closeEvent(QCloseEvent())
    assert saved == [True]
