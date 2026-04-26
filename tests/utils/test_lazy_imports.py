"""Tests for lazy_imports utility."""

import importlib.util
import sys
import types

import pytest


# Helper to check if a package is available
def _has_package(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


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
    pytest.importorskip("sklearn")
    from vector_inspector.utils.lazy_imports import get_sklearn_model

    PCA = get_sklearn_model("PCA")
    assert PCA is not None


def test_get_sklearn_tsne():
    pytest.importorskip("sklearn")
    from vector_inspector.utils.lazy_imports import get_sklearn_model

    TSNE = get_sklearn_model("TSNE")
    assert TSNE is not None


def test_get_sklearn_kmeans():
    pytest.importorskip("sklearn")
    from vector_inspector.utils.lazy_imports import get_sklearn_model

    KMeans = get_sklearn_model("KMeans")
    assert KMeans is not None


def test_get_sklearn_dbscan():
    pytest.importorskip("sklearn")
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
    pytest.importorskip("sklearn")
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


# ---------------------------------------------------------------------------
# FeatureDependencyMissingError — class contract
# ---------------------------------------------------------------------------


def test_feature_dependency_missing_error_is_import_error():
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError

    exc = FeatureDependencyMissingError("viz", "sklearn")
    assert isinstance(exc, ImportError)


def test_feature_dependency_missing_error_carries_feature_id():
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError

    exc = FeatureDependencyMissingError("embeddings", "sentence_transformers")
    assert exc.feature_id == "embeddings"


def test_feature_dependency_missing_error_carries_import_name():
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError

    exc = FeatureDependencyMissingError("documents", "pypdf")
    assert exc.import_name == "pypdf"


def test_feature_dependency_missing_error_message_includes_install_hint():
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError

    exc = FeatureDependencyMissingError("viz", "sklearn")
    assert "pip install vector-inspector[viz]" in str(exc)


# ---------------------------------------------------------------------------
# _IMPORT_TO_FEATURE mapping completeness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "import_name,expected_feature",
    [
        ("sklearn", "viz"),
        ("umap", "viz"),
        ("sentence_transformers", "embeddings"),
        ("transformers", "clip"),
        ("torch", "clip"),
        ("pypdf", "documents"),
        ("docx", "documents"),
    ],
)
def test_import_to_feature_mapping(import_name, expected_feature):
    import vector_inspector.utils.lazy_imports as li

    assert li._IMPORT_TO_FEATURE[import_name] == expected_feature


# ---------------------------------------------------------------------------
# get_sklearn_model raises FeatureDependencyMissingError when sklearn absent
# ---------------------------------------------------------------------------


def test_get_sklearn_pca_raises_feature_error_when_absent(monkeypatch):
    import vector_inspector.utils.lazy_imports as li

    monkeypatch.setattr(li, "_sklearn_cache", {})
    for name in list(sys.modules):
        if name == "sklearn" or name.startswith("sklearn."):
            monkeypatch.setitem(sys.modules, name, None)
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError, get_sklearn_model

    with pytest.raises(FeatureDependencyMissingError) as exc_info:
        get_sklearn_model("PCA")
    assert exc_info.value.feature_id == "viz"


def test_get_sklearn_tsne_raises_feature_error_when_absent(monkeypatch):
    import vector_inspector.utils.lazy_imports as li

    monkeypatch.setattr(li, "_sklearn_cache", {})
    for name in list(sys.modules):
        if name == "sklearn" or name.startswith("sklearn."):
            monkeypatch.setitem(sys.modules, name, None)
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError, get_sklearn_model

    with pytest.raises(FeatureDependencyMissingError) as exc_info:
        get_sklearn_model("TSNE")
    assert exc_info.value.feature_id == "viz"


def test_get_sklearn_umap_raises_feature_error_when_umap_absent(monkeypatch):
    import vector_inspector.utils.lazy_imports as li

    monkeypatch.setattr(li, "_sklearn_cache", {})
    monkeypatch.setitem(sys.modules, "umap", None)
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError, get_sklearn_model

    with pytest.raises(FeatureDependencyMissingError) as exc_info:
        get_sklearn_model("UMAP")
    assert exc_info.value.feature_id == "viz"
    assert exc_info.value.import_name == "umap"


def test_get_sklearn_hdbscan_raises_plain_import_error_not_feature_error(monkeypatch):
    """HDBSCAN is a premium VS dep — must stay as plain ImportError."""
    import vector_inspector.utils.lazy_imports as li

    monkeypatch.setattr(li, "_sklearn_cache", {})
    monkeypatch.setitem(sys.modules, "hdbscan", None)
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError, get_sklearn_model

    with pytest.raises(ImportError) as exc_info:
        get_sklearn_model("HDBSCAN")
    assert not isinstance(exc_info.value, FeatureDependencyMissingError)


# ---------------------------------------------------------------------------
# get_sentence_transformer raises FeatureDependencyMissingError when absent
# ---------------------------------------------------------------------------


def test_get_sentence_transformer_raises_feature_error_when_absent(monkeypatch):
    """Test that get_sentence_transformer raises proper error when sentence_transformers is not importable."""
    import builtins

    import vector_inspector.utils.lazy_imports as li

    # Clear the cache
    monkeypatch.setattr(li, "_sentence_transformer_cache", {})

    # Create a mock that raises ImportError when trying to import sentence_transformers
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "sentence_transformers" or name.startswith("sentence_transformers."):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError, get_sentence_transformer

    with pytest.raises(FeatureDependencyMissingError) as exc_info:
        get_sentence_transformer("all-MiniLM-L6-v2")
    assert exc_info.value.feature_id == "embeddings"
    assert exc_info.value.import_name == "sentence_transformers"


# ---------------------------------------------------------------------------
# get_clip_model_and_processor raises FeatureDependencyMissingError when absent
# ---------------------------------------------------------------------------


def test_get_clip_raises_feature_error_when_transformers_absent(monkeypatch):
    """Test that get_clip_model_and_processor raises proper error when transformers is not importable."""
    import builtins

    import vector_inspector.utils.lazy_imports as li

    # Clear the cache
    monkeypatch.setattr(li, "_clip_cache", {})

    # Create a mock that raises ImportError when trying to import transformers
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "transformers" or name.startswith("transformers."):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError, get_clip_model_and_processor

    with pytest.raises(FeatureDependencyMissingError) as exc_info:
        get_clip_model_and_processor()
    assert exc_info.value.feature_id == "clip"
    assert exc_info.value.import_name == "transformers"


# ---------------------------------------------------------------------------
# get_pypdf / get_python_docx raise FeatureDependencyMissingError when absent
# ---------------------------------------------------------------------------


def test_get_pypdf_raises_feature_error_when_absent(monkeypatch):
    import vector_inspector.utils.lazy_imports as li

    monkeypatch.setattr(li, "_pypdf_cache", None)
    monkeypatch.setitem(sys.modules, "pypdf", None)
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError, get_pypdf

    with pytest.raises(FeatureDependencyMissingError) as exc_info:
        get_pypdf()
    assert exc_info.value.feature_id == "documents"
    assert exc_info.value.import_name == "pypdf"


def test_get_python_docx_raises_feature_error_when_absent(monkeypatch):
    import vector_inspector.utils.lazy_imports as li

    monkeypatch.setattr(li, "_docx_cache", None)
    monkeypatch.setitem(sys.modules, "docx", None)
    from vector_inspector.utils.lazy_imports import FeatureDependencyMissingError, get_python_docx

    with pytest.raises(FeatureDependencyMissingError) as exc_info:
        get_python_docx()
    assert exc_info.value.feature_id == "documents"
    assert exc_info.value.import_name == "docx"
