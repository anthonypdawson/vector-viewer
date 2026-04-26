"""Tests for the core ProviderFactory (connection factory)."""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.core.provider_factory import ProviderFactory


# Helper to check if a provider SDK is available
def _provider_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


class TestProviderFactoryUnsupported:
    def test_unsupported_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported provider"):
            ProviderFactory.create("mysql", {})


@pytest.mark.skipif(not _provider_available("chromadb"), reason="chromadb not installed")
class TestCreateChroma:
    def test_ephemeral(self):
        with patch("vector_inspector.core.provider_factory.ChromaDBConnection") as MockChroma:
            MockChroma.return_value = MagicMock()
            conn = ProviderFactory.create("chromadb", {})
            MockChroma.assert_called_once_with()

    def test_persistent(self):
        with patch("vector_inspector.core.provider_factory.ChromaDBConnection") as MockChroma:
            MockChroma.return_value = MagicMock()
            conn = ProviderFactory.create("chromadb", {"type": "persistent", "path": "/data"})
            MockChroma.assert_called_once_with(path="/data")

    def test_http(self):
        with patch("vector_inspector.core.provider_factory.ChromaDBConnection") as MockChroma:
            MockChroma.return_value = MagicMock()
            conn = ProviderFactory.create("chromadb", {"type": "http", "host": "localhost", "port": 8000})
            MockChroma.assert_called_once_with(host="localhost", port=8000)


@pytest.mark.skipif(not _provider_available("qdrant_client"), reason="qdrant_client not installed")
class TestCreateQdrant:
    def test_ephemeral(self):
        with patch("vector_inspector.core.provider_factory.QdrantConnection") as MockQdrant:
            MockQdrant.return_value = MagicMock()
            ProviderFactory.create("qdrant", {})
            MockQdrant.assert_called_once_with()

    def test_persistent(self):
        with patch("vector_inspector.core.provider_factory.QdrantConnection") as MockQdrant:
            MockQdrant.return_value = MagicMock()
            ProviderFactory.create("qdrant", {"type": "persistent", "path": "/qdrant"})
            MockQdrant.assert_called_once_with(path="/qdrant")

    def test_http_with_api_key(self):
        with patch("vector_inspector.core.provider_factory.QdrantConnection") as MockQdrant:
            MockQdrant.return_value = MagicMock()
            ProviderFactory.create(
                "qdrant",
                {"type": "http", "host": "localhost", "port": 6333},
                {"api_key": "secret"},
            )
            MockQdrant.assert_called_once_with(host="localhost", port=6333, api_key="secret")


@pytest.mark.skipif(not _provider_available("pinecone"), reason="pinecone not installed")
class TestCreatePinecone:
    def test_requires_api_key(self):
        with pytest.raises(ValueError, match="API key"):
            ProviderFactory.create("pinecone", {}, {})

    def test_with_api_key(self):
        with patch("vector_inspector.core.provider_factory.PineconeConnection") as MockPinecone:
            MockPinecone.return_value = MagicMock()
            ProviderFactory.create("pinecone", {}, {"api_key": "pk-123"})
            MockPinecone.assert_called_once_with(api_key="pk-123")


@pytest.mark.skipif(not _provider_available("psycopg2"), reason="psycopg2 not installed")
class TestCreatePgVector:
    def test_http_type(self):
        with patch("vector_inspector.core.provider_factory.PgVectorConnection") as MockPg:
            MockPg.return_value = MagicMock()
            ProviderFactory.create(
                "pgvector",
                {
                    "type": "http",
                    "host": "db.example.com",
                    "port": "5432",
                    "database": "mydb",
                    "user": "user1",
                },
                {"password": "pw"},
            )
            MockPg.assert_called_once_with(
                host="db.example.com",
                port=5432,
                database="mydb",
                user="user1",
                password="pw",
            )

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported connection type"):
            ProviderFactory.create("pgvector", {"type": "persistent"})


@pytest.mark.skipif(not _provider_available("lancedb"), reason="lancedb not installed")
class TestCreateLanceDB:
    def test_default_path(self):
        with patch("vector_inspector.core.provider_factory.ProviderFactory._create_lancedb") as mock_lance:
            mock_lance.return_value = MagicMock()
            ProviderFactory.create("lancedb", {})
            mock_lance.assert_called_once()

    def test_custom_path(self):

        with patch("vector_inspector.core.connections.lancedb_connection.LanceDBConnection") as MockLance:
            MockLance.return_value = MagicMock()
            ProviderFactory.create("lancedb", {"path": "/custom/path"})
            MockLance.assert_called_once_with(uri="/custom/path")


@pytest.mark.skipif(not _provider_available("weaviate"), reason="weaviate not installed")
class TestCreateWeaviate:
    def test_persistent_embedded(self):
        with patch("vector_inspector.core.provider_factory.WeaviateConnection") as MockW:
            MockW.return_value = MagicMock()
            ProviderFactory.create("weaviate", {"type": "persistent", "path": "/wdata"})
            MockW.assert_called_once_with(mode="embedded", persistence_directory="/wdata")

    def test_cloud(self):
        with patch("vector_inspector.core.provider_factory.WeaviateConnection") as MockW:
            MockW.return_value = MagicMock()
            ProviderFactory.create(
                "weaviate",
                {"type": "cloud", "url": "https://mycluster.weaviate.network"},
                {"api_key": "wk-abc"},
            )
            MockW.assert_called_once_with(
                url="https://mycluster.weaviate.network",
                api_key="wk-abc",
                use_grpc=True,
            )

    def test_http(self):
        with patch("vector_inspector.core.provider_factory.WeaviateConnection") as MockW:
            MockW.return_value = MagicMock()
            ProviderFactory.create(
                "weaviate",
                {"type": "http", "host": "localhost", "port": 8080, "use_grpc": False},
                {"api_key": None},
            )
            MockW.assert_called_once_with(host="localhost", port=8080, api_key=None, use_grpc=False)

    def test_default_embedded(self):
        with patch("vector_inspector.core.provider_factory.WeaviateConnection") as MockW:
            MockW.return_value = MagicMock()
            ProviderFactory.create("weaviate", {})
            MockW.assert_called_once_with(mode="embedded")
