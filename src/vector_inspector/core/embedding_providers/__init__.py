"""Embedding provider system for loading and managing embedding models."""

from .base_provider import EmbeddingProvider, EmbeddingMetadata
from .sentence_transformer_provider import SentenceTransformerProvider
from .clip_provider import CLIPProvider
from .provider_factory import ProviderFactory

__all__ = [
    'EmbeddingProvider',
    'EmbeddingMetadata',
    'SentenceTransformerProvider',
    'CLIPProvider',
    'ProviderFactory',
]
