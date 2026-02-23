"""Tests for metadata table helpers (copying vectors, table population, updates)."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from vector_inspector.ui.views.metadata.context import MetadataContext
from vector_inspector.ui.views.metadata.metadata_table import (
    copy_vectors_to_json,
    find_updated_item_page,
    populate_table,
    show_context_menu,
    update_row_in_place,
)


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
    mock_clipboard = Mock()
    mock_qapp.clipboard.return_value = mock_clipboard

    copy_vectors_to_json(mock_table, sample_context, [0])

    mock_clipboard.setText.assert_called_once()
    json_output = mock_clipboard.setText.call_args[0][0]

    data = json.loads(json_output)
    assert data["id"] == "id1"
    assert data["vector"] == [0.1, 0.2, 0.3]
    assert data["dimension"] == 3

    mock_qmsg.information.assert_called_once()


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
@patch("vector_inspector.ui.views.metadata.metadata_table.QApplication")
def test_copy_multiple_vectors(mock_qapp, mock_qmsg, mock_table, sample_context):
    """Test copying multiple vectors to JSON."""
    mock_clipboard = Mock()
    mock_qapp.clipboard.return_value = mock_clipboard

    copy_vectors_to_json(mock_table, sample_context, [0, 2])

    mock_clipboard.setText.assert_called_once()
    json_output = mock_clipboard.setText.call_args[0][0]

    data = json.loads(json_output)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["id"] == "id1"
    assert data[0]["vector"] == [0.1, 0.2, 0.3]
    assert data[1]["id"] == "id3"
    assert data[1]["vector"] == [0.7, 0.8, 0.9]

    mock_qmsg.information.assert_called_once()
    args = mock_qmsg.information.call_args[0]
    assert "2" in args[2]


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
def test_copy_no_embeddings(mock_qmsg, mock_table):
    """Test error handling when no embeddings are available."""
    ctx = MetadataContext(connection=None)
    ctx.current_data = {
        "ids": ["id1"],
        "documents": ["doc1"],
        "metadatas": [{}],
    }

    copy_vectors_to_json(mock_table, ctx, [0])

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

        json_output = mock_clipboard.setText.call_args[0][0]
        data = json.loads(json_output)
        assert data["vector"] == [0.1, 0.2, 0.3]
    except ImportError:
        pytest.skip("numpy not available")


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
def test_copy_invalid_row_index(mock_qmsg, mock_table, sample_context):
    """Test handling of invalid row indices."""
    copy_vectors_to_json(mock_table, sample_context, [999])

    mock_qmsg.warning.assert_called_once()


@patch("vector_inspector.ui.views.metadata.metadata_table.QMessageBox")
@patch("vector_inspector.ui.views.metadata.metadata_table.QApplication")
def test_copy_with_numpy_embeddings_array(mock_qapp, mock_qmsg, mock_table):
    """Test that numpy array embeddings don't cause truthiness error."""
    try:
        import numpy as np

        ctx = MetadataContext(connection=None)
        ctx.current_data = {
            "ids": ["id1", "id2"],
            "documents": ["doc1", "doc2"],
            "metadatas": [{}, {}],
            "embeddings": np.array([[0.1, 0.2], [0.3, 0.4]]),
        }

        mock_clipboard = Mock()
        mock_qapp.clipboard.return_value = mock_clipboard

        copy_vectors_to_json(mock_table, ctx, [0])

        mock_clipboard.setText.assert_called_once()
        json_output = mock_clipboard.setText.call_args[0][0]
        data = json.loads(json_output)
        assert data["id"] == "id1"
    except ImportError:
        pytest.skip("numpy not available")


def test_populate_table_and_update_row(qtbot):
    table = QTableWidget()
    ctx = MetadataContext(connection=None)
    ctx.page_size = 2
    ctx.current_page = 0
    ctx.current_data = {
        "ids": ["a", "b"],
        "documents": ["doc a", "doc b"],
        "metadatas": [{"k": "v1"}, {"k": "v2"}],
    }

    qtbot.addWidget(table)
    populate_table(table, ctx)
    assert table.rowCount() == 2
    assert table.columnCount() >= 3
    assert table.item(0, 0).text() == "a"

    updated = update_row_in_place(
        table,
        ctx,
        {"id": "a", "document": "doc a updated", "metadata": {"k": "v1u"}},
    )
    assert updated is True
    assert ctx.current_data["documents"][0] == "doc a updated"
    assert table.item(0, 1).text().startswith("doc a updated")


def test_find_updated_item_page():
    class FakeConn:
        def get_all_items(self, collection, limit, offset, where):
            return {"ids": [f"id{i}" for i in range(100)]}

    ctx = MetadataContext(connection=FakeConn())
    ctx.current_collection = "col"
    ctx.page_size = 10

    page = find_updated_item_page(ctx, "id35")
    assert page == 3


def test_show_context_menu_no_block(monkeypatch, qtbot):
    table = QTableWidget()
    table.setColumnCount(1)
    table.setRowCount(1)
    table.setItem(0, 0, QTableWidgetItem("a"))

    ctx = MetadataContext(connection=None)
    ctx.current_data = {"ids": ["a"], "documents": ["d1"], "metadatas": [{}]}

    qtbot.addWidget(table)

    monkeypatch.setattr(
        "vector_inspector.ui.views.metadata.metadata_table.QMenu.exec",
        lambda self, *a, **k: None,
    )

    pos = table.visualItemRect(table.item(0, 0)).center()
    show_context_menu(table, pos, ctx, lambda idx: None)
