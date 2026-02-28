"""Tests for cache_helpers module (try_load_from_cache)."""

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget

from vector_inspector.core.cache_manager import CacheEntry, CacheManager
from vector_inspector.ui.views.metadata.cache_helpers import try_load_from_cache
from vector_inspector.ui.views.metadata.context import MetadataContext


# Reset singleton before each test
@pytest.fixture(autouse=True)
def reset_cache_singleton():
    CacheManager._instance = None
    yield
    CacheManager._instance = None


class FakeFilterBuilder:
    def __init__(self):
        self.last_fields = None

    def set_available_fields(self, fields):
        self.last_fields = fields


def _make_widgets(qtbot):
    table = QTableWidget()
    page_label = QLabel()
    prev_btn = QPushButton("Prev")
    next_btn = QPushButton("Next")
    status_label = QLabel()
    qtbot.addWidget(table)
    qtbot.addWidget(page_label)
    qtbot.addWidget(prev_btn)
    qtbot.addWidget(next_btn)
    qtbot.addWidget(status_label)
    return table, page_label, prev_btn, next_btn, status_label


def _make_ctx():
    cm = CacheManager()
    return MetadataContext(connection=None, current_database="db1", current_collection="col1", cache_manager=cm)


def test_try_load_from_cache_miss_returns_false(qtbot):
    ctx = _make_ctx()
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    fb = FakeFilterBuilder()

    result = try_load_from_cache(ctx, table, page_label, prev_btn, next_btn, fb, status_label)
    assert result is False


def test_try_load_from_cache_hit_returns_true(qtbot):
    ctx = _make_ctx()
    data = {"ids": ["a", "b"], "documents": ["doc1", "doc2"], "metadatas": [{}, {}]}
    ctx.cache_manager.set("db1", "col1", CacheEntry(data=data))

    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    fb = FakeFilterBuilder()

    result = try_load_from_cache(ctx, table, page_label, prev_btn, next_btn, fb, status_label)
    assert result is True


def test_try_load_from_cache_hit_sets_status_label(qtbot):
    ctx = _make_ctx()
    data = {"ids": ["x"], "documents": ["d"], "metadatas": [{"k": "v"}]}
    ctx.cache_manager.set("db1", "col1", CacheEntry(data=data))

    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    fb = FakeFilterBuilder()

    try_load_from_cache(ctx, table, page_label, prev_btn, next_btn, fb, status_label)
    assert "cache" in status_label.text().lower() or "1" in status_label.text()


def test_try_load_from_cache_with_search_query(qtbot):
    ctx = _make_ctx()
    data = {"ids": ["a"] * 60, "documents": ["d"] * 60, "metadatas": [{}] * 60}
    ctx.cache_manager.set("db1", "col1", CacheEntry(data=data, search_query="test query"))

    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    fb = FakeFilterBuilder()

    result = try_load_from_cache(ctx, table, page_label, prev_btn, next_btn, fb, status_label)
    assert result is True


def test_try_load_from_cache_full_page_enables_next(qtbot):
    """Cache hit with exactly page_size items should enable Next button."""
    ctx = _make_ctx()
    ctx.page_size = 3
    data = {"ids": ["a", "b", "c"], "documents": ["d"] * 3, "metadatas": [{}] * 3}
    ctx.cache_manager.set("db1", "col1", CacheEntry(data=data))

    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    fb = FakeFilterBuilder()

    try_load_from_cache(ctx, table, page_label, prev_btn, next_btn, fb, status_label)
    assert next_btn.isEnabled() is True


def test_try_load_from_cache_partial_page_disables_next(qtbot):
    """Cache hit with fewer than page_size items should disable Next button."""
    ctx = _make_ctx()
    ctx.page_size = 50
    data = {"ids": ["a", "b"], "documents": ["d", "d"], "metadatas": [{}, {}]}
    ctx.cache_manager.set("db1", "col1", CacheEntry(data=data))

    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    fb = FakeFilterBuilder()

    try_load_from_cache(ctx, table, page_label, prev_btn, next_btn, fb, status_label)
    assert next_btn.isEnabled() is False
