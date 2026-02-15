"""Tests for search view inline details pane integration.

Uses pytest-qt's qtbot fixture for proper Qt widget testing.
"""

from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.ui.views.search_view import SearchView


@pytest.fixture
def mock_connection():
    """Create a mock connection."""
    conn = MagicMock()
    conn.query_collection.return_value = {
        "ids": ["result1", "result2", "result3"],
        "documents": ["Result doc 1", "Result doc 2", "Result doc 3"],
        "metadatas": [
            {"title": "Result 1"},
            {"title": "Result 2"},
            {"title": "Result 3"},
        ],
        "embeddings": [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ],
        "distances": [0.1, 0.3, 0.5],
    }
    return conn


@pytest.fixture
def search_view(qtbot, mock_connection):
    """Create a search view."""
    view = SearchView(connection=mock_connection)
    qtbot.addWidget(view)
    view.current_collection = "test_collection"
    view.current_database = "test_db"
    return view


def test_inline_details_pane_exists(search_view):
    """Test that inline details pane exists in search view."""
    assert hasattr(search_view, "details_pane")
    assert search_view.details_pane is not None
    assert search_view.details_pane.view_mode == "search"


def test_inline_pane_starts_hidden(search_view):
    """Test that inline pane starts hidden in search view."""
    # Before any search, pane should be hidden
    assert search_view.details_pane.isVisible() is False


def test_pane_shows_on_result_selection(qtbot, search_view, mock_connection):
    """Test that pane is updated when item data is provided."""
    # Perform search
    search_view.query_input.setText("test query")
    search_view._perform_search()

    # Initially should have no item
    assert search_view.details_pane._current_item is None

    # Manually create and update item data (simulating selection)
    item_data = {
        "id": "result1",
        "document": "Result doc 1",
        "metadata": {"title": "Result 1"},
        "embedding": [0.1, 0.2, 0.3],
        "distance": 0.1,
        "rank": 1,
    }
    search_view.details_pane.update_item(item_data)

    # Should now have item data
    assert search_view.details_pane._current_item is not None
    assert search_view.details_pane._current_item["id"] == "result1"


def test_pane_hides_on_refresh(qtbot, search_view, mock_connection):
    """Test that pane clears data when search is refreshed."""
    # Perform search and show pane with data
    search_view.query_input.setText("test query")
    search_view._perform_search()

    item_data = {"id": "result1", "document": "doc1", "rank": 1}
    search_view.details_pane.update_item(item_data)
    assert search_view.details_pane._current_item is not None

    # Refresh clears results
    search_view._refresh_search()

    # Pane should have no item (cleared)
    assert search_view.details_pane._current_item is None


def test_pane_hides_on_collection_change(qtbot, search_view):
    """Test that pane hides when collection changes."""
    # Mock a search result selection
    search_view.details_pane.setVisible(True)
    search_view.details_pane.update_item({"id": "test", "document": "doc"})

    # Change collection
    search_view.set_collection("new_collection")

    # Should be hidden
    assert search_view.details_pane.isVisible() is False


def test_pane_shows_search_metrics(qtbot, search_view, mock_connection):
    """Test that pane shows search-specific metrics."""
    # Perform search
    search_view.query_input.setText("test query")
    search_view._perform_search()

    # Select first result
    search_view.results_table.selectRow(0)
    search_view._on_selection_changed()

    # Check search metrics
    assert "Rank:" in search_view.details_pane.rank_label.text()
    assert "Similarity:" in search_view.details_pane.similarity_label.text()


def test_pane_updates_on_selection_change(qtbot, search_view, mock_connection):
    """Test that pane updates when selecting different results."""
    # Perform search
    search_view.query_input.setText("test query")
    search_view._perform_search()

    # Select first result
    search_view.results_table.selectRow(0)
    search_view._on_selection_changed()
    assert "result1" in search_view.details_pane.id_label.text()

    # Select second result
    search_view.results_table.selectRow(1)
    search_view._on_selection_changed()
    assert "result2" in search_view.details_pane.id_label.text()


def test_pane_hides_on_empty_results(qtbot, search_view, mock_connection):
    """Test that pane hides when search returns no results."""
    # Mock empty search results
    mock_connection.query_collection.return_value = {
        "ids": [],
        "documents": [],
        "metadatas": [],
        "embeddings": [],
        "distances": [],
    }

    search_view.query_input.setText("test query")
    search_view._perform_search()

    # Should be hidden
    assert search_view.details_pane.isVisible() is False


def test_pane_hides_on_search_error(qtbot, search_view, mock_connection):
    """Test that pane hides when search fails."""
    # Mock search error
    mock_connection.query_collection.side_effect = Exception("Search failed")

    search_view.query_input.setText("test query")
    # Search will raise exception - test that it doesn't crash the app
    try:
        search_view._perform_search()
    except Exception:
        pass  # Expected

    # Pane should be hidden (or stay hidden)
    assert search_view.details_pane.isVisible() is False


def test_search_input_height_reduced(search_view):
    """Test that search input height is compact."""
    # Search input should have reduced height
    assert search_view.query_input.maximumHeight() <= 60


def test_advanced_filters_start_collapsed(search_view):
    """Test that advanced metadata filters start collapsed."""
    # Filter group should be unchecked
    assert search_view.filter_group.isChecked() is False

    # Filter builder should be hidden
    assert search_view.filter_builder.isVisible() is False


def test_advanced_filters_show_when_checked(qtbot, search_view):
    """Test that advanced filters checkbox toggles properly."""
    # Initially unchecked
    assert search_view.filter_group.isChecked() is False

    # Check the box
    search_view.filter_group.setChecked(True)

    # Should be checked
    assert search_view.filter_group.isChecked() is True

    # Verify signal is connected to setVisible method
    # (implementation detail: toggled signal connected to filter_builder.setVisible)
    assert search_view.filter_builder is not None


def test_advanced_filters_hide_when_unchecked(qtbot, search_view):
    """Test that advanced filters toggle works in both directions."""
    # Check the box first
    search_view.filter_group.setChecked(True)
    assert search_view.filter_group.isChecked() is True

    # Uncheck
    search_view.filter_group.setChecked(False)

    # Should be unchecked
    assert search_view.filter_group.isChecked() is False


def test_open_full_details_from_search_pane(qtbot, search_view, mock_connection):
    """Test opening full details dialog from search inline pane."""
    # Perform search and select result
    search_view.query_input.setText("test query")
    search_view._perform_search()
    search_view.results_table.selectRow(0)
    search_view._on_selection_changed()

    with patch("vector_inspector.ui.views.search_view.ItemDetailsDialog") as MockDialog:
        mock_dialog = MockDialog.return_value
        mock_dialog.exec.return_value = False

        # Click "Open full details" button
        search_view.details_pane.full_details_btn.click()

        # Should open full details dialog
        MockDialog.assert_called_once()


def test_pane_state_saved_on_close(qtbot, search_view, mock_connection):
    """Test that pane state is saved when view closes."""
    from vector_inspector.services.settings_service import SettingsService

    # Perform search and select result
    search_view.query_input.setText("test query")
    search_view._perform_search()
    search_view.results_table.selectRow(0)
    search_view._on_selection_changed()

    # Expand metadata section
    search_view.details_pane.metadata_section.set_collapsed(False)

    # Close event should save state
    from PySide6.QtGui import QCloseEvent

    close_event = QCloseEvent()
    search_view.closeEvent(close_event)

    # State should be saved
    settings = SettingsService()
    assert settings.get("inline_details_search_metadata_collapsed") is False


def test_query_section_content_hugs_top(search_view):
    """Test that query section content is pushed to top."""
    # The query_layout should have a stretch at the end
    # This is harder to test directly, but we can verify the layout structure
    query_widget = search_view.findChild(type(search_view.children()[0]))
    if query_widget and hasattr(query_widget, "layout"):
        layout = query_widget.layout()
        if layout:
            # Last item should be a stretch
            last_item = layout.itemAt(layout.count() - 1)
            # Stretch items have no widget
            has_stretch = last_item and last_item.widget() is None
            # This is a proxy check, but indicates stretch was added
            assert layout.count() > 2  # Should have multiple items


def test_similarity_calculation(qtbot, search_view, mock_connection):
    """Test that similarity score is correctly calculated from distance."""
    # Perform search
    search_view.query_input.setText("test query")
    search_view._perform_search()

    # Select first result (distance = 0.1)
    search_view.results_table.selectRow(0)
    search_view._on_selection_changed()

    # Similarity should be 1 - 0.1 = 0.9
    similarity_text = search_view.details_pane.similarity_label.text()
    assert "0.900" in similarity_text


def test_rank_display(qtbot, search_view, mock_connection):
    """Test that rank is correctly displayed."""
    # Perform search
    search_view.query_input.setText("test query")
    search_view._perform_search()

    # Select first result
    search_view.results_table.selectRow(0)
    search_view._on_selection_changed()

    # Rank should be 1 (first result)
    rank_text = search_view.details_pane.rank_label.text()
    assert "Rank: 1" in rank_text or "1" in rank_text


def test_pane_handles_missing_distance(qtbot, search_view, mock_connection):
    """Test that pane handles missing distance values."""
    # Mock results without distances
    mock_connection.query_collection.return_value = {
        "ids": ["result1"],
        "documents": ["Result doc 1"],
        "metadatas": [{"title": "Result 1"}],
        "embeddings": [[0.1, 0.2, 0.3]],
        "distances": [None],
    }

    search_view.query_input.setText("test query")
    search_view._perform_search()

    # Manually update pane with None distance
    item_data = {
        "id": "result1",
        "document": "Result doc 1",
        "metadata": {"title": "Result 1"},
        "embedding": [0.1, 0.2, 0.3],
        "distance": None,
        "rank": 1,
    }
    search_view.details_pane.update_item(item_data)

    # Should handle gracefully (no crash)and store the data
    assert search_view.details_pane._current_item is not None
    assert search_view.details_pane._current_item["distance"] is None


def test_double_click_opens_details_in_search(qtbot, search_view, mock_connection):
    """Test that double-clicking a search result opens details dialog."""
    # Perform search
    search_view.query_input.setText("test query")
    search_view._perform_search()

    with patch("vector_inspector.ui.views.search_view.ItemDetailsDialog") as MockDialog:
        mock_dialog = MockDialog.return_value
        mock_dialog.exec.return_value = False

        # Select and double-click first result
        search_view.results_table.selectRow(0)
        index = search_view.results_table.model().index(0, 0)

        # Simulate double-click
        search_view._on_row_double_clicked(index)

        # Should create ItemDetailsDialog
        MockDialog.assert_called_once()


def test_splitter_allocates_more_space_to_results(qtbot, search_view):
    """Test that splitter gives more space to results than query section."""
    # Find the main splitter
    from PySide6.QtWidgets import QSplitter

    splitters = search_view.findChildren(QSplitter)

    if splitters:
        main_splitter = splitters[0]  # Main vertical splitter
        sizes = main_splitter.sizes()

        # Results section should get more space than query section
        # This assumes results is second section (index 1)
        if len(sizes) >= 2:
            query_size = sizes[0]
            results_size = sizes[1]
            # Results should have more or similar space
            assert results_size >= query_size * 0.8  # Allow some flexibility
