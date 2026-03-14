"""Search AI service — builds LLM search context payloads and prompt messages.

Used by the "Ask the AI" and "Explain result" features in the Search Results
panel.  All heavy LLM I/O happens in a background QThread (SearchAIWorker);
this module only handles payload construction and prompt formatting.
"""

from __future__ import annotations

from typing import Any

_SYSTEM_PROMPT = (
    "You are a helpful assistant embedded in a vector database explorer tool. "
    "The user has performed a similarity search. "
    "You are given the search query, the top results (with their IDs, snippets, distances, and metadata), "
    "and optionally a specific result the user has selected. "
    "Each result is labeled with its absolute rank number (e.g. '#3' means it was the 3rd result "
    "in the full result list). When the user refers to 'result 3' or 'result #3', they mean the item "
    "labeled '#3' in the context below — not the 3rd item listed unless they specify that (item 3). "
    "Answer the user's question clearly and concisely. "
    "When explaining ranking or relevance, refer to the distances and content provided. "
    "Important: the provided 'distance' values represent how close each result is to the query in vector "
    "space — lower distance means the result is more similar to the query. Do NOT respond with a "
    "tautological answer such as 'Because of the distance'. Instead, use the snippets, metadata, and any "
    "matching terms or features in the context to explain *why* the item is relevant to the query. "
    "For example, point out specific keywords or phrases in the snippet that match the query, any metadata "
    "fields that align with the query (source, tags, etc.), or concrete content overlap; explain how those "
    "elements contribute to relevance. "
    "Do not invent data that is not present in the context."
    "If you cannot find supporting text, say 'No evidence in provided context."
)

_DEFAULT_TOP_N = 5
_SNIPPET_MAX_CHARS = 300

# Hard default for LLM context: send at most this many results unless
# the user explicitly overrides the selection in the Ask AI dialog.
LLM_CONTEXT_MAX = 10
# Warn (but allow) when the user selects more than this many results.
LLM_CONTEXT_WARN = 20


def estimate_tokens(context: dict[str, Any]) -> int:
    """Estimate the number of tokens in a formatted context payload.

    Uses a simple heuristic of ``chars / 4`` applied to the formatted context
    string plus the system prompt.  The estimate will be off by ±20 % in
    practice but is good enough for a real-time UI indicator.

    Args:
        context: Output from :func:`build_search_context`.

    Returns:
        Estimated token count as an integer.
    """
    context_text = _format_context(context)
    total_chars = len(_SYSTEM_PROMPT) + len(context_text)
    return max(1, total_chars // 4)


def build_search_context(
    search_input: str,
    search_results: dict[str, Any],
    selected_row: int | None = None,
    top_n: int = _DEFAULT_TOP_N,
    row_indices: list[int] | None = None,
) -> dict[str, Any]:
    """Build a structured LLM search context payload from the current search state.

    Args:
        search_input: The raw text query the user entered.
        search_results: Raw results dict from the search provider
                        (keys: ``ids``, ``documents``, ``metadatas``, ``distances``).
        selected_row: 0-based index of the currently selected result row, or None.
        top_n: Maximum number of results to include when ``row_indices`` is not
               given.  Automatically clamped to :data:`LLM_CONTEXT_MAX`.
        row_indices: If provided, include exactly these 0-based row indices
                     instead of the first ``top_n`` rows.  Indices outside the
                     result range are silently ignored.

    Returns:
        A dict with keys ``search_input``, ``top_results``, ``selected_result``.
    """
    ids = _unwrap(search_results, "ids")
    documents = _unwrap(search_results, "documents")
    metadatas = _unwrap(search_results, "metadatas")
    distances = _unwrap(search_results, "distances")

    if row_indices is not None:
        # Use explicit indices, filtered to valid range
        valid_indices = [i for i in row_indices if 0 <= i < len(ids)]
    else:
        # Clamp top_n to avoid accidentally sending huge prompts
        effective_top_n = min(top_n, LLM_CONTEXT_MAX)
        valid_indices = list(range(min(effective_top_n, len(ids))))

    top_results = []
    # Use the absolute result rank (original index + 1) so numbering in the
    # LLM context matches the UI/persistent result positions. When a windowed
    # subset is provided via `row_indices`, the displayed ranks should still
    # reflect their absolute placement in the full result list.
    for i in valid_indices:
        rank = i + 1
        item_id = ids[i]
        doc = documents[i] if i < len(documents) else ""
        meta = metadatas[i] if i < len(metadatas) else {}
        dist = distances[i] if i < len(distances) else None
        snippet = str(doc or "")[:_SNIPPET_MAX_CHARS]
        top_results.append(
            {
                "rank": rank,
                "id": str(item_id),
                "snippet": snippet,
                "distance": dist,
                "metadata": dict(meta) if meta else {},
            }
        )

    selected_result: dict[str, Any] | None = None
    if selected_row is not None and 0 <= selected_row < len(ids):
        doc = documents[selected_row] if selected_row < len(documents) else ""
        meta = metadatas[selected_row] if selected_row < len(metadatas) else {}
        dist = distances[selected_row] if selected_row < len(distances) else None
        selected_result = {
            "rank": selected_row + 1,
            "id": str(ids[selected_row]),
            "snippet": str(doc or "")[:_SNIPPET_MAX_CHARS],
            "distance": dist,
            "metadata": dict(meta) if meta else {},
        }

    return {
        "search_input": search_input,
        "top_results": top_results,
        "selected_result": selected_result,
    }


def build_messages(user_prompt: str, context: dict[str, Any]) -> list[dict[str, str]]:
    """Build the messages list to send to the LLM provider.

    Combines the system prompt, structured search context, and the user's
    free-text question into a chat-style ``[{"role": ..., "content": ...}]``
    list that all providers accept.

    Args:
        user_prompt: The user's free-text question.
        context: Output from :func:`build_search_context`.

    Returns:
        A list of message dicts suitable for ``LLMProvider.generate_messages()``.
    """
    context_text = _format_context(context)
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"{context_text}\n\n---\n\nUser question: {user_prompt}"},
    ]


def build_explain_prompt(selected_result: dict[str, Any] | None) -> str:
    """Return a prefilled prompt for the 'Explain result' shortcut.

    Args:
        selected_result: The result item the user right-clicked on, or None.

    Returns:
        A descriptive prefilled question string.
    """
    if selected_result:
        rank = selected_result.get("rank", "?")
        return f"Why is result #{rank} ranked here? What makes it relevant to my search?"
    return "Explain why these results matched my search query."


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _unwrap(results: dict[str, Any], key: str) -> list:
    """Safely unwrap potentially nested result lists (providers may wrap in an outer list)."""
    val = results.get(key)
    if not val:
        return []
    if isinstance(val, list) and val and isinstance(val[0], (list, tuple)):
        return list(val[0])
    return list(val)


def _format_context(context: dict[str, Any]) -> str:
    """Render the search context as readable plain text for inclusion in the prompt."""
    lines = [f"Search query: {context['search_input']!r}", ""]
    top = context.get("top_results", [])
    if top:
        lines.append(f"Top {len(top)} results:")
        for item in top:
            dist_str = f"{item['distance']:.4f}" if item["distance"] is not None else "N/A"
            lines.append(f"  #{item['rank']} [distance={dist_str}] id={item['id']!r}")
            if item["snippet"]:
                snippet = item["snippet"].replace("\n", " ")
                lines.append(f"      snippet: {snippet!r}")
            if item["metadata"]:
                meta_pairs = ", ".join(f"{k}={v!r}" for k, v in list(item["metadata"].items())[:5])
                lines.append(f"      metadata: {{{meta_pairs}}}")
    selected = context.get("selected_result")
    if selected:
        lines.append("")
        dist_str = f"{selected['distance']:.4f}" if selected["distance"] is not None else "N/A"
        lines.append(f"Currently selected result: #{selected['rank']} id={selected['id']!r} [distance={dist_str}]")
        if selected["snippet"]:
            lines.append(f"  snippet: {selected['snippet'].replace(chr(10), ' ')!r}")
        if selected["metadata"]:
            meta_pairs = ", ".join(f"{k}={v!r}" for k, v in list(selected["metadata"].items())[:5])
            lines.append(f"  metadata: {{{meta_pairs}}}")
    return "\n".join(lines)
