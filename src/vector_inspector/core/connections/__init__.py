"""Connection managers for vector databases.

IMPORTANT: Connection classes are imported lazily to avoid import errors
when database providers are not installed. Use get_connection_class() to
retrieve a connection class safely.
"""

from .base_connection import VectorDBConnection

__all__ = [
    "VectorDBConnection",
    "get_connection_class",
]


def get_connection_class(provider: str):
    """Get connection class for a provider, with lazy import.

    Args:
        provider: Provider name (chromadb, qdrant, pinecone, etc.)

    Returns:
        Connection class for the provider

    Raises:
        ImportError: If provider package is not installed
        ValueError: If provider is not supported
    """
    # Lazy imports - only import when actually needed
    if provider == "chromadb":
        from .chroma_connection import ChromaDBConnection

        return ChromaDBConnection
    elif provider == "qdrant":
        from .qdrant_connection import QdrantConnection

        return QdrantConnection
    elif provider == "pinecone":
        from .pinecone_connection import PineconeConnection

        return PineconeConnection
    elif provider == "lancedb":
        from .lancedb_connection import LanceDBConnection

        return LanceDBConnection
    elif provider == "pgvector":
        from .pgvector_connection import PgVectorConnection

        return PgVectorConnection
    elif provider == "weaviate":
        from .weaviate_connection import WeaviateConnection

        return WeaviateConnection
    elif provider == "milvus":
        # Import milvus only if explicitly requested (experimental)
        try:
            from .milvus_connection import MilvusConnection

            return MilvusConnection
        except ImportError:
            raise ImportError(
                "Milvus provider is not installed. Install with: pip install vector-inspector[milvus]"
            )
    else:
        raise ValueError(f"Unsupported provider: {provider}")
