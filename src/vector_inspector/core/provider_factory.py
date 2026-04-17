"""Factory for creating vector database connections from provider configs.

Uses lazy imports to avoid loading database providers that aren't installed.
"""

from typing import Any

from vector_inspector.core.connections import get_connection_class
from vector_inspector.core.connections.base_connection import VectorDBConnection


class ProviderFactory:
    """Factory for creating database connections from configuration."""

    @staticmethod
    def create(
        provider: str, config: dict[str, Any], credentials: dict[str, Any] = None
    ) -> VectorDBConnection:
        """Create a connection object for the specified provider.

        Args:
            provider: Provider type (chromadb, qdrant, pinecone, pgvector, lancedb, weaviate)
            config: Provider-specific configuration
            credentials: Optional credentials (API keys, passwords, etc.)

        Returns:
            VectorDBConnection instance

        Raises:
            ValueError: If provider is unsupported or configuration is invalid
        """
        credentials = credentials or {}

        if provider == "chromadb":
            return ProviderFactory._create_chroma(config, credentials)
        if provider == "qdrant":
            return ProviderFactory._create_qdrant(config, credentials)
        if provider == "pinecone":
            return ProviderFactory._create_pinecone(config, credentials)
        if provider == "pgvector":
            return ProviderFactory._create_pgvector(config, credentials)
        if provider == "lancedb":
            return ProviderFactory._create_lancedb(config, credentials)
        if provider == "weaviate":
            return ProviderFactory._create_weaviate(config, credentials)
        raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def _create_lancedb(config: dict[str, Any], credentials: dict[str, Any]):
        """Create a LanceDB connection."""
        from vector_inspector.core.connections.lancedb_connection import LanceDBConnection

        uri = config.get("path", "./lancedb")
        return LanceDBConnection(uri=uri)

    @staticmethod
    def _create_chroma(config: dict[str, Any], credentials: dict[str, Any]) -> VectorDBConnection:
        """Create a ChromaDB connection."""
        connection_class = get_connection_class("chromadb")
        conn_type = config.get("type")

        if conn_type == "persistent":
            return connection_class(path=config.get("path"))
        if conn_type == "http":
            return connection_class(host=config.get("host"), port=config.get("port"))
        # ephemeral
        return connection_class()

    @staticmethod
    def _create_qdrant(config: dict[str, Any], credentials: dict[str, Any]) -> VectorDBConnection:
        """Create a Qdrant connection."""
        connection_class = get_connection_class("qdrant")
        conn_type = config.get("type")
        api_key = credentials.get("api_key")

        if conn_type == "persistent":
            return connection_class(path=config.get("path"))
        if conn_type == "http":
            return connection_class(host=config.get("host"), port=config.get("port"), api_key=api_key)
        # ephemeral
        return connection_class()

    @staticmethod
    def _create_pinecone(config: dict[str, Any], credentials: dict[str, Any]) -> VectorDBConnection:
        """Create a Pinecone connection."""
        connection_class = get_connection_class("pinecone")
        api_key = credentials.get("api_key")
        if not api_key:
            raise ValueError("Pinecone requires an API key")

        return connection_class(api_key=api_key)

    @staticmethod
    def _create_pgvector(config: dict[str, Any], credentials: dict[str, Any]) -> VectorDBConnection:
        """Create a PgVector/Postgres connection."""
        connection_class = get_connection_class("pgvector")
        conn_type = config.get("type")

        if conn_type == "http":
            host = config.get("host", "localhost")
            port = int(config.get("port", 5432))
            database = config.get("database")
            user = config.get("user")
            # Prefer password from credentials
            password = credentials.get("password")

            return connection_class(host=host, port=port, database=database, user=user, password=password)

        raise ValueError("Unsupported connection type for PgVector profile")

    @staticmethod
    def _create_weaviate(config: dict[str, Any], credentials: dict[str, Any]) -> VectorDBConnection:
        """Create a Weaviate connection."""
        connection_class = get_connection_class("weaviate")
        conn_type = config.get("type")
        api_key = credentials.get("api_key")

        if conn_type == "persistent":
            # Embedded mode
            return connection_class(
                mode="embedded",
                persistence_directory=config.get("path"),
            )
        if conn_type == "cloud":
            # Weaviate Cloud (WCD)
            return connection_class(
                url=config.get("url"),
                api_key=api_key,
                use_grpc=config.get("use_grpc", True),
            )
        if conn_type == "http":
            # Local or self-hosted HTTP
            return connection_class(
                host=config.get("host"),
                port=config.get("port"),
                api_key=api_key,
                use_grpc=config.get("use_grpc", True),
            )
        # Default to embedded ephemeral
        return connection_class(mode="embedded")
