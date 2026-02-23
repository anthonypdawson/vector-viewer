from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.services.search_runner import SearchRunner


def test_search_normalize_flattens_nested():
    fake_conn = MagicMock()
    fake_conn.query.return_value = {
        "ids": [["a", "b"]],
        "distances": [[0.1, 0.2]],
        "metadatas": [[{"k": 1}, {"k": 2}]],
        "documents": [["d1", "d2"]],
    }

    sr = SearchRunner(connection=fake_conn)
    res = sr.search("col", "q")
    assert res["ids"] == ["a", "b"]
    assert res["documents"] == ["d1", "d2"]


def test_search_by_id_missing_embedding_returns_none():
    fake_conn = MagicMock()
    fake_conn.get_by_ids.return_value = {"embeddings": []}
    sr = SearchRunner(connection=fake_conn)
    assert sr.search_by_id("col", "id1") is None


def test_search_by_id_uses_embedding_and_calls_search():
    fake_conn = MagicMock()
    fake_conn.get_by_ids.return_value = {"embeddings": [[0.1, 0.2]]}
    sr = SearchRunner(connection=fake_conn)

    with patch.object(sr, "search", return_value={"ids": ["x"]}) as mock_search:
        res = sr.search_by_id("col", "id1")
        assert res == {"ids": ["x"]}
        mock_search.assert_called()


def test_calculate_similarity_metrics():
    sr = SearchRunner()
    assert sr.calculate_similarity(0.2, "cosine") == pytest.approx(0.8)
    assert sr.calculate_similarity(0.5, "dotproduct") == pytest.approx(0.5)
    assert sr.calculate_similarity(1.0, "euclidean") == pytest.approx(1.0 / (1 + 1.0))
    assert sr.calculate_similarity(2.0, "unknown") == pytest.approx(1.0 / (1 + 2.0))
