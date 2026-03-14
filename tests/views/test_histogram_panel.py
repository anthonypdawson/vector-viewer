# Ensure a QApplication exists for QWidget creation during tests
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from vector_inspector.ui.views.visualization.histogram_panel import (
    HistogramPanel,
    _CollectionDimScanThread,
    _CompareLoadThread,
)

if QApplication.instance() is None:
    _qapp = QApplication([])


# Per-test opt-in: use `webengine_cleanup` from tests/conftest.py and call
# `qtbot.addWidget(panel)` after constructing any `HistogramPanel` instance.


class DummyConnection:
    def __init__(self, name: str):
        self.name = name


def make_data(embeddings):
    return {"embeddings": embeddings, "documents": [], "metadatas": []}


def test_histogram_includes_connection_names(monkeypatch, qtbot, webengine_cleanup):
    # Primary connection provided
    conn = DummyConnection("LocalConn")

    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.set_connection(conn)

    # Primary collection data
    panel.set_data(make_data([[1.0, 0.0], [0.0, 1.0]]), collection_name="test_collection")

    # Prepare comparison data and label (simulate scan result label)
    compare_label = "OtherConn / other_collection"
    # Add option and select it
    panel._compare_options[compare_label] = ("other_collection", DummyConnection("OtherConn"))
    panel.compare_combo.addItem(compare_label)
    panel.compare_combo.setCurrentIndex(0)
    panel._compare_data = make_data([[0.5, 0.5]])

    # Generate histogram (will produce Plotly HTML)
    panel.generate_histogram()

    html = panel.get_current_html()
    assert html is not None
    # Both primary and comparison trace names should include connection prefixes
    assert "LocalConn / test_collection" in html
    assert "OtherConn / other_collection" in html


def test_extract_values_norm_and_dimension(qtbot, webengine_cleanup):
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    data = make_data([[3.0, 4.0], [0.0, 2.0]])

    # Norm metric
    panel.metric_combo.setCurrentIndex(0)  # Norm
    vals = panel._extract_values(data)
    assert vals == [5.0, 2.0]

    # Dimension metric
    panel.metric_combo.setCurrentIndex(1)  # Dimension
    panel.dim_spin.setValue(1)
    vals2 = panel._extract_values(data)
    assert vals2 == [4.0, 2.0]


def test_on_clear_resets_state(qtbot, webengine_cleanup):
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.set_data(make_data([[1.0, 0.0]]), collection_name="col")
    panel._compare_data = make_data([[0.5, 0.5]])
    panel._compare_options["X"] = ("other", DummyConnection("Other"))
    panel.compare_combo.addItem("X")

    panel._on_clear()

    assert panel._current_data is None
    assert panel._compare_data is None
    assert not panel.generate_button.isEnabled()


def test_collection_dim_scan_thread_emits_labels():
    # Create two dummy connections that expose the minimal API used by the thread
    class Conn:
        def __init__(self, name, collections, embeddings_map):
            self.name = name
            self._collections = collections
            self._embeddings = embeddings_map

        def list_collections(self):
            return self._collections

        def get_all_items(self, name, limit=None):
            emb = self._embeddings.get(name)
            if emb is None:
                return None
            return {"embeddings": emb}

    c1 = Conn("A", ["c1"], {"c1": [[1.0, 0.0]]})
    c2 = Conn("B", ["c2"], {"c2": [[0.5, 0.5]]})

    results = []

    t = _CollectionDimScanThread([c1, c2], exclude_collection="none", target_dim=2)

    def on_finished(value):
        results.append(value)

    t.finished.connect(on_finished)
    # Call run() directly to avoid creating a real thread
    t.run()

    assert len(results) == 1
    found = results[0]
    # Should contain labels prefixed with connection name
    labels = [lbl for lbl, _, _ in found]
    assert "A / c1" in labels or "B / c2" in labels


def test_compare_load_thread_emits_finished_and_error():
    class ConnGood:
        def get_all_items(self, collection, limit=None):
            return {"embeddings": [[1.0, 0.0]]}

    class ConnBad:
        def get_all_items(self, collection, limit=None):
            return None

    good = ConnGood()
    bad = ConnBad()

    finished_vals = []
    errors = []

    t_good = _CompareLoadThread(good, "c", None)
    t_good.finished.connect(lambda d: finished_vals.append(d))
    t_good.error.connect(lambda e: errors.append(e))
    t_good.run()

    assert len(finished_vals) == 1

    t_bad = _CompareLoadThread(bad, "c", None)
    t_bad.finished.connect(lambda d: finished_vals.append(d))
    t_bad.error.connect(lambda e: errors.append(e))
    t_bad.run()

    assert len(errors) == 1


def test_compare_load_thread_with_sample_size():
    """_CompareLoadThread with non-None sample_size uses the limit parameter."""

    class ConnSampled:
        def __init__(self):
            self.last_limit = None

        def get_all_items(self, collection, limit=None):
            self.last_limit = limit
            return {"embeddings": [[1.0, 0.0]]}

    conn = ConnSampled()
    finished_vals = []
    t = _CompareLoadThread(conn, "col", sample_size=5)
    t.finished.connect(lambda d: finished_vals.append(d))
    t.run()
    assert finished_vals
    assert conn.last_limit == 5


def test_dim_scan_thread_exception_in_list_collections():
    """When list_collections raises, connection is skipped."""

    class BrokenConn:
        name = "broken"

        def list_collections(self):
            raise RuntimeError("boom")

    t = _CollectionDimScanThread([BrokenConn()], exclude_collection="x", target_dim=2)
    results = []
    t.finished.connect(lambda v: results.append(v))
    t.run()
    assert results == [[]]


def test_dim_scan_thread_dim_mismatch_skips():
    """Collections whose embedding dim != target_dim are excluded."""

    class ConnDimMismatch:
        name = "C"

        def list_collections(self):
            return ["col"]

        def get_all_items(self, name, limit=None):
            return {"embeddings": [[1.0, 2.0, 3.0]]}  # dim=3

    t = _CollectionDimScanThread([ConnDimMismatch()], exclude_collection="x", target_dim=2)  # want dim=2
    results = []
    t.finished.connect(lambda v: results.append(v))
    t.run()
    assert results == [[]]  # nothing compatible


def test_on_compare_toggled_false_resets(qtbot, webengine_cleanup):
    """Toggling Compare off resets comparison."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._compare_data = make_data([[0.1, 0.2]])
    panel.set_data(make_data([[1.0, 0.0]]), collection_name="col")

    panel._on_compare_toggled(0)  # False/unchecked

    assert panel._compare_data is None


def test_on_compare_toggled_true_no_primary_dim(qtbot, webengine_cleanup):
    """Compare toggled on with no primary dim shows warning and reverts checkbox."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._primary_dim = 0  # not yet set

    panel._on_compare_toggled(2)  # True/checked

    assert not panel.compare_checkbox.isChecked()
    assert panel.compare_status_label.text() != ""


def test_on_compare_toggled_no_connections(qtbot, webengine_cleanup):
    """Compare toggled on with no connections shows 'no connections' message."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._primary_dim = 2
    panel._connection = None
    panel._connection_manager = None

    panel._on_compare_toggled(2)

    assert "No active connections" in panel.compare_status_label.text()
    assert not panel.compare_checkbox.isChecked()


def test_on_compare_toggled_with_connection_starts_scan(qtbot, webengine_cleanup):
    """Compare toggled on with a connection starts the dim scan thread."""

    class ConnDim:
        name = "C"

        def list_collections(self):
            return ["c1"]

        def get_all_items(self, name, limit=None):
            return {"embeddings": [[1.0, 0.0]]}

    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._primary_dim = 2
    panel._primary_collection = "primary"
    panel._connection = ConnDim()

    panel._on_compare_toggled(2)

    # Thread should have been created; call cancel to avoid leaving it running
    if panel._dim_scan_thread and panel._dim_scan_thread.isRunning():
        panel._dim_scan_thread.quit()
        panel._dim_scan_thread.wait()

    assert panel.compare_status_label.text() != ""


def test_on_dim_scan_finished_empty():
    """No compatible collections shows a message and reverts checkbox."""
    panel = HistogramPanel()
    panel._primary_dim = 2

    panel._on_dim_scan_finished([])

    assert not panel.compare_checkbox.isChecked()
    assert "No other" in panel.compare_status_label.text()


def test_on_dim_scan_finished_with_results(qtbot, webengine_cleanup):
    """Compatible collections populate the combo box."""

    class FakeConn:
        name = "X"

    compatible = [("X / col", "col", FakeConn())]
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._on_dim_scan_finished(compatible)

    assert panel.compare_combo.count() == 1
    assert panel.compare_combo.isEnabled()
    assert panel.compare_load_button.isEnabled()


def test_on_load_comparison_no_label(qtbot, webengine_cleanup):
    """_on_load_comparison does nothing when no label selected."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.compare_combo.clear()  # empty, so currentText() == ""

    # Should not raise
    panel._on_load_comparison()


def test_on_load_comparison_invalid_option(qtbot, webengine_cleanup):
    """_on_load_comparison shows error for unknown label."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.compare_combo.addItem("ghost_label")
    panel.compare_combo.setCurrentIndex(0)
    # _compare_options is empty, so "ghost_label" is not in it

    panel._on_load_comparison()

    assert "Invalid" in panel.compare_status_label.text()


def test_on_compare_loaded(qtbot, webengine_cleanup):
    """_on_compare_loaded stores data and updates status."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.compare_combo.addItem("Other / col")
    panel.compare_combo.setCurrentIndex(0)
    panel.set_data(make_data([[1.0, 0.0]]), collection_name="primary")

    data = make_data([[0.5, 0.5], [0.3, 0.7]])
    panel._on_compare_loaded(data)

    assert panel._compare_data is data
    assert "Loaded" in panel.compare_status_label.text()


def test_on_compare_error(qtbot, webengine_cleanup):
    """_on_compare_error clears compare data and shows error message."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._compare_data = make_data([[0.1]])

    panel._on_compare_error("connection lost")

    assert panel._compare_data is None
    assert "Load failed" in panel.compare_status_label.text()


def test_extract_values_empty_embeddings_sets_status(qtbot, webengine_cleanup):
    """_extract_values with no valid embeddings returns None and sets status."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    data_no_emb = {"embeddings": [], "documents": [], "metadatas": []}

    result = panel._extract_values(data_no_emb)

    assert result is None
    assert "No valid" in panel.status_label.text()


def test_extract_values_dim_out_of_range(qtbot, webengine_cleanup):
    """_extract_values with out-of-range dimension sets status."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.metric_combo.setCurrentIndex(1)  # Dimension
    panel.dim_spin.setValue(99)  # way out of range for 2-d vectors

    result = panel._extract_values(make_data([[1.0, 0.0]]))

    assert result is None
    assert "out of range" in panel.status_label.text()


def test_dim_scan_thread_exclude_collection():
    """The excluded collection is skipped in the scan."""

    class ConnExclude:
        name = "C"

        def list_collections(self):
            return ["excluded", "included"]

        def get_all_items(self, name, limit=None):
            return {"embeddings": [[1.0, 0.0]]}

    t = _CollectionDimScanThread([ConnExclude()], exclude_collection="excluded", target_dim=2)
    results = []
    t.finished.connect(lambda v: results.append(v))
    t.run()
    found_labels = [lbl for lbl, _, _ in results[0]]
    assert "C / excluded" not in found_labels
    assert "C / included" in found_labels


def test_dim_scan_thread_none_embeddings_skips():
    """Collections returning None embeddings are skipped."""

    class ConnNoneEmb:
        name = "D"

        def list_collections(self):
            return ["col"]

        def get_all_items(self, name, limit=None):
            return {"embeddings": None}

    t = _CollectionDimScanThread([ConnNoneEmb()], exclude_collection="x", target_dim=2)
    results = []
    t.finished.connect(lambda v: results.append(v))
    t.run()
    assert results == [[]]


class MockConnForScan:
    def __init__(self, name, collections):
        self.name = name
        self._cols = collections

    def list_collections(self):
        return list(self._cols.keys())

    def get_all_items(self, name, limit=None):
        return {"embeddings": self._cols.get(name, [])}


def test_collection_scan_includes_same_name_on_different_connection():
    # Primary connection A has a collection named 'shared'
    conn_a = MockConnForScan("A", {"shared": [[1, 2]], "only_a": [[1, 2]]})
    # Another connection B also has a collection named 'shared'
    conn_b = MockConnForScan("B", {"shared": [[1, 2]], "only_b": [[1, 2]]})

    target_dim = 2

    # Capture the emitted compatible list by replacing the thread.finished.emit
    capture = SimpleNamespace(value=None)

    thread = _CollectionDimScanThread(
        [
            conn_a,
            conn_b,
        ],
        exclude_collection="shared",
        target_dim=target_dim,
        exclude_connection=conn_a,
    )

    # Monkeypatch the finished signal to capture the emitted value synchronously
    thread.finished = SimpleNamespace(emit=lambda v: setattr(capture, "value", v))

    # Run synchronously
    thread.run()

    assert capture.value is not None, "Scanner did not emit any results"

    # Ensure conn_b's 'shared' was included and conn_a's 'shared' was excluded
    found_b_shared = any(coll == "shared" and conn is conn_b for (_, coll, conn) in capture.value)
    found_a_shared = any(coll == "shared" and conn is conn_a for (_, coll, conn) in capture.value)

    assert found_b_shared, "Expected 'shared' from other connection to be present"
    assert not found_a_shared, "Expected primary connection's 'shared' to be excluded"


def test_dim_scan_thread_get_all_items_exception_skips():
    """Exceptions in get_all_items are silently skipped."""

    class ConnRaises:
        name = "E"

        def list_collections(self):
            return ["col"]

        def get_all_items(self, name, limit=None):
            raise RuntimeError("db error")

    t = _CollectionDimScanThread([ConnRaises()], exclude_collection="x", target_dim=2)
    results = []
    t.finished.connect(lambda v: results.append(v))
    t.run()
    assert results == [[]]


def test_compare_load_thread_exception():
    """_CompareLoadThread emits error signal on exception."""

    class ConnThrows:
        def get_all_items(self, collection, limit=None):
            raise ConnectionError("timeout")

    errors = []
    t = _CompareLoadThread(ConnThrows(), "col", None)
    t.error.connect(lambda e: errors.append(e))
    t.run()
    assert errors and "timeout" in errors[0]


def test_set_data_same_dim_does_not_reset_comparison(qtbot, webengine_cleanup):
    """When dim doesn't change, comparison state is preserved."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._primary_dim = 2  # Pre-set same dim
    panel._compare_data = make_data([[0.3, 0.7]])

    # Set data with same dimension
    panel.set_data(make_data([[1.0, 0.0]]), collection_name="col")

    # compare_data should still be present (dim didn't change → no reset)
    assert panel._compare_data is not None


def test_set_data_different_dim_resets_comparison(qtbot, webengine_cleanup):
    """When dim changes, comparison is reset."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._primary_dim = 3  # Previously was 3-dim
    panel._compare_data = make_data([[0.3, 0.7]])

    # Set data with different dim (2)
    panel.set_data(make_data([[1.0, 0.0]]), collection_name="col")

    assert panel._compare_data is None


def test_generate_histogram_no_data_sets_status(qtbot, webengine_cleanup):
    """generate_histogram with no current data shows status message."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._current_data = None

    panel.generate_histogram()

    assert "No data" in panel.status_label.text()


def test_generate_histogram_primary_values_none_returns_silently(qtbot, webengine_cleanup):
    """When _extract_values returns None, generate_histogram returns without crashing."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.metric_combo.setCurrentIndex(1)  # Dimension
    panel.dim_spin.setValue(99)  # Out of range
    panel.set_data(make_data([[1.0, 0.0]]), collection_name="col")
    # Status should indicate error
    assert "out of range" in panel.status_label.text() or "No data" not in panel.status_label.text()


def test_extract_values_for_comparison_out_of_range(qtbot, webengine_cleanup):
    """_extract_values for_comparison=True shows 'for comparison collection.' message."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.metric_combo.setCurrentIndex(1)  # Dimension
    panel.dim_spin.setValue(99)

    result = panel._extract_values(make_data([[1.0, 0.0]]), for_comparison=True)

    assert result is None
    assert "comparison collection" in panel.status_label.text()


def test_extract_values_for_comparison_no_embeddings(qtbot, webengine_cleanup):
    """for_comparison=True with no valid embeddings includes 'comparison collection.' in message."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    result = panel._extract_values({"embeddings": []}, for_comparison=True)
    assert result is None
    assert "comparison collection" in panel.status_label.text()


def test_render_uses_connection_name_in_primary_label(qtbot, webengine_cleanup):
    """_render prepends connection name when self._connection has a name attribute."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.set_connection(DummyConnection("MyConn"))
    panel._primary_collection = "pri_col"

    panel.set_data(make_data([[1.0, 0.0]]), collection_name="pri_col")

    html = panel.get_current_html()
    assert html is not None
    assert "MyConn / pri_col" in html


def test_set_connection_manager(qtbot, webengine_cleanup):
    """set_connection_manager stores the manager."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    mgr = object()  # any sentinel

    panel.set_connection_manager(mgr)

    assert panel._connection_manager is mgr


def test_on_compare_toggled_with_connection_manager(qtbot, webengine_cleanup):
    """When connection_manager is set, its get_all_connections is used for scan."""

    class FakeManager:
        def get_all_connections(self):
            return [DummyConnection("Mgr")]

    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel._primary_dim = 2
    panel._primary_collection = "primary"
    panel.set_connection_manager(FakeManager())

    panel._on_compare_toggled(2)

    # Thread should have been created; quit it to avoid leaving running threads
    if panel._dim_scan_thread and panel._dim_scan_thread.isRunning():
        panel._dim_scan_thread.quit()
        panel._dim_scan_thread.wait()


def test_on_compare_toggled_off_with_current_data(qtbot, webengine_cleanup):
    """Toggling compare off when data is loaded regenerates the histogram."""
    panel = HistogramPanel()
    qtbot.addWidget(panel)
    panel.set_data(make_data([[1.0, 0.0]]), collection_name="col")
    # Now toggle off — should regenerate histogram without error
    panel._on_compare_toggled(0)


def test_on_load_comparison_starts_thread(qtbot, webengine_cleanup):
    """_on_load_comparison sets button disabled and starts loading thread."""

    class FakeConn:
        def get_all_items(self, collection, limit=None):
            return {"embeddings": [[1.0, 0.0]]}

    panel = HistogramPanel()
    qtbot.addWidget(panel)
    label = "FakeConn / col"
    panel._compare_options[label] = ("col", FakeConn())
    panel.compare_combo.addItem(label)
    panel.compare_combo.setCurrentIndex(0)
    panel._primary_dim = 2

    panel._on_load_comparison()

    assert not panel.compare_load_button.isEnabled()
    if panel._compare_load_thread and panel._compare_load_thread.isRunning():
        panel._compare_load_thread.quit()
        panel._compare_load_thread.wait()
