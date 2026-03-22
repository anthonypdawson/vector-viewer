from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget

from vector_inspector.core.cache_manager import CacheEntry, CacheManager
from vector_inspector.ui.views.metadata.cache_helpers import try_load_from_cache


class DummyCtx:
    def __init__(self, cache_manager, db="db", coll="coll"):
        self.cache_manager = cache_manager
        self.current_database = db
        self.current_collection = coll
        self.page_size = 10


def make_widgets(qtbot):
    table = QTableWidget()
    qtbot.addWidget(table)
    page_label = QLabel()
    qtbot.addWidget(page_label)
    prev_btn = QPushButton()
    qtbot.addWidget(prev_btn)
    next_btn = QPushButton()
    qtbot.addWidget(next_btn)
    filter_builder = None
    status_label = QLabel()
    qtbot.addWidget(status_label)
    total_label = QLabel()
    qtbot.addWidget(total_label)
    return table, page_label, prev_btn, next_btn, filter_builder, status_label, total_label


def test_try_load_from_cache_shows_total_when_search_query(qtbot):
    cm = CacheManager()
    cm.clear()
    data = {"ids": ["a", "b", "c"]}
    entry = CacheEntry(data=data, search_query="q")
    cm.set("db", "coll", entry)

    ctx = DummyCtx(cm, db="db", coll="coll")
    table, page_label, prev_btn, next_btn, filter_builder, status_label, total_label = make_widgets(qtbot)
    ok = try_load_from_cache(ctx, table, page_label, prev_btn, next_btn, filter_builder, status_label, total_label)
    assert ok
    assert "Total:" in total_label.text()


def test_try_load_from_cache_shows_showing_when_no_search_query(qtbot):
    cm = CacheManager()
    cm.clear()
    data = {"ids": ["a"]}
    entry = CacheEntry(data=data, search_query="")
    cm.set("db", "coll", entry)

    ctx = DummyCtx(cm, db="db", coll="coll")
    table, page_label, prev_btn, next_btn, filter_builder, status_label, total_label = make_widgets(qtbot)
    ok = try_load_from_cache(ctx, table, page_label, prev_btn, next_btn, filter_builder, status_label, total_label)
    assert ok
    assert "Showing:" in total_label.text()
