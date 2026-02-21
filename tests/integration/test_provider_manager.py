"""Tests for services/provider_manager.py."""

from unittest.mock import MagicMock

import pytest

from vector_inspector.services.provider_manager import ProviderManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _conn_with(class_name: str, **methods) -> MagicMock:
    """Return a Mock whose class name contains `class_name`."""
    conn = MagicMock()
    conn.__class__ = type(class_name, (), {})
    for method, return_value in methods.items():
        getattr(conn, method).return_value = return_value
    return conn


# ---------------------------------------------------------------------------
# Construction & set_connection
# ---------------------------------------------------------------------------


def test_init_no_connection():
    pm = ProviderManager()
    assert pm.connection is None


def test_init_with_connection():
    conn = MagicMock()
    pm = ProviderManager(connection=conn)
    assert pm.connection is conn


def test_set_connection_updates():
    pm = ProviderManager()
    conn = MagicMock()
    pm.set_connection(conn)
    assert pm.connection is conn


def test_set_connection_to_none():
    conn = MagicMock()
    pm = ProviderManager(connection=conn)
    pm.set_connection(None)
    assert pm.connection is None


# ---------------------------------------------------------------------------
# get_databases
# ---------------------------------------------------------------------------


def test_get_databases_no_connection():
    pm = ProviderManager()
    assert pm.get_databases() == []


def test_get_databases_with_method():
    conn = MagicMock()
    conn.list_databases.return_value = ["db1", "db2"]
    pm = ProviderManager(connection=conn)
    assert pm.get_databases() == ["db1", "db2"]


def test_get_databases_no_method():
    conn = MagicMock(spec=[])  # no list_databases attr
    pm = ProviderManager(connection=conn)
    assert pm.get_databases() == []


def test_get_databases_exception_returns_empty():
    conn = MagicMock()
    conn.list_databases.side_effect = RuntimeError("boom")
    pm = ProviderManager(connection=conn)
    assert pm.get_databases() == []


# ---------------------------------------------------------------------------
# get_collections
# ---------------------------------------------------------------------------


def test_get_collections_no_connection():
    pm = ProviderManager()
    assert pm.get_collections() == []


def test_get_collections_with_method():
    conn = MagicMock()
    conn.list_collections.return_value = ["col1", "col2"]
    pm = ProviderManager(connection=conn)
    assert pm.get_collections() == ["col1", "col2"]


def test_get_collections_no_method():
    conn = MagicMock(spec=[])
    pm = ProviderManager(connection=conn)
    assert pm.get_collections() == []


def test_get_collections_exception_returns_empty():
    conn = MagicMock()
    conn.list_collections.side_effect = RuntimeError("boom")
    pm = ProviderManager(connection=conn)
    assert pm.get_collections() == []


def test_get_collections_database_arg_ignored():
    """database arg is accepted but not forwarded (current impl ignores it)."""
    conn = MagicMock()
    conn.list_collections.return_value = ["a"]
    pm = ProviderManager(connection=conn)
    assert pm.get_collections(database="mydb") == ["a"]


# ---------------------------------------------------------------------------
# get_collection_info
# ---------------------------------------------------------------------------


def test_get_collection_info_no_connection():
    pm = ProviderManager()
    assert pm.get_collection_info("col") is None


def test_get_collection_info_returns_dict():
    info = {"name": "col", "count": 10}
    conn = MagicMock()
    conn.get_collection_info.return_value = info
    pm = ProviderManager(connection=conn)
    result = pm.get_collection_info("col")
    assert result == info
    conn.get_collection_info.assert_called_once_with("col")


def test_get_collection_info_no_method():
    conn = MagicMock(spec=[])
    pm = ProviderManager(connection=conn)
    assert pm.get_collection_info("col") is None


def test_get_collection_info_exception_returns_none():
    conn = MagicMock()
    conn.get_collection_info.side_effect = RuntimeError("boom")
    pm = ProviderManager(connection=conn)
    assert pm.get_collection_info("col") is None


# ---------------------------------------------------------------------------
# get_provider_type
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "class_name, expected",
    [
        ("ChromaDBConnection", "chromadb"),
        ("QdrantConnection", "qdrant"),
        ("PineconeConnection", "pinecone"),
        ("WeaviateConnection", "weaviate"),
        ("MilvusConnection", "milvus"),
        ("LanceDBConnection", "lancedb"),
        ("PgVectorConnection", "pgvector"),
        ("UnknownConnection", None),
    ],
)
def test_get_provider_type(class_name, expected):
    conn = _conn_with(class_name)
    pm = ProviderManager(connection=conn)
    assert pm.get_provider_type() == expected


def test_get_provider_type_no_connection():
    pm = ProviderManager()
    assert pm.get_provider_type() is None


# ---------------------------------------------------------------------------
# normalize_item
# ---------------------------------------------------------------------------


def test_normalize_item_qdrant_converts_float_strings():
    pm = ProviderManager()
    item = {"id": "1", "metadata": {"score": "0.95", "label": "cat"}}
    result = pm.normalize_item(item, "qdrant")
    assert result["metadata"]["score"] == 0.95
    assert result["metadata"]["label"] == "cat"  # non-numeric string unchanged


def test_normalize_item_qdrant_non_numeric_string_unchanged():
    pm = ProviderManager()
    item = {"id": "1", "metadata": {"name": "hello"}}
    result = pm.normalize_item(item, "qdrant")
    assert result["metadata"]["name"] == "hello"


def test_normalize_item_qdrant_no_metadata_key():
    pm = ProviderManager()
    item = {"id": "1"}
    result = pm.normalize_item(item, "qdrant")
    assert result == {"id": "1"}


def test_normalize_item_chroma_renames_metadatas():
    pm = ProviderManager()
    item = {"id": "1", "metadatas": {"a": 1}}
    result = pm.normalize_item(item, "chroma")
    assert result["metadata"] == {"a": 1}


def test_normalize_item_chroma_keeps_metadata_if_present():
    pm = ProviderManager()
    item = {"id": "1", "metadata": {"a": 1}}
    result = pm.normalize_item(item, "chroma")
    # already has metadata; metadatas not present so nothing changes
    assert result["metadata"] == {"a": 1}


def test_normalize_item_weaviate_flattens_payload():
    pm = ProviderManager()
    item = {"id": "1", "payload": {"name": "foo", "score": 0.5}}
    result = pm.normalize_item(item, "weaviate")
    assert result["name"] == "foo"
    assert result["score"] == 0.5
    assert "payload" not in result


def test_normalize_item_weaviate_no_payload():
    pm = ProviderManager()
    item = {"id": "1", "metadata": {"x": 1}}
    result = pm.normalize_item(item, "weaviate")
    assert result == {"id": "1", "metadata": {"x": 1}}


def test_normalize_item_pinecone_converts_int_id():
    pm = ProviderManager()
    item = {"id": 42, "values": [0.1]}
    result = pm.normalize_item(item, "pinecone")
    assert result["id"] == "42"
    assert isinstance(result["id"], str)


def test_normalize_item_pinecone_string_id_unchanged():
    pm = ProviderManager()
    item = {"id": "abc", "values": [0.1]}
    result = pm.normalize_item(item, "pinecone")
    assert result["id"] == "abc"


def test_normalize_item_unknown_provider_passthrough():
    pm = ProviderManager()
    item = {"id": "1", "metadata": {"x": 1}}
    result = pm.normalize_item(item, "somedb")
    assert result == item


def test_normalize_item_does_not_mutate_original():
    pm = ProviderManager()
    original = {"id": 5, "values": [0.1]}
    pm.normalize_item(original, "pinecone")
    assert original["id"] == 5  # unchanged


# ---------------------------------------------------------------------------
# normalize_batch
# ---------------------------------------------------------------------------


def test_normalize_batch_empty():
    pm = ProviderManager()
    assert pm.normalize_batch([], "qdrant") == []


def test_normalize_batch_applies_to_all():
    pm = ProviderManager()
    items = [
        {"id": 1, "values": []},
        {"id": 2, "values": []},
    ]
    result = pm.normalize_batch(items, "pinecone")
    assert all(isinstance(r["id"], str) for r in result)
    assert len(result) == 2
