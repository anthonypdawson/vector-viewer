"""Tests for SearchThread (search_threads module)."""

from vector_inspector.ui.views.search_threads import SearchThread


class FakeConnection:
    def query_collection(self, collection, query_texts, n_results, where=None):
        return {"ids": [["id1"]], "documents": [["doc1"]], "distances": [[0.1]]}


class FailingConnection:
    def query_collection(self, *args, **kwargs):
        raise RuntimeError("search failed")


class EmptyConnection:
    def query_collection(self, *args, **kwargs):
        return None


def test_search_thread_emits_finished_on_success(qtbot):
    thread = SearchThread(
        connection=FakeConnection(),
        collection="test_col",
        query_text="hello",
        n_results=5,
    )
    with qtbot.waitSignal(thread.finished, timeout=5000) as blocker:
        thread.start()
    results = blocker.args[0]
    assert "ids" in results


def test_search_thread_emits_error_when_no_connection(qtbot):
    thread = SearchThread(
        connection=None,
        collection="test_col",
        query_text="hello",
        n_results=5,
    )
    with qtbot.waitSignal(thread.error, timeout=5000) as blocker:
        thread.start()
    assert "No database connection" in blocker.args[0]
    thread.wait()


def test_search_thread_emits_error_on_exception(qtbot):
    thread = SearchThread(
        connection=FailingConnection(),
        collection="test_col",
        query_text="hello",
        n_results=5,
    )
    with qtbot.waitSignal(thread.error, timeout=5000) as blocker:
        thread.start()
    assert "search failed" in blocker.args[0]
    thread.wait()


def test_search_thread_emits_error_when_results_none(qtbot):
    thread = SearchThread(
        connection=EmptyConnection(),
        collection="test_col",
        query_text="hello",
        n_results=5,
    )
    with qtbot.waitSignal(thread.error, timeout=5000) as blocker:
        thread.start()
    assert blocker.args[0]  # some error message
    thread.wait()


def test_search_thread_passes_server_filter(qtbot):
    """Verify server_filter is forwarded to query_collection."""
    calls = []

    class RecordingConnection:
        def query_collection(self, collection, query_texts, n_results, where=None):
            calls.append(where)
            return {"ids": [["id1"]], "documents": [["doc"]]}

    thread = SearchThread(
        connection=RecordingConnection(),
        collection="col",
        query_text="q",
        n_results=3,
        server_filter={"field": {"$eq": "val"}},
    )
    with qtbot.waitSignal(thread.finished, timeout=5000):
        thread.start()
    assert calls[0] == {"field": {"$eq": "val"}}


# ---------------------------------------------------------------------------
# Direct run() tests for coverage (PySide6 C++ threads don't get traced)
# ---------------------------------------------------------------------------


def test_search_thread_run_direct_success():
    thread = SearchThread(
        connection=FakeConnection(),
        collection="test_col",
        query_text="hello",
        n_results=5,
    )
    finished = []
    thread.finished.connect(lambda r: finished.append(r))
    thread.run()
    assert finished and "ids" in finished[0]


def test_search_thread_run_direct_no_connection():
    thread = SearchThread(
        connection=None,
        collection="col",
        query_text="q",
        n_results=3,
    )
    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()
    assert errors and "No database connection" in errors[0]


def test_search_thread_run_direct_no_results():
    thread = SearchThread(
        connection=EmptyConnection(),
        collection="col",
        query_text="q",
        n_results=3,
    )
    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()
    assert errors  # "Search failed"


def test_search_thread_run_direct_exception():
    thread = SearchThread(
        connection=FailingConnection(),
        collection="col",
        query_text="q",
        n_results=3,
    )
    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()
    assert errors and "search failed" in errors[0]
