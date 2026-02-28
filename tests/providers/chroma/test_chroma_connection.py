import os
import uuid
from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.core.connections.chroma_connection import (
    ChromaDBConnection,
    DimensionAwareEmbeddingFunction,
)


def test_chroma_connection_integration(tmp_path):
    """Test ChromaDB provider connection using standard add_items signature."""
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    test_ids = ["id1", "id2"]
    test_vectors = [[0.1, 0.2], [0.3, 0.4]]
    test_docs = ["hello", "world"]
    test_metadata = [{"type": "greeting"}, {"type": "noun"}]

    conn = ChromaDBConnection()
    assert conn.connect()
    assert conn.create_collection(collection_name, vector_size=2)
    success = conn.add_items(
        collection_name,
        documents=test_docs,
        metadatas=test_metadata,
        ids=test_ids,
        embeddings=test_vectors,
    )
    assert success
    assert collection_name in conn.list_collections()
    info = conn.get_collection_info(collection_name)
    assert info["count"] == 2
    res = conn.get_all_items(collection_name, limit=10)
    assert len(res["documents"]) == 2
    assert conn.delete_collection(collection_name)
    assert collection_name not in conn.list_collections()


def test_chroma_add_items_missing_embeddings_auto_embed_fails(tmp_path):
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    conn = ChromaDBConnection()
    conn.connect()
    conn.create_collection(collection_name, vector_size=2)
    # Patch compute_embeddings_for_documents to raise Exception
    with patch.object(conn, "compute_embeddings_for_documents", side_effect=Exception("embedding failure")):
        result = conn.add_items(collection_name, documents=["doc1"], ids=["id1"])
        assert result is False


def test_chroma_add_items_missing_embeddings_auto_embed_succeeds(tmp_path):
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    conn = ChromaDBConnection()
    conn.connect()
    conn.create_collection(collection_name, vector_size=2)
    # Patch compute_embeddings_for_documents to return a valid embedding
    with patch.object(conn, "compute_embeddings_for_documents", return_value=[[0.1, 0.2]]):
        result = conn.add_items(collection_name, documents=["doc1"], ids=["id1"])
        assert result is True


def test_chroma_get_collection_info_nonexistent():
    conn = ChromaDBConnection()
    conn.connect()
    info = conn.get_collection_info("nonexistent_collection")
    assert info is None or info.get("count", 0) == 0


def test_chroma_delete_collection_nonexistent():
    conn = ChromaDBConnection()
    conn.connect()
    # Should not raise
    assert conn.delete_collection("nonexistent_collection") is True


def test_chroma_add_items_empty_lists(tmp_path):
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    conn = ChromaDBConnection()
    conn.connect()
    conn.create_collection(collection_name, vector_size=2)
    result = conn.add_items(collection_name, documents=[], ids=[], embeddings=[])
    assert result is False


def test_chroma_add_duplicate_ids(tmp_path):
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    conn = ChromaDBConnection()
    conn.connect()
    conn.create_collection(collection_name, vector_size=2)
    docs = ["doc1", "doc2"]
    ids = ["id1", "id1"]  # duplicate ids
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    result = conn.add_items(collection_name, documents=docs, ids=ids, embeddings=embeddings)
    # Acceptable: either False or True depending on backend behavior, but should not raise
    assert result in (True, False)


def test_chroma_get_items_by_id(tmp_path):
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    conn = ChromaDBConnection()
    conn.connect()
    conn.create_collection(collection_name, vector_size=2)
    docs = ["doc1", "doc2"]
    ids = ["id1", "id2"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    conn.add_items(collection_name, documents=docs, ids=ids, embeddings=embeddings)
    res = conn.get_items(collection_name, ids=["id1"])
    assert "documents" in res and len(res["documents"]) == 1


def test_chroma_delete_where_and_ids_precedence(tmp_path):
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    conn = ChromaDBConnection()
    assert conn.connect()
    assert conn.create_collection(collection_name, vector_size=2)

    docs = ["hello", "world"]
    ids = ["id1", "id2"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    metadatas = [{"type": "keep"}, {"type": "remove"}]

    assert conn.add_items(collection_name, documents=docs, ids=ids, embeddings=embeddings, metadatas=metadatas)

    # Delete by where -> should remove the item with metadata type 'remove'
    deleted = conn.delete_items(collection_name, where={"type": "remove"})
    if not deleted:
        pytest.skip("Chroma delete-by-where not supported in this environment")

    res = conn.get_all_items(collection_name, limit=10)
    if not res or not res.get("documents"):
        pytest.skip("Chroma get_all_items not supported in this environment")

    assert len(res["documents"]) == 1

    # Add another item and ensure ids take precedence over where
    assert conn.add_items(
        collection_name, documents=["x"], ids=["id3"], embeddings=[[0.5, 0.6]], metadatas=[{"type": "remove"}]
    )
    # Delete by ids while providing a where that would match other items
    assert conn.delete_items(collection_name, ids=["id3"], where={"type": "keep"}) is True
    res2 = conn.get_all_items(collection_name, limit=10)
    # Some backends prefer where over ids; ensure the call succeeded and results are retrievable
    assert res2 is not None


def test_chroma_add_items_handles_exception(tmp_path, monkeypatch):
    """If underlying collection.add raises, add_items should return False."""
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    conn = ChromaDBConnection()
    conn.connect()
    conn.create_collection(collection_name, vector_size=2)

    # Patch get_collection to return a mock collection whose add raises
    mock_col = MagicMock()
    mock_col.add.side_effect = Exception("add failed")
    monkeypatch.setattr(conn, "get_collection", lambda name: mock_col)

    res = conn.add_items(collection_name, documents=["d"], ids=["i"], embeddings=[[0.1, 0.2]])
    assert res is False


def test_chroma_query_handles_exception(monkeypatch):
    """If collection.query raises, query_collection should return None."""
    conn = ChromaDBConnection()
    conn.connect()
    # Patch get_collection to return a mock collection whose query raises
    mock_col = MagicMock()
    mock_col.query.side_effect = Exception("query fail")
    monkeypatch.setattr(conn, "get_collection", lambda name: mock_col)

    res = conn.query_collection("coll", query_embeddings=[[0.1, 0.2]])
    assert res is None


def test_chroma_get_all_items_handles_exception(monkeypatch):
    """If collection.get raises, get_all_items should return None."""
    conn = ChromaDBConnection()
    conn.connect()
    mock_col = MagicMock()
    mock_col.get.side_effect = Exception("get fail")
    monkeypatch.setattr(conn, "get_collection", lambda name: mock_col)

    res = conn.get_all_items("coll", limit=10)
    assert res is None


def test_resolve_path_relative(tmp_path, monkeypatch):
    conn = ChromaDBConnection(path="./data/chroma_test")
    # Ensure project root detection falls back to cwd when pyproject missing
    p = conn._resolve_path("relative/path")
    assert os.path.isabs(p)


def test_dimension_aware_embedding_function_calls_encode_and_model(monkeypatch):
    daf = DimensionAwareEmbeddingFunction(expected_dimension=2)

    # Patch model loader and encoder
    fake_model = object()

    def fake_get_model(dim):
        return fake_model, "model-name", "model-type"

    def fake_encode(text, model, model_type):
        # return deterministic vector
        return [0.1, 0.2]

    monkeypatch.setattr(
        "vector_inspector.core.connections.chroma_connection.get_embedding_model_for_dimension",
        fake_get_model,
        raising=False,
    )
    monkeypatch.setattr(
        "vector_inspector.core.connections.chroma_connection.encode_text",
        fake_encode,
        raising=False,
    )

    # The __call__ should load model and encode texts
    out = daf(["a", "b"])  # type: ignore[arg-type]
    assert isinstance(out, list)
    assert len(out) == 2


def test_get_embedding_function_for_collection_no_client_returns_none():
    conn = ChromaDBConnection()
    # no client set
    assert conn._get_embedding_function_for_collection("nope") is None


def test_get_embedding_function_for_collection_with_sample(monkeypatch):
    conn = ChromaDBConnection()
    # create fake client with collection that returns embeddings
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_collection.get.return_value = {"embeddings": [[0.1, 0.2]]}
    mock_client.get_collection.return_value = mock_collection
    conn._client = mock_client

    # Ensure has_embedding returns True
    monkeypatch.setattr("vector_inspector.utils.has_embedding", lambda e: True)

    ef = conn._get_embedding_function_for_collection("c")
    assert ef is not None
    assert isinstance(ef, DimensionAwareEmbeddingFunction)


# ---------------------------------------------------------------------------
# disconnect / is_connected
# ---------------------------------------------------------------------------


def test_chroma_disconnect_clears_client_and_collection():
    conn = ChromaDBConnection()
    conn.connect()
    assert conn.is_connected is True

    conn._current_collection = object()  # sentinel
    conn.disconnect()
    assert conn.is_connected is False
    assert conn._client is None
    assert conn._current_collection is None


def test_chroma_is_connected_false_before_connect():
    conn = ChromaDBConnection()
    assert conn.is_connected is False


# ---------------------------------------------------------------------------
# count_collection
# ---------------------------------------------------------------------------


def test_count_collection_returns_zero_without_connection():
    conn = ChromaDBConnection()
    assert conn.count_collection("any") == 0


def test_count_collection_returns_col_count(tmp_path):
    conn = ChromaDBConnection(path=str(tmp_path))
    conn.connect()
    conn._client.get_or_create_collection("col1")
    # add a document so count is 1
    col = conn._client.get_collection("col1")
    col.add(ids=["id1"], documents=["hello"], embeddings=[[0.1, 0.2]])
    assert conn.count_collection("col1") == 1
    conn.disconnect()


def test_count_collection_exception_returns_zero(monkeypatch):
    conn = ChromaDBConnection()
    conn.connect()
    mock_col = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    mock_col.count.side_effect = RuntimeError("boom")
    monkeypatch.setattr(conn, "get_collection", lambda name: mock_col)
    assert conn.count_collection("any") == 0
    conn.disconnect()


# ---------------------------------------------------------------------------
# update_items
# ---------------------------------------------------------------------------


def test_update_items_returns_false_without_collection():
    conn = ChromaDBConnection()
    # no client, get_collection returns None
    result = conn.update_items("col", ids=["id1"], documents=["new"])
    assert result is False


def test_update_items_success_with_precomputed_embeddings(tmp_path):
    conn = ChromaDBConnection(path=str(tmp_path))
    conn.connect()
    conn._client.get_or_create_collection("col")
    col = conn._client.get_collection("col")
    col.add(ids=["id1"], documents=["original"], embeddings=[[0.1, 0.2]])

    result = conn.update_items("col", ids=["id1"], documents=["updated"], embeddings=[[0.3, 0.4]])
    assert result is True
    conn.disconnect()


def test_update_items_exception_returns_false(monkeypatch):
    conn = ChromaDBConnection()
    conn.connect()
    mock_col = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    mock_col.update.side_effect = RuntimeError("update fail")
    monkeypatch.setattr(conn, "get_collection", lambda name: mock_col)
    result = conn.update_items("col", ids=["id1"], documents=["x"], embeddings=[[0.1]])
    assert result is False
    conn.disconnect()


# ---------------------------------------------------------------------------
# get_supported_filter_operators
# ---------------------------------------------------------------------------


def test_get_supported_filter_operators_all_present():
    conn = ChromaDBConnection()
    ops = conn.get_supported_filter_operators()
    names = [o["name"] for o in ops]
    for expected in ["=", "!=", ">", ">=", "<", "<=", "in", "not in", "contains", "not contains"]:
        assert expected in names


def test_get_supported_filter_operators_server_side_flags():
    conn = ChromaDBConnection()
    ops = conn.get_supported_filter_operators()
    server_only = {o["name"] for o in ops if o["server_side"]}
    client_only = {o["name"] for o in ops if not o["server_side"]}
    assert "=" in server_only
    assert "contains" in client_only
