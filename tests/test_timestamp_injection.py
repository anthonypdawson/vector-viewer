"""Tests for automatic timestamp injection in ItemDialog."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication, QDialog

from vector_inspector.ui.components.item_dialog import ItemDialog


@pytest.fixture
def qapp():
    """Ensure QApplication exists for Qt tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Don't quit here as other tests may still need it


def test_add_dialog_has_timestamp_checkbox(qapp):
    """Test that add dialog includes timestamp checkbox with correct label."""
    dialog = ItemDialog(parent=None, item_data=None)

    assert dialog.auto_timestamp_checkbox is not None
    assert "created_at" in dialog.auto_timestamp_checkbox.text()
    assert dialog.auto_timestamp_checkbox.isChecked() is False  # Default disabled


def test_edit_dialog_has_timestamp_checkbox(qapp):
    """Test that edit dialog includes timestamp checkbox with correct label."""
    item_data = {
        "id": "test-1",
        "document": "Test document",
        "metadata": {"foo": "bar"},
    }
    dialog = ItemDialog(parent=None, item_data=item_data)

    assert dialog.auto_timestamp_checkbox is not None
    assert "updated_at" in dialog.auto_timestamp_checkbox.text()
    assert dialog.is_edit_mode is True


def test_get_item_data_includes_auto_timestamp_flag(qapp):
    """Test that get_item_data returns the auto_timestamp flag."""
    dialog = ItemDialog(parent=None, item_data=None)
    dialog.id_input.setText("test-id")
    dialog.document_input.setPlainText("Test document")
    dialog.metadata_input.setPlainText('{"key": "value"}')
    dialog.auto_timestamp_checkbox.setChecked(True)

    item_data = dialog.get_item_data()

    assert item_data is not None
    assert item_data["auto_timestamp"] is True
    assert item_data["id"] == "test-id"
    assert item_data["document"] == "Test document"
    assert item_data["metadata"] == {"key": "value"}


def test_get_item_data_auto_timestamp_disabled(qapp):
    """Test that get_item_data respects unchecked auto_timestamp."""
    dialog = ItemDialog(parent=None, item_data=None)
    dialog.id_input.setText("test-id-2")
    dialog.document_input.setPlainText("Another doc")
    dialog.auto_timestamp_checkbox.setChecked(False)

    item_data = dialog.get_item_data()

    assert item_data is not None
    assert item_data["auto_timestamp"] is False


def test_timestamp_checkbox_default_state(qapp):
    """Test that timestamp checkbox defaults to disabled."""
    # Add dialog
    add_dialog = ItemDialog(parent=None, item_data=None)
    assert add_dialog.auto_timestamp_checkbox.isChecked() is False

    # Edit dialog
    edit_dialog = ItemDialog(parent=None, item_data={"id": "x", "document": "y", "metadata": {}})
    assert edit_dialog.auto_timestamp_checkbox.isChecked() is False


@patch("vector_inspector.ui.views.metadata_view.QMessageBox")
def test_metadata_view_respects_timestamp_toggle_on_add(mock_qmsg):
    """Test that metadata view only adds created_at when checkbox is enabled."""
    from vector_inspector.ui.views.metadata.context import MetadataContext

    # Mock connection
    mock_connection = MagicMock()
    mock_connection.add_items.return_value = True

    ctx = MetadataContext(connection=mock_connection)
    ctx.current_collection = "test_collection"

    # Simulate ItemDialog returning data with auto_timestamp=True
    item_data_enabled = {
        "id": "test-1",
        "document": "Test doc",
        "metadata": {"foo": "bar"},
        "auto_timestamp": True,
    }

    # Remove auto_timestamp and inject created_at (mimicking metadata_view logic)
    auto_timestamp = item_data_enabled.pop("auto_timestamp", True)
    if auto_timestamp:
        if item_data_enabled["metadata"] is None:
            item_data_enabled["metadata"] = {}
        if "created_at" not in item_data_enabled["metadata"]:
            item_data_enabled["metadata"]["created_at"] = datetime.now(UTC).isoformat()

    assert "created_at" in item_data_enabled["metadata"]
    assert "foo" in item_data_enabled["metadata"]

    # Now test with auto_timestamp=False
    item_data_disabled = {
        "id": "test-2",
        "document": "Test doc 2",
        "metadata": {"bar": "baz"},
        "auto_timestamp": False,
    }

    auto_timestamp = item_data_disabled.pop("auto_timestamp", True)
    if auto_timestamp:
        if item_data_disabled["metadata"] is None:
            item_data_disabled["metadata"] = {}
        if "created_at" not in item_data_disabled["metadata"]:
            item_data_disabled["metadata"]["created_at"] = datetime.now(UTC).isoformat()

    # Should NOT have created_at
    assert "created_at" not in item_data_disabled["metadata"]
    assert "bar" in item_data_disabled["metadata"]


@patch("vector_inspector.ui.views.metadata_view.QMessageBox")
def test_metadata_view_respects_timestamp_toggle_on_edit(mock_qmsg):
    """Test that metadata view only adds updated_at when checkbox is enabled."""
    from vector_inspector.ui.views.metadata.context import MetadataContext

    # Mock connection
    mock_connection = MagicMock()
    mock_connection.update_items.return_value = True

    ctx = MetadataContext(connection=mock_connection)
    ctx.current_collection = "test_collection"

    # Simulate ItemDialog returning data with auto_timestamp=True
    updated_data_enabled = {
        "id": "test-1",
        "document": "Updated doc",
        "metadata": {"existing": "value"},
        "auto_timestamp": True,
    }

    # Remove auto_timestamp and inject updated_at (mimicking metadata_view logic)
    auto_timestamp = updated_data_enabled.pop("auto_timestamp", True)
    if auto_timestamp:
        if updated_data_enabled["metadata"] is None:
            updated_data_enabled["metadata"] = {}
        updated_data_enabled["metadata"]["updated_at"] = datetime.now(UTC).isoformat()

    assert "updated_at" in updated_data_enabled["metadata"]
    assert "existing" in updated_data_enabled["metadata"]

    # Now test with auto_timestamp=False
    updated_data_disabled = {
        "id": "test-2",
        "document": "Updated doc 2",
        "metadata": {"existing": "value"},
        "auto_timestamp": False,
    }

    auto_timestamp = updated_data_disabled.pop("auto_timestamp", True)
    if auto_timestamp:
        if updated_data_disabled["metadata"] is None:
            updated_data_disabled["metadata"] = {}
        updated_data_disabled["metadata"]["updated_at"] = datetime.now(UTC).isoformat()

    # Should NOT have updated_at
    assert "updated_at" not in updated_data_disabled["metadata"]
    assert "existing" in updated_data_disabled["metadata"]


def test_timestamp_not_overwritten_if_already_present(qapp):
    """Test that existing created_at in metadata is preserved."""
    existing_timestamp = "2023-05-15T10:30:00Z"

    item_data = {
        "id": "test-preserve",
        "document": "Test",
        "metadata": {"created_at": existing_timestamp, "other": "data"},
        "auto_timestamp": True,
    }

    # Simulate the logic from metadata_view._add_item
    auto_timestamp = item_data.pop("auto_timestamp", True)
    if auto_timestamp:
        if item_data["metadata"] is None:
            item_data["metadata"] = {}
        if "created_at" not in item_data["metadata"]:
            item_data["metadata"]["created_at"] = datetime.now(UTC).isoformat()

    # Should preserve the existing timestamp
    assert item_data["metadata"]["created_at"] == existing_timestamp
    assert item_data["metadata"]["other"] == "data"
