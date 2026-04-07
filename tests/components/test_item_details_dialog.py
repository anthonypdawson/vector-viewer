"""Tests for ItemDetailsDialog component."""

import json
import uuid

from vector_inspector.ui.components.item_details_dialog import ItemDetailsDialog


def test_item_details_dialog_uuid_metadata_does_not_crash(qtbot):
    """Regression: UUID values in metadata must not raise TypeError (Weaviate).

    Weaviate returns UUID objects in metadata.  Before the json_safe fix:
        TypeError: Object of type UUID is not JSON serializable
    was raised in _populate_fields() -> json.dumps(filtered_metadata).
    """
    item_data = {
        "id": "test-node",
        "document": "Weaviate node document",
        "metadata": {
            "node_id": uuid.UUID("59b15ca8-89d4-47b6-abed-86fae7b46a85"),
            "ref_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            "label": "Node",
        },
        "embedding": [0.1, 0.2, 0.3],
    }

    # Must not raise
    dialog = ItemDetailsDialog(item_data=item_data, show_search_info=False)
    qtbot.addWidget(dialog)

    metadata_text = dialog.metadata_display.toPlainText()
    parsed = json.loads(metadata_text)
    assert parsed["node_id"] == "59b15ca8-89d4-47b6-abed-86fae7b46a85"
    assert parsed["label"] == "Node"


def test_item_details_dialog_mixed_non_serializable_metadata(qtbot):
    """Regression: mixed non-JSON types must not crash dialog construction."""
    import enum
    import pathlib

    class Status(enum.Enum):
        ACTIVE = "active"

    item_data = {
        "id": "test-mixed",
        "document": "doc",
        "metadata": {
            "ref": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "path": pathlib.Path("/data/file.txt"),
            "status": Status.ACTIVE,
            "tags": frozenset(["x", "y"]),
        },
        "embedding": None,
    }

    dialog = ItemDetailsDialog(item_data=item_data, show_search_info=False)
    qtbot.addWidget(dialog)

    metadata_text = dialog.metadata_display.toPlainText()
    parsed = json.loads(metadata_text)
    assert parsed["ref"] == "12345678-1234-5678-1234-567812345678"
    assert parsed["status"] == "active"
