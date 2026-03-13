"""Unit tests for the SearchContext dataclass and AppState.search_context integration."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vector_inspector.state import AppState, SearchContext

# ---------------------------------------------------------------------------
# SearchContext dataclass
# ---------------------------------------------------------------------------


def test_search_context_requires_query_text():
    ctx = SearchContext(query_text="hello")
    assert ctx.query_text == "hello"


def test_search_context_defaults_query_embedding_to_none():
    ctx = SearchContext(query_text="q")
    assert ctx.query_embedding is None


def test_search_context_defaults_embedding_model_to_none():
    ctx = SearchContext(query_text="q")
    assert ctx.embedding_model is None


def test_search_context_defaults_embedding_provider_to_none():
    ctx = SearchContext(query_text="q")
    assert ctx.embedding_provider is None


def test_search_context_timestamp_is_utc_aware():
    ctx = SearchContext(query_text="q")
    assert ctx.timestamp.tzinfo is not None
    assert ctx.timestamp.tzinfo == UTC


def test_search_context_timestamp_is_recent():
    before = datetime.now(UTC)
    ctx = SearchContext(query_text="q")
    after = datetime.now(UTC)
    assert before <= ctx.timestamp <= after


def test_search_context_accepts_query_embedding():
    emb = [0.1, 0.2, 0.3]
    ctx = SearchContext(query_text="q", query_embedding=emb)
    assert ctx.query_embedding == [0.1, 0.2, 0.3]


def test_search_context_accepts_embedding_model():
    ctx = SearchContext(query_text="q", embedding_model="all-MiniLM-L6-v2")
    assert ctx.embedding_model == "all-MiniLM-L6-v2"


def test_search_context_accepts_embedding_provider():
    ctx = SearchContext(query_text="q", embedding_provider="chromadb")
    assert ctx.embedding_provider == "chromadb"


def test_search_context_all_fields():
    emb = [0.5, 0.6]
    ts = datetime(2026, 3, 12, 0, 0, 0, tzinfo=UTC)
    ctx = SearchContext(
        query_text="my query",
        timestamp=ts,
        query_embedding=emb,
        embedding_model="text-embedding-3-small",
        embedding_provider="openai",
    )
    assert ctx.query_text == "my query"
    assert ctx.timestamp == ts
    assert ctx.query_embedding == [0.5, 0.6]
    assert ctx.embedding_model == "text-embedding-3-small"
    assert ctx.embedding_provider == "openai"


def test_search_context_equality():
    ts = datetime(2026, 3, 12, 0, 0, 0, tzinfo=UTC)
    ctx1 = SearchContext(query_text="q", timestamp=ts, query_embedding=[0.1])
    ctx2 = SearchContext(query_text="q", timestamp=ts, query_embedding=[0.1])
    assert ctx1 == ctx2


def test_search_context_inequality_on_query_text():
    ts = datetime(2026, 3, 12, 0, 0, 0, tzinfo=UTC)
    ctx1 = SearchContext(query_text="a", timestamp=ts)
    ctx2 = SearchContext(query_text="b", timestamp=ts)
    assert ctx1 != ctx2


# ---------------------------------------------------------------------------
# AppState.search_context property
# ---------------------------------------------------------------------------


@pytest.fixture
def app_state(qapp):
    return AppState()


def test_search_context_initially_none(app_state):
    assert app_state.search_context is None


def test_search_context_property_returns_full_context(app_state):
    ctx = SearchContext(
        query_text="test query",
        query_embedding=[0.1, 0.2],
        embedding_model="all-MiniLM-L6-v2",
        embedding_provider="qdrant",
    )
    app_state.set_search_results({"ids": ["x"]}, context=ctx)
    stored = app_state.search_context
    assert stored is ctx


def test_search_context_persists_query_embedding(app_state):
    emb = [0.3, 0.4, 0.5]
    ctx = SearchContext(query_text="q", query_embedding=emb)
    app_state.set_search_results({"ids": []}, context=ctx)
    assert app_state.search_context.query_embedding == emb


def test_search_context_persists_embedding_model(app_state):
    ctx = SearchContext(query_text="q", embedding_model="paraphrase-MiniLM-L6-v2")
    app_state.set_search_results({"ids": []}, context=ctx)
    assert app_state.search_context.embedding_model == "paraphrase-MiniLM-L6-v2"


def test_search_context_persists_embedding_provider(app_state):
    ctx = SearchContext(query_text="q", embedding_provider="lancedb")
    app_state.set_search_results({"ids": []}, context=ctx)
    assert app_state.search_context.embedding_provider == "lancedb"


def test_search_query_shim_returns_query_text(app_state):
    ctx = SearchContext(query_text="shim check")
    app_state.set_search_results({"ids": []}, context=ctx)
    assert app_state.search_query == "shim check"


def test_search_query_shim_returns_none_when_no_context(app_state):
    assert app_state.search_query is None


def test_search_context_cleared_on_clear_search_results(app_state):
    ctx = SearchContext(query_text="q", query_embedding=[1.0], embedding_model="m")
    app_state.set_search_results({"ids": []}, context=ctx)
    app_state.clear_search_results()
    assert app_state.search_context is None
    assert app_state.search_query is None


def test_set_search_results_without_context_preserves_existing(app_state):
    ctx = SearchContext(query_text="original", query_embedding=[0.9])
    app_state.set_search_results({"ids": ["a"]}, context=ctx)
    # second call with no context — existing context must be unchanged
    app_state.set_search_results({"ids": ["b"]})
    assert app_state.search_context is ctx
    assert app_state.search_query == "original"
