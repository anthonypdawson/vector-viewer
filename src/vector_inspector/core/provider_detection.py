"""Provider detection and installation helpers.

Detects which vector database providers are available (installed) and provides
installation instructions for missing ones.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderInfo:
    """Information about a vector database provider."""

    id: str
    name: str
    available: bool
    install_command: str
    import_name: str
    description: str


# Provider registry with installation info
PROVIDERS = [
    {
        "id": "chromadb",
        "name": "ChromaDB",
        "import_name": "chromadb",
        "install_command": "pip install vector-inspector[chromadb]",
        "description": "Local persistent or HTTP client",
    },
    {
        "id": "qdrant",
        "name": "Qdrant",
        "import_name": "qdrant_client",
        "install_command": "pip install vector-inspector[qdrant]",
        "description": "Local, remote, or cloud vector database",
    },
    {
        "id": "pinecone",
        "name": "Pinecone",
        "import_name": "pinecone",
        "install_command": "pip install vector-inspector[pinecone]",
        "description": "Cloud-hosted vector database",
    },
    {
        "id": "lancedb",
        "name": "LanceDB",
        "import_name": "lancedb",
        "install_command": "pip install vector-inspector[lancedb]",
        "description": "Embedded vector database",
    },
    {
        "id": "pgvector",
        "name": "PostgreSQL (pgvector)",
        "import_name": "psycopg2",
        "install_command": "pip install vector-inspector[pgvector]",
        "description": "PostgreSQL with vector extension",
    },
    {
        "id": "weaviate",
        "name": "Weaviate",
        "import_name": "weaviate",
        "install_command": "pip install vector-inspector[weaviate]",
        "description": "Local or cloud with GraphQL",
    },
    {
        "id": "milvus",
        "name": "Milvus",
        "import_name": "pymilvus",
        "install_command": "pip install vector-inspector[milvus]",
        "description": "Distributed vector database",
    },
]


def check_provider_available(import_name: str) -> bool:
    """Check if a provider's package is importable.

    Args:
        import_name: The Python package name to try importing

    Returns:
        True if the package can be imported, False otherwise
    """
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def get_all_providers() -> list[ProviderInfo]:
    """Get information about all providers, including availability status.

    Returns:
        List of ProviderInfo objects with availability status
    """
    result = []
    for provider in PROVIDERS:
        available = check_provider_available(provider["import_name"])
        result.append(
            ProviderInfo(
                id=provider["id"],
                name=provider["name"],
                available=available,
                install_command=provider["install_command"],
                import_name=provider["import_name"],
                description=provider["description"],
            )
        )
    return result


def get_available_providers() -> list[ProviderInfo]:
    """Get only the providers that are currently available (installed).

    Returns:
        List of available ProviderInfo objects
    """
    return [p for p in get_all_providers() if p.available]


def get_provider_info(provider_id: str) -> Optional[ProviderInfo]:
    """Get information about a specific provider.

    Args:
        provider_id: The provider identifier (e.g., "chromadb", "qdrant")

    Returns:
        ProviderInfo object or None if provider not found
    """
    all_providers = get_all_providers()
    for provider in all_providers:
        if provider.id == provider_id:
            return provider
    return None


def get_install_instructions_message(provider_id: str) -> str:
    """Get user-friendly installation instructions for a provider.

    Args:
        provider_id: The provider identifier

    Returns:
        Formatted message with installation instructions
    """
    provider = get_provider_info(provider_id)
    if not provider:
        return f"Unknown provider: {provider_id}"

    if provider.available:
        return f"{provider.name} is already installed."

    return f"""{provider.name} is not installed.

To use {provider.name}, install it with:

    {provider.install_command}

Or install the recommended bundle with common databases:

    pip install vector-inspector[recommended]

Or install everything:

    pip install vector-inspector[all]
"""


# Feature detection (embeddings, visualization, etc.)
@dataclass
class FeatureInfo:
    """Information about an optional feature."""

    id: str
    name: str
    available: bool
    install_command: str
    description: str


def check_embeddings_available() -> bool:
    """Check if embedding providers are available."""
    try:
        import sentence_transformers  # noqa: F401

        return True
    except ImportError:
        return False


def check_clip_available() -> bool:
    """Check if CLIP (multimodal embeddings) is available."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401

        return True
    except ImportError:
        return False


def check_viz_available() -> bool:
    """Check if advanced visualization (UMAP, t-SNE) is available."""
    try:
        import sklearn  # noqa: F401
        import umap  # noqa: F401

        return True
    except ImportError:
        return False


def check_documents_available() -> bool:
    """Check if document import dependencies (pypdf, python-docx) are available."""
    try:
        import docx  # noqa: F401
        import pypdf  # noqa: F401

        return True
    except ImportError:
        return False


def get_all_feature_info() -> list[FeatureInfo]:
    """Get information about all optional feature groups in display order.

    Returns:
        List of FeatureInfo objects for every known feature group.
    """
    return [info for fid in ("viz", "embeddings", "clip", "documents") if (info := get_feature_info(fid)) is not None]


def get_feature_info(feature_id: str) -> Optional[FeatureInfo]:
    """Get information about an optional feature.

    Args:
        feature_id: Feature identifier (embeddings, clip, viz, documents)

    Returns:
        FeatureInfo object or None if feature not found
    """
    features = {
        "embeddings": FeatureInfo(
            id="embeddings",
            name="Text Embeddings",
            available=check_embeddings_available(),
            install_command="pip install vector-inspector[embeddings]",
            description="Generate embeddings for semantic search",
        ),
        "clip": FeatureInfo(
            id="clip",
            name="Multimodal (CLIP)",
            available=check_clip_available(),
            install_command="pip install vector-inspector[clip]",
            description="Image and text embeddings with CLIP",
        ),
        "viz": FeatureInfo(
            id="viz",
            name="Advanced Visualization",
            available=check_viz_available(),
            install_command="pip install vector-inspector[viz]",
            description="UMAP, t-SNE, clustering algorithms",
        ),
        "documents": FeatureInfo(
            id="documents",
            name="Document Import",
            available=check_documents_available(),
            install_command="pip install vector-inspector[documents]",
            description="Import PDF and DOCX files",
        ),
    }
    return features.get(feature_id)


# ---------------------------------------------------------------------------
# Static (no availability check) helpers — use these when building UI rows
# before running checks in a background thread.
# ---------------------------------------------------------------------------


def get_feature_static_info(feature_id: str) -> Optional[FeatureInfo]:
    """Return static feature info with ``available=False`` — no import checks run."""
    _static: dict[str, FeatureInfo] = {
        "viz": FeatureInfo(
            id="viz",
            name="Advanced Visualization",
            available=False,
            install_command="pip install vector-inspector[viz]",
            description="UMAP, t-SNE, clustering algorithms",
        ),
        "embeddings": FeatureInfo(
            id="embeddings",
            name="Text Embeddings",
            available=False,
            install_command="pip install vector-inspector[embeddings]",
            description="Generate embeddings for semantic search",
        ),
        "clip": FeatureInfo(
            id="clip",
            name="Multimodal (CLIP)",
            available=False,
            install_command="pip install vector-inspector[clip]",
            description="Image and text embeddings with CLIP",
        ),
        "documents": FeatureInfo(
            id="documents",
            name="Document Import",
            available=False,
            install_command="pip install vector-inspector[documents]",
            description="Import PDF and DOCX files",
        ),
    }
    return _static.get(feature_id)


def get_all_feature_metadata() -> list[FeatureInfo]:
    """Return all feature info with ``available=False`` — no import checks run.

    Use this to populate UI rows before a background availability check.
    """
    return [
        info for fid in ("viz", "embeddings", "clip", "documents") if (info := get_feature_static_info(fid)) is not None
    ]


def get_feature_availability_checks() -> dict[str, Callable[[], bool]]:
    """Return ``{feature_id: check_callable}`` for background availability checking."""
    return {
        "viz": check_viz_available,
        "embeddings": check_embeddings_available,
        "clip": check_clip_available,
        "documents": check_documents_available,
    }


def get_provider_static_info(provider_id: str) -> Optional[ProviderInfo]:
    """Return static provider info with ``available=False`` — no import checks run."""
    for p in PROVIDERS:
        if p["id"] == provider_id:
            return ProviderInfo(
                id=p["id"],
                name=p["name"],
                available=False,
                install_command=p["install_command"],
                import_name=p["import_name"],
                description=p["description"],
            )
    return None


def get_all_provider_metadata() -> list[ProviderInfo]:
    """Return all provider info with ``available=False`` — no import checks run.

    Use this to populate UI rows before a background availability check.
    """
    return [
        ProviderInfo(
            id=p["id"],
            name=p["name"],
            available=False,
            install_command=p["install_command"],
            import_name=p["import_name"],
            description=p["description"],
        )
        for p in PROVIDERS
    ]


def get_provider_availability_checks() -> dict[str, Callable[[], bool]]:
    """Return ``{provider_id: check_callable}`` for background availability checking."""
    return {p["id"]: (lambda import_name=p["import_name"]: check_provider_available(import_name)) for p in PROVIDERS}
