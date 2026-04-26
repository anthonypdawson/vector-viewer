"""Tests verifying that query_collection returns query_embedding and query_embedding_model.

These tests validate the changes that thread the query embedding vector (and model name
where available) through every provider's query_collection return dict, so that
SearchContext can be populated after a search completes.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# ChromaDB
# ---------------------------------------------------------------------------


def test_chroma_query_collection_includes_query_embedding(tmp_path):
    """query_collection with explicit embeddings always populates query_embedding."""
    pytest.importorskip("chromadb")
    from vector_inspector.core.connections.chroma_connection import ChromaDBConnection

    col = f"qe_test_{uuid.uuid4().hex[:6]}"
    conn = ChromaDBConnection()
    assert conn.connect()
    assert conn.create_collection(col, vector_size=2)
    conn.add_items(col, documents=["doc1"], ids=["id1"], embeddings=[[0.1, 0.2]])

    emb = [0.3, 0.4]
    result = conn.query_collection(col, query_embeddings=[emb], n_results=1)

    assert result is not None
    assert "query_embedding" in result
    assert result["query_embedding"] == emb
    conn.delete_collection(col)


def test_chroma_query_collection_query_embedding_model_none_when_embeddings_provided(tmp_path):
    """When embeddings are passed directly (no texts), model name cannot be determined."""
    pytest.importorskip("chromadb")
    from vector_inspector.core.connections.chroma_connection import ChromaDBConnection

    col = f"qe_test_{uuid.uuid4().hex[:6]}"
    conn = ChromaDBConnection()
    conn.connect()
    conn.create_collection(col, vector_size=2)
    conn.add_items(col, documents=["doc1"], ids=["id1"], embeddings=[[0.1, 0.2]])

    result = conn.query_collection(col, query_embeddings=[[0.1, 0.2]], n_results=1)

    assert result is not None
    # query_embedding_model is None when embeddings are passed in directly
    assert result["query_embedding_model"] is None
    conn.delete_collection(col)


# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------


def test_qdrant_query_collection_includes_query_embedding(tmp_path):
    """query_collection with explicit embeddings populates query_embedding."""
    pytest.importorskip("qdrant_client")
    from vector_inspector.core.connections.qdrant_connection import QdrantConnection

    col = f"qe_test_{uuid.uuid4().hex[:6]}"
    db_path = str(tmp_path / "qdrant_qe")
    conn = QdrantConnection(path=db_path)
    assert conn.connect()
    assert conn.create_collection(col, vector_size=2, distance="Cosine")
    conn.add_items(col, documents=["doc1"], ids=["id1"], embeddings=[[0.1, 0.2]])

    emb = [0.1, 0.2]
    result = conn.query_collection(col, query_embeddings=[emb], n_results=1)

    assert result is not None
    assert "query_embedding" in result
    assert result["query_embedding"] == emb


def test_qdrant_query_collection_query_embedding_model_none_for_passthrough(tmp_path):
    """Model name is None when embeddings are passed directly (no text lookup)."""
    pytest.importorskip("qdrant_client")
    from vector_inspector.core.connections.qdrant_connection import QdrantConnection

    col = f"qe_test_{uuid.uuid4().hex[:6]}"
    db_path = str(tmp_path / "qdrant_qe2")
    conn = QdrantConnection(path=db_path)
    conn.connect()
    conn.create_collection(col, vector_size=2, distance="Cosine")
    conn.add_items(col, documents=["doc1"], ids=["id1"], embeddings=[[0.5, 0.5]])

    result = conn.query_collection(col, query_embeddings=[[0.5, 0.5]], n_results=1)

    assert result is not None
    assert result["query_embedding_model"] is None


# ---------------------------------------------------------------------------
# LanceDB
# ---------------------------------------------------------------------------


def test_lancedb_query_collection_includes_query_embedding(tmp_path):
    """query_collection with explicit embeddings populates query_embedding."""
    pytest.importorskip("lancedb")
    from vector_inspector.core.connections.lancedb_connection import LanceDBConnection

    col = f"qe_test_{uuid.uuid4().hex[:6]}"
    conn = LanceDBConnection(uri=str(tmp_path))
    assert conn.connect()
    assert conn.create_collection(col, vector_size=2)
    conn.add_items(col, documents=["doc1"], ids=["id1"], embeddings=[[1.0, 0.0]])

    emb = [1.0, 0.0]
    result = conn.query_collection(col, query_embeddings=[emb], n_results=1)

    assert result is not None
    assert "query_embedding" in result
    assert result["query_embedding"] == emb


def test_lancedb_query_collection_query_embedding_model_is_none(tmp_path):
    """LanceDB does not expose the model name; query_embedding_model is None."""
    pytest.importorskip("lancedb")
    from vector_inspector.core.connections.lancedb_connection import LanceDBConnection

    col = f"qe_test_{uuid.uuid4().hex[:6]}"
    conn = LanceDBConnection(uri=str(tmp_path))
    conn.connect()
    conn.create_collection(col, vector_size=2)
    conn.add_items(col, documents=["doc1"], ids=["id1"], embeddings=[[0.0, 1.0]])

    result = conn.query_collection(col, query_embeddings=[[0.0, 1.0]], n_results=1)

    assert result is not None
    assert result["query_embedding_model"] is None


# ---------------------------------------------------------------------------
# Weaviate (mock-based)
# ---------------------------------------------------------------------------


@pytest.fixture
def _mock_weaviate(monkeypatch):
    pytest.importorskip("weaviate")
    mock_weaviate = MagicMock()
    mock_client = MagicMock()
    mock_client.is_ready.return_value = True
    mock_weaviate.connect_to_local.return_value = mock_client

    monkeypatch.setattr(
        "vector_inspector.core.connections.weaviate_connection.get_weaviate_client",
        lambda: mock_weaviate,
    )
    return mock_weaviate, mock_client


def test_weaviate_query_collection_includes_query_embedding(_mock_weaviate):
    pytest.importorskip("weaviate")
    from vector_inspector.core.connections.weaviate_connection import WeaviateConnection

    _mock_wv, mock_client = _mock_weaviate

    mock_collection = MagicMock()
    mock_obj = MagicMock()
    mock_obj.uuid = uuid.uuid4()
    mock_obj.properties = {"document": "doc1"}
    mock_obj.metadata.distance = 0.1
    mock_obj.vector = [0.5, 0.5]
    mock_response = MagicMock()
    mock_response.objects = [mock_obj]
    mock_collection.query.near_vector.return_value = mock_response
    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost")
    conn.connect()

    emb = [0.5, 0.5]
    result = conn.query_collection("TestCol", query_embeddings=[emb], n_results=5)

    assert result is not None
    assert "query_embedding" in result
    assert result["query_embedding"] == emb


def test_weaviate_query_collection_query_embedding_model_is_none(_mock_weaviate):
    """Weaviate doesn't expose model name; query_embedding_model is None."""
    pytest.importorskip("weaviate")
    from vector_inspector.core.connections.weaviate_connection import WeaviateConnection

    _mock_wv, mock_client = _mock_weaviate

    mock_collection = MagicMock()
    mock_response = MagicMock()
    mock_response.objects = []
    mock_collection.query.near_vector.return_value = mock_response
    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost")
    conn.connect()

    result = conn.query_collection("TestCol", query_embeddings=[[0.1, 0.2]], n_results=1)

    assert result is not None
    assert result["query_embedding_model"] is None


# ---------------------------------------------------------------------------
# PgVector (mock-based)
# ---------------------------------------------------------------------------


@pytest.fixture
def _mock_pg():
    pytest.importorskip("psycopg2")
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_conn, mock_cursor


def test_pgvector_query_collection_includes_query_embedding(_mock_pg):
    pytest.importorskip("psycopg2")
    from vector_inspector.core.connections.pgvector_connection import PgVectorConnection

    _mock_conn, mock_cursor = _mock_pg
    row = ("id1", "doc1", json.dumps({"k": "v"}), "[0.1,0.2]", 0.05)
    mock_cursor.fetchall.return_value = [row]
    mock_cursor.description = [("id",), ("document",), ("metadata",), ("embedding",), ("distance",)]

    conn = PgVectorConnection()
    conn.connect()
    conn._get_table_schema = lambda name: {
        "id": "text",
        "document": "text",
        "metadata": "jsonb",
        "embedding": "vector",
    }

    emb = [0.1, 0.2]
    result = conn.query_collection("coll", query_embeddings=[emb], n_results=1)

    assert result is not None
    assert "query_embedding" in result
    assert result["query_embedding"] == emb


def test_pgvector_query_collection_query_embedding_model_none_for_passthrough(_mock_pg):
    """Model name is None when embeddings are passed directly."""
    pytest.importorskip("psycopg2")
    from vector_inspector.core.connections.pgvector_connection import PgVectorConnection

    _mock_conn, mock_cursor = _mock_pg
    mock_cursor.fetchall.return_value = []
    mock_cursor.description = [("id",), ("document",), ("metadata",), ("embedding",), ("distance",)]

    conn = PgVectorConnection()
    conn.connect()
    conn._get_table_schema = lambda name: {
        "id": "text",
        "document": "text",
        "metadata": "jsonb",
        "embedding": "vector",
    }

    result = conn.query_collection("coll", query_embeddings=[[0.3, 0.4]], n_results=1)

    assert result is not None
    assert result["query_embedding_model"] is None


# ---------------------------------------------------------------------------
# Pinecone (mock-based)
# ---------------------------------------------------------------------------


@pytest.fixture
def _mock_pinecone():
    pytest.importorskip("pinecone")
    from vector_inspector.core.connections.pinecone_connection import PineconeConnection

    mock_client = MagicMock()
    mock_index = MagicMock()
    mock_client.Index.return_value = mock_index

    mock_match = MagicMock()
    mock_match.id = "match1"
    mock_match.score = 0.9
    mock_match.metadata = {"document": "doc1"}
    mock_match.values = [0.1, 0.2]

    mock_result = MagicMock()
    mock_result.matches = [mock_match]
    mock_index.query.return_value = mock_result

    def _fake_connect(self):
        self._client = mock_client
        return True

    with patch("vector_inspector.core.connections.pinecone_connection.Pinecone") as mock_pinecone_cls:
        mock_pinecone_cls.return_value = mock_client
        with patch.object(PineconeConnection, "connect", new=_fake_connect):
            yield mock_client, mock_index


def test_pinecone_query_collection_includes_query_embedding(_mock_pinecone):
    pytest.importorskip("pinecone")
    from vector_inspector.core.connections.pinecone_connection import PineconeConnection

    _mock_client, _mock_index = _mock_pinecone
    conn = PineconeConnection(api_key="test-key")
    conn.connect()

    emb = [0.15, 0.25]
    result = conn.query_collection("test-index", query_embeddings=[emb], n_results=10)

    assert result is not None
    assert "query_embedding" in result
    assert result["query_embedding"] == emb


def test_pinecone_query_collection_query_embedding_model_none(_mock_pinecone):
    """Pinecone non-hosted path doesn't expose model name."""
    pytest.importorskip("pinecone")
    from vector_inspector.core.connections.pinecone_connection import PineconeConnection

    _mock_client, _mock_index = _mock_pinecone
    conn = PineconeConnection(api_key="test-key")
    conn.connect()

    result = conn.query_collection("test-index", query_embeddings=[[0.1, 0.2]], n_results=5)

    assert result is not None
    assert result["query_embedding_model"] is None
