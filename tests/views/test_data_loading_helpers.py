from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget

from vector_inspector.ui.views.metadata.data_loading_helpers import (
    process_loaded_data,
)


class DummyCtx:
    def __init__(self):
        self.client_filters = False
        self.current_page = 0
        self.page_size = 10
        self.current_data = None
        self.current_data_full = None
        self.current_database = None
        self.current_collection = None
        self.cache_manager = None


def make_widgets(qtbot):
    table = QTableWidget()
    qtbot.addWidget(table)
    status = QLabel()
    qtbot.addWidget(status)
    page_label = QLabel()
    qtbot.addWidget(page_label)
    prev_btn = QPushButton()
    qtbot.addWidget(prev_btn)
    next_btn = QPushButton()
    qtbot.addWidget(next_btn)
    total_label = QLabel()
    qtbot.addWidget(total_label)
    return table, status, page_label, prev_btn, next_btn, total_label


def test_process_loaded_data_handles_empty(qtbot):
    ctx = DummyCtx()
    table, status, page_label, prev_btn, next_btn, total_label = make_widgets(qtbot)
    # Empty data dict should clear total_label and set status
    process_loaded_data({}, table, ctx, status, page_label, prev_btn, next_btn, None, total_label)
    assert table.rowCount() == 0
    assert total_label.text() == ""
    assert "No data" in status.text() or "No more data" in status.text()


def test_process_loaded_data_client_side_total_shown(qtbot):
    ctx = DummyCtx()
    ctx.client_filters = True
    table, status, page_label, prev_btn, next_btn, total_label = make_widgets(qtbot)

    data = {"ids": [1, 2, 3, 4], "documents": ["a", "b", "c", "d"]}
    # Page size smaller than total to force pagination
    ctx.page_size = 2
    process_loaded_data(data, table, ctx, status, page_label, prev_btn, next_btn, None, total_label)
    assert "Total:" in total_label.text()


def test_process_loaded_data_server_side_total_absent(qtbot):
    ctx = DummyCtx()
    table, status, page_label, prev_btn, next_btn, total_label = make_widgets(qtbot)
    # Server-side with no total_count field should leave total_label blank
    data = {"ids": [1, 2]}
    process_loaded_data(data, table, ctx, status, page_label, prev_btn, next_btn, None, total_label)
    assert total_label.text() == ""


def test_process_loaded_data_server_side_total_present(qtbot):
    ctx = DummyCtx()
    table, status, page_label, prev_btn, next_btn, total_label = make_widgets(qtbot)
    data = {"ids": [1], "total_count": 42}
    process_loaded_data(data, table, ctx, status, page_label, prev_btn, next_btn, None, total_label)
    assert "Total: 42" in total_label.text()
