"""Tests for lazy_imports utility."""

import sys
import types

import pytest


def _reset_lazy_caches():
    """Clear cached module singletons between tests."""
    import vector_inspector.utils.lazy_imports as li

    li._plotly_cache = None
    li._sklearn_cache = {}
    li._numpy_cache = None
    li._weaviate_cache = None


def test_get_plotly_returns_module():
    from vector_inspector.utils.lazy_imports import get_plotly

    go = get_plotly()
    assert go is not None


def test_get_numpy_returns_module():
    from vector_inspector.utils.lazy_imports import get_numpy

    np = get_numpy()
    assert np is not None
    assert hasattr(np, "array")


def test_get_sklearn_pca():
    from vector_inspector.utils.lazy_imports import get_sklearn_model

    PCA = get_sklearn_model("PCA")
    assert PCA is not None


def test_get_sklearn_tsne():
    from vector_inspector.utils.lazy_imports import get_sklearn_model

    TSNE = get_sklearn_model("TSNE")
    assert TSNE is not None


def test_get_sklearn_kmeans():
    from vector_inspector.utils.lazy_imports import get_sklearn_model

    KMeans = get_sklearn_model("KMeans")
    assert KMeans is not None


def test_get_sklearn_dbscan():
    from vector_inspector.utils.lazy_imports import get_sklearn_model

    DBSCAN = get_sklearn_model("DBSCAN")
    assert DBSCAN is not None


def test_get_sklearn_umap_mocked(monkeypatch):
    """UMAP branch via a fake umap module."""
    _reset_lazy_caches()

    fake_umap = types.ModuleType("umap")

    class FakeUMAP:
        pass

    fake_umap.UMAP = FakeUMAP
    monkeypatch.setitem(sys.modules, "umap", fake_umap)

    from vector_inspector.utils.lazy_imports import get_sklearn_model

    result = get_sklearn_model("UMAP")
    assert result is FakeUMAP


def test_get_sklearn_hdbscan_import_error(monkeypatch):
    """HDBSCAN raises ImportError when hdbscan not installed."""
    _reset_lazy_caches()
    monkeypatch.setitem(sys.modules, "hdbscan", None)

    from vector_inspector.utils.lazy_imports import get_sklearn_model

    with pytest.raises(ImportError, match="hdbscan"):
        get_sklearn_model("HDBSCAN")


def test_get_sklearn_optics_mocked(monkeypatch):
    """OPTICS branch via a fake sklearn.cluster module."""
    _reset_lazy_caches()

    class FakeOPTICS:
        pass

    # sklearn.cluster is likely already imported; patch the attribute directly
    import sklearn.cluster as real_cluster

    monkeypatch.setattr(real_cluster, "OPTICS", FakeOPTICS)

    from vector_inspector.utils.lazy_imports import get_sklearn_model

    result = get_sklearn_model("OPTICS")
    assert result is FakeOPTICS


def test_get_weaviate_client_mocked(monkeypatch):
    """Weaviate branch via a fake weaviate module."""
    _reset_lazy_caches()

    fake_weaviate = types.ModuleType("weaviate")
    monkeypatch.setitem(sys.modules, "weaviate", fake_weaviate)

    from vector_inspector.utils.lazy_imports import get_weaviate_client

    result = get_weaviate_client()
    assert result is fake_weaviate
