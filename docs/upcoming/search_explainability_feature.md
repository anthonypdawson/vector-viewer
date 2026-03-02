# Vector Inspector — Search Result Explainability Feature Design

## The Core Idea

Allow users to ask "why?" about their search results. Using a local LLM, Vector Inspector can explain why a specific result was returned for a query, or why one result ranked higher than another. This turns Vector Inspector from a passive result viewer into an active RAG debugging tool.

---

## What Makes This Useful

When a RAG pipeline returns unexpected results, developers currently have limited options for understanding why. They can look at similarity scores and metadata, but the gap between "this scored 0.87" and "this is why it scored 0.87" requires intuition built up over time.

The explainability feature bridges that gap — plain language explanations grounded in the actual query, document content, scores, and rankings.

---

## UI Approach

### Entry Point
Multi-select rows in the search results table. A dedicated button appears (or becomes active) in the UI — more discoverable than right-click, and naturally handles both use cases with a single control.

Button label adapts to selection:
- **1 result selected** → "Explain Result"
- **2+ results selected** → "Compare Results"

Same button, same action — behavior scales with selection. No mode switching required.

### Output Location
Explanation appears as a collapsible section in the existing **inline details pane**. This keeps it contextually connected to the result data already shown there.

- Section is hidden by default — doesn't clutter the pane for users who don't use it
- Appears and persists once explanation is generated — user can scroll back to it
- Collapsible so it can be dismissed without losing the result data

---

## The Two Modes

### Single Result — "Explain Result"

**What gets sent to the LLM:**
- The original query
- The document/chunk content
- Similarity score and rank position
- Result metadata
- Surrounding results for context (e.g. ranks 1–5) so the explanation isn't made in isolation

**Prompt intent:** *"Explain in plain language why this document is relevant to this query, and what specific aspects of the content drove the similarity score."*

**Output:** A natural language explanation identifying what the document and query have in common, which terms or concepts contributed most, and any caveats about why the match might be imperfect.

---

### Multi-Result — "Compare Results"

**What gets sent to the LLM:**
- All of the above for each selected result
- Relative ranks and scores for each
- The delta between scores if relevant

**Prompt intent:** *"Explain why result A ranked higher than result B — what does A have that B lacks for this query? What are the meaningful differences between these results from a retrieval perspective?"*

**Output:** A comparative explanation identifying what distinguishes the higher-ranked result, what the lower-ranked result is missing or has in excess, and what this suggests about how the embedding model is interpreting the query.

The comparative case is more valuable for RAG debugging — understanding *why* ranking happened the way it did is where embedding model weaknesses surface.

---

## Scoring Dimensions to Explain

The LLM explanation can be grounded in multiple signals:

| Signal | Available from |
|---|---|
| Similarity score | Already in search results |
| Rank position | Already in search results |
| Document content | Already in result data |
| Metadata fields | Already in result data |
| Query text | Already known |
| Embedding dimensions | Existing embedding inspector infrastructure |

The embedding dimension analysis (already in the roadmap) is a natural complement — the LLM explanation could reference which conceptual dimensions contributed most, backed by the dimension-level data.

---

## Relationship to the Evaluation Feature

These two features share the same core infrastructure:

| Component | Explainability | Evaluation |
|---|---|---|
| Local LLM integration | ✅ Required | ✅ Required |
| Query + result data passed to LLM | ✅ Required | ✅ Required |
| LLM prompt patterns | Similar | Similar |
| Collection cloning | ❌ Not needed | ✅ Required |
| Batch/automated runs | ❌ Not needed | ✅ Required |

Build the LLM integration layer with both features in mind to avoid implementing it twice.

---

## Suggested Ship Order

**Ship explainability first.** It is:
- Simpler — no cloning, no wizard, no cleanup
- More immediately demonstrable — a screenshot or short video of an explanation appearing in the details pane is self-explanatory
- A natural stepping stone — gets users comfortable with LLM-assisted analysis before the more complex evaluation workflow
- A good hook for discovery — *"Vector Inspector can now explain why your search returned those results"* is a concrete, tweetable capability

The evaluation feature builds naturally on top of it, and users who've used explainability will immediately understand the value of comparative evaluation.

---

## Future Extensions (v2)

- **Explain why a result was NOT returned** — given a query and a document the user expected to see, explain why it ranked low or didn't appear
- **Suggest query improvements** — given a result explanation, suggest how to rewrite the query to get better results
- **Explanation history** — persist explanations alongside results so they can be reviewed later
- **Export explanations** — include LLM explanations in exported result sets

---

## Vector Studio Limits

- Free: single result explanation only
- Free: basic LLM model (smaller/faster default)
- Studio: multi-result comparison — explain why one result ranked higher than another
- Studio: more capable LLM model selection
- Studio: explanation history and export

See [Feature Limitations](feature_limitations.md) for full details.

---

## Local LLM Integration

See the companion LLM Provider Architecture doc for full details. Summary:

- **No Ollama requirement** — llama-cpp-python runs entirely in-process, no separate server
- **Default model** ships/downloads on first use (e.g. Phi-3-mini, Qwen2.5-1.5B)
- **Provider abstraction** means Ollama, OpenAI, and llama-cpp are all interchangeable
- **Auto-detection order:** user config → Ollama if running → llama-cpp fallback
- **Configured in Settings → LLM section** (see Settings Architecture doc)

---

## Infrastructure Already Built

| Feature needed | Status |
|---|---|
| Search results table with selection | ✅ Done |
| Inline details pane | ✅ Done |
| Result data (content, score, metadata) | ✅ Done |
| Embedding dimension analysis | 🔲 In roadmap |
| Local LLM integration (Ollama) | 🔲 Needed (shared with evaluation) |
| Explanation prompt + parser | 🔲 Needed |
| Details pane explanation section | 🔲 Needed |
| Multi-select + adaptive button UI | 🔲 Needed |
