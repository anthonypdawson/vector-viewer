"""Tests for copy vector to JSON functionality."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from vector_inspector.ui.views.metadata.context import MetadataContext
from vector_inspector.ui.views.metadata.metadata_table import copy_vectors_to_json


@pytest.fixture
def mock_table():
    """Create a mock QTableWidget."""
    return MagicMock()


@pytest.fixture
def sample_context():
    """Create a MetadataContext with sample vector data."""
    ctx = MetadataContext(connection=None)
    ctx.current_data = {
        "ids": ["id1", "id2", "id3"],
        "documents": ["doc1", "doc2", "doc3"],
        "metadatas": [{}, {}, {}],
        "embeddings": [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ],
    }
    return ctx


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
@patch("vector_inspector.ui.views.metadata.metadata_table.QApplication")
def test_copy_single_vector(mock_qapp, mock_qmsg, mock_table, sample_context):
    """Test copying a single vector to JSON."""
    # Setup mocks
    mock_clipboard = Mock()
    mock_qapp.clipboard.return_value = mock_clipboard

    # Copy first row
    copy_vectors_to_json(mock_table, sample_context, [0])

    # Verify clipboard was called with JSON
    mock_clipboard.setText.assert_called_once()
    json_output = mock_clipboard.setText.call_args[0][0]

    # Parse and verify JSON structure
    data = json.loads(json_output)
    assert data["id"] == "id1"
    assert data["vector"] == [0.1, 0.2, 0.3]
    assert data["dimension"] == 3

    # Verify success message shown
    mock_qmsg.information.assert_called_once()


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
@patch("vector_inspector.ui.views.metadata.metadata_table.QApplication")
def test_copy_multiple_vectors(mock_qapp, mock_qmsg, mock_table, sample_context):
    """Test copying multiple vectors to JSON."""
    # Setup mocks
    mock_clipboard = Mock()
    mock_qapp.clipboard.return_value = mock_clipboard

    # Copy multiple rows
    copy_vectors_to_json(mock_table, sample_context, [0, 2])

    # Verify clipboard was called
    mock_clipboard.setText.assert_called_once()
    json_output = mock_clipboard.setText.call_args[0][0]

    # Parse and verify JSON structure (should be an array)
    data = json.loads(json_output)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["id"] == "id1"
    assert data[0]["vector"] == [0.1, 0.2, 0.3]
    assert data[1]["id"] == "id3"
    assert data[1]["vector"] == [0.7, 0.8, 0.9]

    # Verify success message mentions plural
    mock_qmsg.information.assert_called_once()
    args = mock_qmsg.information.call_args[0]
    assert "2" in args[2]  # Check message contains count


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
def test_copy_no_embeddings(mock_qmsg, mock_table):
    """Test error handling when no embeddings are available."""
    ctx = MetadataContext(connection=None)
    ctx.current_data = {
        "ids": ["id1"],
        "documents": ["doc1"],
        "metadatas": [{}],
        # No embeddings key
    }

    copy_vectors_to_json(mock_table, ctx, [0])

    # Verify warning message shown
    mock_qmsg.warning.assert_called_once()
    args = mock_qmsg.warning.call_args[0]
    assert "No vector" in args[2] or "No Vector" in args[2]


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
@patch("vector_inspector.ui.views.metadata.metadata_table.QApplication")
def test_copy_numpy_array_vector(mock_qapp, mock_qmsg, mock_table):
    """Test copying vectors that are numpy arrays."""
    try:
        import numpy as np

        ctx = MetadataContext(connection=None)
        ctx.current_data = {
            "ids": ["id1"],
            "documents": ["doc1"],
            "metadatas": [{}],
            "embeddings": [np.array([0.1, 0.2, 0.3])],
        }

        mock_clipboard = Mock()
        mock_qapp.clipboard.return_value = mock_clipboard

        copy_vectors_to_json(mock_table, ctx, [0])

        # Verify numpy array was converted to list
        json_output = mock_clipboard.setText.call_args[0][0]
        data = json.loads(json_output)
        assert data["vector"] == [0.1, 0.2, 0.3]
    except ImportError:
        pytest.skip("numpy not available")


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
def test_copy_invalid_row_index(mock_qmsg, mock_table, sample_context):
    """Test handling of invalid row indices."""
    # Try to copy row that doesn't exist
    copy_vectors_to_json(mock_table, sample_context, [999])

    # Should show warning about no data
    mock_qmsg.warning.assert_called_once()


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
@patch("vector_inspector.ui.views.metadata.metadata_table.QApplication")
def test_copy_with_numpy_embeddings_array(mock_qapp, mock_qmsg, mock_table):
    """Test that numpy array embeddings don't cause truthiness error."""
    try:
        import numpy as np

        # Create context with numpy array for embeddings
        ctx = MetadataContext(connection=None)
        ctx.current_data = {
            "ids": ["id1", "id2"],
            "documents": ["doc1", "doc2"],
            "metadatas": [{}, {}],
            "embeddings": np.array([[0.1, 0.2], [0.3, 0.4]]),  # numpy array, not list
        }

        mock_clipboard = Mock()
        mock_qapp.clipboard.return_value = mock_clipboard

        # This should NOT raise "ValueError: The truth value of an array..."
        copy_vectors_to_json(mock_table, ctx, [0])

        # Verify it worked
        mock_clipboard.setText.assert_called_once()
        json_output = mock_clipboard.setText.call_args[0][0]
        data = json.loads(json_output)
        assert data["id"] == "id1"
    except ImportError:
        pytest.skip("numpy not available")
