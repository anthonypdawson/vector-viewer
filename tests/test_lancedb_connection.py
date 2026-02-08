import pytest
from vector_inspector.core.connections.lancedb_connection import LanceDBConnection
import uuid


def test_lancedb_connection_integration(tmp_path):
    """Test LanceDB provider connection using standard add_items signature."""
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    test_ids = ["id1", "id2"]
    test_vectors = [[0.1, 0.2], [0.3, 0.4]]
    test_docs = ["hello", "world"]
    test_metadata = [{"type": "greeting"}, {"type": "noun"}]

    db_path = str(tmp_path)
    conn = LanceDBConnection(uri=db_path)
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
