"""Factory for creating embedding providers."""

from typing import Optional, Dict, Type
from .base_provider import EmbeddingProvider
from .sentence_transformer_provider import SentenceTransformerProvider
from .clip_provider import CLIPProvider
from ..model_registry import get_model_registry


class ProviderFactory:
    """Factory for creating appropriate embedding providers based on model type."""
    
    # Registry of provider classes by type
    _PROVIDER_REGISTRY: Dict[str, Type[EmbeddingProvider]] = {
        "sentence-transformer": SentenceTransformerProvider,
        "clip": CLIPProvider,
    }
    
    # Model name patterns to auto-detect provider type
    _MODEL_PATTERNS = {
        "clip": ["clip", "CLIP"],
        "sentence-transformer": [
            "sentence-transformers/",
            "all-MiniLM",
            "all-mpnet",
            "all-roberta",
            "paraphrase-",
            "multi-qa-",
            "msmarco-",
            "gtr-",
            "bge-",
            "gte-",
            "e5-",
            "jina-",
            "nomic-",
        ]
    }
    
    @classmethod
    def create(
        cls,
        model_name: str,
        model_type: Optional[str] = None,
        **kwargs
    ) -> EmbeddingProvider:
        """Create an embedding provider for the given model.
        
        Args:
            model_name: Model identifier (HF ID, path, or API name)
            model_type: Explicit provider type (sentence-transformer, clip, openai, etc.)
                       If None, will attempt auto-detection based on model name
            **kwargs: Additional arguments passed to provider constructor
            
        Returns:
            Appropriate EmbeddingProvider instance
            
        Raises:
            ValueError: If model type is unknown or cannot be auto-detected
        """
        # Auto-detect provider type if not specified
        if model_type is None:
            model_type = cls._detect_provider_type(model_name)
        
        # Normalize model type
        model_type = model_type.lower()
        
        # Get provider class from registry
        provider_class = cls._PROVIDER_REGISTRY.get(model_type)
        
        if provider_class is None:
            # Check if it's a cloud provider (not yet implemented)
            if model_type in ["openai", "cohere", "vertex-ai", "voyage"]:
                raise NotImplementedError(
                    f"Cloud provider '{model_type}' not yet implemented. "
                    f"Currently supported: {', '.join(cls._PROVIDER_REGISTRY.keys())}"
                )
            else:
                raise ValueError(
                    f"Unknown provider type: {model_type}. "
                    f"Supported types: {', '.join(cls._PROVIDER_REGISTRY.keys())}"
                )
        
        # Create and return provider instance
        return provider_class(model_name, **kwargs)
    
    @classmethod
    def _detect_provider_type(cls, model_name: str) -> str:
        """Auto-detect provider type based on model name patterns.
        
        First checks the known model registry, then falls back to pattern matching.
        
        Args:
            model_name: Model identifier
            
        Returns:
            Detected provider type
            
        Raises:
            ValueError: If provider type cannot be detected
        """
        # First, check if model is in registry
        registry = get_model_registry()
        model_info = registry.get_model_by_name(model_name)
        if model_info:
            return model_info.type
        
        # Fall back to pattern matching
        model_name_lower = model_name.lower()
        
        # Check each pattern category
        for provider_type, patterns in cls._MODEL_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in model_name_lower:
                    return provider_type
        
        # Default to sentence-transformer for HuggingFace models
        if "/" in model_name and not model_name.startswith("http"):
            return "sentence-transformer"
        
        raise ValueError(
            f"Cannot auto-detect provider type for model: {model_name}. "
            "Please specify model_type explicitly."
        )
    
    @classmethod
    def register_provider(cls, model_type: str, provider_class: Type[EmbeddingProvider]):
        """Register a new provider type.
        
        Args:
            model_type: Provider type identifier
            provider_class: Provider class (must inherit from EmbeddingProvider)
        """
        if not issubclass(provider_class, EmbeddingProvider):
            raise TypeError(f"{provider_class} must inherit from EmbeddingProvider")
        
        cls._PROVIDER_REGISTRY[model_type.lower()] = provider_class
    
    @classmethod
    def list_supported_types(cls) -> list:
        """Get list of supported provider types.
        
        Returns:
            List of registered provider type names
        """
        return list(cls._PROVIDER_REGISTRY.keys())
    
    @classmethod
    def supports_type(cls, model_type: str) -> bool:
        """Check if a provider type is supported.
        
        Args:
            model_type: Provider type to check
            
        Returns:
            True if supported, False otherwise
        """
        return model_type.lower() in cls._PROVIDER_REGISTRY


# Convenience function for creating providers
def create_provider(
    model_name: str,
    model_type: Optional[str] = None,
    **kwargs
) -> EmbeddingProvider:
    """Create an embedding provider (convenience wrapper around ProviderFactory).
    
    Args:
        model_name: Model identifier
        model_type: Optional explicit provider type
        **kwargs: Additional arguments for provider
        
    Returns:
        EmbeddingProvider instance
    """
    return ProviderFactory.create(model_name, model_type, **kwargs)
