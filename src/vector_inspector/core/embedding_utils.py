"""Utilities for managing embedding models and vector dimensions."""

from typing import Optional, Union, Tuple
from sentence_transformers import SentenceTransformer


# Mapping of vector dimensions to appropriate models
# Format: dimension -> list of (model_name, model_type, description)
# Listed in order of preference for ambiguous cases
DIMENSION_TO_MODEL = {
    384: [
        ("all-MiniLM-L6-v2", "sentence-transformer", "Fast text embeddings"),
    ],
    512: [
        ("openai/clip-vit-base-patch32", "clip", "Multi-modal (text + images)"),
        ("paraphrase-albert-small-v2", "sentence-transformer", "Text-only paraphrase"),
    ],
    768: [
        ("all-mpnet-base-v2", "sentence-transformer", "High quality text embeddings"),
    ],
    1024: [
        ("all-roberta-large-v1", "sentence-transformer", "Large text embeddings"),
    ],
    1536: [
        ("gtr-t5-large", "sentence-transformer", "Very large text embeddings"),
    ],
}

# Default model to use when dimension is unknown or not mapped
DEFAULT_MODEL = ("all-MiniLM-L6-v2", "sentence-transformer")


def get_model_for_dimension(dimension: int, prefer_multimodal: bool = True) -> Tuple[str, str]:
    """
    Get the appropriate embedding model name and type for a given vector dimension.
    
    Args:
        dimension: The vector dimension size
        prefer_multimodal: If True and multiple models exist for this dimension, 
                          prefer multi-modal (CLIP) over text-only models
        
    Returns:
        Tuple of (model_name, model_type) where model_type is "sentence-transformer" or "clip"
    """
    if dimension in DIMENSION_TO_MODEL:
        models = DIMENSION_TO_MODEL[dimension]
        if len(models) == 1:
            return (models[0][0], models[0][1])
        
        # Multiple models available - apply preference
        if prefer_multimodal:
            # Prefer CLIP/multimodal
            for model_name, model_type, desc in models:
                if model_type == "clip":
                    return (model_name, model_type)
        
        # Default to first option
        return (models[0][0], models[0][1])
    
    # Find the closest dimension if exact match not found
    closest_dim = min(DIMENSION_TO_MODEL.keys(), key=lambda x: abs(x - dimension))
    models = DIMENSION_TO_MODEL[closest_dim]
    return (models[0][0], models[0][1])


def get_available_models_for_dimension(dimension: int) -> list:
    """
    Get all available model options for a given dimension.
    
    Args:
        dimension: The vector dimension size
        
    Returns:
        List of tuples: [(model_name, model_type, description), ...]
    """
    if dimension in DIMENSION_TO_MODEL:
        return DIMENSION_TO_MODEL[dimension]
    return []


def load_embedding_model(model_name: str, model_type: str) -> Union[SentenceTransformer, any]:
    """
    Load an embedding model (sentence-transformer or CLIP).
    
    Args:
        model_name: Name of the model to load
        model_type: Type of model ("sentence-transformer" or "clip")
        
    Returns:
        Loaded model (SentenceTransformer or CLIP model)
    """
    if model_type == "clip":
        from transformers import CLIPModel, CLIPProcessor
        model = CLIPModel.from_pretrained(model_name)
        processor = CLIPProcessor.from_pretrained(model_name)
        return (model, processor)
    else:
        return SentenceTransformer(model_name)


def encode_text(text: str, model: Union[SentenceTransformer, Tuple], model_type: str) -> list:
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
    else:
        # sentence-transformer
        embedding = model.encode(text)
        return embedding.tolist()


def get_embedding_model_for_dimension(dimension: int) -> Tuple[Union[SentenceTransformer, Tuple], str, str]:
    """
    Get a loaded embedding model for a specific dimension.
    
    Args:
        dimension: The vector dimension size
        
    Returns:
        Tuple of (loaded_model, model_name, model_type)
    """
    model_name, model_type = get_model_for_dimension(dimension)
    model = load_embedding_model(model_name, model_type)
    return (model, model_name, model_type)
