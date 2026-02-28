"""Tests for data_operations module (background task functions)."""

import pytest

from vector_inspector.ui.views.metadata.data_operations import (
    load_collection_data,
    update_collection_item,
)


class FakeConnection:
    def __init__(self, data=None, update_success=True):
        self._data = data
        self._update_success = update_success
        self.last_get_all_args = {}
        self.last_update_args = {}

    def get_all_items(self, collection, limit=None, offset=None, where=None):
        self.last_get_all_args = dict(collection=collection, limit=limit, offset=offset, where=where)
        return self._data

    def update_items(self, collection, ids, documents=None, metadatas=None, embeddings=None):
        self.last_update_args = dict(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)
        return self._update_success


# ---------------------------------------------------------------------------
# load_collection_data
# ---------------------------------------------------------------------------


def test_load_collection_data_no_connection_raises():
    with pytest.raises(Exception, match="No database connection"):
        load_collection_data(None, "col", None, None, None)


def test_load_collection_data_returns_data():
    data = {"ids": ["a"], "documents": ["hello"]}
    conn = FakeConnection(data=data)
    result = load_collection_data(conn, "my_col", 10, 0, None)
    assert result is data
    assert conn.last_get_all_args["collection"] == "my_col"
    assert conn.last_get_all_args["limit"] == 10
    assert conn.last_get_all_args["offset"] == 0


def test_load_collection_data_passes_server_filter():
    data = {"ids": ["x"], "documents": ["doc"]}
    conn = FakeConnection(data=data)
    server_filter = {"field": {"$eq": "value"}}
    load_collection_data(conn, "col", None, None, server_filter)
    assert conn.last_get_all_args["where"] == server_filter


def test_load_collection_data_none_response_raises():
    conn = FakeConnection(data=None)
    with pytest.raises(Exception, match="Failed to load data"):
        load_collection_data(conn, "col", None, None, None)


def test_load_collection_data_empty_dict_raises():
    conn = FakeConnection(data={})
    with pytest.raises(Exception, match="Failed to load data"):
        load_collection_data(conn, "col", None, None, None)


# ---------------------------------------------------------------------------
# update_collection_item
# ---------------------------------------------------------------------------


def test_update_collection_item_no_connection_raises():
    with pytest.raises(Exception, match="No database connection"):
        update_collection_item(None, "col", {"id": "x", "document": "d", "metadata": {}})


def test_update_collection_item_success():
    item = {"id": "id1", "document": "new doc", "metadata": {"key": "val"}}
    conn = FakeConnection(update_success=True)
    result = update_collection_item(conn, "col", item)
    assert result is item
    assert conn.last_update_args["ids"] == ["id1"]
    assert conn.last_update_args["documents"] == ["new doc"]
    assert conn.last_update_args["metadatas"] == [{"key": "val"}]


def test_update_collection_item_failure_raises():
    item = {"id": "id1", "document": "doc", "metadata": {}}
    conn = FakeConnection(update_success=False)
    with pytest.raises(Exception, match="Failed to update item"):
        update_collection_item(conn, "col", item)


def test_update_collection_item_with_embeddings_arg():
    item = {"id": "id2", "document": "d2", "metadata": {}}
    conn = FakeConnection(update_success=True)
    embeddings = [[0.1, 0.2, 0.3]]
    update_collection_item(conn, "col", item, embeddings_arg=embeddings)
    assert conn.last_update_args["embeddings"] == embeddings


def test_update_collection_item_without_embeddings_arg_passes_none():
    item = {"id": "id3", "document": "d3", "metadata": {}}
    conn = FakeConnection(update_success=True)
    update_collection_item(conn, "col", item, embeddings_arg=None)
    # embeddings kwarg should not be passed (or be None) when embeddings_arg is None
    assert conn.last_update_args.get("embeddings") is None
