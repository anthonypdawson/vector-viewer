"""Tests for item_update_helpers module."""

import pytest
from PySide6.QtWidgets import QMessageBox

from vector_inspector.core.cache_manager import CacheManager
from vector_inspector.ui.views.metadata.context import MetadataContext
from vector_inspector.ui.views.metadata.item_update_helpers import (
    _show_update_success_message,
    process_item_update_success,
)


@pytest.fixture(autouse=True)
def reset_cache_singleton():
    CacheManager._instance = None
    yield
    CacheManager._instance = None


class FakeCache:
    def __init__(self):
        self.invalidated = []

    def invalidate(self, db, coll):
        self.invalidated.append((db, coll))


class FakeView:
    def __init__(self, qtbot, table=None):
        if table is None:
            from PySide6.QtWidgets import QTableWidget

            table = QTableWidget()
            qtbot.addWidget(table)
        self.table = table
        self._load_data_calls = 0

        # A mock filter_group
        class _FG:
            def isChecked(self):
                return False

        class _FB:
            def has_filters(self):
                return False

            def get_filters_split(self):
                return None, None

        self.filter_group = _FG()
        self.filter_builder = _FB()

    def _load_data(self):
        self._load_data_calls += 1


def _make_ctx(db="db1", coll="col1"):
    cm = CacheManager()
    ctx = MetadataContext(
        connection=None,
        current_database=db,
        current_collection=coll,
        cache_manager=cm,
    )
    ctx.cache_manager = FakeCache()
    return ctx


# ---------------------------------------------------------------------------
# _show_update_success_message
# ---------------------------------------------------------------------------


def test_show_update_success_generate_and_regen(qtbot, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda p, t, m: messages.append((t, m)))
    view = FakeView(qtbot)
    _show_update_success_message(view, generate_on_edit=True, regen_count=5)
    assert len(messages) == 1
    assert "regenerated" in messages[0][1].lower()


def test_show_update_success_generate_no_regen(qtbot, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda p, t, m: messages.append((t, m)))
    view = FakeView(qtbot)
    _show_update_success_message(view, generate_on_edit=True, regen_count=0)
    assert len(messages) == 1
    assert "No embeddings" in messages[0][1]


def test_show_update_success_preserve_no_regen(qtbot, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda p, t, m: messages.append((t, m)))
    view = FakeView(qtbot)
    _show_update_success_message(view, generate_on_edit=False, regen_count=0)
    assert len(messages) == 1
    assert "preserved" in messages[0][1].lower()


def test_show_update_success_preserve_with_regen(qtbot, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda p, t, m: messages.append((t, m)))
    view = FakeView(qtbot)
    _show_update_success_message(view, generate_on_edit=False, regen_count=3)
    assert len(messages) == 1


# ---------------------------------------------------------------------------
# process_item_update_success — cache invalidation
# ---------------------------------------------------------------------------


def test_process_item_update_invalidates_cache(qtbot, monkeypatch):
    import vector_inspector.ui.views.metadata as meta_pkg

    # Stub out the in-place update to simulate failure (returns False) so we reach _load_data
    monkeypatch.setattr(meta_pkg, "update_row_in_place", lambda table, ctx, data: False)
    monkeypatch.setattr(meta_pkg, "find_updated_item_page", lambda ctx, item_id: None)

    ctx = _make_ctx()
    view = FakeView(qtbot)
    updated_data = {"id": "id1", "document": "doc", "metadata": {}}

    process_item_update_success(updated_data, ctx, view, generate_on_edit=False)

    assert ("db1", "col1") in ctx.cache_manager.invalidated


def test_process_item_update_falls_back_to_load_data(qtbot, monkeypatch):
    import vector_inspector.ui.views.metadata as meta_pkg

    monkeypatch.setattr(meta_pkg, "update_row_in_place", lambda table, ctx, data: False)
    monkeypatch.setattr(meta_pkg, "find_updated_item_page", lambda ctx, item_id: None)

    ctx = _make_ctx()
    view = FakeView(qtbot)
    updated_data = {"id": "id1", "document": "doc", "metadata": {}}

    process_item_update_success(updated_data, ctx, view, generate_on_edit=False)

    assert view._load_data_calls == 1


def test_process_item_update_in_place_success_no_reload(qtbot, monkeypatch):
    import vector_inspector.ui.views.metadata.item_update_helpers as iuh

    # Patch on the module where the name is bound (from ... import update_row_in_place)
    monkeypatch.setattr(iuh, "update_row_in_place", lambda table, ctx, data: True)

    ctx = _make_ctx()
    view = FakeView(qtbot)
    updated_data = {"id": "id1", "document": "doc", "metadata": {}}

    process_item_update_success(updated_data, ctx, view, generate_on_edit=False)

    assert view._load_data_calls == 0


def test_process_item_update_with_filter_active(qtbot, monkeypatch):
    """Covers the branch when filter_group is checked and has_filters is True."""
    import vector_inspector.ui.views.metadata.item_update_helpers as iuh

    monkeypatch.setattr(iuh, "update_row_in_place", lambda table, ctx, data: False)
    monkeypatch.setattr(iuh, "find_updated_item_page", lambda ctx, item_id: None)

    ctx = _make_ctx()

    class FilterableView(FakeView):
        def __init__(self, qtbot):
            super().__init__(qtbot)

            class CheckedGroup:
                def isChecked(self):
                    return True

            class ActiveBuilder:
                def has_filters(self):
                    return True

                def get_filters_split(self):
                    return {"age": {"$gt": 18}}, []

            self.filter_group = CheckedGroup()
            self.filter_builder = ActiveBuilder()

    view = FilterableView(qtbot)
    updated_data = {"id": "id1", "document": "doc", "metadata": {}}
    process_item_update_success(updated_data, ctx, view, generate_on_edit=False)
    # server_filter should be set on ctx
    assert ctx.server_filter == {"age": {"$gt": 18}}


def test_process_item_update_navigates_to_page(qtbot, monkeypatch):
    """Covers the branch when find_updated_item_page returns a page number."""
    import vector_inspector.ui.views.metadata.item_update_helpers as iuh

    monkeypatch.setattr(iuh, "update_row_in_place", lambda table, ctx, data: False)
    monkeypatch.setattr(iuh, "find_updated_item_page", lambda ctx, item_id: 2)

    ctx = _make_ctx()
    view = FakeView(qtbot)
    updated_data = {"id": "id42", "document": "doc", "metadata": {}}

    process_item_update_success(updated_data, ctx, view, generate_on_edit=False)

    assert ctx.current_page == 2
    assert view._load_data_calls == 1
