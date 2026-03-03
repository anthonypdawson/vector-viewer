---
title: LLM Providers Quickstart
---

# Quickstart — LLM Provider Configuration

This quick reference shows example environment variables and selection behavior for common setups: `llama-cpp` (local in-process), `Ollama` (self-hosted HTTP), and OpenAI-compatible cloud providers.

> Note: actual provider implementations may require additional setup; this example shows the selection/configuration rules used by the runtime manager.

## Environment variables (examples)

- `VI_LLM_PROVIDER` — preferred provider id (e.g., `llama-cpp`, `ollama`, `openai`).
- `VI_LLM_MODEL` — default model name to use when none is specified in calls.
- `VI_OLLAMA_URL` — Ollama HTTP endpoint (e.g., `http://localhost:11434`).
- `OPENAI_API_KEY` — API key for OpenAI-compatible providers (used by `openai` runtime).
- `VI_LLM_DEBUG` — enable structured debug logging for selection and requests.

## Example setups

1) Local llama-cpp (in-process)

Set environment and start application with the model manager pointing to downloaded model files.

```bash
export VI_LLM_PROVIDER=llama-cpp
export VI_LLM_MODEL=ggml-vicuna-13b-q4_0
export VI_LLM_DEBUG=1
```

Notes: ensure `llama-cpp` optional deps are installed in your environment. The runtime manager will mark `health().ok == false` and include remediation hints if optional deps are missing.

2) Ollama (self-hosted HTTP)

```bash
export VI_LLM_PROVIDER=ollama
export VI_OLLAMA_URL=http://localhost:11434
export VI_LLM_MODEL=vicuna-13b
```

3) OpenAI-compatible (cloud)

```bash
export VI_LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-xxxx
export VI_LLM_MODEL=gpt-4o-mini
```

## Selection_debug example

When `VI_LLM_DEBUG=1`, the runtime manager logs a structured `selection_debug` like:

```json
{
  "selected_provider": "ollama",
  "reason": {"source":"env","key":"VI_LLM_PROVIDER","value":"ollama","timestamp":"2026-03-03T12:00:00Z"},
  "fallbacks": []
}
```

## Quick troubleshooting

- Provider missing optional deps: `health().ok == false` with `remediation_hint` describing how to install.
- Conflicting configuration: runtime manager prefers explicit app config > env vars > auto-detect > fallback.

## Next steps

- Use `--llm-dry-run` to print prompts and inspect token counts without sending requests.
- Run tests using the `fake_provider` to validate runtime manager behavior before enabling real providers in CI.
