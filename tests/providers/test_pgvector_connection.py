import pytest
from unittest.mock import patch, MagicMock
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
    result = conn.add_items(
        "test_collection", documents=documents, metadatas=metadatas, ids=ids, embeddings=embeddings
    )
    assert result is True
    assert mock_cursor.execute.called


def test_pgvector_add_items_missing_embeddings_auto_embed_fails(mock_pgvector_conn):
    _, mock_cursor = mock_pgvector_conn
    conn = PgVectorConnection()
    conn.connect()
    # Patch compute_embeddings_for_documents to raise Exception
    conn.compute_embeddings_for_documents = lambda *a, **kw: (_ for _ in ()).throw(
        Exception("embedding failure")
    )
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
