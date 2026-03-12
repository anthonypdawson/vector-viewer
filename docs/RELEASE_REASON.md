## Release Notes (0.6.0) — 2026-03-10

### 🚀 Vector Inspector Becomes AI‑Augmented
This release introduces **Ask the AI**, a new interactive assistant that can explain search results, analyze ranking behavior, summarize clusters, and help you understand *why* items ranked the way they did.  
It’s the first release where Vector Inspector doesn’t just show your data — it interprets it.

---

## 🧠 Ask the AI — Search Results

Vector Inspector now includes an AI‑powered assistant that can explain search results, summarize clusters, and provide natural‑language insight into semantic search behavior.

- Added **Ask the AI** button to the Search Results toolbar and **Explain result** to the right‑click context menu.
- Opening Ask the AI launches a non‑modal streaming dialog (`ui/components/ask_ai_dialog.py`) pre‑filled with:
  - the search query  
  - top‑N results (id, snippet, score, metadata)  
  - the selected result  
- **Explain result** auto‑generates a focused explanation prompt that the user may edit before sending.
- Responses stream in real time from the configured LLM provider (Ollama, llama‑cpp, or any OpenAI‑compatible API) using the existing `app_state.llm_provider`.
- A collapsible **Context Preview** shows exactly what will be sent to the LLM.
- Added `services/search_ai_service.py` — a pure‑Python payload builder and prompt formatter (fully unit‑tested, no Qt dependencies).
- Added 22 unit tests covering payload building, nested result unwrapping, snippet truncation, prompt generation, and context formatting.

---

## 🎛️ Ask the AI — Context Clamping & Result Selection

To keep prompts efficient and prevent runaway context windows, Ask the AI now includes smarter defaults and user‑controlled selection tools.

- **Context clamped** to the top 10 results (`LLM_CONTEXT_MAX = 10`) to avoid accidental overflows.
- New **Result Selection** panel:
  - checkable list of all results  
  - range selectors (From/To + Apply Range)  
  - **Reset to Default** restores the initial top‑N  
- **Real‑time token estimate** (`~X tokens — Y results selected`) updates as the selection changes.
- **Over‑limit warning** when more than 20 results are selected (`LLM_CONTEXT_WARN = 20`).
- **Configure LLM…** button appears when no provider is configured.
- LLM availability checks added to `_ask_ai()` and `_explain_result()` with direct Settings shortcuts.
- **Explain result** now uses a **3‑item window** (selected row ± 1) for tighter, more focused prompts.
- Added `estimate_tokens(context)` utility (chars / 4 heuristic).
- Added `row_indices` override to `build_search_context`.
- Service tests expanded to 31; view tests expanded to 13.

---