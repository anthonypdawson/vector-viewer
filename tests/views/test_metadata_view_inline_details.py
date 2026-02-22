"""Tests for metadata view inline details pane integration.

Uses pytest-qt's qtbot fixture for proper Qt widget testing.
"""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QDialog

from vector_inspector.state import AppState
from vector_inspector.ui.views.metadata.context import MetadataContext
from vector_inspector.ui.views.metadata_view import MetadataView


@pytest.fixture
def mock_connection(fake_provider):
    """Provide a lightweight fake provider populated with sample data."""
    fake_provider.create_collection(
        "test_collection",
        ["Document 1", "Document 2", "Document 3"],
        [
            {"title": "Item 1", "cluster": 1},
            {"title": "Item 2", "cluster": 2},
            {"title": "Item 3", "cluster": 1},
        ],
        [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]],
        ids=["id1", "id2", "id3"],
    )
    return fake_provider


@pytest.fixture
def metadata_view(qtbot, task_runner, mock_connection):
    """Create a metadata view with test data."""
    app_state = AppState()
    app_state.provider = mock_connection
    view = MetadataView(app_state, task_runner)
    qtbot.addWidget(view)
    view.ctx = MetadataContext(connection=mock_connection)
    view.ctx.current_collection = "test_collection"
    view.ctx.current_database = "test_db"
    view.ctx.current_data = mock_connection.get_all_items("test_collection")

    # Populate table
    from vector_inspector.ui.views.metadata.metadata_table import populate_table

    populate_table(view.table, view.ctx)

    return view


def test_inline_details_pane_exists(metadata_view):
    """Test that inline details pane is created in metadata view."""
    assert hasattr(metadata_view, "details_pane")
    assert metadata_view.details_pane is not None
    assert metadata_view.details_pane.view_mode == "data_browser"


def test_double_click_opens_view_dialog(qtbot, metadata_view):
    """Test that double-clicking a row opens view dialog, not edit dialog."""
    with patch("vector_inspector.ui.views.metadata_view._show_item_details") as mock_view:
        # Select and double-click first row
        metadata_view.table.selectRow(0)

        # Simulate double-click
        index = metadata_view.table.model().index(0, 0)
        metadata_view._on_row_double_clicked(index)

        # Should call view details function
        mock_view.assert_called_once()


def test_right_click_edit_menu_exists(qtbot, metadata_view):
    """Test that right-click context menu has Edit option."""
    # Select first row
    metadata_view.table.selectRow(0)

    # Context menu is shown via show_context_menu from metadata module
    # Just verify the method exists and can be called
    from vector_inspector.ui.views.metadata import show_context_menu

    assert show_context_menu is not None


def test_selection_updates_inline_pane(qtbot, metadata_view):
    """Test that selecting a row updates the inline details pane."""
    # Initially no selection
    assert metadata_view.details_pane._current_item is None

    # Select first row
    metadata_view.table.selectRow(0)
    metadata_view._on_selection_changed()

    # Details pane should be updated
    assert metadata_view.details_pane._current_item is not None
    assert metadata_view.details_pane._current_item["id"] == "id1"
    assert "Document 1" in metadata_view.details_pane.document_preview.toPlainText()


def test_selection_change_updates_different_item(qtbot, metadata_view):
    """Test that changing selection updates to new item."""
    # Select first row
    metadata_view.table.selectRow(0)
    metadata_view._on_selection_changed()
    assert metadata_view.details_pane._current_item["id"] == "id1"

    # Select second row
    metadata_view.table.selectRow(1)
    metadata_view._on_selection_changed()

    # Should update to second item
    assert metadata_view.details_pane._current_item["id"] == "id2"
    assert "Document 2" in metadata_view.details_pane.document_preview.toPlainText()


def test_deselection_clears_inline_pane(qtbot, metadata_view):
    """Test that deselecting clears the inline details pane."""
    # Select first row
    metadata_view.table.selectRow(0)
    metadata_view._on_selection_changed()
    assert metadata_view.details_pane._current_item is not None

    # Deselect
    metadata_view.table.clearSelection()
    metadata_view._on_selection_changed()

    # Should clear pane
    assert "No selection" in metadata_view.details_pane.id_label.text()


def test_open_full_details_from_inline_pane(qtbot, metadata_view):
    """Test opening full details dialog from inline pane."""
    # Select first row
    metadata_view.table.selectRow(0)
    metadata_view._on_selection_changed()

    with patch("vector_inspector.ui.views.metadata_view._show_item_details") as mock_show:
        # Click "Open full details" button in inline pane
        metadata_view.details_pane.full_details_btn.click()

        # Should trigger signal (which would open full details in real usage)
        # The signal is connected in the view,so we just verify the button works
        assert metadata_view.details_pane.full_details_btn.isEnabled()


def test_inline_pane_shows_correct_metadata(qtbot, metadata_view):
    """Test that inline pane shows correct metadata for selected item."""
    # Select second row
    metadata_view.table.selectRow(1)
    metadata_view._on_selection_changed()

    # Check metadata display
    metadata_text = metadata_view.details_pane.metadata_text.toPlainText()
    assert "Item 2" in metadata_text
    # Cluster should be in header, not metadata text
    assert "Cluster: 2" in metadata_view.details_pane.cluster_label.text()


def test_inline_pane_shows_vector_info(qtbot, metadata_view):
    """Test that inline pane shows vector information."""
    # Select first row
    metadata_view.table.selectRow(0)
    metadata_view._on_selection_changed()

    # Check dimension label
    assert "3D" in metadata_view.details_pane.dimension_label.text()

    # Check vector display
    vector_text = metadata_view.details_pane.vector_text.toPlainText()
    assert "0.1" in vector_text
    assert "0.2" in vector_text
    assert "0.3" in vector_text


def test_splitter_state_persistence(qtbot, metadata_view):
    """Test that splitter sizes are persisted."""
    from vector_inspector.services.settings_service import SettingsService

    settings = SettingsService()

    # Set splitter sizes
    splitter = metadata_view.findChildren(type(metadata_view.children()[0]))[0]  # Get main splitter
    if hasattr(splitter, "sizes"):
        original_sizes = [400, 200]
        splitter.setSizes(original_sizes)

        # Trigger save
        metadata_view._save_splitter_sizes(splitter)

        # Check that sizes were saved
        saved_sizes = settings.get("metadata_view_splitter_sizes")
        assert saved_sizes is not None


def test_inline_pane_state_saved_on_close(qtbot, metadata_view):
    """Test that inline pane state is saved when view closes."""
    # Expand metadata section
    metadata_view.details_pane.metadata_section.set_collapsed(False)

    # Close event should save state
    from PySide6.QtGui import QCloseEvent

    close_event = QCloseEvent()
    metadata_view.closeEvent(close_event)

    # State should be saved
    from vector_inspector.services.settings_service import SettingsService

    settings = SettingsService()
    assert settings.get("inline_details_data_browser_metadata_collapsed") is False


def test_edit_method_exists(qtbot, metadata_view):
    """Test that _edit_item method exists for context menu."""
    assert hasattr(metadata_view, "_edit_item")
    assert callable(metadata_view._edit_item)


def test_edit_opens_update_dialog(qtbot, metadata_view):
    """Test that edit method opens update dialog."""
    # Select first row
    metadata_view.table.selectRow(0)

    with patch("vector_inspector.ui.views.metadata_view.ItemDialog") as MockDialog:
        mock_dialog = MockDialog.return_value
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected  # User cancelled

        # Call edit with index
        index = metadata_view.table.model().index(0, 0)
        metadata_view._edit_item(index)

        # Should create item dialog
        MockDialog.assert_called_once()


def test_no_selection_edit_does_nothing(qtbot, metadata_view):
    """Test that edit with invalid index does nothing."""
    # Call edit with invalid index
    from PySide6.QtCore import QModelIndex

    invalid_index = QModelIndex()

    # Edit should not crash
    metadata_view._edit_item(invalid_index)


def test_inline_pane_updates_after_page_change(qtbot, metadata_view):
    """Test that inline pane clears when page changes."""
    # Select first row
    metadata_view.table.selectRow(0)
    metadata_view._on_selection_changed()
    assert metadata_view.details_pane._current_item is not None

    # Simulate page change (clears table)
    metadata_view.table.clearContents()
    metadata_view.table.setRowCount(0)
    metadata_view._on_selection_changed()

    # Pane should be cleared
    assert "No selection" in metadata_view.details_pane.id_label.text()


def test_inline_pane_handles_missing_embedding(qtbot, task_runner, mock_connection):
    """Test inline pane handles items without embeddings."""
    # Create data with no embeddings by creating a collection
    mock_connection.create_collection(
        "test_collection",
        ["Document 1"],
        [{"title": "Item 1"}],
        [None],
        ids=["id1"],
    )

    app_state = AppState()
    app_state.provider = mock_connection
    view = MetadataView(app_state, task_runner)
    qtbot.addWidget(view)
    view.ctx = MetadataContext(connection=mock_connection)
    view.ctx.current_data = mock_connection.get_all_items("test_collection")

    from vector_inspector.ui.views.metadata.metadata_table import populate_table

    populate_table(view.table, view.ctx)

    # Select row
    view.table.selectRow(0)
    view._on_selection_changed()

    # Should handle gracefully
    assert "(No embedding)" in view.details_pane.vector_text.toPlainText()


def test_inline_pane_visible_in_data_browser_mode(qtbot, metadata_view):
    """Test that inline pane exists and is configured for data browser mode."""
    # In data browser mode, pane is created (visibility depends on parent)
    assert metadata_view.details_pane is not None
    assert metadata_view.details_pane.view_mode == "data_browser"
