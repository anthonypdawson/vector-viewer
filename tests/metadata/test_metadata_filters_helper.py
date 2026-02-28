"""Tests for metadata_filters module."""

from vector_inspector.ui.views.metadata.metadata_filters import update_filter_fields


class FakeFilterBuilder:
    def __init__(self):
        self.last_fields = None

    def set_available_fields(self, fields):
        self.last_fields = fields


def test_update_filter_fields_with_metadata():
    data = {
        "ids": ["a", "b"],
        "metadatas": [{"source": "wiki", "year": 2020}, {"source": "arxiv", "year": 2021}],
    }
    fb = FakeFilterBuilder()
    update_filter_fields(fb, data)
    # Fields come from first metadata entry, sorted
    assert fb.last_fields == ["source", "year"]


def test_update_filter_fields_empty_metadatas_not_set():
    data = {"ids": [], "metadatas": []}
    fb = FakeFilterBuilder()
    update_filter_fields(fb, data)
    assert fb.last_fields is None  # set_available_fields never called


def test_update_filter_fields_none_metadata_entry_not_set():
    data = {"ids": ["a"], "metadatas": [None]}
    fb = FakeFilterBuilder()
    update_filter_fields(fb, data)
    assert fb.last_fields is None


def test_update_filter_fields_missing_metadatas_key():
    data = {"ids": ["a"]}
    fb = FakeFilterBuilder()
    update_filter_fields(fb, data)
    assert fb.last_fields is None


def test_update_filter_fields_returns_sorted_keys():
    data = {"ids": ["x"], "metadatas": [{"z_field": 1, "a_field": 2, "m_field": 3}]}
    fb = FakeFilterBuilder()
    update_filter_fields(fb, data)
    assert fb.last_fields == ["a_field", "m_field", "z_field"]
