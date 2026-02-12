from vector_inspector.ui.views.metadata.context import MetadataContext


class DummyCache:
    def __init__(self) -> None:
        self.invalidated = None

    def invalidate(self, database: str, collection: str) -> None:
        self.invalidated = (database, collection)


def test_reset_pagination() -> None:
    ctx = MetadataContext(connection=None)
    ctx.current_page = 5
    ctx.reset_pagination()
    assert ctx.current_page == 0


def test_reset_data() -> None:
    ctx = MetadataContext(connection=None)
    ctx.current_data = {"ids": [1, 2]}
    ctx.current_data_full = {"ids": [1, 2, 3]}
    ctx._select_id_after_load = "x"
    ctx.reset_data()
    assert ctx.current_data is None
    assert ctx.current_data_full is None
    assert ctx._select_id_after_load is None


def test_get_item_count_and_has_data() -> None:
    ctx = MetadataContext(connection=None)
    # no data
    assert ctx.get_item_count() == 0
    assert not ctx.has_data()

    # with items
    ctx.current_data = {"ids": ["a", "b", "c"]}
    assert ctx.get_item_count() == 3
    assert ctx.has_data()

    # empty ids
    ctx.current_data = {"ids": []}
    assert ctx.get_item_count() == 0
    assert not ctx.has_data()


def test_set_collection_resets_state() -> None:
    ctx = MetadataContext(connection=None)
    ctx.current_data = {"ids": [1]}
    ctx.current_page = 3
    ctx.set_collection("col1", "db1")
    assert ctx.current_collection == "col1"
    assert ctx.current_database == "db1"
    assert ctx.current_data is None
    assert ctx.current_page == 0


def test_invalidate_cache_calls_cache_manager() -> None:
    dummy = DummyCache()
    ctx = MetadataContext(connection=None)
    ctx.cache_manager = dummy
    ctx.current_database = "dbx"
    ctx.current_collection = "collx"
    ctx.invalidate_cache()
    assert dummy.invalidated == ("dbx", "collx")
