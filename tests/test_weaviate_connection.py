"""Tests for Weaviate connection provider."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.core.connections.weaviate_connection import WeaviateConnection


@pytest.fixture
def mock_weaviate_client(monkeypatch):
    """Mock the Weaviate client for testing."""
    from unittest.mock import MagicMock

    # Create mock Weaviate module
    mock_weaviate = MagicMock()
    mock_client = MagicMock()

    # Configure mock client
    mock_client.is_ready.return_value = True
    mock_client.connect.return_value = None
    mock_client.close.return_value = None

    # Mock collections
    mock_collections = MagicMock()
    mock_collections.list_all.return_value = {}
    mock_client.collections = mock_collections

    # Mock connection params
    mock_connection_params = MagicMock()
    mock_weaviate.connect.ConnectionParams.from_url.return_value = mock_connection_params

    # Mock WeaviateClient constructor
    mock_weaviate.WeaviateClient.return_value = mock_client

    # Mock auth
    mock_weaviate.auth = MagicMock()

    # Mock config
    mock_config = MagicMock()
    mock_weaviate.config = mock_config

    # Patch the lazy import
    def mock_get_weaviate_client():
        return mock_weaviate

    monkeypatch.setattr(
        "vector_inspector.core.connections.weaviate_connection.get_weaviate_client",
        mock_get_weaviate_client,
    )

    return mock_weaviate, mock_client


def test_weaviate_connection_init():
    """Test Weaviate connection initialization."""
    conn = WeaviateConnection(host="localhost", port=8080)
    assert conn.host == "localhost"
    assert conn.port == 8080
    assert conn._client is None


def test_weaviate_connection_with_url():
    """Test Weaviate connection initialization with URL."""
    conn = WeaviateConnection(url="https://my-weaviate.weaviate.network")
    assert conn.url == "https://my-weaviate.weaviate.network"
    assert conn._client is None


def test_weaviate_connection_with_api_key():
    """Test Weaviate connection initialization with API key."""
    conn = WeaviateConnection(
        url="https://my-weaviate.weaviate.network", api_key="my-secret-key"
    )
    assert conn.api_key == "my-secret-key"


def test_weaviate_connect_success(mock_weaviate_client):
    """Test successful connection to Weaviate."""
    _mock_weaviate, mock_client = mock_weaviate_client

    conn = WeaviateConnection(host="localhost", port=8080)
    result = conn.connect()

    assert result is True
    assert conn.is_connected is True


def test_weaviate_connect_failure(mock_weaviate_client):
    """Test failed connection to Weaviate."""
    _mock_weaviate, mock_client = mock_weaviate_client
    mock_client.is_ready.return_value = False

    conn = WeaviateConnection(host="localhost", port=8080)
    result = conn.connect()

    assert result is False
    assert conn.is_connected is False


def test_weaviate_disconnect(mock_weaviate_client):
    """Test disconnecting from Weaviate."""
    _mock_weaviate, mock_client = mock_weaviate_client

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()
    conn.disconnect()

    assert conn._client is None
    mock_client.close.assert_called_once()


def test_weaviate_list_collections(mock_weaviate_client):
    """Test listing collections."""
    _mock_weaviate, mock_client = mock_weaviate_client
    mock_client.collections.list_all.return_value = {
        "TestCollection1": MagicMock(),
        "TestCollection2": MagicMock(),
    }

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()
    collections = conn.list_collections()

    assert "TestCollection1" in collections
    assert "TestCollection2" in collections
    assert len(collections) == 2


def test_weaviate_create_collection(mock_weaviate_client):
    """Test creating a collection."""
    mock_weaviate, mock_client = mock_weaviate_client

    # Mock the classes config
    mock_classes_config = MagicMock()
    mock_weaviate.classes = MagicMock()
    mock_weaviate.classes.config = mock_classes_config

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()
    result = conn.create_collection("TestCollection", vector_size=384, distance="Cosine")

    assert result is True
    mock_client.collections.create.assert_called_once()


def test_weaviate_delete_collection(mock_weaviate_client):
    """Test deleting a collection."""
    _mock_weaviate, mock_client = mock_weaviate_client

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()
    result = conn.delete_collection("TestCollection")

    assert result is True
    mock_client.collections.delete.assert_called_once_with("TestCollection")


def test_weaviate_add_items_with_embeddings(mock_weaviate_client):
    """Test adding items with pre-computed embeddings."""
    _mock_weaviate, mock_client = mock_weaviate_client

    # Mock collection
    mock_collection = MagicMock()
    mock_batch = MagicMock()
    mock_batch.__enter__ = MagicMock(return_value=mock_batch)
    mock_batch.__exit__ = MagicMock(return_value=False)
    mock_collection.batch.dynamic.return_value = mock_batch
    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()

    documents = ["doc1", "doc2"]
    embeddings = [[0.1, 0.2], [0.3, 0.4]]
    ids = ["id1", "id2"]

    result = conn.add_items(
        "TestCollection", documents=documents, embeddings=embeddings, ids=ids
    )

    assert result is True


def test_weaviate_add_items_empty_documents(mock_weaviate_client):
    """Test adding empty documents list."""
    _mock_weaviate, _mock_client = mock_weaviate_client

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()

    result = conn.add_items("TestCollection", documents=[], embeddings=[])

    assert result is False


def test_weaviate_add_items_auto_embed(mock_weaviate_client):
    """Test adding items with automatic embedding generation."""
    _mock_weaviate, mock_client = mock_weaviate_client

    # Mock collection
    mock_collection = MagicMock()
    mock_batch = MagicMock()
    mock_batch.__enter__ = MagicMock(return_value=mock_batch)
    mock_batch.__exit__ = MagicMock(return_value=False)
    mock_collection.batch.dynamic.return_value = mock_batch
    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()

    documents = ["doc1", "doc2"]

    # Mock compute_embeddings_for_documents
    with patch.object(
        conn, "compute_embeddings_for_documents", return_value=[[0.1, 0.2], [0.3, 0.4]]
    ):
        result = conn.add_items("TestCollection", documents=documents)

    assert result is True


def test_weaviate_get_collection_info(mock_weaviate_client):
    """Test getting collection info."""
    _mock_weaviate, mock_client = mock_weaviate_client

    # Mock collection
    mock_collection = MagicMock()
    mock_config = MagicMock()
    mock_config.vector_config = {}
    mock_collection.config.get.return_value = mock_config

    # Mock aggregate
    mock_aggregate = MagicMock()
    mock_aggregate.total_count = 10
    mock_collection.aggregate.over_all.return_value = mock_aggregate

    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()
    info = conn.get_collection_info("TestCollection")

    assert info is not None
    assert info["name"] == "TestCollection"
    assert info["count"] == 10


def test_weaviate_count_collection(mock_weaviate_client):
    """Test counting items in collection."""
    _mock_weaviate, mock_client = mock_weaviate_client

    # Mock collection
    mock_collection = MagicMock()
    mock_aggregate = MagicMock()
    mock_aggregate.total_count = 42
    mock_collection.aggregate.over_all.return_value = mock_aggregate
    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()
    count = conn.count_collection("TestCollection")

    assert count == 42


def test_weaviate_query_collection(mock_weaviate_client):
    """Test querying collection."""
    _mock_weaviate, mock_client = mock_weaviate_client

    # Mock collection
    mock_collection = MagicMock()

    # Mock query response
    mock_obj = MagicMock()
    mock_obj.uuid = uuid.uuid4()
    mock_obj.properties = {"document": "test doc", "key": "value"}
    mock_obj.metadata.distance = 0.5
    mock_obj.vector = [0.1, 0.2]

    mock_response = MagicMock()
    mock_response.objects = [mock_obj]
    mock_collection.query.near_vector.return_value = mock_response

    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()

    query_embeddings = [[0.5, 0.5]]
    result = conn.query_collection("TestCollection", query_embeddings=query_embeddings, n_results=5)

    assert result is not None
    assert "ids" in result
    assert "documents" in result
    assert len(result["ids"]) == 1


def test_weaviate_get_all_items(mock_weaviate_client):
    """Test getting all items from collection."""
    _mock_weaviate, mock_client = mock_weaviate_client

    # Mock collection
    mock_collection = MagicMock()

    # Mock objects
    mock_obj1 = MagicMock()
    mock_obj1.uuid = uuid.uuid4()
    mock_obj1.properties = {"document": "doc1", "key": "val1"}
    mock_obj1.vector = [0.1, 0.2]

    mock_obj2 = MagicMock()
    mock_obj2.uuid = uuid.uuid4()
    mock_obj2.properties = {"document": "doc2", "key": "val2"}
    mock_obj2.vector = [0.3, 0.4]

    mock_response = MagicMock()
    mock_response.objects = [mock_obj1, mock_obj2]
    mock_collection.query.fetch_objects.return_value = mock_response

    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()
    result = conn.get_all_items("TestCollection", limit=10)

    assert result is not None
    assert len(result["ids"]) == 2
    assert len(result["documents"]) == 2
    assert "doc1" in result["documents"]
    assert "doc2" in result["documents"]


def test_weaviate_update_items(mock_weaviate_client):
    """Test updating items in collection."""
    _mock_weaviate, mock_client = mock_weaviate_client

    # Mock collection
    mock_collection = MagicMock()

    # Mock existing object
    mock_existing = MagicMock()
    mock_existing.properties = {"document": "old doc", "key": "old value"}
    mock_existing.vector = [0.1, 0.2]
    mock_collection.query.fetch_object_by_id.return_value = mock_existing

    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()

    # Use a valid UUID string
    test_uuid = str(uuid.uuid4())
    result = conn.update_items(
        "TestCollection",
        ids=[test_uuid],
        documents=["new doc"],
        metadatas=[{"key": "new value"}],
        embeddings=[[0.5, 0.6]],
    )

    assert result is True
    mock_collection.data.update.assert_called_once()


def test_weaviate_delete_items_by_id(mock_weaviate_client):
    """Test deleting items by ID."""
    _mock_weaviate, mock_client = mock_weaviate_client

    # Mock collection
    mock_collection = MagicMock()
    mock_client.collections.get.return_value = mock_collection

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()

    # Use valid UUID strings
    test_uuid1 = str(uuid.uuid4())
    test_uuid2 = str(uuid.uuid4())
    result = conn.delete_items("TestCollection", ids=[test_uuid1, test_uuid2])

    assert result is True
    assert mock_collection.data.delete_by_id.call_count == 2


def test_weaviate_get_connection_info(mock_weaviate_client):
    """Test getting connection info."""
    _mock_weaviate, _mock_client = mock_weaviate_client

    conn = WeaviateConnection(host="localhost", port=8080)
    conn.connect()
    info = conn.get_connection_info()

    assert info["provider"] == "Weaviate"
    assert info["connected"] is True
    assert info["mode"] == "local"
    assert info["host"] == "localhost"
    assert info["port"] == 8080


def test_weaviate_get_connection_info_cloud():
    """Test getting connection info for cloud instance."""
    conn = WeaviateConnection(url="https://my-cluster.weaviate.network", api_key="key")
    info = conn.get_connection_info()

    assert info["provider"] == "Weaviate"
    assert info["mode"] == "cloud"
    assert "weaviate.network" in info["url"]


def test_weaviate_supported_filter_operators(mock_weaviate_client):
    """Test getting supported filter operators."""
    _mock_weaviate, _mock_client = mock_weaviate_client

    conn = WeaviateConnection(host="localhost", port=8080)
    operators = conn.get_supported_filter_operators()

    assert len(operators) > 0
    assert any(op["name"] == "=" for op in operators)
    assert any(op["name"] == "in" for op in operators)


def test_weaviate_embedded_mode_init():
    """Test Weaviate embedded mode initialization."""
    conn = WeaviateConnection(
        mode="embedded",
        persistence_directory="/tmp/weaviate_test",
        embedded_version="1.28.0",
    )
    assert conn.mode == "embedded"
    assert conn.persistence_directory == "/tmp/weaviate_test"
    assert conn.embedded_version == "1.28.0"


def test_weaviate_embedded_mode_connection(mock_weaviate_client):
    """Test connecting to Weaviate in embedded mode."""
    mock_weaviate, mock_client = mock_weaviate_client

    # Mock embedded options
    mock_embedded_options = MagicMock()
    mock_weaviate.embedded.EmbeddedOptions.return_value = mock_embedded_options

    conn = WeaviateConnection(
        mode="embedded",
        persistence_directory="/tmp/weaviate_test",
    )
    result = conn.connect()

    assert result is True
    assert conn.is_connected is True
    # Verify embedded options were used
    mock_weaviate.embedded.EmbeddedOptions.assert_called_once()


def test_weaviate_embedded_mode_auto_detect():
    """Test auto-detection of embedded mode from persistence_directory."""
    # Connection without mode but with persistence_directory should be detected as embedded
    conn = WeaviateConnection(persistence_directory="/tmp/weaviate_test")
    
    # Check that get_connection_info recognizes it as embedded
    info = conn.get_connection_info()
    assert info["mode"] == "embedded"
    assert info["persistence_directory"] == "/tmp/weaviate_test"


def test_weaviate_embedded_mode_connection_info(mock_weaviate_client):
    """Test connection info for embedded mode."""
    _mock_weaviate, _mock_client = mock_weaviate_client

    conn = WeaviateConnection(
        mode="embedded",
        persistence_directory="/tmp/weaviate_test",
        embedded_version="1.28.0",
    )
    conn.connect()
    info = conn.get_connection_info()

    assert info["provider"] == "Weaviate"
    assert info["mode"] == "embedded"
    assert info["persistence_directory"] == "/tmp/weaviate_test"
    assert info["version"] == "1.28.0"


def test_weaviate_embedded_collections(mock_weaviate_client):
    """Test that embedded mode can list collections."""
    mock_weaviate, mock_client = mock_weaviate_client

    # Mock embedded options
    mock_embedded_options = MagicMock()
    mock_weaviate.embedded.EmbeddedOptions.return_value = mock_embedded_options

    mock_client.collections.list_all.return_value = {
        "EmbeddedCollection": MagicMock(),
    }

    conn = WeaviateConnection(mode="embedded", persistence_directory="/tmp/weaviate_test")
    conn.connect()
    collections = conn.list_collections()

    assert "EmbeddedCollection" in collections

