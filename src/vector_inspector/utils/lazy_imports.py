"""Lazy import utilities for performance optimization."""

import threading
from typing import Any

_plotly_cache = None
_sklearn_cache = {}
_numpy_cache = None
_weaviate_cache = None


def get_plotly():
    """Lazy import plotly graph_objects."""
    global _plotly_cache
    if _plotly_cache is None:
        import plotly.graph_objects as go

        _plotly_cache = go
    return _plotly_cache


def get_numpy():
    """Lazy import numpy."""
    global _numpy_cache
    if _numpy_cache is None:
        import numpy as np

        _numpy_cache = np
    return _numpy_cache


def get_sklearn_model(model_name: str) -> Any:
    """
    Lazy import sklearn models.

    Args:
        model_name: Name of the model ('PCA', 'TSNE', 'UMAP', 'HDBSCAN', 'KMeans', 'DBSCAN')

    Returns:
        The model class
    """
    global _sklearn_cache
    if model_name not in _sklearn_cache:
        if model_name == "PCA":
            from sklearn.decomposition import PCA

            _sklearn_cache["PCA"] = PCA
        elif model_name == "TSNE":
            from sklearn.manifold import TSNE

            _sklearn_cache["TSNE"] = TSNE
        elif model_name == "UMAP":
            import umap

            _sklearn_cache["UMAP"] = umap.UMAP
        elif model_name == "HDBSCAN":
            try:
                import hdbscan

                _sklearn_cache["HDBSCAN"] = hdbscan.HDBSCAN
            except ImportError as e:
                raise ImportError(
                    "hdbscan is not installed. This is a premium feature. Install with: pip install hdbscan"
                ) from e
        elif model_name == "KMeans":
            from sklearn.cluster import KMeans

            _sklearn_cache["KMeans"] = KMeans
        elif model_name == "DBSCAN":
            from sklearn.cluster import DBSCAN

            _sklearn_cache["DBSCAN"] = DBSCAN
        elif model_name == "OPTICS":
            from sklearn.cluster import OPTICS

            _sklearn_cache["OPTICS"] = OPTICS
    return _sklearn_cache[model_name]


def get_weaviate_client() -> Any:
    """Lazy import weaviate client."""
    global _weaviate_cache
    if _weaviate_cache is None:
        import weaviate

        _weaviate_cache = weaviate
    return _weaviate_cache


# ---------------------------------------------------------------------------
# Ingestion dependencies (optional)
# ---------------------------------------------------------------------------

# Keyed by model name so custom CLIP variants also benefit from the same cache.
_clip_cache: dict[str, tuple[Any, Any]] = {}
# Lock prevents two threads from loading the same model simultaneously, which
# can cause a native segfault inside torch_cpu.dll (access violation 0xc0000005).
_clip_lock = threading.Lock()
_sentence_transformer_cache: dict[str, Any] = {}
_sentence_transformer_lock = threading.Lock()
_pillow_cache: Any = None
_pypdf_cache: Any = None
_docx_cache: Any = None


def get_clip_model_and_processor(model_name: str = "openai/clip-vit-base-patch32") -> tuple[Any, Any]:
    """Lazy-load a CLIP model and processor; thread-safe; cached by model name.

    The double-checked locking pattern ensures that once the model is cached a
    second caller sees it immediately without acquiring the lock, while still
    preventing two threads from loading simultaneously (which can crash
    torch_cpu.dll with an access violation).
    """
    if model_name in _clip_cache:
        return _clip_cache[model_name]
    with _clip_lock:
        # Re-check inside the lock in case another thread populated it while we
        # were waiting.
        if model_name not in _clip_cache:
            from transformers import CLIPModel, CLIPProcessor

            model = CLIPModel.from_pretrained(model_name)
            processor = CLIPProcessor.from_pretrained(model_name)
            _clip_cache[model_name] = (model, processor)
    return _clip_cache[model_name]


def get_sentence_transformer(model_name: str = "all-MiniLM-L6-v2") -> Any:
    """Lazy-load a SentenceTransformer model; thread-safe; cached per model name."""
    if model_name in _sentence_transformer_cache:
        return _sentence_transformer_cache[model_name]
    with _sentence_transformer_lock:
        if model_name not in _sentence_transformer_cache:
            from sentence_transformers import SentenceTransformer

            _sentence_transformer_cache[model_name] = SentenceTransformer(model_name)
    return _sentence_transformer_cache[model_name]


def get_pillow() -> Any:
    """Lazy-load Pillow (PIL.Image, cached after first call)."""
    global _pillow_cache
    if _pillow_cache is None:
        from PIL import Image

        _pillow_cache = Image
    return _pillow_cache


def get_pypdf() -> Any:
    """Lazy-load pypdf module (cached after first call)."""
    global _pypdf_cache
    if _pypdf_cache is None:
        import pypdf

        _pypdf_cache = pypdf
    return _pypdf_cache


def get_python_docx() -> Any:
    """Lazy-load python-docx module (cached after first call)."""
    global _docx_cache
    if _docx_cache is None:
        import docx

        _docx_cache = docx
    return _docx_cache
