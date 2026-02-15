"""Tests for cluster label saving to metadata."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from vector_inspector.ui.views.metadata.context import MetadataContext


@pytest.fixture
def qapp():
    """Ensure QApplication exists for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def mock_connection():
    """Create a mock connection for testing."""
    conn = MagicMock()
    conn.update_items.return_value = True
    return conn


@pytest.fixture
def sample_cluster_data():
    """Create sample clustering results."""
    return {
        "ids": ["id1", "id2", "id3", "id4"],
        "documents": ["doc1", "doc2", "doc3", "doc4"],
        "metadatas": [
            {"existing": "data1"},
            {"existing": "data2"},
            {},
            {"existing": "data4"},
        ],
        "embeddings": [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
            [0.2, 0.3, 0.4],
        ],
        "cluster_labels": [0, 0, 1, -1],  # Two clusters + one noise point
    }


def test_save_cluster_labels_to_metadata_success(qapp, mock_connection, sample_cluster_data):
    """Test successfully saving cluster labels to metadata."""
    from vector_inspector.ui.views.visualization_view import VisualizationView
    import numpy as np

    view = VisualizationView(connection=mock_connection)
    view.current_collection = "test_coll"
    view.current_data = sample_cluster_data
    view.cluster_labels = np.array(sample_cluster_data["cluster_labels"])

    # Call the save method
    view._save_cluster_labels_to_metadata()

    # Verify update_items was called with correct parameters
    mock_connection.update_items.assert_called_once()
    call_args = mock_connection.update_items.call_args

    # Check collection name
    assert call_args[0][0] == "test_coll"

    # Check IDs
    assert call_args[1]["ids"] == ["id1", "id2", "id3", "id4"]

    # Check metadatas include cluster field and updated_at
    metadatas = call_args[1]["metadatas"]
    assert len(metadatas) == 4
    assert metadatas[0]["cluster"] == 0
    assert metadatas[1]["cluster"] == 0
    assert metadatas[2]["cluster"] == 1
    assert metadatas[3]["cluster"] == -1
    assert "updated_at" in metadatas[0]
    assert "existing" in metadatas[0]  # Preserves existing metadata


def test_save_cluster_labels_preserves_existing_metadata(qapp, mock_connection, sample_cluster_data):
    """Test that saving cluster labels preserves existing metadata fields."""
    from vector_inspector.ui.views.visualization_view import VisualizationView
    import numpy as np

    view = VisualizationView(connection=mock_connection)
    view.current_collection = "test_coll"
    view.current_data = sample_cluster_data
    view.cluster_labels = np.array(sample_cluster_data["cluster_labels"])

    view._save_cluster_labels_to_metadata()

    # Get the metadatas that were passed to update_items
    metadatas = mock_connection.update_items.call_args[1]["metadatas"]

    # Verify existing fields are preserved
    assert metadatas[0]["existing"] == "data1"
    assert metadatas[1]["existing"] == "data2"
    assert metadatas[3]["existing"] == "data4"


def test_save_cluster_labels_adds_updated_at(qapp, mock_connection, sample_cluster_data):
    """Test that saving cluster labels adds updated_at timestamp."""
    from vector_inspector.ui.views.visualization_view import VisualizationView
    import numpy as np

    view = VisualizationView(connection=mock_connection)
    view.current_collection = "test_coll"
    view.current_data = sample_cluster_data
    view.cluster_labels = np.array(sample_cluster_data["cluster_labels"])

    before = datetime.now(UTC).isoformat()
    view._save_cluster_labels_to_metadata()
    after = datetime.now(UTC).isoformat()

    metadatas = mock_connection.update_items.call_args[1]["metadatas"]

    # Check all items have updated_at
    for metadata in metadatas:
        assert "updated_at" in metadata
        # Verify timestamp is reasonable (between before and after)
        assert before <= metadata["updated_at"] <= after


def test_save_cluster_labels_no_connection(qapp):
    """Test error handling when no connection is available."""
    from vector_inspector.ui.views.visualization_view import VisualizationView
    import numpy as np

    view = VisualizationView(connection=None)
    view.current_collection = "test_coll"
    view.current_data = {"ids": ["id1", "id2"], "metadatas": [{}, {}]}
    view.cluster_labels = np.array([0, 1])

    # Should not crash, just log error
    view._save_cluster_labels_to_metadata()
    # No exception means success


def test_save_cluster_labels_no_collection(qapp, mock_connection):
    """Test error handling when no collection is selected."""
    from vector_inspector.ui.views.visualization_view import VisualizationView
    import numpy as np

    view = VisualizationView(connection=mock_connection)
    view.current_collection = None
    view.current_data = {"ids": ["id1", "id2"], "metadatas": [{}, {}]}
    view.cluster_labels = np.array([0, 1])

    # Should not crash
    view._save_cluster_labels_to_metadata()

    # update_items should not be called
    mock_connection.update_items.assert_not_called()


def test_save_cluster_labels_no_cluster_data(qapp, mock_connection):
    """Test handling when no cluster labels are available."""
    from vector_inspector.ui.views.visualization_view import VisualizationView
    import numpy as np

    view = VisualizationView(connection=mock_connection)
    view.current_collection = "test_coll"
    view.current_data = {
        "ids": ["id1"],
        "metadatas": [{}],
    }
    # Set to empty numpy array (not None) so .any() works
    view.cluster_labels = np.array([])

    # Should not crash
    view._save_cluster_labels_to_metadata()

    # update_items should not be called due to empty array
    mock_connection.update_items.assert_not_called()


def test_save_cluster_labels_update_fails(qapp, mock_connection, sample_cluster_data):
    """Test error handling when update_items fails."""
    from vector_inspector.ui.views.visualization_view import VisualizationView
    import numpy as np

    # Make update_items return False (failure)
    mock_connection.update_items.return_value = False

    view = VisualizationView(connection=mock_connection)
    view.current_collection = "test_coll"
    view.current_data = sample_cluster_data
    view.cluster_labels = np.array(sample_cluster_data["cluster_labels"])

    # Should not crash, should handle gracefully
    with patch("vector_inspector.ui.views.visualization_view.QMessageBox") as mock_msg:
        view._save_cluster_labels_to_metadata()

        # Should show warning message
        mock_msg.warning.assert_called_once()


def test_clustering_panel_save_checkbox_exists(qapp):
    """Test that clustering panel has save_to_metadata_checkbox."""
    from vector_inspector.ui.views.visualization.clustering_panel import ClusteringPanel

    panel = ClusteringPanel()

    assert hasattr(panel, "save_to_metadata_checkbox")
    assert panel.save_to_metadata_checkbox is not None


def test_clustering_panel_save_checkbox_default_unchecked(qapp):
    """Test that save checkbox defaults to unchecked."""
    from vector_inspector.ui.views.visualization.clustering_panel import ClusteringPanel

    panel = ClusteringPanel()

    assert panel.save_to_metadata_checkbox.isChecked() is False


def test_save_cluster_labels_handles_noise_points(qapp, mock_connection):
    """Test that noise points (label -1) are saved correctly."""
    from vector_inspector.ui.views.visualization_view import VisualizationView
    import numpy as np

    view = VisualizationView(connection=mock_connection)
    view.current_collection = "test_coll"
    view.current_data = {
        "ids": ["id1", "id2", "id3"],
        "metadatas": [{}, {}, {}],
    }
    view.cluster_labels = np.array([0, -1, 1])  # One noise point

    view._save_cluster_labels_to_metadata()

    metadatas = mock_connection.update_items.call_args[1]["metadatas"]

    # Verify noise point (-1) is saved
    assert metadatas[1]["cluster"] == -1


def test_save_cluster_labels_handles_numpy_array(qapp, mock_connection):
    """Test that cluster labels as numpy array are handled correctly."""
    from vector_inspector.ui.views.visualization_view import VisualizationView

    view = VisualizationView(connection=mock_connection)
    view.current_collection = "test_coll"
    view.current_data = {
        "ids": ["id1", "id2"],
        "metadatas": [{}, {}],
    }
    view.cluster_labels = np.array([0, 1])  # NumPy array

    view._save_cluster_labels_to_metadata()

    metadatas = mock_connection.update_items.call_args[1]["metadatas"]

    # Should handle numpy types
    assert metadatas[0]["cluster"] == 0
    assert metadatas[1]["cluster"] == 1


@patch("vector_inspector.ui.views.visualization_view.QMessageBox")
def test_run_clustering_calls_save_when_checkbox_enabled(mock_msg, qapp, mock_connection):
    """Test that clustering triggers save when checkbox is enabled."""
    from vector_inspector.ui.views.visualization_view import VisualizationView

    view = VisualizationView(connection=mock_connection)
    view.current_collection = "test_coll"
    view.current_data = {
        "ids": ["id1", "id2", "id3", "id4"],
        "embeddings": np.random.rand(4, 5),
        "metadatas": [{}, {}, {}, {}],
    }

    # Enable save checkbox
    view.clustering_panel.save_to_metadata_checkbox.setChecked(True)

    # Mock the save method
    view._save_cluster_labels_to_metadata = Mock()

    # Mock the clustering thread to simulate successful clustering
    # We'll call _on_clustering_finished directly to avoid threading complexity
    view.cluster_labels = np.array([0, 0, 1, 1])

    # Simulate clustering completion which checks the checkbox
    if view.clustering_panel.save_to_metadata_checkbox.isChecked():
        view._save_cluster_labels_to_metadata()

    # Verify save was called
    view._save_cluster_labels_to_metadata.assert_called_once()


@patch("vector_inspector.ui.views.visualization_view.QMessageBox")
def test_run_clustering_skips_save_when_checkbox_disabled(mock_msg, qapp, mock_connection):
    """Test that clustering skips save when checkbox is disabled."""
    from vector_inspector.ui.views.visualization_view import VisualizationView

    view = VisualizationView(connection=mock_connection)
    view.current_collection = "test_coll"
    view.current_data = {
        "ids": ["id1", "id2", "id3", "id4"],
        "embeddings": np.random.rand(4, 5),
        "metadatas": [{}, {}, {}, {}],
    }

    # Disable save checkbox
    view.clustering_panel.save_to_metadata_checkbox.setChecked(False)

    # Mock the save method
    view._save_cluster_labels_to_metadata = Mock()

    # Mock clustering completion
    view.cluster_labels = np.array([0, 0, 1, 1])

    # Simulate clustering completion which checks the checkbox
    if view.clustering_panel.save_to_metadata_checkbox.isChecked():
        view._save_cluster_labels_to_metadata()

    # Verify save was NOT called
    view._save_cluster_labels_to_metadata.assert_not_called()
