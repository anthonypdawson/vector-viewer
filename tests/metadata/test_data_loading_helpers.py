"""Tests for data_loading_helpers (process_loaded_data and helpers)."""

import pytest
from PySide6.QtWidgets import QLabel, QPushButton, QTableWidget

from vector_inspector.core.cache_manager import CacheManager
from vector_inspector.ui.views.metadata.context import MetadataContext
from vector_inspector.ui.views.metadata.data_loading_helpers import process_loaded_data


@pytest.fixture(autouse=True)
def reset_cache_singleton():
    CacheManager._instance = None
    yield
    CacheManager._instance = None


class FakeFilterBuilder:
    def __init__(self):
        self.last_fields = None
        self._has_filters = False

    def set_available_fields(self, fields):
        self.last_fields = fields

    def has_filters(self):
        return self._has_filters


def _make_widgets(qtbot):
    table = QTableWidget()
    page_label = QLabel()
    prev_btn = QPushButton("Prev")
    next_btn = QPushButton("Next")
    status_label = QLabel()
    for w in (table, page_label, prev_btn, next_btn, status_label):
        qtbot.addWidget(w)
    return table, page_label, prev_btn, next_btn, status_label


def _make_ctx(page=0, client_filters=None, cache_manager=None):
    cm = cache_manager or CacheManager()
    return MetadataContext(
        connection=None,
        current_database="db1",
        current_collection="col1",
        cache_manager=cm,
        current_page=page,
        client_filters=client_filters or [],
    )


# ---------------------------------------------------------------------------
# process_loaded_data — empty data cases
# ---------------------------------------------------------------------------


def test_process_loaded_data_none_empties_table(qtbot):
    ctx = _make_ctx()
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    table.setRowCount(3)

    process_loaded_data(None, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder())

    assert table.rowCount() == 0


def test_process_loaded_data_no_ids_empties_table(qtbot):
    ctx = _make_ctx()
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    table.setRowCount(2)

    process_loaded_data({"ids": []}, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder())

    assert table.rowCount() == 0


def test_process_loaded_data_empty_no_page_back_sets_status(qtbot):
    ctx = _make_ctx(page=0)
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)

    process_loaded_data({}, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder())

    assert "No data" in status_label.text()


def test_process_loaded_data_empty_beyond_first_page_decrements_page(qtbot):
    ctx = _make_ctx(page=2)
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)

    process_loaded_data({}, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder())

    assert ctx.current_page == 1
    assert "No more" in status_label.text()


# ---------------------------------------------------------------------------
# process_loaded_data — server-side pagination (no client filters)
# ---------------------------------------------------------------------------


def test_process_loaded_data_server_side_populates_table(qtbot):
    data = {
        "ids": ["a", "b"],
        "documents": ["doc1", "doc2"],
        "metadatas": [{"field": "val1"}, {"field": "val2"}],
        "embeddings": None,
    }
    ctx = _make_ctx()
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)

    process_loaded_data(data, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder())

    assert table.rowCount() == 2


# ---------------------------------------------------------------------------
# process_loaded_data — client-side filtering
# ---------------------------------------------------------------------------


def test_process_loaded_data_client_filters_applied(qtbot, monkeypatch):
    """Client-side filters should be applied and filtered data rendered."""
    import vector_inspector.ui.views.metadata.data_loading_helpers as dlh

    # Pretend client filter keeps only first item
    filtered = {"ids": ["a"], "documents": ["doc1"], "metadatas": [{"field": "val1"}]}
    monkeypatch.setattr(dlh, "apply_client_side_filters", lambda data, filters: filtered)

    data = {
        "ids": ["a", "b"],
        "documents": ["doc1", "doc2"],
        "metadatas": [{"field": "val1"}, {"field": "val2"}],
    }
    ctx = _make_ctx(client_filters=[{"field": "field", "op": "=", "value": "val1"}])
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)

    process_loaded_data(data, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder())

    assert table.rowCount() == 1


def test_process_loaded_data_client_filter_all_removed_sets_zero_rows(qtbot, monkeypatch):
    import vector_inspector.ui.views.metadata.data_loading_helpers as dlh

    monkeypatch.setattr(dlh, "apply_client_side_filters", lambda data, filters: {"ids": []})

    data = {"ids": ["a"], "documents": ["d"], "metadatas": [{}]}
    ctx = _make_ctx(client_filters=[{"field": "f", "op": "=", "value": "no_match"}])
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)

    process_loaded_data(data, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder())

    assert table.rowCount() == 0
    assert "No data" in status_label.text()


# ---------------------------------------------------------------------------
# _handle_server_side_pagination — has_next_page trim branch
# ---------------------------------------------------------------------------


def test_process_loaded_data_trims_extra_items_to_page_size(qtbot):
    """When server returns page_size+1 items, data is trimmed to page_size."""
    ctx = _make_ctx()
    page_size = ctx.page_size  # 50
    ids = [f"id{i}" for i in range(page_size + 1)]
    docs = [f"doc{i}" for i in range(page_size + 1)]
    metas = [{"x": i} for i in range(page_size + 1)]
    data = {"ids": ids, "documents": docs, "metadatas": metas, "embeddings": None}

    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    process_loaded_data(data, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder())

    assert table.rowCount() == page_size


# ---------------------------------------------------------------------------
# _trim_data_to_page_size — exception-handling branches
# ---------------------------------------------------------------------------


def test_trim_data_len_raises_uses_bool_fallback():
    """len() raises → falls back to bool(); slicing still works."""
    from vector_inspector.ui.views.metadata.data_loading_helpers import _trim_data_to_page_size

    class RaisesLen:
        def __bool__(self):
            return True

        def __len__(self):
            raise TypeError("not sizeable")

        def __iter__(self):
            return iter([10, 20, 30])

        def __getitem__(self, key):
            return [10, 20, 30][key]

    data = {"ids": RaisesLen(), "documents": [], "metadatas": [], "embeddings": []}
    result = _trim_data_to_page_size(data, 2)
    assert len(result["ids"]) == 2


def test_trim_data_slice_raises_uses_list_conversion():
    """Slicing raises → falls back to list(lst)[:page_size]."""
    from vector_inspector.ui.views.metadata.data_loading_helpers import _trim_data_to_page_size

    class RaisesSlice:
        def __len__(self):
            return 3

        def __getitem__(self, key):
            if isinstance(key, slice):
                raise TypeError("no slicing")
            return [10, 20, 30][key]

        def __iter__(self):
            return iter([10, 20, 30])

    data = {"ids": RaisesSlice(), "documents": [], "metadatas": [], "embeddings": []}
    result = _trim_data_to_page_size(data, 2)
    assert result["ids"] == [10, 20]


def test_trim_data_slice_and_list_both_raise_returns_empty():
    """Both slicing and list() raise → falls back to empty list."""
    from vector_inspector.ui.views.metadata.data_loading_helpers import _trim_data_to_page_size

    class RaisesAll:
        def __len__(self):
            return 3

        def __getitem__(self, key):
            raise TypeError("no")

        def __iter__(self):
            raise TypeError("no iter")

    data = {"ids": RaisesAll(), "documents": [], "metadatas": [], "embeddings": []}
    result = _trim_data_to_page_size(data, 2)
    assert result["ids"] == []


# ---------------------------------------------------------------------------
# _save_to_cache — early return when db/collection is None
# ---------------------------------------------------------------------------


def test_save_to_cache_skips_when_database_none(qtbot):
    """_save_to_cache returns early when current_database is None."""
    from vector_inspector.ui.views.metadata.data_loading_helpers import _save_to_cache

    ctx = _make_ctx()
    ctx.current_database = None
    table, *_ = _make_widgets(qtbot)

    _save_to_cache(ctx, {"ids": ["a"]}, FakeFilterBuilder(), table)

    # Nothing should be cached (cache is empty since singleton was reset)
    assert len(ctx.cache_manager._cache) == 0


def test_save_to_cache_skips_when_collection_none(qtbot):
    """_save_to_cache returns early when current_collection is None."""
    from vector_inspector.ui.views.metadata.data_loading_helpers import _save_to_cache

    ctx = _make_ctx()
    ctx.current_collection = None
    table, *_ = _make_widgets(qtbot)

    _save_to_cache(ctx, {"ids": ["a"]}, FakeFilterBuilder(), table)

    assert len(ctx.cache_manager._cache) == 0


def test_save_to_cache_no_cache_manager(qtbot):
    """_save_to_cache returns early when cache_manager is None."""
    from vector_inspector.ui.views.metadata.data_loading_helpers import _save_to_cache

    ctx = _make_ctx()
    ctx.cache_manager = None
    table, *_ = _make_widgets(qtbot)

    # Should not raise, just return early
    _save_to_cache(ctx, {"ids": ["a"]}, FakeFilterBuilder(), table)


# ---------------------------------------------------------------------------
# _select_item_if_needed — item found in ids
# ---------------------------------------------------------------------------


def test_select_item_if_needed_selects_matching_row(qtbot):
    """When _select_id_after_load matches an id, that row is selected."""
    from PySide6.QtWidgets import QTableWidgetItem

    from vector_inspector.ui.views.metadata.data_loading_helpers import _select_item_if_needed

    table = QTableWidget(3, 1)
    qtbot.addWidget(table)
    for i in range(3):
        table.setItem(i, 0, QTableWidgetItem(f"val{i}"))

    ctx = _make_ctx()
    ctx.current_data = {"ids": ["id0", "id1", "id2"]}
    ctx._select_id_after_load = "id1"

    _select_item_if_needed(table, ctx)

    assert ctx._select_id_after_load is None
    assert table.currentRow() == 1


def test_select_item_if_needed_exception_clears_select_id(qtbot):
    """When the try block raises, except clears _select_id_after_load."""
    from vector_inspector.ui.views.metadata.data_loading_helpers import _select_item_if_needed

    class RaisesGet:
        def get(self, key, default=None):
            raise RuntimeError("boom")

    table = QTableWidget(1, 1)
    qtbot.addWidget(table)

    ctx = _make_ctx()
    ctx.current_data = RaisesGet()
    ctx._select_id_after_load = "x"

    _select_item_if_needed(table, ctx)

    assert ctx._select_id_after_load is None


# ---------------------------------------------------------------------------
# total_label update paths
# ---------------------------------------------------------------------------


def test_process_loaded_data_server_side_sets_total_label_from_response(qtbot):
    """total_count in server response data is shown in the total_label."""
    data = {
        "ids": ["a"],
        "documents": ["doc1"],
        "metadatas": [{"field": "val"}],
        "embeddings": None,
        "total_count": 42,
    }
    ctx = _make_ctx()
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    total_label = QLabel()
    qtbot.addWidget(total_label)

    process_loaded_data(
        data, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder(), total_label=total_label
    )

    assert "42" in total_label.text()


def test_process_loaded_data_server_side_empty_total_label_when_no_count(qtbot):
    """When total_count not in data, total_label should be cleared."""
    data = {"ids": ["a"], "documents": ["doc1"], "metadatas": [{}]}
    ctx = _make_ctx()
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    total_label = QLabel("old value")
    qtbot.addWidget(total_label)

    process_loaded_data(
        data, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder(), total_label=total_label
    )

    assert total_label.text() == ""


def test_process_loaded_data_client_side_sets_total_label(qtbot, monkeypatch):
    """Client-side path should show filtered total count in total_label."""
    import vector_inspector.ui.views.metadata.data_loading_helpers as dlh

    filtered = {"ids": ["a", "b"], "documents": ["d1", "d2"], "metadatas": [{}, {}]}
    monkeypatch.setattr(dlh, "apply_client_side_filters", lambda data, filters: filtered)

    data = {"ids": ["a", "b", "c"], "documents": ["d1", "d2", "d3"], "metadatas": [{}, {}, {}]}
    ctx = _make_ctx(client_filters=True)
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    total_label = QLabel()
    qtbot.addWidget(total_label)

    process_loaded_data(
        data, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder(), total_label=total_label
    )

    assert "2" in total_label.text()


def test_process_loaded_data_empty_clears_total_label(qtbot):
    """Empty data path should clear total_label."""
    ctx = _make_ctx()
    table, page_label, prev_btn, next_btn, status_label = _make_widgets(qtbot)
    total_label = QLabel("stale")
    qtbot.addWidget(total_label)

    process_loaded_data(
        {}, table, ctx, status_label, page_label, prev_btn, next_btn, FakeFilterBuilder(), total_label=total_label
    )

    assert total_label.text() == ""


def test_save_to_cache_with_to_dict_filter_builder(qtbot):
    """_save_to_cache should call filter_builder.to_dict() when available."""
    from vector_inspector.ui.views.metadata.data_loading_helpers import _save_to_cache

    class DictFilterBuilder(FakeFilterBuilder):
        def to_dict(self):
            return {"field": "x", "op": "=", "value": "y"}

    ctx = _make_ctx()
    table, *_ = _make_widgets(qtbot)

    _save_to_cache(ctx, {"ids": ["a"]}, DictFilterBuilder(), table)

    entry = ctx.cache_manager.get("db1", "col1")
    assert entry is not None
    assert entry.search_query == {"field": "x", "op": "=", "value": "y"}
