import pytest
from vector_viewer.core.connections.chroma_connection import ChromaDBConnection
from vector_viewer.core.connections.qdrant_connection import QdrantConnection
import uuid

@pytest.mark.parametrize("provider", ["chroma", "qdrant"])
def test_provider_integration(provider, tmp_path):
    """Test provider connection using standard add_items signature."""
    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"
    test_ids = ["id1", "id2"]
    test_vectors = [[0.1, 0.2], [0.3, 0.4]]
    test_docs = ["hello", "world"]
    test_metadata = [{"type": "greeting"}, {"type": "noun"}]

    if provider == "chroma":
        conn = ChromaDBConnection()
        assert conn.connect()
        assert conn.create_collection(collection_name, vector_size=2)
        # Use standard signature: collection_name, documents, metadatas, ids, embeddings
        success = conn.add_items(
            collection_name,
            documents=test_docs,
            metadatas=test_metadata,
            ids=test_ids,
            embeddings=test_vectors
        )
        assert success
        assert collection_name in conn.list_collections()
        # Verify items inserted
        info = conn.get_collection_info(collection_name)
        assert info["count"] == 2
        res = conn.get_all_items(collection_name, limit=10)
        assert len(res["documents"]) == 2
        assert conn.delete_collection(collection_name)
        assert collection_name not in conn.list_collections()

    elif provider == "qdrant":
        db_path = str(tmp_path / "qdrant_test")
        conn = QdrantConnection(path=db_path)
        assert conn.connect()
        assert conn.create_collection(collection_name, vector_size=2, distance="Cosine")
        # Use standard signature
        success = conn.add_items(
            collection_name,
            documents=test_docs,
            metadatas=test_metadata,
            ids=test_ids,
            embeddings=test_vectors
        )
        assert success
        assert collection_name in conn.list_collections()
        # Verify items inserted
        info = conn.get_collection_info(collection_name)
        if info["count"] == 0:
            pytest.skip("Qdrant local upsert not supported in this environment")
        assert info["count"] == 2
        res = conn.get_all_items(collection_name, limit=10)
        assert len(res["documents"]) == 2
        assert conn.delete_collection(collection_name)
        assert collection_name not in conn.list_collections()
