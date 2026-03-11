## Release Notes (0.6.0) — 2026-03-10

### Ask the AI — Search Results
- Add **Ask the AI** button to the Search Results toolbar and **Explain result** right-click context menu entry in the Search view.
- Clicking "Ask the AI" or "Explain result" opens a non-modal streaming dialog (`ui/components/ask_ai_dialog.py`) pre-filled with the current search context: search query, top-N results (id, snippet, score, metadata), and the selected result.
- "Explain result" pre-populates the prompt with a ranked-result explanation question; the user can edit the prompt before sending.
- Responses stream in real time from the configured LLM provider (Ollama, llama-cpp, or OpenAI-compatible) via the existing `app_state.llm_provider` — no new provider config required.
- Attached context preview is shown in a collapsible group so users can inspect what is sent before submission.
- Add `services/search_ai_service.py` — pure-Python payload builder and prompt formatter; no Qt dependencies, fully unit-tested.
- Add 22 unit tests in `tests/services/test_search_ai_service.py` covering payload building, nested result unwrapping, snippet truncation, prompt generation, and context formatting.

### Ask the AI — LLM Context Clamping & Result Selection
- **LLM context now clamped** by default to the top 10 results (`LLM_CONTEXT_MAX = 10`) to prevent
  accidental context-window overflows; previously the full table size (up to 100) was sent.
- **User-configurable result selection** in the Ask AI dialog: a new collapsible "Result selection"
  section shows a checkable list of all available results plus range quick-selectors (From / To
  spinboxes + "Apply Range" button), so users can choose exactly which rows are included.
- **Reset to Default** button restores the selection back to the initial top-N rows each time
  the dialog is opened.
- **Real-time token estimate** label (`~X tokens — Y results selected`) updates as the selection
  changes, giving users immediate feedback before sending.
- **Over-limit warning** displayed when more than `LLM_CONTEXT_WARN = 20` results are selected,
  advising users to reduce the selection to keep prompts small.
- **"Configure LLM…" button** appears in the status bar when no LLM provider is configured,
  opening the Settings dialog directly — no manual navigation required.
- **LLM availability check** in both `_ask_ai()` and `_explain_result()`: if the LLM provider is
  not available a message is shown with an "Open Settings" shortcut; the dialog does not open.
- **Explain result 3-item window**: the "Explain result" action now sends only the selected result
  plus the row immediately before and after it (guarding against first/last-row edge cases), instead
  of the full top-N context.  This keeps explanation prompts tight and focused.
- Add `estimate_tokens(context)` utility to `search_ai_service.py` (chars / 4 heuristic).
- Add `LLM_CONTEXT_MAX` and `LLM_CONTEXT_WARN` constants to `search_ai_service.py`.
- Add `row_indices` parameter to `build_search_context` for explicit result selection override.
- Service tests extended to 31 (up from 22); view tests extended to 13 (up from ~5).

---