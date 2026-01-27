import pytest
from vector_inspector.core.connections.chroma_connection import ChromaDBConnection
import uuid
from unittest.mock import patch


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
    with patch.object(
        conn, "compute_embeddings_for_documents", side_effect=Exception("embedding failure")
    ):
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
