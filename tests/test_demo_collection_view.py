"""Tests for DemoCollectionView showing new testing patterns."""

from unittest.mock import MagicMock

import pytest

from vector_inspector.services import ThreadedTaskRunner
from vector_inspector.state import AppState
from vector_inspector.ui.views.demo_collection_view import DemoCollectionView


@pytest.fixture
def app_state():
    """Create AppState instance for testing."""
    return AppState()


@pytest.fixture
def task_runner():
    """Create TaskRunner instance for testing."""
    return ThreadedTaskRunner()


@pytest.fixture
def demo_view(app_state, task_runner, qtbot):
    """Create DemoCollectionView for testing."""
    view = DemoCollectionView(app_state, task_runner)
    qtbot.addWidget(view)
    return view


def test_demo_view_initializes(demo_view):
    """Test that demo view initializes correctly."""
    assert demo_view.table is not None
    assert demo_view.status_label is not None
    assert demo_view.load_button is not None
    assert demo_view.table.rowCount() == 0


def test_demo_view_reacts_to_provider_change(demo_view, app_state, qtbot):
    """Test that view reacts to provider changes."""
    # Create mock connection
    mock_connection = MagicMock()
    mock_connection.get_all_items = MagicMock(
        return_value={
            "ids": ["id1", "id2"],
            "metadatas": [{"key": "value"}, {}],
            "documents": ["doc1", "doc2"],
            "embeddings": [[0.1, 0.2], [0.3, 0.4]],
        }
    )

    # Change provider
    with qtbot.waitSignal(app_state.provider_changed):
        app_state.provider = mock_connection

    # Verify button enabled
    assert demo_view.load_button.isEnabled()


def test_demo_view_reacts_to_data_load(demo_view, app_state, qtbot):
    """Test that view reacts to data being loaded."""
    # Prepare test data
    test_data = {
        "ids": ["test1", "test2", "test3"],
        "metadatas": [{"meta": "1"}, {"meta": "2"}, {"meta": "3"}],
        "documents": ["Document 1", "Document 2", "Document 3"],
        "embeddings": [[0.1], [0.2], [0.3]],
    }

    # Load data via AppState
    with qtbot.waitSignal(app_state.vectors_loaded):
        app_state.set_data(test_data)

    # Verify table populated
    assert demo_view.table.rowCount() == 3
    assert demo_view.table.item(0, 0).text() == "test1"
    assert demo_view.table.item(1, 0).text() == "test2"
    assert demo_view.table.item(2, 0).text() == "test3"


def test_demo_view_reacts_to_collection_change(demo_view, app_state, qtbot):
    """Test that view reacts to collection changes."""
    # Mock connection
    mock_connection = MagicMock()
    app_state.provider = mock_connection

    # Change collection
    with qtbot.waitSignal(app_state.collection_changed):
        app_state.collection = "test_collection"

    # Verify status updated
    assert "test_collection" in demo_view.status_label.text()


def test_demo_view_displays_empty_table_initially(demo_view):
    """Test that table is empty initially."""
    assert demo_view.table.rowCount() == 0


def test_demo_view_handles_loading_state(demo_view, app_state, qtbot):
    """Test that view reacts to loading state changes."""
    # Start loading
    with qtbot.waitSignal(app_state.loading_started):
        app_state.start_loading("Test loading...")

    # Verify button disabled during loading
    assert not demo_view.load_button.isEnabled()

    # Finish loading
    with qtbot.waitSignal(app_state.loading_finished):
        app_state.finish_loading()

    # Verify button re-enabled
    assert demo_view.load_button.isEnabled()


def test_demo_view_handles_error(demo_view, app_state, qtbot, monkeypatch):
    """Test that view handles errors correctly."""
    # Mock QMessageBox to avoid showing actual dialog
    mock_critical = MagicMock()
    monkeypatch.setattr("PySide6.QtWidgets.QMessageBox.critical", mock_critical)

    # Emit error
    with qtbot.waitSignal(app_state.error_occurred):
        app_state.emit_error("Test Error", "This is a test error")

    # Verify error dialog was called
    mock_critical.assert_called_once()


def test_demo_view_services_get_connection_on_provider_change(demo_view, app_state):
    """Test that services receive connection when provider changes."""
    # Create mock connection
    mock_connection = MagicMock()

    # Change provider
    app_state.provider = mock_connection

    # Verify services got connection
    assert demo_view.collection_loader.connection == mock_connection
    assert demo_view.metadata_loader.connection == mock_connection


def test_demo_view_load_button_disabled_without_connection(demo_view):
    """Test that load button is disabled without connection."""
    # No connection set, button should be disabled
    assert not demo_view.load_button.isEnabled()


def test_demo_view_populates_table_correctly(demo_view, app_state):
    """Test table population with various data."""
    # Test data with different metadata depths
    test_data = {
        "ids": ["id1", "id2"],
        "metadatas": [{"key1": "value1", "key2": "value2"}, {}],
        "documents": ["Short doc", "A" * 200],  # Long document to test truncation
        "embeddings": [[0.1, 0.2], [0.3, 0.4]],
    }

    app_state.set_data(test_data)

    # Check table contents
    assert demo_view.table.rowCount() == 2

    # Check ID column
    assert demo_view.table.item(0, 0).text() == "id1"
    assert demo_view.table.item(1, 0).text() == "id2"

    # Check that long document is truncated
    doc_text = demo_view.table.item(1, 2).text()
    assert len(doc_text) <= 103  # 100 chars + "..."


def test_demo_view_integration_with_task_runner(demo_view, app_state, task_runner, qtbot):
    """Test integration with TaskRunner for background operations."""
    # Mock connection with get_all_items
    mock_connection = MagicMock()
    test_data = {
        "ids": ["bg1", "bg2"],
        "metadatas": [{}, {}],
        "documents": ["Doc 1", "Doc 2"],
        "embeddings": [[0.1], [0.2]],
    }
    mock_connection.get_all_items = MagicMock(return_value=test_data)

    # Set up connection and collection
    app_state.provider = mock_connection
    app_state.collection = "test_collection"

    # Trigger load (this uses task_runner)
    # Note: In real use, data would be loaded asynchronously
    # For testing, we can directly test the callbacks

    # Simulate successful load
    demo_view._on_load_complete(test_data)

    # Verify data in AppState
    assert app_state.full_data == test_data

    # Verify table populated
    assert demo_view.table.rowCount() == 2


def test_demo_view_no_data_no_crash(demo_view, app_state):
    """Test that view handles empty data gracefully."""
    # Set empty data
    empty_data = {"ids": [], "metadatas": [], "documents": [], "embeddings": []}

    app_state.set_data(empty_data)

    # Should not crash
    assert demo_view.table.rowCount() == 0
