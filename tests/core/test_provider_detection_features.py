"""Tests for provider_detection — optional feature group detection."""

import sys

import pytest

from vector_inspector.core.provider_detection import (
    FeatureInfo,
    check_clip_available,
    check_documents_available,
    check_embeddings_available,
    check_viz_available,
    get_all_feature_info,
    get_feature_info,
)

# ---------------------------------------------------------------------------
# check_documents_available
# ---------------------------------------------------------------------------


def test_check_documents_available_false_when_pypdf_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdf", None)
    # Force re-evaluation (function doesn't cache, so just calling it is enough)
    assert check_documents_available() is False


def test_check_documents_available_false_when_docx_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "docx", None)
    assert check_documents_available() is False


def test_check_viz_available_false_when_sklearn_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "sklearn", None)
    assert check_viz_available() is False


def test_check_viz_available_false_when_umap_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "umap", None)
    assert check_viz_available() is False


def test_check_embeddings_available_false_when_sentence_transformers_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    assert check_embeddings_available() is False


def test_check_clip_available_false_when_torch_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    assert check_clip_available() is False


# ---------------------------------------------------------------------------
# get_feature_info — documents entry
# ---------------------------------------------------------------------------


def test_get_feature_info_documents_returns_feature_info():
    info = get_feature_info("documents")
    assert info is not None
    assert isinstance(info, FeatureInfo)


def test_get_feature_info_documents_id():
    info = get_feature_info("documents")
    assert info.id == "documents"


def test_get_feature_info_documents_install_command_contains_extra():
    info = get_feature_info("documents")
    assert "vector-inspector[documents]" in info.install_command


def test_get_feature_info_documents_has_name():
    info = get_feature_info("documents")
    assert info.name


def test_get_feature_info_unknown_returns_none():
    assert get_feature_info("nonexistent") is None


# ---------------------------------------------------------------------------
# get_feature_info — all known feature IDs return a FeatureInfo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("feature_id", ["viz", "embeddings", "clip", "documents"])
def test_get_feature_info_all_known_ids(feature_id):
    info = get_feature_info(feature_id)
    assert info is not None
    assert info.id == feature_id
    assert info.install_command
    assert info.name


# ---------------------------------------------------------------------------
# get_all_feature_info
# ---------------------------------------------------------------------------


def test_get_all_feature_info_returns_four_items():
    features = get_all_feature_info()
    assert len(features) == 4


def test_get_all_feature_info_all_are_feature_info():
    for item in get_all_feature_info():
        assert isinstance(item, FeatureInfo)


def test_get_all_feature_info_ids_match_expected_order():
    ids = [f.id for f in get_all_feature_info()]
    assert ids == ["viz", "embeddings", "clip", "documents"]
