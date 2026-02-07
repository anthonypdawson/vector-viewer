"""Lazy import utilities for performance optimization."""

from typing import Any

_plotly_cache = None
_sklearn_cache = {}
_numpy_cache = None


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
                    "hdbscan is not installed. This is a premium feature. "
                    "Install with: pip install hdbscan"
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
