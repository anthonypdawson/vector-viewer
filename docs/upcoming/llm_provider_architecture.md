# Vector Inspector — LLM Provider Architecture & Settings Redesign

## LLM Provider Abstraction

A clean provider interface so evaluation and explainability features are decoupled from any specific LLM backend:

```python
class LLMProvider:
    def generate(self, prompt: str) -> str: ...
    def is_available(self) -> bool: ...
    def get_model_name(self) -> str: ...

class LlamaCppProvider(LLMProvider): ...   # default, in-process
class OllamaProvider(LLMProvider): ...     # if Ollama is running
class OpenAICompatibleProvider(LLMProvider): ...  # cloud or local OpenAI-compatible API
```

This mirrors the existing vector DB connection abstraction — new providers can be added without touching evaluation or explainability code.

---

## Provider Selection — Auto-Detection Order

On first use (or when no provider is configured), detect in priority order:

1. **User-configured provider** in Settings → LLM
2. **Ollama** — check if running at `localhost:11434`, use opportunistically
3. **llama-cpp-python** — in-process fallback, download default model if needed

This means users with Ollama already running get that automatically. Everyone else just works with zero setup.

---

## llama-cpp-python (Default Provider)

Runs entirely in-process via Python bindings for llama.cpp. No separate server, no API keys.

**Advantages:**
- Zero setup for end users
- No data leaves the machine
- GPU acceleration if available, CPU fallback if not
- Uses existing model cache infrastructure

**Default model candidates** (small enough for CPU, capable enough for the task):
- `Phi-3-mini-4k-instruct` (3.8B) — Microsoft, excellent instruction following
- `Qwen2.5-1.5B-Instruct` — tiny, surprisingly capable
- `Llama-3.2-1B-Instruct` — Meta's smallest

Recommendation: **Phi-3-mini** as default — best balance of size and quality for explanation/evaluation tasks.

**Model delivery:**
- Download GGUF file on first use, store in existing model cache directory
- Show download progress in the same loading dialog pattern already used elsewhere
- User can swap to a different GGUF model via Settings → LLM

**Windows note:** Pre-built wheels for llama-cpp-python are available on PyPI and should work without C++ build tools, but worth testing on Windows specifically before committing to this as default.

---

## Settings Dialog Redesign

The settings dialog needs sections. Current single-window approach won't scale as LLM config, embedding config, appearance, cache, and telemetry all compete for space.

### Recommended Structure

**Sidebar navigation** (similar to VS Code settings, or System Preferences style):

```
Settings
├── General
│   ├── Appearance
│   ├── Breadcrumbs
│   └── Default behaviors
├── Connections
│   └── Max connections, auto-reconnect, etc.
├── Embeddings
│   └── Model cache, custom models, auto-generate
├── LLM                          ← new
│   ├── Provider selection
│   ├── Default model
│   ├── Model cache directory
│   └── Advanced (context length, temperature, etc.)
├── Cache
│   └── Search cache, TTL, etc.
├── Telemetry
│   └── Enable/disable, privacy info
└── Advanced
    └── Logging, debug options
```
For existing settings, just move them into the appropriate section without changing the UI controls too much. For LLM settings, design new controls as needed (dropdowns, file pickers, sliders).

### LLM Settings Section (detail)

| Setting | Type | Default |
|---|---|---|
| Provider | Dropdown (Auto / llama-cpp / Ollama / OpenAI-compatible) | Auto |
| Default model (llama-cpp) | File picker + download button | Phi-3-mini |
| Model cache directory | Directory picker | `~/.vector-inspector/llm_cache` |
| Ollama base URL | Text field | `http://localhost:11434` |
| OpenAI-compatible base URL | Text field | — |
| OpenAI-compatible API key | Password field | — |
| Model name (OpenAI-compatible) | Text field | — |
| Context length | Spinner | 4096 |
| Temperature | Slider (0.0–1.0) | 0.1 (low for deterministic explanations) |

**Auto provider** should show which provider was detected and is currently active, so the user understands what's happening without having to configure anything.

---

## Vector Studio Limits

- Free: auto-detection only, default model, no configuration
- Free: basic Settings → LLM section (provider status display only)
- Studio: full provider selection (llama-cpp, Ollama, OpenAI-compatible)
- Studio: custom model selection, configurable context length and temperature
- Studio: OpenAI-compatible API support for cloud backends
- Studio: full Settings → LLM configuration section

See [Feature Limitations](feature_limitations.md) for full details.

---

## Shared Infrastructure

Both the explainability and evaluation features use the same LLM provider layer — implement once, use everywhere:

```
LLMProviderFactory
    ├── ExplainabilityService   (uses LLMProvider)
    └── EvaluationService       (uses LLMProvider)
```

Mirrors the existing `ProviderFactory` / connection pattern already in the codebase.

---

## Model Cache Integration

llama-cpp GGUF models should use the same cache infrastructure as embedding models:

- Same cache directory structure
- Same settings for custom cache directory
- Same cache info display in Settings → Cache
- Same `clear cache` flow

Avoids duplicating cache management logic and keeps the UX consistent.

---

## Implementation Notes

- Temperature should default low (0.1) for explanation tasks — you want deterministic, factual output not creative generation
- Context window needs to be large enough for query + multiple documents + prompt — 4096 minimum, 8192 preferred
- Streaming output would improve perceived responsiveness for longer explanations — worth considering for the details pane
- The `is_available()` check on each provider enables graceful degradation and clear error messaging ("Ollama was detected but is no longer running — falling back to llama-cpp")
