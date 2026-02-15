"""Test embedding handling in UI components."""

import numpy as np
from PySide6.QtWidgets import QApplication

from vector_inspector.ui.components.item_details_dialog import ItemDetailsDialog
from vector_inspector.utils import has_embedding


def test_has_embedding_utility():
    """Ensure has_embedding() handles various input types safely."""
    # Test None
    assert has_embedding(None) is False

    # Test empty list
    assert has_embedding([]) is False

    # Test list with values
    assert has_embedding([0.1, 0.2, 0.3]) is True

    # Test NumPy arrays (the key case that triggers ValueError with direct truthiness)
    assert has_embedding(np.zeros(16)) is True
    assert has_embedding(np.array([])) is False

    # Test single-element arrays
    assert has_embedding(np.array([1.0])) is True


def test_item_details_dialog_handles_numpy_embedding():
    """Ensure ItemDetailsDialog can be created with a NumPy embedding without error."""
    app = QApplication.instance() or QApplication([])

    embedding = np.zeros(16)
    item = {
        "id": "test-1",
        "document": "hello world",
        "metadata": {"foo": "bar"},
        "embedding": embedding,
    }

    dlg = ItemDetailsDialog(None, item_data=item, show_search_info=False)

    # Populate fields (constructor already calls it) and ensure vector_display exists and contains a dimension hint
    if dlg.vector_display is None:
        # If embedding widget wasn't created, that's unexpected for this test
        raise AssertionError("vector_display should be present for embedding")

    text = dlg.vector_display.toPlainText()
    assert "Dimension" in text or "dimension" in text.lower()

    # Clean up
    dlg.accept()
    try:
        app.quit()
    except Exception:
        pass


def test_item_details_dialog_handles_empty_embedding():
    """Ensure ItemDetailsDialog handles empty/None embeddings gracefully."""
    app = QApplication.instance() or QApplication([])

    # Test with None embedding
    item_none = {
        "id": "test-2",
        "document": "hello",
        "metadata": {},
        "embedding": None,
    }

    dlg_none = ItemDetailsDialog(None, item_data=item_none, show_search_info=False)
    # vector_display should not be created for None embedding
    assert dlg_none.vector_display is None
    dlg_none.accept()

    # Test with empty array
    item_empty = {
        "id": "test-3",
        "document": "world",
        "metadata": {},
        "embedding": np.array([]),
    }

    dlg_empty = ItemDetailsDialog(None, item_data=item_empty, show_search_info=False)
    # vector_display should not be created for empty embedding
    assert dlg_empty.vector_display is None
    dlg_empty.accept()

    try:
        app.quit()
    except Exception:
        pass


def test_item_details_dialog_shows_enhanced_metadata():
    """Ensure ItemDetailsDialog shows timestamps, cluster, and dimension info."""
    app = QApplication.instance() or QApplication([])

    embedding = np.random.rand(128)
    item = {
        "id": "test-enhanced",
        "document": "test document with enhanced metadata",
        "metadata": {
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": 1705318200,  # Unix timestamp
            "cluster": 3,
            "foo": "bar",
            "category": "test",
        },
        "embedding": embedding,
    }

    dlg = ItemDetailsDialog(None, item_data=item, show_search_info=False)

    # Check that timestamp fields were created
    assert dlg.created_label is not None
    assert dlg.updated_label is not None
    assert "2024-01-15" in dlg.created_label.text()

    # Check that cluster field was created
    assert dlg.cluster_label is not None
    assert "3" in dlg.cluster_label.text()

    # Check that dimension field was created
    assert dlg.dimension_label is not None
    assert "128" in dlg.dimension_label.text()

    # Check that filtered metadata doesn't include extracted fields
    metadata_text = dlg.metadata_display.toPlainText()
    assert "created_at" not in metadata_text
    assert "updated_at" not in metadata_text
    assert "cluster" not in metadata_text
    # But should still have other fields
    assert "foo" in metadata_text
    assert "category" in metadata_text

    dlg.accept()
    try:
        app.quit()
    except Exception:
        pass


def test_item_details_dialog_search_info_with_metrics():
    """Ensure ItemDetailsDialog shows search metrics when available."""
    app = QApplication.instance() or QApplication([])

    embedding = np.random.rand(64)
    item = {
        "id": "test-search",
        "document": "search result document",
        "metadata": {"label": "test"},
        "embedding": embedding,
        "distance": 0.234,
        "rank": 5,
        "dot_product": 0.876,
        "cosine_similarity": 0.766,
    }

    dlg = ItemDetailsDialog(None, item_data=item, show_search_info=True)

    # Check search fields
    assert dlg.rank_label is not None
    assert "5" in dlg.rank_label.text()

    assert dlg.distance_label is not None
    assert "0.234" in dlg.distance_label.text()

    # Check additional metrics
    assert dlg.dot_product_label is not None
    assert "0.876" in dlg.dot_product_label.text()

    assert dlg.cosine_label is not None
    assert "0.766" in dlg.cosine_label.text()

    dlg.accept()
    try:
        app.quit()
    except Exception:
        pass
