"""Tests for ClusteringPanel covering uncovered branches."""

from __future__ import annotations

import pytest

from vector_inspector.ui.views.visualization.clustering_panel import ClusteringPanel


@pytest.fixture
def panel(qtbot):
    """A ClusteringPanel without app_state (default/free mode)."""
    p = ClusteringPanel()
    qtbot.addWidget(p)
    return p


@pytest.fixture
def panel_advanced(qtbot, app_state_with_fake_provider):
    """A ClusteringPanel with advanced features enabled."""
    app_state = app_state_with_fake_provider
    # Force advanced features on for testing the advanced params branches
    app_state._advanced_features_enabled = True
    p = ClusteringPanel(app_state=app_state)
    qtbot.addWidget(p)
    return p


# ---------------------------------------------------------------------------
# _toggle_advanced
# ---------------------------------------------------------------------------


def test_toggle_advanced_shows_then_hides(qtbot, panel):
    """Clicking advanced toggle twice hides and re-shows the advanced widget."""
    # Show panel so isVisible() works correctly
    panel.show()
    qtbot.waitExposed(panel)

    # Initially hidden (as set up in __init__ + _setup_ui)
    assert panel.advanced_widget.isHidden()

    # First toggle → should show
    panel._toggle_advanced()
    assert not panel.advanced_widget.isHidden()
    assert "▼" in panel.advanced_toggle.text()

    # Second toggle → should hide
    panel._toggle_advanced()
    assert panel.advanced_widget.isHidden()
    assert "▶" in panel.advanced_toggle.text()


# ---------------------------------------------------------------------------
# _on_algorithm_changed with advanced widget visible
# ---------------------------------------------------------------------------


def test_on_algorithm_changed_updates_advanced_controls_when_visible(qtbot, panel):
    """When advanced widget is visible, _on_algorithm_changed also hides/shows advanced controls."""
    panel.show()
    qtbot.waitExposed(panel)

    panel._toggle_advanced()  # show advanced section
    assert not panel.advanced_widget.isHidden()

    # Switch to KMeans
    panel._on_algorithm_changed("KMeans")

    # HDBSCAN controls should be hidden in advanced section
    # KMeans advanced controls should be visible
    # Just assert no exception and cluster_result_label is cleared
    assert panel.cluster_result_label.isHidden()


def test_on_algorithm_changed_clears_result_label(panel):
    """Changing algorithm clears the cluster result label."""
    panel.cluster_result_label.setText("old result")
    panel.cluster_result_label.setVisible(True)

    panel._on_algorithm_changed("DBSCAN")

    assert panel.cluster_result_label.isHidden()
    assert panel.cluster_result_label.text() == ""


# ---------------------------------------------------------------------------
# get_clustering_params — KMeans and DBSCAN and OPTICS basic branches
# ---------------------------------------------------------------------------


def test_get_clustering_params_kmeans_basic(panel):
    """KMeans params without advanced features."""
    panel.cluster_algorithm_combo.setCurrentText("KMeans")
    params = panel.get_clustering_params()

    assert "n_clusters" in params
    assert isinstance(params["n_clusters"], int)
    # advanced params not included in free mode
    assert "init" not in params
    assert "max_iter" not in params


def test_get_clustering_params_dbscan_basic(panel):
    """DBSCAN params without advanced features."""
    panel.cluster_algorithm_combo.setCurrentText("DBSCAN")
    params = panel.get_clustering_params()

    assert "eps" in params
    assert "min_samples" in params
    assert "metric" not in params


def test_get_clustering_params_optics_basic(panel):
    """OPTICS params without advanced features."""
    panel.cluster_algorithm_combo.setCurrentText("OPTICS")
    params = panel.get_clustering_params()

    assert "min_samples" in params
    assert "max_eps" in params
    assert "xi" not in params


def test_get_clustering_params_hdbscan_basic(panel):
    """HDBSCAN params without advanced features."""
    panel.cluster_algorithm_combo.setCurrentText("HDBSCAN")
    params = panel.get_clustering_params()

    assert "min_cluster_size" in params
    assert "min_samples" in params
    assert "cluster_selection_epsilon" not in params


# ---------------------------------------------------------------------------
# get_clustering_params with advanced features enabled
# ---------------------------------------------------------------------------


def test_get_clustering_params_hdbscan_advanced(qtbot, app_state_with_fake_provider):
    """HDBSCAN params include advanced params when advanced_features_enabled."""
    app_state = app_state_with_fake_provider

    # Override advanced_features_enabled to return True
    class AdvancedAppState:
        """Minimal app_state stub with advanced features on."""

        advanced_features_enabled = True

    p = ClusteringPanel(app_state=AdvancedAppState())
    qtbot.addWidget(p)

    p.cluster_algorithm_combo.setCurrentText("HDBSCAN")
    params = p.get_clustering_params()

    assert "cluster_selection_epsilon" in params
    assert "allow_single_cluster" in params
    assert "metric" in params
    assert "alpha" in params
    assert "cluster_selection_method" in params


def test_get_clustering_params_kmeans_advanced(qtbot):
    """KMeans params include advanced params when advanced_features_enabled."""

    class AdvancedAppState:
        advanced_features_enabled = True

    p = ClusteringPanel(app_state=AdvancedAppState())
    qtbot.addWidget(p)

    p.cluster_algorithm_combo.setCurrentText("KMeans")
    params = p.get_clustering_params()

    assert "init" in params
    assert "max_iter" in params
    assert "tol" in params
    assert "algorithm" in params


def test_get_clustering_params_dbscan_advanced(qtbot):
    """DBSCAN params include advanced params when advanced_features_enabled."""

    class AdvancedAppState:
        advanced_features_enabled = True

    p = ClusteringPanel(app_state=AdvancedAppState())
    qtbot.addWidget(p)

    p.cluster_algorithm_combo.setCurrentText("DBSCAN")
    params = p.get_clustering_params()

    assert "metric" in params
    assert "algorithm" in params
    assert "leaf_size" in params


def test_get_clustering_params_optics_advanced(qtbot):
    """OPTICS params include advanced params when advanced_features_enabled."""

    class AdvancedAppState:
        advanced_features_enabled = True

    p = ClusteringPanel(app_state=AdvancedAppState())
    qtbot.addWidget(p)

    p.cluster_algorithm_combo.setCurrentText("OPTICS")
    params = p.get_clustering_params()

    assert "metric" in params
    assert "xi" in params
    assert "cluster_method" in params
    assert "algorithm" in params
    assert "leaf_size" in params
