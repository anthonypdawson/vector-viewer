"""Utilities for managing embedding models and vector dimensions."""

from __future__ import annotations  # Allows us to use class names in typehints while lazyloading

from typing import Any

# Lazy import: see below
from vector_inspector.core.logging import log_info
from vector_inspector.core.model_registry import get_model_registry

# Default model to use when dimension is unknown or not mapped
DEFAULT_MODEL = ("all-MiniLM-L6-v2", "sentence-transformer")


def _get_dimension_to_model_dict():
    """Build dimension->models dictionary from registry.

    Returns:
        Dict mapping dimension to list of (name, type, description) tuples
    """
    registry = get_model_registry()
    dimension_map = {}

    for dimension in registry.get_all_dimensions():
        models = registry.get_models_by_dimension(dimension)
        dimension_map[dimension] = [(m.name, m.type, m.description) for m in models]

    return dimension_map


# For backward compatibility - dynamically loads from registry
DIMENSION_TO_MODEL = _get_dimension_to_model_dict()


def get_model_for_dimension(dimension: int, prefer_multimodal: bool = True) -> tuple[str, str]:
    """
    Get the appropriate embedding model name and type for a given vector dimension.

    Args:
        dimension: The vector dimension size
        prefer_multimodal: If True and multiple models exist for this dimension,
                          prefer multi-modal (CLIP) over text-only models

    Returns:
        Tuple of (model_name, model_type) where model_type is "sentence-transformer" or "clip"
    """
    registry = get_model_registry()
    models = registry.get_models_by_dimension(dimension)

    if not models:
        # Find the closest dimension if exact match not found
        closest_dim = registry.find_closest_dimension(dimension)
        if closest_dim:
            models = registry.get_models_by_dimension(closest_dim)

    if not models:
        return DEFAULT_MODEL

    if len(models) == 1:
        return (models[0].name, models[0].type)

    # Multiple models available - apply preference
    if prefer_multimodal:
        # Prefer CLIP/multimodal
        for model in models:
            if model.modality == "multimodal" or model.type == "clip":
                return (model.name, model.type)

    # Default to first option
    return (models[0].name, models[0].type)


def get_available_models_for_dimension(dimension: int) -> list:
    """
    Get all available model options for a given dimension.
    Includes both predefined (from registry) and custom user-added models.

    Args:
        dimension: The vector dimension size

    Returns:
        List of tuples: [(model_name, model_type, description), ...]
    """
    # Start with models from registry
    registry = get_model_registry()
    registry_models = registry.get_models_by_dimension(dimension)
    models = [(m.name, m.type, m.description) for m in registry_models]

    # Add custom models from settings
    try:
        from vector_inspector.services.settings_service import SettingsService

        settings = SettingsService()
        custom_models = settings.get_custom_embedding_models(dimension)

        for model in custom_models:
            # Format: (model_name, model_type, description)
            models.append((model["name"], model["type"], f"{model['description']} (custom)"))
    except Exception as e:
        log_info("Warning: Could not load custom models: %s", e)

    return models


def load_embedding_model(model_name: str, model_type: str) -> SentenceTransformer | Any:
    """
    Load an embedding model (sentence-transformer or CLIP).

    Uses disk cache when available to speed up repeated loads.

    Args:
        model_name: Name of the model to load
        model_type: Type of model ("sentence-transformer" or "clip")

    Returns:
        Loaded model (SentenceTransformer or CLIP model)
    """
    from vector_inspector.core.model_cache import (
        is_cache_enabled,
        load_cached_path,
        save_model_to_cache,
    )

    # Try to load from cache first
    cached_path = load_cached_path(model_name)

    if model_type == "clip":
        from transformers import CLIPModel, CLIPProcessor

        if cached_path:
            try:
                # Load from cache
                model = CLIPModel.from_pretrained(str(cached_path))
                processor_path = cached_path / "processor"
                if processor_path.exists():
                    processor = CLIPProcessor.from_pretrained(str(processor_path))
                else:
                    # Fallback: load processor from original model name
                    processor = CLIPProcessor.from_pretrained(model_name)
                log_info(f"Loaded CLIP model from cache: {model_name}")
                return (model, processor)
            except Exception as e:
                log_info(f"Failed to load from cache, downloading: {e}")

        # Load from HuggingFace
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)

        # Cache for future use
        if is_cache_enabled():
            save_model_to_cache((model, processor), model_name, model_type)

        # Returns a tuple: (CLIPModel, CLIPProcessor)
        return (model, processor)
    from sentence_transformers import SentenceTransformer

    if cached_path:
        try:
            # Load from cache
            model = SentenceTransformer(str(cached_path))
            log_info(f"Loaded sentence-transformer from cache: {model_name}")
            return model
        except Exception as e:
            log_info(f"Failed to load from cache, downloading: {e}")

    # Load from HuggingFace
    model = SentenceTransformer(model_name)

    # Cache for future use
    if is_cache_enabled():
        save_model_to_cache(model, model_name, model_type)

    # Returns a SentenceTransformer instance
    return model


def encode_text(text: str, model: SentenceTransformer | tuple, model_type: str) -> list:
    """
    Encode text using the appropriate model.

    Args:
        text: Text to encode
        model: The loaded model (SentenceTransformer or (CLIPModel, CLIPProcessor) tuple)
        model_type: Type of model ("sentence-transformer" or "clip")

    Returns:
        Embedding vector as a list
    """
    if model_type == "clip":
        import torch

        clip_model, processor = model
        inputs = processor(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            text_features = clip_model.get_text_features(**inputs)
        # Normalize the features (CLIP embeddings are typically normalized)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features[0].cpu().numpy().tolist()
    # sentence-transformer
    # Lazy import for type hint only
    # from sentence_transformers import SentenceTransformer
    embedding = model.encode(text)
    return embedding.tolist()


def get_embedding_model_for_dimension(
    dimension: int,
) -> tuple[SentenceTransformer | tuple, str, str]:
    """
    Get a loaded embedding model for a specific dimension.

    Args:
        dimension: The vector dimension size

    Returns:
        Tuple of (loaded_model, model_name, model_type)
    """
    model_name, model_type = get_model_for_dimension(dimension)
    model = load_embedding_model(model_name, model_type)
    # Returns a tuple: (loaded_model, model_name, model_type)
    return (model, model_name, model_type)
