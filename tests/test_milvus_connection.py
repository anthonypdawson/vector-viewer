"""Tests for Milvus connection."""

import tempfile
import pytest
from pathlib import Path

from vector_inspector.core.connections.milvus_connection import MilvusConnection


def test_milvus_connection_init():
    """Test Milvus connection initialization."""
    conn = MilvusConnection(host="localhost", port=19530)
    assert conn.host == "localhost"
    assert conn.port == 19530
    assert not conn.is_connected


def test_milvus_connection_uri():
    """Test Milvus connection with URI."""
    with tempfile.TemporaryDirectory() as tmpdir:
        uri = str(Path(tmpdir) / "milvus_lite.db")
        conn = MilvusConnection(uri=uri)
        assert conn.uri == uri
        assert not conn.is_connected


def test_milvus_create_collection():
    """Test creating a Milvus collection."""
    # Note: This test requires a running Milvus instance
    # Skip if Milvus is not available
    pytest.skip("Requires running Milvus instance")
    
    conn = MilvusConnection(host="localhost", port=19530)
    
    if not conn.connect():
        pytest.skip("Cannot connect to Milvus")
    
    try:
        # Create test collection
        success = conn.create_collection("test_collection", vector_size=384, distance="Cosine")
        assert success
        
        # Verify collection exists
        collections = conn.list_collections()
        assert "test_collection" in collections
        
        # Get collection info
        info = conn.get_collection_info("test_collection")
        assert info is not None
        assert info["name"] == "test_collection"
        assert info["vector_dimension"] == 384
        
        # Clean up
        conn.delete_collection("test_collection")
    finally:
        conn.disconnect()


def test_milvus_add_and_query():
    """Test adding items and querying in Milvus."""
    # Note: This test requires a running Milvus instance
    # Skip if Milvus is not available
    pytest.skip("Requires running Milvus instance")
    
    conn = MilvusConnection(host="localhost", port=19530)
    
    if not conn.connect():
        pytest.skip("Cannot connect to Milvus")
    
    try:
        # Create test collection
        conn.create_collection("test_query", vector_size=3, distance="Cosine")
        
        # Add test items
        documents = ["doc1", "doc2", "doc3"]
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        ids = ["id1", "id2", "id3"]
        
        success = conn.add_items(
            "test_query",
            documents=documents,
            embeddings=embeddings,
            ids=ids,
        )
        assert success
        
        # Query
        results = conn.query_collection(
            "test_query",
            query_embeddings=[[1.0, 0.0, 0.0]],
            n_results=2,
        )
        
        assert results is not None
        assert len(results["ids"]) == 1
        assert len(results["ids"][0]) <= 2
        
        # Clean up
        conn.delete_collection("test_query")
    finally:
        conn.disconnect()


def test_milvus_count_collection():
    """Test counting items in a Milvus collection."""
    # Note: This test requires a running Milvus instance
    # Skip if Milvus is not available
    pytest.skip("Requires running Milvus instance")
    
    conn = MilvusConnection(host="localhost", port=19530)
    
    if not conn.connect():
        pytest.skip("Cannot connect to Milvus")
    
    try:
        # Create and populate collection
        conn.create_collection("test_count", vector_size=2, distance="L2")
        
        documents = ["doc1", "doc2"]
        embeddings = [[1.0, 0.0], [0.0, 1.0]]
        
        conn.add_items("test_count", documents=documents, embeddings=embeddings)
        
        # Count items
        count = conn.count_collection("test_count")
        assert count == 2
        
        # Clean up
        conn.delete_collection("test_count")
    finally:
        conn.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
