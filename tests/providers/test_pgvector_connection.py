import json
from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.core.connections.pgvector_connection import PgVectorConnection


@pytest.fixture
def mock_pgvector_conn():
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_conn, mock_cursor


def test_pgvector_connect_success(mock_pgvector_conn):
    mock_conn, _ = mock_pgvector_conn
    conn = PgVectorConnection()
    assert conn.connect() is True
    mock_conn.cursor.assert_called()


def test_pgvector_create_collection(mock_pgvector_conn):
    _, mock_cursor = mock_pgvector_conn
    conn = PgVectorConnection()
    conn.connect()
    # Simulate successful execution
    mock_cursor.execute.return_value = None
    result = conn.create_collection("test_collection", vector_size=2)
    assert result is True
    assert mock_cursor.execute.called


def test_pgvector_add_items(mock_pgvector_conn):
    _, mock_cursor = mock_pgvector_conn
    conn = PgVectorConnection()
    conn.connect()
    # Simulate successful execution
    mock_cursor.execute.return_value = None
    documents = ["doc1", "doc2"]
    metadatas = [{"type": "a"}, {"type": "b"}]
    ids = ["id1", "id2"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    result = conn.add_items("test_collection", documents=documents, metadatas=metadatas, ids=ids, embeddings=embeddings)
    assert result is True
    assert mock_cursor.execute.called


def test_pgvector_add_items_missing_embeddings_auto_embed_fails(mock_pgvector_conn):
    _, mock_cursor = mock_pgvector_conn
    conn = PgVectorConnection()
    conn.connect()
    # Patch compute_embeddings_for_documents to raise Exception
    conn.compute_embeddings_for_documents = lambda *a, **kw: (_ for _ in ()).throw(Exception("embedding failure"))
    result = conn.add_items("test_collection", documents=["doc1"], ids=["id1"])
    assert result is False


def test_pgvector_add_items_missing_embeddings_auto_embed_succeeds(mock_pgvector_conn):
    _, mock_cursor = mock_pgvector_conn
    conn = PgVectorConnection()
    conn.connect()
    # Patch compute_embeddings_for_documents to return a valid embedding
    conn.compute_embeddings_for_documents = lambda *a, **kw: [[0.1, 0.2]]
    result = conn.add_items("test_collection", documents=["doc1"], ids=["id1"])
    assert result is True
    assert mock_cursor.execute.called


def test_pgvector_get_collection_info(mock_pgvector_conn):
    _, mock_cursor = mock_pgvector_conn
    conn = PgVectorConnection()
    conn.connect()
    # Simulate fetchone returning count
    mock_cursor.fetchone.return_value = (2,)
    info = conn.get_collection_info("test_collection")
    assert info["count"] == 2


def test_pgvector_delete_collection(mock_pgvector_conn):
    _, mock_cursor = mock_pgvector_conn
    conn = PgVectorConnection()
    conn.connect()
    mock_cursor.execute.return_value = None
    result = conn.delete_collection("test_collection")
    assert result is True
    assert mock_cursor.execute.called


def test_list_collections(mock_pgvector_conn):
    mock_conn, mock_cursor = mock_pgvector_conn
    # Simulate two tables returned
    mock_cursor.fetchall.return_value = [("table1",), ("table2",)]
    conn = PgVectorConnection()
    conn.connect()
    tables = conn.list_collections()
    assert "table1" in tables and "table2" in tables


def test_list_databases_uses_client_or_tmp(mock_pgvector_conn):
    mock_conn, mock_cursor = mock_pgvector_conn
    # Simulate databases
    mock_cursor.fetchall.return_value = [("postgres",), ("mydb",)]
    conn = PgVectorConnection()
    conn.connect()
    dbs = conn.list_databases()
    assert "postgres" in dbs and "mydb" in dbs


def test_get_items_parses_metadata_and_embedding(mock_pgvector_conn):
    mock_conn, mock_cursor = mock_pgvector_conn
    # Prepare a single row with metadata JSON and string vector
    row = ("id1", "doc1", json.dumps({"a": 1}), "[0.1,0.2]")
    mock_cursor.fetchall.return_value = [row]
    # description tuples; only first element (name) is used
    mock_cursor.description = [("id",), ("document",), ("metadata",), ("embedding",)]

    conn = PgVectorConnection()
    conn.connect()
    # Stub schema so _get_table_schema doesn't try to use the same mocked fetchall
    conn._get_table_schema = lambda name: {
        "id": "text",
        "document": "text",
        "metadata": "jsonb",
        "embedding": "vector",
    }
    res = conn.get_items("coll", ["id1"])
    assert res["ids"] == ["id1"]
    assert res["documents"] == ["doc1"]
    assert res["metadatas"] == [{"a": 1}]
    assert res["embeddings"] == [[0.1, 0.2]]


def test_count_collection_returns_count(mock_pgvector_conn):
    mock_conn, mock_cursor = mock_pgvector_conn
    mock_cursor.fetchone.return_value = (42,)
    conn = PgVectorConnection()
    conn.connect()
    assert conn.count_collection("coll") == 42


def test_query_collection_returns_per_query_lists(mock_pgvector_conn):
    mock_conn, mock_cursor = mock_pgvector_conn
    # Simulate one query embedding; rows returned per query
    # Provide metadata as JSON string and embedding string
    row = ("id1", "doc1", json.dumps({"k": "v"}), "[0.5,0.6]", 0.123)
    mock_cursor.fetchall.return_value = [row]
    mock_cursor.description = [
        ("id",),
        ("document",),
        ("metadata",),
        ("embedding",),
        ("distance",),
    ]

    conn = PgVectorConnection()
    conn.connect()
    # Prevent _get_table_schema from calling the mocked fetchall for schema
    conn._get_table_schema = lambda name: {
        "id": "text",
        "document": "text",
        "metadata": "jsonb",
        "embedding": "vector",
    }
    out = conn.query_collection("coll", query_embeddings=[[0.1, 0.2]], n_results=1)
    assert out is not None
    assert isinstance(out["ids"], list)
    assert out["ids"][0] == ["id1"]
    assert out["documents"][0] == ["doc1"]
    assert out["metadatas"][0] == [{"k": "v"}]
    assert out["embeddings"][0] == [[0.5, 0.6]]


def test_get_all_items_with_limit_offset_and_where(mock_pgvector_conn):
    mock_conn, mock_cursor = mock_pgvector_conn
    row1 = ("id1", "doc1", json.dumps({"t": "x"}), "[1,2]")
    row2 = ("id2", "doc2", json.dumps({"t": "y"}), "[3,4]")
    mock_cursor.fetchall.return_value = [row1, row2]
    mock_cursor.description = [
        ("id",),
        ("document",),
        ("metadata",),
        ("embedding",),
    ]

    conn = PgVectorConnection()
    conn.connect()
    conn._get_table_schema = lambda name: {
        "id": "text",
        "document": "text",
        "metadata": "jsonb",
        "embedding": "vector",
    }
    res = conn.get_all_items("coll", limit=2, offset=0, where={"t": "x"})
    assert res is not None
    assert res["ids"] == ["id1", "id2"]


def test_update_items_generates_embeddings_when_needed(mock_pgvector_conn):
    mock_conn, mock_cursor = mock_pgvector_conn

    conn = PgVectorConnection()
    conn.connect()

    # Stub schema to include metadata JSON column
    conn._get_table_schema = lambda name: {
        "id": "text",
        "document": "text",
        "metadata": "jsonb",
        "embedding": "vector",
    }

    # compute embeddings for the one provided document
    conn.compute_embeddings_for_documents = lambda collection, docs: [[9.9, 9.8]]

    ids = ["a", "b"]
    documents = ["docA", None]
    res = conn.update_items("coll", ids, documents=documents)
    assert res is True
    assert conn._last_regenerated_count == 1


def test_delete_items_commits_and_returns_true(mock_pgvector_conn):
    mock_conn, mock_cursor = mock_pgvector_conn
    conn = PgVectorConnection()
    conn.connect()
    assert conn.delete_items("coll", ids=["x"]) is True
    assert mock_cursor.execute.called


def test_get_connection_info_reflects_connection_state(mock_pgvector_conn):
    mock_conn, mock_cursor = mock_pgvector_conn
    conn = PgVectorConnection(host="h", port=1, database="d", user="u")
    assert conn.get_connection_info()["connected"] is False
    conn.connect()
    info = conn.get_connection_info()
    assert info["host"] == "h"
    assert info["port"] == 1
    assert info["database"] == "d"
    assert info["user"] == "u"
    assert info["connected"] is True


def test_parse_vector_various_inputs():
    conn = PgVectorConnection()
    # list input
    assert conn._parse_vector([0.1, 0.2]) == [0.1, 0.2]
    # empty string
    assert conn._parse_vector("[]") == []
    # normal string
    assert conn._parse_vector("[1.0,2.0]") == [1.0, 2.0]
    # malformed string returns []
    assert conn._parse_vector("not-a-vector") == []
