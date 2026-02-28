"""Tests for VisualizationView and its thread classes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from vector_inspector.ui.views.visualization_view import (
    ClusteringThread,
    VisualizationDataLoadThread,
    VisualizationThread,
    VisualizationView,
)

# ---------------------------------------------------------------------------
# VisualizationThread tests
# ---------------------------------------------------------------------------


def test_visualization_thread_emits_finished_on_success(qtbot):
    embeddings = np.array([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])
    thread = VisualizationThread(embeddings, "pca", 2)

    result_holder = []
    thread.finished.connect(lambda r: result_holder.append(r))

    with patch(
        "vector_inspector.ui.views.visualization_view.VisualizationService.reduce_dimensions",
        return_value=np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]),
    ):
        qtbot.waitSignal(thread.finished, timeout=5000, raising=True)
        thread.run()

    assert len(result_holder) == 1
    assert result_holder[0].shape == (3, 2)


def test_visualization_thread_emits_error_when_result_is_none(qtbot):
    embeddings = np.array([[1.0, 0.0], [0.0, 1.0]])
    thread = VisualizationThread(embeddings, "pca", 2)

    errors = []
    thread.error.connect(lambda e: errors.append(e))

    with patch(
        "vector_inspector.ui.views.visualization_view.VisualizationService.reduce_dimensions",
        return_value=None,
    ):
        thread.run()

    assert errors == ["Dimensionality reduction failed"]


def test_visualization_thread_emits_error_on_exception(qtbot):
    embeddings = np.array([[1.0, 0.0], [0.0, 1.0]])
    thread = VisualizationThread(embeddings, "pca", 2)

    errors = []
    thread.error.connect(lambda e: errors.append(e))

    with patch(
        "vector_inspector.ui.views.visualization_view.VisualizationService.reduce_dimensions",
        side_effect=RuntimeError("boom"),
    ):
        thread.run()

    assert len(errors) == 1
    assert "boom" in errors[0]


# ---------------------------------------------------------------------------
# ClusteringThread tests
# ---------------------------------------------------------------------------


def test_clustering_thread_emits_finished(qtbot):
    embeddings = np.array([[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]])
    thread = ClusteringThread(embeddings, "KMeans", {"n_clusters": 2})

    results = []
    thread.finished.connect(lambda r: results.append(r))

    fake_labels = np.array([0, 1, 0])
    with patch(
        "vector_inspector.core.clustering.run_clustering",
        return_value=(fake_labels, "KMeans"),
    ):
        thread.run()

    assert len(results) == 1
    labels, algo = results[0]
    assert algo == "KMeans"
    assert list(labels) == [0, 1, 0]


def test_clustering_thread_emits_error_on_exception(qtbot):
    embeddings = np.array([[1.0, 0.0]])
    thread = ClusteringThread(embeddings, "DBSCAN", {})

    errors = []
    thread.error.connect(lambda e: errors.append(e))

    with patch(
        "vector_inspector.core.clustering.run_clustering",
        side_effect=ValueError("bad params"),
    ):
        thread.run()

    assert len(errors) == 1
    assert "bad params" in errors[0]


# ---------------------------------------------------------------------------
# VisualizationDataLoadThread tests
# ---------------------------------------------------------------------------


def test_data_load_thread_emits_finished(qtbot):
    mock_connection = MagicMock()
    mock_connection.get_all_items.return_value = {"ids": ["a"], "embeddings": [[1.0, 0.0]]}

    thread = VisualizationDataLoadThread(mock_connection, "col1", sample_size=None)

    results = []
    thread.finished.connect(lambda d: results.append(d))

    thread.run()

    assert len(results) == 1
    assert results[0]["ids"] == ["a"]
    mock_connection.get_all_items.assert_called_once_with("col1")


def test_data_load_thread_uses_limit_when_sample_size_is_set():
    mock_connection = MagicMock()
    mock_connection.get_all_items.return_value = {"ids": ["a"], "embeddings": [[1.0, 0.0]]}

    thread = VisualizationDataLoadThread(mock_connection, "col1", sample_size=100)

    results = []
    thread.finished.connect(lambda d: results.append(d))

    thread.run()

    mock_connection.get_all_items.assert_called_once_with("col1", limit=100)


def test_data_load_thread_emits_error_when_no_connection():
    thread = VisualizationDataLoadThread(None, "col1", sample_size=None)

    errors = []
    thread.error.connect(lambda e: errors.append(e))

    thread.run()

    assert errors == ["No database connection available"]


def test_data_load_thread_emits_error_when_data_is_empty():
    mock_connection = MagicMock()
    mock_connection.get_all_items.return_value = {}

    thread = VisualizationDataLoadThread(mock_connection, "col1", sample_size=None)

    errors = []
    thread.error.connect(lambda e: errors.append(e))

    thread.run()

    assert errors == ["Failed to load data"]


def test_data_load_thread_emits_error_on_exception():
    mock_connection = MagicMock()
    mock_connection.get_all_items.side_effect = ConnectionError("no connection")

    thread = VisualizationDataLoadThread(mock_connection, "col1", sample_size=None)

    errors = []
    thread.error.connect(lambda e: errors.append(e))

    thread.run()

    assert len(errors) == 1
    assert "no connection" in errors[0]


# ---------------------------------------------------------------------------
# VisualizationView instantiation and basic methods
# ---------------------------------------------------------------------------


@pytest.fixture
def viz_view(qtbot, app_state_with_fake_provider, task_runner):
    """A VisualizationView with a fake provider."""
    view = VisualizationView(app_state_with_fake_provider, task_runner)
    qtbot.addWidget(view)
    return view


def test_visualization_view_instantiates(viz_view):
    """VisualizationView can be constructed."""
    assert viz_view.current_collection == ""
    assert viz_view.current_data is None
    assert viz_view.reduced_data is None
    assert viz_view.cluster_labels is None


def test_visualization_view_status_label_initial(viz_view):
    assert viz_view.status_label.text() == "No collection selected"


def test_set_collection_updates_state(viz_view):
    viz_view.set_collection("my_col")

    assert viz_view.current_collection == "my_col"
    assert viz_view.current_data is None
    assert viz_view.reduced_data is None
    assert viz_view.cluster_labels is None
    assert "my_col" in viz_view.status_label.text()


def test_set_collection_clears_old_cluster_results(qtbot, viz_view):
    """set_collection resets clustering panel label if present."""
    viz_view.clustering_panel.cluster_result_label.setVisible(True)
    viz_view.clustering_panel.cluster_result_label.setText("Old result")

    viz_view.set_collection("new_col")

    assert viz_view.clustering_panel.cluster_result_label.isHidden()


def test_on_collection_changed_calls_set_collection(viz_view):
    viz_view._on_collection_changed("col_abc")

    assert viz_view.current_collection == "col_abc"


def test_on_collection_changed_empty_does_nothing(viz_view):
    viz_view.current_collection = "original"
    viz_view._on_collection_changed("")

    assert viz_view.current_collection == "original"


def test_on_provider_changed_updates_connection(viz_view):
    new_conn = MagicMock()
    viz_view._on_provider_changed(new_conn)

    assert viz_view.connection is new_conn


def test_on_loading_started_shows_dialog(viz_view):
    """_on_loading_started calls show_loading on the dialog."""
    viz_view.loading_dialog = MagicMock()
    viz_view._on_loading_started("Working...")
    viz_view.loading_dialog.show_loading.assert_called_once_with("Working...")


def test_on_loading_finished_hides_dialog(viz_view):
    viz_view.loading_dialog = MagicMock()
    viz_view._on_loading_finished()
    viz_view.loading_dialog.hide.assert_called_once()


# ---------------------------------------------------------------------------
# _generate_visualization edge cases
# ---------------------------------------------------------------------------


def test_generate_visualization_no_collection_shows_warning(qtbot, viz_view, monkeypatch):
    """Without a collection selected, a warning box is shown and no thread started."""
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    viz_view.current_collection = ""
    viz_view._generate_visualization()

    assert warned, "Expected QMessageBox.warning to be called"
    assert viz_view.data_load_thread is None


def test_generate_visualization_starts_thread_when_collection_set(qtbot, viz_view, monkeypatch):
    """With a collection set, a data load thread should be started."""
    started = []

    class FakeThread:
        def isRunning(self):
            return False

        def finished(self, *a):
            pass

        finished = MagicMock()
        error = MagicMock()

        def connect(self, fn):
            pass

        def start(self):
            started.append(True)

    fake_thread_instance = FakeThread()

    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.VisualizationDataLoadThread",
        lambda *a, **kw: fake_thread_instance,
    )

    viz_view.current_collection = "test_collection"
    viz_view._generate_visualization()

    assert started, "Expected the data load thread to be started"


# ---------------------------------------------------------------------------
# _on_data_loaded edge cases
# ---------------------------------------------------------------------------


def test_on_data_loaded_warns_when_no_embeddings(qtbot, viz_view, monkeypatch):
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view._on_data_loaded({"ids": ["a"], "embeddings": None})

    assert warned


def test_on_data_loaded_warns_when_empty_data(qtbot, viz_view, monkeypatch):
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view._on_data_loaded({})

    assert warned


def test_on_data_loaded_starts_visualization_thread(qtbot, viz_view, monkeypatch):
    """Valid data triggers a VisualizationThread."""
    started = []

    class FakeVizThread:
        finished = MagicMock()
        error = MagicMock()

        def start(self):
            started.append(True)

    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.VisualizationThread",
        lambda *a, **kw: FakeVizThread(),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view.current_collection = "col"

    data = {"ids": ["a", "b"], "embeddings": [[1.0, 0.0], [0.0, 1.0]], "metadatas": [{}, {}]}
    viz_view._on_data_loaded(data)

    assert started
    assert viz_view.current_data is data


# ---------------------------------------------------------------------------
# _on_data_load_error
# ---------------------------------------------------------------------------


def test_on_data_load_error_shows_warning(qtbot, viz_view, monkeypatch):
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view._on_data_load_error("timeout")

    assert warned


# ---------------------------------------------------------------------------
# _on_reduction_finished / _on_reduction_error
# ---------------------------------------------------------------------------


def test_on_reduction_finished_updates_reduced_data(qtbot, viz_view, monkeypatch):
    monkeypatch.setattr(viz_view.plot_panel, "create_plot", lambda **kw: None)
    monkeypatch.setattr(viz_view.plot_panel, "get_current_html", lambda: None)
    viz_view.loading_dialog = MagicMock()
    viz_view.current_data = {"ids": ["a"], "embeddings": [[1.0, 0.0]]}

    reduced = np.array([[0.1, 0.2], [0.3, 0.4]])
    viz_view._on_reduction_finished(reduced)

    assert viz_view.reduced_data is reduced
    assert viz_view.status_label.text() == "Visualization complete"
    assert viz_view.dr_panel.generate_button.isEnabled()
    assert viz_view.dr_panel.open_browser_button.isEnabled()


def test_on_reduction_error_shows_warning(qtbot, viz_view, monkeypatch):
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view._on_reduction_error("failed to converge")

    assert warned
    assert "failed" in viz_view.status_label.text().lower()
    assert viz_view.dr_panel.generate_button.isEnabled()


# ---------------------------------------------------------------------------
# _on_clustering_error
# ---------------------------------------------------------------------------


def test_on_clustering_error_shows_warning(qtbot, viz_view, monkeypatch):
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view._on_clustering_error("memory error")

    assert warned
    assert viz_view.clustering_panel.cluster_button.isEnabled()


# ---------------------------------------------------------------------------
# _on_clustering_finished
# ---------------------------------------------------------------------------


def test_on_clustering_finished_updates_labels(qtbot, viz_view, monkeypatch):
    """_on_clustering_finished sets cluster_labels and updates panel label."""
    viz_view.loading_dialog = MagicMock()
    labels = np.array([0, 1, 0, 1])
    viz_view._on_clustering_finished((labels, "KMeans"))

    assert list(viz_view.cluster_labels) == [0, 1, 0, 1]
    assert not viz_view.clustering_panel.cluster_result_label.isHidden()
    assert "2" in viz_view.clustering_panel.cluster_result_label.text()


def test_on_clustering_finished_density_algo_counts_noise(qtbot, viz_view, monkeypatch):
    """HDBSCAN/-1 labels are counted as noise, not clusters."""
    viz_view.loading_dialog = MagicMock()
    labels = np.array([0, 1, -1, -1])
    viz_view._on_clustering_finished((labels, "HDBSCAN"))

    text = viz_view.clustering_panel.cluster_result_label.text()
    assert "2" in text  # 2 noise
    assert "noise" in text.lower()


def test_on_clustering_finished_with_reduced_data_recreates_plot(qtbot, viz_view, monkeypatch):
    """When reduced_data is available, plot is recreated after clustering."""
    viz_view.loading_dialog = MagicMock()
    viz_view.reduced_data = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8]])
    viz_view.current_data = {"ids": ["a", "b", "c", "d"], "embeddings": [[1, 0]] * 4}

    created = []
    monkeypatch.setattr(viz_view.plot_panel, "create_plot", lambda **kw: created.append(True))
    monkeypatch.setattr(viz_view.plot_panel, "get_current_html", lambda: None)

    labels = np.array([0, 1, 0, 1])
    viz_view._on_clustering_finished((labels, "KMeans"))

    assert created


# ---------------------------------------------------------------------------
# view_in_data_browser signal
# ---------------------------------------------------------------------------


def test_on_view_in_data_browser_emits_signal(qtbot, viz_view):
    emitted = []
    viz_view.view_in_data_browser_requested.connect(lambda pid: emitted.append(pid))

    viz_view._on_view_in_data_browser(0, "item_xyz")

    assert emitted == ["item_xyz"]


def test_on_view_in_data_browser_ignores_empty_id(qtbot, viz_view):
    emitted = []
    viz_view.view_in_data_browser_requested.connect(lambda pid: emitted.append(pid))

    viz_view._on_view_in_data_browser(0, "")

    assert not emitted


# ---------------------------------------------------------------------------
# cleanup_temp_html
# ---------------------------------------------------------------------------


def test_cleanup_temp_html_removes_files(viz_view, tmp_path):
    import os

    f = tmp_path / "test.html"
    f.write_text("<html/>")
    viz_view.temp_html_files = [str(f)]

    viz_view.cleanup_temp_html()

    assert not os.path.exists(str(f))
    assert viz_view.temp_html_files == []


def test_cleanup_temp_html_tolerates_missing_files(viz_view):
    viz_view.temp_html_files = ["/nonexistent/path/file123.html"]
    # Should not raise
    viz_view.cleanup_temp_html()
    assert viz_view.temp_html_files == []


# ---------------------------------------------------------------------------
# _on_error
# ---------------------------------------------------------------------------


def test_on_error_shows_critical_dialog(qtbot, viz_view, monkeypatch):
    """_on_error pops a critical QMessageBox."""
    crits = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.critical",
        lambda *a, **kw: crits.append(True),
    )
    viz_view._on_error("Test Error", "Something went wrong")
    assert crits


# ---------------------------------------------------------------------------
# on_use_all_changed inner function
# ---------------------------------------------------------------------------


def test_use_all_checkbox_disables_sample_spin(qtbot, viz_view):
    """Checking use_all disables sample_spin; unchecking re-enables it."""
    viz_view.use_all_checkbox.setEnabled(True)  # Enable for test
    viz_view.use_all_checkbox.setChecked(True)
    assert not viz_view.sample_spin.isEnabled()
    viz_view.use_all_checkbox.setChecked(False)
    assert viz_view.sample_spin.isEnabled()


# ---------------------------------------------------------------------------
# _generate_visualization – use_all path and cancel-running-thread
# ---------------------------------------------------------------------------


def test_generate_visualization_uses_all_data_when_checked(qtbot, viz_view, monkeypatch):
    """use_all_checkbox checked → sample_size=None passed to data load thread."""
    captured_sample_sizes = []

    class FakeLoadThread:
        finished = MagicMock()
        error = MagicMock()

        def __init__(self, conn, coll, sample_size, parent=None):
            captured_sample_sizes.append(sample_size)

        def isRunning(self):
            return False

        def start(self):
            pass

    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.VisualizationDataLoadThread",
        FakeLoadThread,
    )
    viz_view.loading_dialog = MagicMock()
    viz_view.current_collection = "test_collection"
    viz_view.use_all_checkbox.setEnabled(True)
    viz_view.use_all_checkbox.setChecked(True)
    viz_view._generate_visualization()

    assert captured_sample_sizes and captured_sample_sizes[0] is None


def test_generate_visualization_cancels_running_thread(qtbot, viz_view, monkeypatch):
    """When a data load thread is already running, quit/wait are called before starting new one."""
    quit_called = []
    wait_called = []

    class RunningThread:
        def isRunning(self):
            return True

        def quit(self):
            quit_called.append(True)

        def wait(self):
            wait_called.append(True)

        finished = MagicMock()
        error = MagicMock()

        def start(self):
            pass

    class FakeNewThread:
        finished = MagicMock()
        error = MagicMock()

        def isRunning(self):
            return False

        def start(self):
            pass

    viz_view.data_load_thread = RunningThread()
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.VisualizationDataLoadThread",
        lambda *a, **kw: FakeNewThread(),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view.current_collection = "test_col"
    viz_view._generate_visualization()

    assert quit_called
    assert wait_called


# ---------------------------------------------------------------------------
# _on_data_loaded – t-SNE method conversion
# ---------------------------------------------------------------------------


def test_on_data_loaded_tsne_method_handled(qtbot, viz_view, monkeypatch):
    """t-SNE method combo value is normalized to 'tsne' before thread creation."""
    thread_methods = []

    class FakeVizThread:
        finished = MagicMock()
        error = MagicMock()

        def __init__(self, embeddings, method, n_components):
            thread_methods.append(method)

        def start(self):
            pass

    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.VisualizationThread",
        FakeVizThread,
    )
    viz_view.loading_dialog = MagicMock()
    viz_view.current_collection = "col"

    # Find and select the t-SNE option in the combo if present, else just set text
    combo = viz_view.dr_panel.method_combo
    tsne_index = None
    for i in range(combo.count()):
        if "t-sne" in combo.itemText(i).lower():
            tsne_index = i
            break
    if tsne_index is not None:
        combo.setCurrentIndex(tsne_index)
        data = {"ids": ["a", "b"], "embeddings": [[1.0, 0.0], [0.0, 1.0]], "metadatas": [{}, {}]}
        viz_view._on_data_loaded(data)
        assert "tsne" in thread_methods


# ---------------------------------------------------------------------------
# _save_temp_html
# ---------------------------------------------------------------------------


def test_save_temp_html_writes_file_when_html_available(viz_view, monkeypatch):
    """_save_temp_html writes HTML content to a temp file."""
    import os

    html_content = "<html><body>test chart</body></html>"
    monkeypatch.setattr(viz_view.plot_panel, "get_current_html", lambda: html_content)

    viz_view._save_temp_html()

    assert viz_view._last_temp_html is not None
    assert os.path.exists(viz_view._last_temp_html)
    with open(viz_view._last_temp_html, encoding="utf-8") as f:
        assert "test chart" in f.read()
    # Cleanup
    os.unlink(viz_view._last_temp_html)


# ---------------------------------------------------------------------------
# _open_in_browser
# ---------------------------------------------------------------------------


def test_open_in_browser_calls_webbrowser_open(viz_view, monkeypatch):
    """_open_in_browser calls webbrowser.open with file URL."""
    opened_urls = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.webbrowser.open",
        lambda url: opened_urls.append(url),
    )
    viz_view._last_temp_html = "/some/path/test.html"
    viz_view._open_in_browser()
    assert opened_urls


def test_open_in_browser_does_nothing_without_html(viz_view, monkeypatch):
    """_open_in_browser is a no-op when no temp html exists."""
    opened_urls = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.webbrowser.open",
        lambda url: opened_urls.append(url),
    )
    viz_view._last_temp_html = None
    viz_view._open_in_browser()
    assert not opened_urls


# ---------------------------------------------------------------------------
# _run_clustering
# ---------------------------------------------------------------------------


def test_run_clustering_no_collection_warns(qtbot, viz_view, monkeypatch):
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    viz_view.current_collection = ""
    viz_view._run_clustering()
    assert warned


def test_run_clustering_with_existing_data_starts_clustering_thread(qtbot, viz_view, monkeypatch):
    """When current_data is already loaded, _run_clustering starts a ClusteringThread."""
    started = []

    class FakeClusterThread:
        finished = MagicMock()
        error = MagicMock()

        def start(self):
            started.append(True)

    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.ClusteringThread",
        lambda *a, **kw: FakeClusterThread(),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view.current_collection = "test_col"
    viz_view.current_data = {"embeddings": [[1, 0], [0, 1]], "ids": ["a", "b"]}
    viz_view._run_clustering()

    assert started


def test_run_clustering_without_data_creates_load_thread(qtbot, viz_view, monkeypatch):
    """When current_data is None, _run_clustering creates a data load thread."""
    started = []

    class FakeLoadThread:
        finished = MagicMock()
        error = MagicMock()

        def isRunning(self):
            return False

        def start(self):
            started.append(True)

    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.VisualizationDataLoadThread",
        lambda *a, **kw: FakeLoadThread(),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view.current_collection = "test_col"
    viz_view.current_data = None
    viz_view._run_clustering()

    assert started


# ---------------------------------------------------------------------------
# _on_clustering_data_loaded
# ---------------------------------------------------------------------------


def test_on_clustering_data_loaded_valid_data_starts_clustering(qtbot, viz_view, monkeypatch):
    started = []

    class FakeClusterThread:
        finished = MagicMock()
        error = MagicMock()

        def start(self):
            started.append(True)

    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.ClusteringThread",
        lambda *a, **kw: FakeClusterThread(),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view.current_collection = "test_col"

    data = {"ids": ["a", "b"], "embeddings": [[1.0, 0.0], [0.0, 1.0]], "metadatas": [{}, {}]}
    viz_view._on_clustering_data_loaded(data)

    assert viz_view.current_data is data
    assert started


def test_on_clustering_data_loaded_no_embeddings_shows_warning(qtbot, viz_view, monkeypatch):
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    viz_view.loading_dialog = MagicMock()
    viz_view._on_clustering_data_loaded({"ids": ["a"], "embeddings": None})
    assert warned


# ---------------------------------------------------------------------------
# _on_clustering_finished + save-to-metadata checkbox
# ---------------------------------------------------------------------------


def test_on_clustering_finished_saves_labels_when_checkbox_checked(qtbot, viz_view, monkeypatch):
    """When save_to_metadata is checked, _save_cluster_labels_to_metadata is called."""
    saved = []
    monkeypatch.setattr(viz_view, "_save_cluster_labels_to_metadata", lambda: saved.append(True))
    viz_view.loading_dialog = MagicMock()
    viz_view.clustering_panel.save_to_metadata_checkbox.setChecked(True)

    labels = np.array([0, 1])
    viz_view._on_clustering_finished((labels, "KMeans"))

    assert saved


# ---------------------------------------------------------------------------
# _save_cluster_labels_to_metadata
# ---------------------------------------------------------------------------


def test_save_cluster_labels_to_metadata_success(qtbot, viz_view):
    """_save_cluster_labels_to_metadata updates metadata via connection.update_items."""
    mock_conn = MagicMock()
    mock_conn.update_items.return_value = True
    viz_view.connection = mock_conn
    viz_view.current_collection = "test_col"
    viz_view.current_data = {"ids": ["a", "b"], "metadatas": [{}, {}], "embeddings": [[1, 0], [0, 1]]}
    viz_view.cluster_labels = np.array([0, 1])

    viz_view._save_cluster_labels_to_metadata()

    mock_conn.update_items.assert_called_once()


def test_save_cluster_labels_to_metadata_update_fails_warns(qtbot, viz_view, monkeypatch):
    """When update_items returns False, a warning is shown."""
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    mock_conn = MagicMock()
    mock_conn.update_items.return_value = False
    viz_view.connection = mock_conn
    viz_view.current_collection = "test_col"
    viz_view.current_data = {"ids": ["a", "b"], "metadatas": [{}, {}]}
    viz_view.cluster_labels = np.array([0, 1])

    viz_view._save_cluster_labels_to_metadata()

    assert warned


def test_save_cluster_labels_exception_shows_warning(qtbot, viz_view, monkeypatch):
    """Exception in _save_cluster_labels_to_metadata shows a warning."""
    warned = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.visualization_view.QMessageBox.warning",
        lambda *a, **kw: warned.append(True),
    )
    mock_conn = MagicMock()
    mock_conn.update_items.side_effect = RuntimeError("db error")
    viz_view.connection = mock_conn
    viz_view.current_collection = "test_col"
    viz_view.current_data = {"ids": ["a", "b"], "metadatas": [{}, {}]}
    viz_view.cluster_labels = np.array([0, 1])

    viz_view._save_cluster_labels_to_metadata()

    assert warned


# ---------------------------------------------------------------------------
# set_collection exception path
# ---------------------------------------------------------------------------


def test_set_collection_exception_in_try_block_is_swallowed(qtbot, viz_view):
    """Exception when clearing clustering panel label is silently ignored."""
    bad_label = MagicMock()
    bad_label.setVisible.side_effect = RuntimeError("widget error")
    viz_view.clustering_panel.cluster_result_label = bad_label

    viz_view.set_collection("some_col")  # Should not raise

    assert viz_view.current_collection == "some_col"
