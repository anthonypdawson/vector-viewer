"""Tests for search_ai_service — payload building and prompt formatting."""

import pytest

from vector_inspector.services.search_ai_service import (
    LLM_CONTEXT_MAX,
    LLM_CONTEXT_WARN,
    _format_context,
    _unwrap,
    build_explain_prompt,
    build_messages,
    build_search_context,
    estimate_tokens,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FLAT_RESULTS = {
    "ids": ["id1", "id2", "id3"],
    "documents": ["doc one", "doc two", "doc three"],
    "metadatas": [{"tag": "a"}, {"tag": "b"}, {"tag": "c"}],
    "distances": [0.1, 0.2, 0.3],
}

_NESTED_RESULTS = {
    "ids": [["id1", "id2"]],
    "documents": [["doc one", "doc two"]],
    "metadatas": [[{"tag": "a"}, {"tag": "b"}]],
    "distances": [[0.1, 0.2]],
}


# ---------------------------------------------------------------------------
# _unwrap
# ---------------------------------------------------------------------------


def test_unwrap_flat_list():
    assert _unwrap({"ids": ["a", "b"]}, "ids") == ["a", "b"]


def test_unwrap_nested_list():
    assert _unwrap({"ids": [["a", "b"]]}, "ids") == ["a", "b"]


def test_unwrap_missing_key():
    assert _unwrap({}, "ids") == []


def test_unwrap_empty_value():
    assert _unwrap({"ids": []}, "ids") == []


# ---------------------------------------------------------------------------
# build_search_context
# ---------------------------------------------------------------------------


def test_context_top_results_count():
    ctx = build_search_context("hello", _FLAT_RESULTS, top_n=2)
    assert len(ctx["top_results"]) == 2


def test_context_top_results_fields():
    ctx = build_search_context("hello", _FLAT_RESULTS, top_n=3)
    item = ctx["top_results"][0]
    assert item["rank"] == 1
    assert item["id"] == "id1"
    assert item["distance"] == pytest.approx(0.1)
    assert item["snippet"] == "doc one"
    assert item["metadata"] == {"tag": "a"}


def test_context_search_input_preserved():
    ctx = build_search_context("my query", _FLAT_RESULTS)
    assert ctx["search_input"] == "my query"


def test_context_no_selected_result_when_none():
    ctx = build_search_context("q", _FLAT_RESULTS, selected_row=None)
    assert ctx["selected_result"] is None


def test_context_selected_result_correct():
    ctx = build_search_context("q", _FLAT_RESULTS, selected_row=1)
    sel = ctx["selected_result"]
    assert sel is not None
    assert sel["rank"] == 2
    assert sel["id"] == "id2"
    assert sel["distance"] == pytest.approx(0.2)


def test_context_selected_row_out_of_bounds():
    ctx = build_search_context("q", _FLAT_RESULTS, selected_row=99)
    assert ctx["selected_result"] is None


def test_context_handles_nested_results():
    ctx = build_search_context("q", _NESTED_RESULTS, top_n=2)
    assert len(ctx["top_results"]) == 2
    assert ctx["top_results"][0]["id"] == "id1"


def test_context_snippet_truncated():
    long_doc = "x" * 400
    results = {
        "ids": ["id1"],
        "documents": [long_doc],
        "metadatas": [{}],
        "distances": [0.5],
    }
    ctx = build_search_context("q", results, top_n=1)
    assert len(ctx["top_results"][0]["snippet"]) <= 300


# ---------------------------------------------------------------------------
# build_explain_prompt
# ---------------------------------------------------------------------------


def test_explain_prompt_with_selected_result():
    selected = {"rank": 3, "id": "abc", "distance": 0.7, "snippet": "", "metadata": {}}
    prompt = build_explain_prompt(selected)
    assert "3" in prompt
    assert len(prompt) > 10


def test_explain_prompt_without_selected_result():
    prompt = build_explain_prompt(None)
    assert isinstance(prompt, str)
    assert len(prompt) > 5


# ---------------------------------------------------------------------------
# build_messages
# ---------------------------------------------------------------------------


def test_messages_has_system_and_user_roles():
    ctx = build_search_context("test", _FLAT_RESULTS, top_n=2)
    msgs = build_messages("Why is result 1 ranked first?", ctx)
    roles = [m["role"] for m in msgs]
    assert "system" in roles
    assert "user" in roles


def test_messages_user_contains_prompt():
    ctx = build_search_context("test", _FLAT_RESULTS, top_n=2)
    msgs = build_messages("My question here", ctx)
    user_msg = next(m for m in msgs if m["role"] == "user")
    assert "My question here" in user_msg["content"]


def test_messages_user_contains_search_input():
    ctx = build_search_context("find cats", _FLAT_RESULTS, top_n=2)
    msgs = build_messages("explain", ctx)
    user_msg = next(m for m in msgs if m["role"] == "user")
    assert "find cats" in user_msg["content"]


def test_messages_user_contains_selected_result_info():
    ctx = build_search_context("q", _FLAT_RESULTS, selected_row=0, top_n=3)
    msgs = build_messages("explain", ctx)
    user_msg = next(m for m in msgs if m["role"] == "user")
    assert "id1" in user_msg["content"]


# ---------------------------------------------------------------------------
# _format_context
# ---------------------------------------------------------------------------


def test_format_context_includes_query():
    ctx = build_search_context("my search", _FLAT_RESULTS, top_n=2)
    text = _format_context(ctx)
    assert "my search" in text


def test_format_context_includes_scores():
    ctx = build_search_context("q", _FLAT_RESULTS, top_n=2)
    text = _format_context(ctx)
    assert "0.1000" in text
    assert "distance=" in text


def test_format_context_includes_selected_when_present():
    ctx = build_search_context("q", _FLAT_RESULTS, selected_row=2, top_n=3)
    text = _format_context(ctx)
    assert "id3" in text
    assert "selected" in text.lower()


def test_format_context_no_selected_when_absent():
    ctx = build_search_context("q", _FLAT_RESULTS, selected_row=None, top_n=2)
    text = _format_context(ctx)
    assert "selected" not in text.lower()


# ---------------------------------------------------------------------------
# LLM_CONTEXT_MAX clamping and row_indices override
# ---------------------------------------------------------------------------

# Build a large fake result set (25 items)
_LARGE_RESULTS = {
    "ids": [f"id{i}" for i in range(25)],
    "documents": [f"doc {i}" for i in range(25)],
    "metadatas": [{"i": i} for i in range(25)],
    "distances": [i * 0.01 for i in range(25)],
}


def test_context_clamped_to_llm_context_max():
    """Without row_indices, top_n is clamped to LLM_CONTEXT_MAX even if caller passes top_n=100."""
    ctx = build_search_context("q", _LARGE_RESULTS, top_n=100)
    assert len(ctx["top_results"]) <= LLM_CONTEXT_MAX


def test_context_row_indices_override():
    """Explicit row_indices selects exactly those rows in the given order, rank starts at 1."""
    ctx = build_search_context("q", _LARGE_RESULTS, row_indices=[2, 0])
    assert len(ctx["top_results"]) == 2
    assert ctx["top_results"][0]["id"] == "id2"
    # Ranks reflect absolute positions in the full result list (index+1)
    assert ctx["top_results"][0]["rank"] == 3
    assert ctx["top_results"][1]["id"] == "id0"
    assert ctx["top_results"][1]["rank"] == 1


def test_context_row_indices_out_of_bounds_ignored():
    """Out-of-bounds indices are silently dropped; valid ones are preserved."""
    ctx = build_search_context("q", _LARGE_RESULTS, row_indices=[0, 999, 1])
    ids = [r["id"] for r in ctx["top_results"]]
    assert "id0" in ids
    assert "id1" in ids
    # 999 is out of range and must not appear
    assert len(ctx["top_results"]) == 2


def test_context_row_indices_empty_list():
    """Passing an empty row_indices returns no top_results."""
    ctx = build_search_context("q", _LARGE_RESULTS, row_indices=[])
    assert ctx["top_results"] == []


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


def test_estimate_tokens_returns_positive_int():
    ctx = build_search_context("hello", _FLAT_RESULTS, top_n=2)
    tokens = estimate_tokens(ctx)
    assert isinstance(tokens, int)
    assert tokens > 0


def test_estimate_tokens_larger_context_gives_more_tokens():
    small_ctx = build_search_context("q", _FLAT_RESULTS, top_n=1)
    large_ctx = build_search_context("q", _FLAT_RESULTS, top_n=3)
    assert estimate_tokens(large_ctx) >= estimate_tokens(small_ctx)


def test_estimate_tokens_proportional():
    """Two identical contexts should produce the same estimate."""
    ctx1 = build_search_context("same query", _FLAT_RESULTS, top_n=2)
    ctx2 = build_search_context("same query", _FLAT_RESULTS, top_n=2)
    assert estimate_tokens(ctx1) == estimate_tokens(ctx2)


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


def test_llm_context_max_is_positive():
    assert LLM_CONTEXT_MAX > 0


def test_llm_context_warn_gt_max():
    assert LLM_CONTEXT_WARN > LLM_CONTEXT_MAX
