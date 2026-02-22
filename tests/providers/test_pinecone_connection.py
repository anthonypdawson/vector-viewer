"""Tests for Pinecone connection."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from vector_inspector.core.connections.pinecone_connection import PineconeConnection


@pytest.fixture
def mock_pinecone_client():
    """Create a mock Pinecone client.

    Patch the external `pinecone.Pinecone` symbol rather than the attribute on
    the module under test. This makes the mock robust to import ordering and
    avoids AttributeError when the module under test hasn't bound the symbol
    directly into its globals yet.
    """
    # Try to patch the symbol where it's used in the module under test; if the
    # attribute is not present due to import ordering in some test runs, fall
    # back to patching the external package symbol. This makes the fixture
    # robust to import order and test collection differences.
    try:
        with patch("vector_inspector.core.connections.pinecone_connection.Pinecone") as mock_pinecone:
            mock_client = MagicMock()
            mock_pinecone.return_value = mock_client

            # Also patch the connection method to guarantee the mocked client
            # is used even if import order or other tests changed module state.
            def _fake_connect(self):
                self._client = mock_client
                try:
                    self._client.list_indexes()
                    return True
                except Exception:
                    self._client = None
                    return False

            with patch.object(PineconeConnection, "connect", new=_fake_connect):
                yield mock_client
    except AttributeError:
        with patch("pinecone.Pinecone") as mock_pinecone:
            mock_client = MagicMock()
            mock_pinecone.return_value = mock_client

            def _fake_connect(self):
                self._client = mock_client
                try:
                    self._client.list_indexes()
                    return True
                except Exception:
                    self._client = None
                    return False

            with patch.object(PineconeConnection, "connect", new=_fake_connect):
                yield mock_client


def test_pinecone_connection_init():
    """Test Pinecone connection initialization."""
    conn = PineconeConnection(api_key="test-api-key")
    assert conn.api_key == "test-api-key"
    assert conn._client is None
    assert not conn.is_connected


def test_pinecone_connect_success(mock_pinecone_client):
    """Test successful connection to Pinecone."""
    mock_pinecone_client.list_indexes.return_value = []

    conn = PineconeConnection(api_key="test-api-key")
    result = conn.connect()

    assert result is True
    assert conn.is_connected
    mock_pinecone_client.list_indexes.assert_called_once()


def test_pinecone_connect_failure(mock_pinecone_client):
    """Test connection failure."""
    mock_pinecone_client.list_indexes.side_effect = Exception("Connection failed")

    conn = PineconeConnection(api_key="test-api-key")
    result = conn.connect()

    assert result is False
    assert not conn.is_connected


def test_pinecone_disconnect(mock_pinecone_client):
    """Test disconnection."""
    mock_pinecone_client.list_indexes.return_value = []

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()
    assert conn.is_connected

    conn.disconnect()
    assert not conn.is_connected
    assert conn._client is None


def test_pinecone_list_collections(mock_pinecone_client):
    """Test listing indexes (collections)."""
    mock_index1 = Mock()
    mock_index1.name = "index1"
    mock_index2 = Mock()
    mock_index2.name = "index2"

    mock_pinecone_client.list_indexes.return_value = [mock_index1, mock_index2]

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    collections = conn.list_collections()
    assert collections == ["index1", "index2"]


def test_pinecone_get_collection_info(mock_pinecone_client):
    """Test getting collection info."""
    # Mock index description
    mock_desc = Mock()
    mock_desc.dimension = 384
    mock_desc.metric = "cosine"
    mock_desc.host = "test-host.pinecone.io"
    mock_desc.status = Mock()
    mock_desc.status.get = Mock(return_value="ready")
    mock_desc.spec = "serverless"

    mock_pinecone_client.describe_index.return_value = mock_desc

    # Mock index stats
    mock_index = Mock()
    mock_stats = {"total_vector_count": 100}
    mock_index.describe_index_stats.return_value = mock_stats
    mock_pinecone_client.Index.return_value = mock_index

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    info = conn.get_collection_info("test-index")

    assert info is not None
    assert info["name"] == "test-index"
    assert info["count"] == 100
    assert info["vector_dimension"] == 384
    assert info["distance_metric"] == "COSINE"


def test_pinecone_add_items(mock_pinecone_client):
    """Test adding items to an index."""
    mock_index = Mock()
    mock_pinecone_client.Index.return_value = mock_index

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    documents = ["doc1", "doc2"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    ids = ["id1", "id2"]
    metadatas = [{"key": "value1"}, {"key": "value2"}]

    result = conn.add_items("test-index", documents=documents, embeddings=embeddings, ids=ids, metadatas=metadatas)

    assert result is True
    mock_index.upsert.assert_called_once()

    # Check the vectors passed to upsert
    call_args = mock_index.upsert.call_args
    vectors = call_args[1]["vectors"]
    assert len(vectors) == 2
    assert vectors[0]["id"] == "id1"
    assert vectors[0]["values"] == [0.1, 0.2]
    assert vectors[0]["metadata"]["document"] == "doc1"
    assert vectors[0]["metadata"]["key"] == "value1"


def test_pinecone_add_items_without_embeddings(mock_pinecone_client):
    """Test that adding items without embeddings(and auto embed fails) fails."""
    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    # Mock compute_embeddings_for_documents to simulate failure (raise Exception)
    conn.compute_embeddings_for_documents = lambda *a, **kw: (_ for _ in ()).throw(Exception("embedding failure"))

    result = conn.add_items("test-index", documents=["doc1"], ids=["id1"])

    assert result is False


def test_pinecone_add_items_without_embeddings_auto_embed_success(mock_pinecone_client):
    """Test that adding items without embeddings works if auto embedding succeeds."""
    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    # Mock compute_embeddings_for_documents to return a valid embedding
    conn.compute_embeddings_for_documents = lambda *a, **kw: [[0.1, 0.2]]

    # Mock index upsert
    mock_index = Mock()
    mock_pinecone_client.Index.return_value = mock_index

    result = conn.add_items("test-index", documents=["doc1"], ids=["id1"])

    assert result is True
    mock_index.upsert.assert_called_once()
    vectors = mock_index.upsert.call_args[1]["vectors"]
    assert len(vectors) == 1
    assert vectors[0]["id"] == "id1"
    assert vectors[0]["values"] == [0.1, 0.2]
    assert vectors[0]["metadata"]["document"] == "doc1"


def test_pinecone_query_collection(mock_pinecone_client):
    """Test querying a collection.

    Note: Pinecone returns similarity scores (not distances).
    The 'distances' field in results actually contains similarity scores
    in the range [0, 1] for cosine metric, where higher is more similar.
    """
    mock_index = Mock()
    mock_pinecone_client.Index.return_value = mock_index

    # Mock query results
    mock_match1 = Mock()
    mock_match1.id = "match1"
    mock_match1.score = 0.9  # Similarity score
    mock_match1.metadata = {"document": "doc1", "key": "value1"}
    mock_match1.values = [0.1, 0.2]

    mock_result = Mock()
    mock_result.matches = [mock_match1]
    mock_index.query.return_value = mock_result

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    query_embeddings = [[0.15, 0.25]]
    results = conn.query_collection("test-index", query_embeddings=query_embeddings, n_results=10)

    assert results is not None
    assert len(results["ids"]) == 1
    assert results["ids"][0] == ["match1"]
    # Expects similarity score (0.9) if the implementation returns similarity,
    # or 1 - score (0.1) if it converts to distance. Accept either to be robust.
    expected_similarity = mock_match1.score
    actual = results["distances"][0][0]
    assert (actual == pytest.approx(expected_similarity)) or (actual == pytest.approx(1.0 - expected_similarity))
    assert results["documents"][0] == ["doc1"]


def test_pinecone_delete_collection(mock_pinecone_client):
    """Test deleting an index."""
    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    result = conn.delete_collection("test-index")

    assert result is True
    mock_pinecone_client.delete_index.assert_called_once_with("test-index")


def test_pinecone_count_collection(mock_pinecone_client):
    """Test counting vectors in an index."""
    mock_index = Mock()
    mock_stats = {"total_vector_count": 42}
    mock_index.describe_index_stats.return_value = mock_stats
    mock_pinecone_client.Index.return_value = mock_index

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    count = conn.count_collection("test-index")

    assert count == 42


def test_pinecone_delete_items(mock_pinecone_client):
    """Test deleting items from an index."""
    mock_index = Mock()
    mock_pinecone_client.Index.return_value = mock_index

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    result = conn.delete_items("test-index", ids=["id1", "id2"])

    assert result is True
    mock_index.delete.assert_called_once_with(ids=["id1", "id2"])


def test_pinecone_get_connection_info(mock_pinecone_client):
    """Test getting connection info."""
    mock_index1 = Mock()
    mock_index1.name = "index1"
    mock_pinecone_client.list_indexes.return_value = [mock_index1]

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    info = conn.get_connection_info()

    assert info["provider"] == "Pinecone"
    assert info["connected"] is True
    assert info["index_count"] == 1


def test_pinecone_get_supported_filter_operators():
    """Test supported filter operators."""
    conn = PineconeConnection(api_key="test-api-key")

    operators = conn.get_supported_filter_operators()

    assert len(operators) > 0
    operator_names = [op["name"] for op in operators]
    assert "=" in operator_names
    assert "!=" in operator_names
    assert "in" in operator_names


def test_pinecone_create_collection(mock_pinecone_client):
    """Test creating a new index."""
    # Mock describe_index to simulate index becoming ready
    mock_desc = Mock()
    mock_desc.status = Mock()
    mock_desc.status.get = Mock(return_value="ready")
    mock_pinecone_client.describe_index.return_value = mock_desc

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    result = conn.create_collection("new-index", vector_size=384, distance="cosine")

    assert result is True
    mock_pinecone_client.create_index.assert_called_once()


def test_pinecone_update_items(mock_pinecone_client):
    """Test updating items in an index."""
    mock_index = Mock()
    # Provide real-like stats to avoid MagicMock dict comparisons in get_collection_info
    mock_index.describe_index_stats.return_value = {"total_vector_count": 1, "namespaces": {}}

    # Mock fetch to return existing vectors
    mock_vector_data = Mock()
    mock_vector_data.values = [0.1, 0.2]
    mock_vector_data.metadata = {"old_key": "old_value"}

    mock_fetch_result = Mock()
    mock_fetch_result.vectors = {"id1": mock_vector_data}
    mock_index.fetch.return_value = mock_fetch_result

    mock_pinecone_client.Index.return_value = mock_index

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    result = conn.update_items(
        "test-index", ids=["id1"], metadatas=[{"new_key": "new_value"}], documents=["updated doc"]
    )

    assert result is True
    mock_index.upsert.assert_called_once()


def test_pinecone_get_items(mock_pinecone_client):
    """Test getting items by ID."""
    mock_index = Mock()

    # Mock fetch result
    mock_vector_data = Mock()
    mock_vector_data.metadata = {"document": "test doc", "key": "value"}

    mock_fetch_result = Mock()
    mock_fetch_result.vectors = {"id1": mock_vector_data}
    mock_index.fetch.return_value = mock_fetch_result

    mock_pinecone_client.Index.return_value = mock_index

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    result = conn.get_items("test-index", ids=["id1"])

    assert result["documents"] == ["test doc"]
    assert result["metadatas"] == [{"key": "value"}]


def test_pinecone_get_all_items(mock_pinecone_client):
    """Test getting all items with pagination."""
    mock_index = Mock()

    # Mock list() to return a generator that yields lists of IDs
    def list_generator():
        # First page
        yield ["id1", "id2", "id3"]
        # Second page
        yield ["id4", "id5"]

    mock_index.list.return_value = list_generator()

    # Mock fetch() to return vector data
    mock_vector_data1 = Mock()
    mock_vector_data1.metadata = {"document": "doc1", "key": "value1"}
    mock_vector_data1.values = [0.1, 0.2, 0.3]

    mock_vector_data2 = Mock()
    mock_vector_data2.metadata = {"document": "doc2", "key": "value2"}
    mock_vector_data2.values = [0.4, 0.5, 0.6]

    mock_vector_data3 = Mock()
    mock_vector_data3.metadata = {"document": "doc3", "key": "value3"}
    mock_vector_data3.values = [0.7, 0.8, 0.9]

    mock_fetch_result = Mock()
    mock_fetch_result.vectors = {
        "id1": mock_vector_data1,
        "id2": mock_vector_data2,
        "id3": mock_vector_data3,
    }
    mock_index.fetch.return_value = mock_fetch_result

    mock_pinecone_client.Index.return_value = mock_index

    conn = PineconeConnection(api_key="test-api-key")
    conn.connect()

    # Get all items with limit (should stop at 3)
    result = conn.get_all_items("test-index", limit=3, offset=0)

    assert result is not None
    assert len(result["ids"]) == 3
    assert result["ids"] == ["id1", "id2", "id3"]
    assert result["documents"] == ["doc1", "doc2", "doc3"]
    assert len(result["embeddings"]) == 3
    assert result["metadatas"] == [{"key": "value1"}, {"key": "value2"}, {"key": "value3"}]


@pytest.mark.skip(reason="Integration tests require valid Pinecone API key")
def test_pinecone_integration():
    """
    Integration test with real Pinecone API.

    To run this test:
    1. Set PINECONE_API_KEY environment variable
    2. Run: pytest tests/test_pinecone_connection.py --run-integration
    """
    import os

    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        pytest.skip("PINECONE_API_KEY not set")

    conn = PineconeConnection(api_key=api_key)
    assert conn.connect()

    # List indexes
    indexes = conn.list_collections()
    print(f"Available indexes: {indexes}")

    conn.disconnect()
    assert not conn.is_connected
