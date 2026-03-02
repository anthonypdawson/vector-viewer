# Vector Inspector vs Vector Studio — Feature Limitations

This document outlines the limitations applied to new LLM-powered features in Vector Inspector (free) compared to what is unlocked in Vector Studio. The general philosophy is **soft limits over hard gates** — free users can experience every feature, but Studio removes constraints that matter to power users and professional workflows.

---

## Search Result Explainability

### Vector Inspector (Free)
- **Single result explanation only** — select one result and explain why it was returned
- Basic LLM model (smaller/faster default, e.g. Qwen2.5-1.5B)
- Explanation grounded in query, document content, similarity score, and rank
- Output appears in inline details pane

### Vector Studio
- **Multi-result comparison** — select 2 or more results and compare why one ranked higher than another
- Access to more capable LLM models (e.g. Phi-3-mini or user-configured model)
- Comparative explanations identify embedding model weaknesses across results
- Explanation history — persist and review past explanations
- Export explanations as part of result sets

### Rationale
Single result explanation is the "aha moment" — demonstrable, shareable, immediately useful. Multi-result comparison is the deeper RAG debugging workflow that a professional user returns to repeatedly. The model quality limit also naturally separates casual use from serious use without blocking access entirely.

---

## RAG Evaluation

### Vector Inspector (Free)
- **Maximum 2 models or collections per evaluation run** — one baseline vs one alternative
- **Maximum 10 queries per evaluation run** — manual input only, no auto-generation
- **Basic scoring only** — relevance metric only (LLM-judged)
- Default LLM model only (no model selection)
- Results show winner on single metric

### Vector Studio
- **Unlimited comparisons** — run baseline against multiple models and/or databases in a single evaluation
- **Unlimited query set size**
- **Auto-generated queries** from collection data using cluster-aware sampling
- **Full scoring dimensions** — relevance, diversity, coverage/hit rate, query latency, index size
- **Model selection** — choose which LLM judges the evaluation
- **Advanced results view** — winner declared per metric with supporting breakdown
- Saved evaluation runs for historical comparison

### Rationale
The 2-model / 10-query free tier is genuinely useful for a quick sanity check — "is this new model better than my current one?" — without requiring Studio. The limits become painful for serious systematic evaluation across multiple options, which is exactly the professional use case Studio targets. Auto-generated cluster-aware sampling is one of the most sophisticated parts of the feature and a natural Studio differentiator.

---

## LLM Provider & Model Selection

### Vector Inspector (Free)
- Auto-detection only (llama-cpp-python → Ollama if running)
- Default model only — no model selection in UI
- Default context length and temperature settings
- Basic Settings → LLM section (provider status only)

### Vector Studio
- Full provider selection — llama-cpp, Ollama, OpenAI-compatible API
- Custom model selection — bring your own GGUF or Ollama model
- Configurable context length and temperature
- OpenAI-compatible API support for cloud LLM backends
- Full Settings → LLM configuration section

### Rationale
Free users get a working local LLM with zero configuration — that's the promise. Studio unlocks the ability to tune the LLM behavior for users who care about evaluation quality and have specific model preferences.

---

## Existing Feature Limits (for reference)

These limits were established prior to the features above and are documented here for completeness:

| Feature | Vector Inspector | Vector Studio |
|---|---|---|
| Search by Vector | ❌ Not available | ✅ Available |
| Advanced clustering options | ❌ Locked | ✅ Unlocked |
| Max clustering sample size | Limited | Unlimited |

---

## General Philosophy

- **No hard walls on new features** — free users can use every new capability at a meaningful level
- **Limits target professional/power use** — the constraints become painful exactly when someone is doing serious work
- **The "aha moment" is always free** — the first experience of a feature should never require Studio
- **Studio is for users who come back repeatedly** — limits are designed to be felt over time, not on first use
- **Feature flags** — limits are enforced through feature flags that Vector Studio enables; the architecture is consistent across all gated features
