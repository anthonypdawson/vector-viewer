"""Tests for PlotPanel and PlotEventBridge."""

import pytest

from vector_inspector.ui.views.visualization.plot_panel import PlotEventBridge, PlotPanel


@pytest.fixture
def plot_panel(qtbot, webengine_cleanup):
    panel = PlotPanel()
    qtbot.addWidget(panel)
    yield panel
    panel.web_view.setPage(None)
    panel.web_view.close()
    panel.deleteLater()


def test_plot_event_bridge_emits_signal(qtbot):
    bridge = PlotEventBridge()
    received = []
    bridge.point_selected.connect(lambda idx, pid: received.append((idx, pid)))

    bridge.onPointSelected(3, "id3")

    assert received == [(3, "id3")]


def test_plot_panel_instantiates(plot_panel):
    panel = plot_panel
    assert panel.selection_label.text() == "No point selected"
    assert not panel.view_data_button.isEnabled()
    assert not panel.clear_selection_button.isEnabled()


def test_on_point_selected_positive_index(plot_panel):
    panel = plot_panel

    panel._on_point_selected(2, "id42")

    assert panel._selected_index == 2
    assert panel._selected_id == "id42"
    assert panel.view_data_button.isEnabled()
    assert panel.clear_selection_button.isEnabled()
    assert "id42" in panel.selection_label.text()


def test_on_point_selected_with_cluster_labels(plot_panel):
    """Cluster label info is appended to selection label when clusters are set."""
    import numpy as np

    panel = plot_panel

    panel._cluster_labels = np.array([0, 1, -1])

    panel._on_point_selected(2, "id2")  # cluster -1 → "Noise"

    assert "Noise" in panel.selection_label.text()

    panel._on_point_selected(0, "id0")  # cluster 0 → "0"
    assert "0" in panel.selection_label.text()


def test_on_point_selected_deselect(plot_panel):
    """Negative point index deselects."""
    panel = plot_panel

    panel._on_point_selected(1, "id1")
    panel._on_point_selected(-1, "")  # deselect

    assert panel._selected_index is None
    assert panel._selected_id is None
    assert not panel.view_data_button.isEnabled()
    assert "No point selected" in panel.selection_label.text()


def test_on_clear_selection_clicked(plot_panel):
    """Clear Selection button triggers deselection."""
    panel = plot_panel

    panel._on_point_selected(0, "id0")
    assert panel._selected_index == 0

    panel._on_clear_selection_clicked()

    assert panel._selected_index is None


def test_on_view_data_clicked_emits_signal(plot_panel):
    """View in Data Browser emits the view_in_data_browser signal."""
    panel = plot_panel

    received = []
    panel.view_in_data_browser.connect(lambda idx, pid: received.append((idx, pid)))

    panel._on_point_selected(5, "abc")
    panel._on_view_data_clicked()

    assert received == [(5, "abc")]


def test_on_view_data_clicked_no_selection(plot_panel):
    """view_in_data_browser not emitted when nothing is selected."""
    panel = plot_panel

    received = []
    panel.view_in_data_browser.connect(lambda idx, pid: received.append((idx, pid)))

    panel._on_view_data_clicked()

    assert received == []


def test_create_plot_none_data(plot_panel):
    """create_plot with None inputs returns early without error."""
    panel = plot_panel

    panel.create_plot(None, None, None, "PCA")

    assert panel._current_html is None


def test_create_plot_2d(plot_panel):
    """create_plot with 2D data renders HTML into the web view."""
    import numpy as np

    panel = plot_panel

    data = {"ids": ["id0", "id1"], "documents": ["doc0", "doc1"]}
    reduced = np.array([[0.1, 0.2], [0.3, 0.4]])

    panel.create_plot(reduced, data, None, "PCA")

    html = panel.get_current_html()
    assert html is not None
    assert "plotly" in html.lower() or "svg" in html.lower() or "<html>" in html.lower()


def test_create_plot_2d_with_clusters(plot_panel):
    """create_plot with cluster labels includes cluster info in hover text."""
    import numpy as np

    panel = plot_panel

    data = {"ids": ["a", "b"], "documents": ["doc a", "doc b"]}
    reduced = np.array([[0.0, 0.0], [1.0, 1.0]])
    labels = np.array([0, -1])

    panel.create_plot(reduced, data, labels, "UMAP")

    assert panel._cluster_labels is not None


def test_create_plot_3d(plot_panel):
    """create_plot with 3D data renders HTML and hides selection container."""
    import numpy as np

    panel = plot_panel

    data = {"ids": ["x"], "documents": ["d"]}
    reduced = np.array([[0.1, 0.2, 0.3]])

    panel.create_plot(reduced, data, None, "t-SNE")

    assert not panel.selection_container.isVisible()
    html = panel.get_current_html()
    assert html is not None


# ---------------------------------------------------------------------------
# PlotEventBridge.onInteraction slot
# ---------------------------------------------------------------------------


def test_bridge_on_interaction_emits_signal():
    """onInteraction slot forwards to the interaction signal."""
    bridge = PlotEventBridge()
    received = []
    bridge.interaction.connect(lambda action, count: received.append((action, count)))

    bridge.onInteraction("zoom", 3)

    assert received == [("zoom", 3)]


def test_bridge_on_interaction_coerces_count():
    """onInteraction wraps count in int() and re-emits."""
    bridge = PlotEventBridge()
    received = []
    bridge.interaction.connect(lambda _action, c: received.append(c))
    bridge.onInteraction("pan", 0)
    assert received == [0]


# ---------------------------------------------------------------------------
# PlotPanel._on_interaction — telemetry emission
# ---------------------------------------------------------------------------


def test_on_interaction_calls_telemetry(plot_panel, monkeypatch):
    """_on_interaction sends a telemetry event via TelemetryService.send_event."""
    import vector_inspector.ui.views.visualization.plot_panel as pp_mod

    events = []
    monkeypatch.setattr(
        pp_mod.TelemetryService, "send_event", staticmethod(lambda name, payload: events.append((name, payload)))
    )

    plot_panel._on_interaction("zoom", 2)

    assert events, "Expected at least one telemetry send_event call"
    name, payload = events[0]
    assert name == "ui.visualization_interacted"
    assert payload["metadata"]["action"] == "zoom"
    assert payload["metadata"]["selected_count"] == 2


def test_on_interaction_tolerates_exception(plot_panel, monkeypatch):
    """_on_interaction must not raise even if telemetry fails."""
    import vector_inspector.ui.views.visualization.plot_panel as pp_mod

    def boom(*_a, **_kw):
        raise RuntimeError("telemetry down")

    monkeypatch.setattr(pp_mod.TelemetryService, "send_event", staticmethod(boom))

    # Should not raise
    plot_panel._on_interaction("pan", 0)


# ---------------------------------------------------------------------------
# dispose()
# ---------------------------------------------------------------------------


def test_dispose_clears_references(qtbot):
    """dispose() nulls out web_view, channel, and _event_bridge."""
    panel = PlotPanel()
    qtbot.addWidget(panel)
    panel.dispose()
    assert panel.web_view is None
    assert panel.channel is None
    assert panel._event_bridge is None


def test_dispose_is_idempotent(qtbot):
    """Calling dispose() twice must not raise."""
    panel = PlotPanel()
    qtbot.addWidget(panel)
    panel.dispose()
    panel.dispose()  # second call must be safe
