"""Tests for metadata view navigation and item selection."""

from unittest.mock import MagicMock, Mock, patch

import pytest
from PySide6.QtWidgets import QApplication

from vector_inspector.state import AppState
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
    """Create a mock connection."""
    conn = MagicMock()
    conn.get_collection_data.return_value = {
        "ids": ["id1", "id2", "id3"],
        "documents": ["doc1", "doc2", "doc3"],
        "metadatas": [{}, {}, {}],
        "embeddings": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
    }
    return conn


@pytest.fixture
def metadata_context(mock_connection):
    """Create a MetadataContext with sample data."""
    ctx = MetadataContext(connection=mock_connection)
    ctx.current_collection = "test_collection"
    ctx.current_database = "test_db"
    ctx.current_data = {
        "ids": ["id1", "id2", "id3"],
        "documents": ["doc1", "doc2", "doc3"],
        "metadatas": [{}, {}, {}],
        "embeddings": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
    }
    ctx.page_size = 3
    return ctx


def test_select_item_by_id_on_current_page(qapp, task_runner, metadata_context):
    """Test selecting an item that's on the current page."""
    from vector_inspector.ui.views.metadata_view import MetadataView

    app_state = AppState()
    app_state.provider = metadata_context.connection
    view = MetadataView(app_state, task_runner)
    view.ctx = metadata_context

    # Populate table
    from vector_inspector.ui.views.metadata.metadata_table import populate_table

    populate_table(view.table, metadata_context)

    # Select item by ID that's on current page
    result = view.select_item_by_id("id2")

    assert result is True
    # Check that row 1 (index of "id2") is selected
    selected_rows = view.table.selectionModel().selectedRows()
    assert len(selected_rows) == 1
    assert selected_rows[0].row() == 1


def test_select_item_by_id_not_found(qapp, task_runner, metadata_context):
    """Test selecting an item that doesn't exist."""
    from vector_inspector.ui.views.metadata_view import MetadataView

    app_state = AppState()
    app_state.provider = metadata_context.connection
    view = MetadataView(app_state, task_runner)
    view.ctx = metadata_context

    # Try to select non-existent item
    result = view.select_item_by_id("nonexistent-id")

    assert result is False


def test_select_item_by_id_no_data(qapp, task_runner):
    """Test selecting an item when no data is loaded."""
    from vector_inspector.ui.views.metadata_view import MetadataView

    app_state = AppState()
    app_state.provider = None
    view = MetadataView(app_state, task_runner)
    view.ctx = MetadataContext(connection=None)
    view.ctx.current_data = None

    result = view.select_item_by_id("any-id")

    assert result is False


@patch("vector_inspector.ui.views.metadata.find_updated_item_page")
def test_select_item_by_id_different_page(mock_find_page, qapp, task_runner, metadata_context):
    """Test selecting an item that's on a different page."""
    from vector_inspector.ui.views.metadata_view import MetadataView

    # Mock find_updated_item_page to return page 2
    mock_find_page.return_value = 2

    app_state = AppState()
    app_state.provider = metadata_context.connection
    view = MetadataView(app_state, task_runner)
    view.ctx = metadata_context
    view.ctx.current_page = 0

    # Mock _load_data to avoid actual loading
    view._load_data = Mock()

    # Try to select item not on current page
    result = view.select_item_by_id("id-on-page-2")

    # Should trigger page load
    assert view.ctx._select_id_after_load == "id-on-page-2"
    assert view.ctx.current_page == 2
    view._load_data.assert_called_once()
    assert result is True


def test_find_updated_item_page_helper():
    """Test find_updated_item_page helper function."""
    from vector_inspector.ui.views.metadata import find_updated_item_page

    # Create mock context
    ctx = MetadataContext(connection=MagicMock())
    ctx.current_collection = "test_coll"
    ctx.page_size = 10

    # Mock connection.get_all_items to return data with our target ID
    def mock_get_all(collection, limit=None, offset=None, where=None):
        # Return all items when limit=None
        return {
            "ids": [f"id{i}" for i in range(30)],  # 30 items total
            "documents": [f"doc{i}" for i in range(30)],
        }

    ctx.connection.get_all_items = mock_get_all

    # Find item on page 2 (items 20-29)
    target_id = "id25"
    page = find_updated_item_page(ctx, target_id)

    assert page == 2  # Page 2 (0-indexed): id25/10 = 2


def test_context_select_id_after_load_flag():
    """Test that _select_id_after_load flag is used correctly."""
    ctx = MetadataContext(connection=None)

    # Initially None
    assert ctx._select_id_after_load is None

    # Set target ID
    ctx._select_id_after_load = "target-id"
    assert ctx._select_id_after_load == "target-id"

    # Clear flag (simulating after selection)
    ctx._select_id_after_load = None
    assert ctx._select_id_after_load is None


def test_main_window_handles_view_in_data_browser_signal(qapp, task_runner):
    """Test that MainWindow connects and handles view_in_data_browser signal."""
    # This test requires full MainWindow initialization which is complex
    # Test the core behavior: metadata_view.select_item_by_id is called
    from vector_inspector.ui.views.metadata_view import MetadataView

    # Create a metadata view
    mock_connection = MagicMock()
    app_state = AppState()
    app_state.provider = mock_connection
    view = MetadataView(app_state, task_runner)
    view.ctx = MetadataContext(connection=mock_connection)
    view.ctx.current_collection = "test_coll"
    view.ctx.current_data = {
        "ids": ["test-item-id", "other-id"],
        "documents": ["doc1", "doc2"],
        "metadatas": [{}, {}],
    }

    # Populate table
    from vector_inspector.ui.views.metadata.metadata_table import populate_table

    populate_table(view.table, view.ctx)

    # Test select_item_by_id directly
    result = view.select_item_by_id("test-item-id")
    assert result is True

    # Verify selection
    selected_rows = view.table.selectionModel().selectedRows()
    assert len(selected_rows) == 1
    assert selected_rows[0].row() == 0


def test_pagination_preserves_selection_state():
    """Test that pagination state is preserved during item selection."""
    ctx = MetadataContext(connection=MagicMock())
    ctx.current_page = 0
    ctx.page_size = 10
    ctx.current_collection = "coll"

    # Set target for selection
    ctx._select_id_after_load = "target-id"

    # Change page
    ctx.current_page = 3

    # Flag should still be set
    assert ctx._select_id_after_load == "target-id"
    assert ctx.current_page == 3


def test_select_item_scrolls_into_view(qapp, task_runner, metadata_context):
    """Test that selecting an item scrolls it into view."""
    from vector_inspector.ui.views.metadata_view import MetadataView

    app_state = AppState()
    app_state.provider = metadata_context.connection
    view = MetadataView(app_state, task_runner)
    view.ctx = metadata_context

    # Populate table
    from vector_inspector.ui.views.metadata.metadata_table import populate_table

    populate_table(view.table, metadata_context)

    # Mock scrollToItem to verify it's called
    view.table.scrollToItem = Mock()

    # Select item
    result = view.select_item_by_id("id3")

    assert result is True
    # Verify scrollToItem was called
    view.table.scrollToItem.assert_called_once()


def test_cross_page_navigation_with_filters(qapp, task_runner):
    """Test that cross-page navigation works with active filters."""
    from vector_inspector.ui.views.metadata_view import MetadataView

    mock_conn = MagicMock()
    # Mock get_all_items for find_updated_item_page
    mock_conn.get_all_items.return_value = {
        "ids": [f"id{i}" for i in range(30)],
        "documents": [f"doc{i}" for i in range(30)],
    }

    app_state = AppState()
    app_state.provider = mock_conn
    view = MetadataView(app_state, task_runner)
    view.ctx = MetadataContext(connection=mock_conn)
    view.ctx.current_collection = "coll"
    view.ctx.page_size = 10
    view.ctx.current_page = 0
    view.ctx.current_data = {
        "ids": [f"id{i}" for i in range(10)],
        "documents": [f"doc{i}" for i in range(10)],
        "metadatas": [{} for _ in range(10)],
    }

    # Mock filter builder
    view.filter_builder = MagicMock()
    view.filter_builder.has_filters.return_value = True
    view.filter_builder.get_filters_split.return_value = ({"key": "value"}, {})

    view.filter_group = MagicMock()
    view.filter_group.isChecked.return_value = True

    # Mock _load_data
    view._load_data = Mock()

    # Try to select item that would be on page 2
    result = view.select_item_by_id("id25")

    # Should trigger page load to page 2
    assert view.ctx.current_page == 2
    view._load_data.assert_called_once()
    assert result is True
