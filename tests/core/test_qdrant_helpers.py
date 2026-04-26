"""Tests for qdrant_filter_builder and qdrant_embedding_resolver helpers."""

import pytest

# Skip entire module if qdrant_client not installed
pytest.importorskip("qdrant_client")

from unittest.mock import MagicMock

from vector_inspector.core.connections.qdrant_helpers.qdrant_filter_builder import build_filter


class TestBuildFilter:
    def test_none_input_returns_none(self):
        assert build_filter(None) is None

    def test_empty_dict_returns_none(self):
        assert build_filter({}) is None

    def test_simple_equality(self):
        f = build_filter({"color": "red"})
        assert f is not None
        assert len(f.must) == 1

    def test_eq_operator(self):
        f = build_filter({"score": {"$eq": 5}})
        assert f is not None
        assert len(f.must) == 1

    def test_ne_operator(self):
        f = build_filter({"status": {"$ne": "inactive"}})
        assert f is not None
        assert f.must is None or len(f.must) == 0
        assert len(f.must_not) == 1

    def test_in_operator(self):
        f = build_filter({"tag": {"$in": ["a", "b", "c"]}})
        assert f is not None
        assert len(f.must) == 1

    def test_nin_operator(self):
        f = build_filter({"tag": {"$nin": ["x", "y"]}})
        assert f is not None
        # $nin maps to MatchExcept which goes into must conditions
        assert len(f.must) == 1

    def test_contains_operator(self):
        f = build_filter({"text": {"$contains": "hello"}})
        assert f is not None
        assert len(f.must) == 1

    def test_not_contains_operator(self):
        f = build_filter({"text": {"$not_contains": "spam"}})
        assert f is not None
        assert len(f.must_not) == 1

    def test_gt_operator(self):
        f = build_filter({"price": {"$gt": 10}})
        assert f is not None
        assert len(f.must) == 1

    def test_gte_operator(self):
        f = build_filter({"price": {"$gte": 10}})
        assert f is not None
        assert len(f.must) == 1

    def test_lt_operator(self):
        f = build_filter({"price": {"$lt": 100}})
        assert f is not None
        assert len(f.must) == 1

    def test_lte_operator(self):
        f = build_filter({"price": {"$lte": 100}})
        assert f is not None
        assert len(f.must) == 1

    def test_multiple_keys(self):
        f = build_filter({"color": "blue", "size": {"$gt": 5}})
        assert f is not None
        assert len(f.must) == 2

    def test_mixed_must_and_must_not(self):
        f = build_filter({"color": {"$eq": "red"}, "status": {"$ne": "deleted"}})
        assert f is not None
        assert len(f.must) == 1
        assert len(f.must_not) == 1

    def test_exception_returns_none(self, monkeypatch):
        """If inner logic raises, build_filter returns None."""

        def bad_items():
            raise RuntimeError("boom")

        # Simulate a broken dict by monkeypatching dict.items
        class BadDict(dict):
            def items(self):
                raise RuntimeError("boom")

        result = build_filter(BadDict({"x": 1}))
        assert result is None


class TestResolveEmbeddingModel:
    """Tests for qdrant_embedding_resolver.resolve_embedding_model."""

    def test_no_collection_info_uses_default(self, monkeypatch):
        from vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver import (
            resolve_embedding_model,
        )
        from vector_inspector.core.embedding_utils import DEFAULT_MODEL

        mock_conn = MagicMock()
        mock_conn.get_collection_info.return_value = None

        mock_model = MagicMock()
        monkeypatch.setattr(
            "vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver.load_embedding_model",
            lambda name, mtype: mock_model,
        )

        model, model_name, model_type = resolve_embedding_model(mock_conn, "my_col")
        assert model_name == DEFAULT_MODEL[0]
        assert model_type == DEFAULT_MODEL[1]

    def test_uses_explicit_embedding_model_from_collection_info(self, monkeypatch):
        from vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver import (
            resolve_embedding_model,
        )

        mock_conn = MagicMock()
        mock_conn.get_collection_info.return_value = {
            "embedding_model": "custom-model",
            "embedding_model_type": "clip",
        }

        mock_model = MagicMock()
        monkeypatch.setattr(
            "vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver.load_embedding_model",
            lambda name, mtype: mock_model,
        )

        model, name, mtype = resolve_embedding_model(mock_conn, "col")
        assert name == "custom-model"
        assert mtype == "clip"

    def test_falls_back_to_dimension_lookup(self, monkeypatch):
        from vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver import (
            resolve_embedding_model,
        )

        mock_conn = MagicMock()
        mock_conn.get_collection_info.return_value = {"vector_dimension": 384}

        mock_model = MagicMock()
        monkeypatch.setattr(
            "vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver.load_embedding_model",
            lambda name, mtype: mock_model,
        )
        monkeypatch.setattr(
            "vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver.get_model_for_dimension",
            lambda dim: ("dim-model", "sentence-transformer"),
        )

        model, name, mtype = resolve_embedding_model(mock_conn, "col")
        assert name == "dim-model"

    def test_unknown_dimension_uses_default(self, monkeypatch):
        from vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver import (
            resolve_embedding_model,
        )
        from vector_inspector.core.embedding_utils import DEFAULT_MODEL

        mock_conn = MagicMock()
        mock_conn.get_collection_info.return_value = {"vector_dimension": "Unknown"}

        mock_model = MagicMock()
        monkeypatch.setattr(
            "vector_inspector.core.connections.qdrant_helpers.qdrant_embedding_resolver.load_embedding_model",
            lambda name, mtype: mock_model,
        )

        model, name, mtype = resolve_embedding_model(mock_conn, "col")
        assert name == DEFAULT_MODEL[0]
