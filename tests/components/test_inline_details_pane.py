"""Tests for inline details pane component.

Uses pytest-qt's qtbot fixture for proper Qt widget testing.
"""

import json
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from vector_inspector.ui.components.inline_details_pane import (
    CollapsibleSection,
    InlineDetailsPane,
)


@pytest.fixture
def sample_item_data():
    """Sample item data for testing."""
    return {
        "id": "test-id-123",
        "document": "This is a test document with some content",
        "metadata": {
            "title": "Test Document",
            "created_at": "2024-01-15T10:30:00",
            "updated_at": "2024-01-16T14:20:00",
            "cluster": 2,
            "category": "test",
        },
        "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
    }


@pytest.fixture
def search_item_data(sample_item_data):
    """Sample search result item data."""
    data = sample_item_data.copy()
    data["rank"] = 1
    data["distance"] = 0.234
    return data


# CollapsibleSection Tests


def test_collapsible_section_creation(qtbot):
    """Test creating a collapsible section."""
    section = CollapsibleSection("Test Section")
    qtbot.addWidget(section)
    assert section.toggle_button.text().endswith("Test Section")
    assert section.is_collapsed() is True
    assert section.content_widget.isVisible() is False


def test_collapsible_section_toggle(qtbot):
    """Test toggling a collapsible section."""
    section = CollapsibleSection("Test Section")
    qtbot.addWidget(section)
    section.show()  # Show widget for visibility tests

    # Initially collapsed
    assert section.is_collapsed() is True

    # Toggle to expand
    section._toggle()
    assert section.is_collapsed() is False
    assert section.content_widget.isVisible() is True
    assert section.toggle_button.text().startswith("▼")

    # Toggle to collapse
    section._toggle()
    assert section.is_collapsed() is True
    assert section.content_widget.isVisible() is False
    assert section.toggle_button.text().startswith("▶")


def test_collapsible_section_set_collapsed(qtbot):
    """Test programmatically setting collapsed state."""
    section = CollapsibleSection("Test Section")
    qtbot.addWidget(section)
    section.show()  # Show widget for visibility tests

    # Set to expanded
    section.set_collapsed(False)
    assert section.is_collapsed() is False
    assert section.content_widget.isVisible() is True

    # Set to collapsed
    section.set_collapsed(True)
    assert section.is_collapsed() is True
    assert section.content_widget.isVisible() is False


# InlineDetailsPane Tests - Data Browser Mode


def test_inline_details_pane_creation_data_browser(qtbot):
    """Test creating inline details pane in data browser mode."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)

    assert pane.view_mode == "data_browser"
    # In data browser mode, starts visible (not explicitly hidden like search mode)
    # Note: isVisible() returns False until widget is shown or added to visible parent
    assert hasattr(pane, "id_label")
    assert hasattr(pane, "document_preview")
    assert hasattr(pane, "metadata_section")
    assert hasattr(pane, "vector_section")


def test_inline_details_pane_creation_search(qtbot):
    """Test creating inline details pane in search mode."""
    pane = InlineDetailsPane(view_mode="search")
    qtbot.addWidget(pane)

    assert pane.view_mode == "search"
    assert pane.isVisible() is False  # Starts hidden in search mode
    assert hasattr(pane, "rank_label")
    assert hasattr(pane, "similarity_label")


def test_update_item_with_data(qtbot, sample_item_data):
    """Test updating pane with item data."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)
    pane.update_item(sample_item_data)

    # Check header info
    assert "test-id-123" in pane.id_label.text()
    assert "5D" in pane.dimension_label.text()  # 5 dimensions
    assert "Cluster: 2" in pane.cluster_label.text()

    # Check document preview
    assert "This is a test document" in pane.document_preview.toPlainText()

    # Check metadata (should exclude displayed fields)
    metadata_text = pane.metadata_text.toPlainText()
    metadata_dict = json.loads(metadata_text)
    assert "title" in metadata_dict
    assert "category" in metadata_dict
    assert "cluster" not in metadata_dict  # Shown in header
    assert "created_at" not in metadata_dict  # Shown in header


def test_update_item_with_search_data(qtbot, search_item_data):
    """Test updating pane with search result data."""
    pane = InlineDetailsPane(view_mode="search")
    qtbot.addWidget(pane)
    pane.update_item(search_item_data)

    # Should show pane when data provided
    assert pane.isVisible() is True

    # Check search-specific fields
    assert "Rank: 1" in pane.rank_label.text()
    assert "Similarity:" in pane.similarity_label.text()
    assert "0.766" in pane.similarity_label.text()  # 1 - 0.234 = 0.766


def test_update_item_clear_display(qtbot, sample_item_data):
    """Test clearing display with None."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)

    # First populate with data
    pane.update_item(sample_item_data)
    assert "test-id-123" in pane.id_label.text()

    # Clear display
    pane.update_item(None)
    assert pane.id_label.text() == "No selection"
    assert pane.document_preview.toPlainText() == ""
    assert pane.metadata_text.toPlainText() == ""
    assert pane.vector_text.toPlainText() == ""


def test_update_item_hides_search_pane(qtbot, search_item_data):
    """Test that search mode pane hides when cleared."""
    pane = InlineDetailsPane(view_mode="search")
    qtbot.addWidget(pane)

    # Show with data
    pane.update_item(search_item_data)
    assert pane.isVisible() is True

    # Hide when cleared
    pane.update_item(None)
    assert pane.isVisible() is False


def test_update_item_long_document_truncation(qtbot):
    """Test that long documents are truncated in preview."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)

    # Create item with very long document
    long_doc = "A" * 600  # Longer than 500 char limit
    item = {
        "id": "test-id",
        "document": long_doc,
        "metadata": {},
        "embedding": [0.1, 0.2],
    }

    pane.update_item(item)
    preview_text = pane.document_preview.toPlainText()

    assert len(preview_text) <= 503  # 500 + "..."
    assert preview_text.endswith("...")


def test_update_item_no_document(qtbot):
    """Test handling item with no document."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)

    item = {
        "id": "test-id",
        "document": None,
        "metadata": {},
        "embedding": [0.1, 0.2],
    }

    pane.update_item(item)
    assert pane.document_preview.toPlainText() == "(No document text)"


def test_update_item_no_embedding(qtbot):
    """Test handling item with no embedding."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)

    item = {
        "id": "test-id",
        "document": "Test doc",
        "metadata": {},
        "embedding": None,
    }

    pane.update_item(item)
    assert pane.vector_text.toPlainText() == "(No embedding)"
    assert pane.dimension_label.text() == ""


def test_update_item_no_metadata(qtbot):
    """Test handling item with no metadata."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)

    item = {
        "id": "test-id",
        "document": "Test doc",
        "metadata": None,
        "embedding": [0.1, 0.2],
    }

    pane.update_item(item)
    assert pane.metadata_text.toPlainText() == "(No metadata)"


def test_copy_vector_to_clipboard(qtbot, sample_item_data):
    """Test copying vector to clipboard."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)
    pane.update_item(sample_item_data)

    # Trigger copy
    pane._copy_vector()

    # Check clipboard
    clipboard = QApplication.clipboard()
    clipboard_text = clipboard.text()
    assert "0.1" in clipboard_text
    assert "0.5" in clipboard_text


def test_copy_vector_json_to_clipboard(qtbot, sample_item_data):
    """Test copying vector as JSON to clipboard."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)
    pane.update_item(sample_item_data)

    # Trigger copy as JSON
    pane._copy_vector_json()

    # Check clipboard
    clipboard = QApplication.clipboard()
    clipboard_text = clipboard.text()
    data = json.loads(clipboard_text)

    assert data["id"] == "test-id-123"
    assert data["dimension"] == 5
    assert data["vector"] == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_open_full_details_signal(qtbot, sample_item_data):
    """Test that open_full_details signal is emitted."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)
    pane.update_item(sample_item_data)

    # Connect signal to mock
    mock_handler = Mock()
    pane.open_full_details.connect(mock_handler)

    # Click the button
    pane.full_details_btn.click()

    # Verify signal was emitted
    mock_handler.assert_called_once()


def test_state_persistence_save(qtbot, sample_item_data):
    """Test saving pane state."""
    from vector_inspector.services.settings_service import SettingsService

    settings = SettingsService()
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)
    pane.update_item(sample_item_data)

    # Expand metadata section
    pane.metadata_section.set_collapsed(False)

    # Save state
    pane.save_state()

    # Check settings were saved
    assert settings.get("inline_details_data_browser_metadata_collapsed") is False
    assert settings.get("inline_details_data_browser_vector_collapsed") is True


def test_state_persistence_load(qtbot):
    """Test loading pane state."""
    from vector_inspector.services.settings_service import SettingsService

    settings = SettingsService()

    # Set saved state
    settings.set("inline_details_search_metadata_collapsed", False)
    settings.set("inline_details_search_vector_collapsed", False)

    # Create pane (should load state)
    pane = InlineDetailsPane(view_mode="search")
    qtbot.addWidget(pane)

    # Verify state was loaded
    assert pane.metadata_section.is_collapsed() is False
    assert pane.vector_section.is_collapsed() is False


def test_timestamp_formatting(qtbot):
    """Test timestamp formatting in header."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)

    item = {
        "id": "test-id",
        "document": "Test",
        "metadata": {
            "created_at": "2024-01-15T10:30:00Z",
        },
        "embedding": [0.1],
    }

    pane.update_item(item)

    # Should show formatted timestamp
    timestamp_text = pane.timestamp_label.text()
    assert "2024-01-15" in timestamp_text or "10:30" in timestamp_text


def test_vector_dimension_display(qtbot):
    """Test vector dimension display in section header."""
    pane = InlineDetailsPane(view_mode="data_browser")
    qtbot.addWidget(pane)

    item = {
        "id": "test-id",
        "document": "Test",
        "metadata": {},
        "embedding": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
    }

    pane.update_item(item)

    # Vector section title should show dimension
    section_title = pane.vector_section.toggle_button.text()
    assert "7-dim" in section_title
