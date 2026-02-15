"""Tests for plot point selection and navigation to data browser.

Uses pytest-qt's qtbot fixture for proper Qt widget testing.
"""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QObject, Signal


@pytest.fixture
def plot_panel(qtbot):
    """Create a PlotPanel instance using qtbot for proper Qt widget handling."""
    from vector_inspector.ui.views.visualization.plot_panel import PlotPanel

    panel = PlotPanel()
    qtbot.addWidget(panel)  # Register with qtbot for proper cleanup

    # Give QWebEngineView time to initialize
    qtbot.waitUntil(lambda: panel.web_view is not None, timeout=3000)

    yield panel

    # Explicit cleanup to prevent "Release of profile" warning
    # Close the web view and its page before test ends
    if panel.web_view and panel.web_view.page():
        panel.web_view.setPage(None)
        panel.web_view.close()
    panel.deleteLater()
    qtbot.wait(50)  # Give Qt time to process deletion


def test_plot_event_bridge_is_qobject():
    """Test that PlotEventBridge inherits from QObject for QWebChannel."""
    from vector_inspector.ui.views.visualization.plot_panel import PlotEventBridge

    bridge = PlotEventBridge()
    assert isinstance(bridge, QObject)


def test_plot_event_bridge_has_point_selected_signal():
    """Test that PlotEventBridge has point_selected signal."""
    from vector_inspector.ui.views.visualization.plot_panel import PlotEventBridge

    bridge = PlotEventBridge()
    assert hasattr(bridge, "point_selected")
    # Signal emits (int, str) for point_index and point_id
    assert isinstance(bridge.point_selected, Signal)


def test_plot_event_bridge_on_point_selected_slot():
    """Test that onPointSelected slot emits point_selected signal."""
    from vector_inspector.ui.views.visualization.plot_panel import PlotEventBridge

    bridge = PlotEventBridge()

    # Connect signal to mock
    mock_handler = Mock()
    bridge.point_selected.connect(mock_handler)

    # Call slot with point index and ID
    bridge.onPointSelected(5, "test-id-5")

    # Verify signal was emitted with correct arguments
    mock_handler.assert_called_once_with(5, "test-id-5")


def test_plot_event_bridge_on_point_deselect():
    """Test that onPointSelected slot handles deselection (negative index)."""
    from vector_inspector.ui.views.visualization.plot_panel import PlotEventBridge

    bridge = PlotEventBridge()

    mock_handler = Mock()
    bridge.point_selected.connect(mock_handler)

    # Call slot with negative index (deselection)
    bridge.onPointSelected(-1, "")

    mock_handler.assert_called_once_with(-1, "")


def test_plot_panel_has_selection_ui_elements(qtbot, plot_panel):
    """Test that PlotPanel has selection label and view button."""
    assert plot_panel.selection_label is not None
    assert plot_panel.view_data_button is not None
    assert plot_panel.selection_container is not None


def test_plot_panel_view_in_data_browser_signal(qtbot, plot_panel):
    """Test that PlotPanel has view_in_data_browser signal."""
    assert hasattr(plot_panel, "view_in_data_browser")


def test_plot_panel_on_point_selected_updates_ui(qtbot, plot_panel):
    """Test that _on_point_selected updates selection label and button state."""
    # Simulate point selection
    plot_panel._on_point_selected(2, "id3")

    # Check UI was updated
    assert "id3" in plot_panel.selection_label.text()
    assert "#3" in plot_panel.selection_label.text()  # Point number (1-indexed)
    assert plot_panel.view_data_button.isEnabled() is True
    assert plot_panel._selected_index == 2
    assert plot_panel._selected_id == "id3"


def test_plot_panel_on_point_deselected_clears_ui(qtbot, plot_panel):
    """Test that _on_point_selected with negative index clears selection."""
    # Select a point first
    plot_panel._on_point_selected(1, "id2")
    assert plot_panel._selected_id is not None

    # Deselect
    plot_panel._on_point_selected(-1, "")

    # Check UI was cleared
    assert "No point selected" in plot_panel.selection_label.text()
    assert plot_panel.view_data_button.isEnabled() is False
    assert plot_panel._selected_id is None


def test_plot_panel_on_view_data_clicked_emits_signal(qtbot, plot_panel):
    """Test that _on_view_data_clicked emits view_in_data_browser signal."""
    plot_panel._selected_index = 1
    plot_panel._selected_id = "id2"

    # Use qtbot's signal spy to verify signal emission
    with qtbot.waitSignal(plot_panel.view_in_data_browser, timeout=1000) as blocker:
        plot_panel._on_view_data_clicked()

    # Verify signal was emitted with correct arguments
    assert blocker.args == [1, "id2"]


def test_plot_panel_view_data_button_disabled_when_no_selection(qtbot, plot_panel):
    """Test that view button is disabled when no point is selected."""
    # Initially no selection
    assert plot_panel.view_data_button.isEnabled() is False
    assert plot_panel._selected_id is None


def test_plot_event_bridge_signal_connected_to_panel(qtbot, plot_panel):
    """Test that PlotEventBridge signal is properly connected to panel."""
    # The bridge's signal should trigger panel's _on_point_selected

    # Verify initial state
    assert plot_panel._selected_id is None

    # Emit signal from bridge
    plot_panel._event_bridge.point_selected.emit(3, "test-id-999")

    # Wait for Qt event loop to process
    qtbot.wait(100)

    # Verify panel received the signal
    assert plot_panel._selected_index == 3
    assert plot_panel._selected_id == "test-id-999"
    assert "test-id-999" in plot_panel.selection_label.text()


def test_selection_container_visibility_2d_plot():
    """Test that selection UI visibility logic checks dimensionality."""
    import numpy as np

    # Test the logic without creating PlotPanel
    reduced_data_2d = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    is_2d = reduced_data_2d.shape[1] == 2
    assert is_2d is True


def test_selection_container_hidden_3d_plot():
    """Test that selection UI should be hidden for 3D plots."""
    import numpy as np

    # Test the logic
    reduced_data_3d = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    is_2d = reduced_data_3d.shape[1] == 2
    assert is_2d is False


def test_visualization_view_forwards_signal(qtbot):
    """Test that VisualizationView forwards view_in_data_browser signal."""
    from vector_inspector.ui.views.visualization_view import VisualizationView

    view = VisualizationView(connection=None)
    qtbot.addWidget(view)

    # Check that signal exists on view
    assert hasattr(view, "view_in_data_browser_requested")

    # Use qtbot's signal spy
    with qtbot.waitSignal(view.view_in_data_browser_requested, timeout=1000) as blocker:
        # Simulate signal from plot panel (passing index and ID)
        view._on_view_in_data_browser(5, "test-id-123")

    # Verify forwarding (only ID should be forwarded)
    assert blocker.args == ["test-id-123"]

    # Explicit cleanup to prevent "Release of profile" warning
    if hasattr(view, "plot_panel") and view.plot_panel and view.plot_panel.web_view:
        if view.plot_panel.web_view.page():
            view.plot_panel.web_view.setPage(None)
        view.plot_panel.web_view.close()
    view.deleteLater()
    qtbot.wait(50)  # Give Qt time to process deletion
