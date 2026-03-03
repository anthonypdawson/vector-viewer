---
title: LLM Providers — Consolidated Design
---

# LLM Providers — Consolidated Design

This document captures the combined recommendations for the `llm-providers` branch: a minimal, consistent provider interface, a model manager separation, normalized errors and capabilities, and a deterministic, debuggable runtime.

**Goal:** provide a single, well-documented provider layer for Vector Inspector / Vector Studio that: is pluggable, testable, and consistent across local (llama-cpp), self-hosted (Ollama), and cloud (OpenAI-compatible) providers.

**Audience:** maintainers of `src/**` provider code, Vector Studio integration engineers, and UI authors.

---

## 1. Design Principles

- Keep the provider layer narrowly scoped to text generation and model metadata.
- Separate provider lifecycle and selection from model file management and caching.
- Normalize surface area: capabilities, health checks, a unified `generate()` signature, and a streaming contract.
- Treat optional deps (e.g., `llama-cpp`) as feature flags with runtime checks and clear warnings.

## 2. Base Provider Interface (concept)

Provide a minimal provider API surface so upper layers do not need provider-specific logic.

- `generate(messages, model, stream=False, **kwargs)` — single canonical call for completions/chat.
- `stream(messages, model, **kwargs)` — returns an async iterator or sync generator per runtime.
- `models()` — list available models + metadata.
- `capabilities()` — `ProviderCapabilities` object describing streaming, max context, tokenizer info, roles.
- `health()` — lightweight probe of connectivity and model availability.

Keep the interface small so consumers only rely on stable, well-tested primitives.

## 3. Provider vs Model

- Provider identity: the runtime integration (llama-cpp process, Ollama HTTP endpoint, OpenAI-compatible HTTP).
- Model identity: a model artifact available through a provider (e.g., `ggml-vicuna-13b-q4_0`).

Providers may expose many models — expose them via `models()` and include per-model metadata (context window, tokenizer, cost estimates).

## 4. ProviderCapabilities (schema)

Include a small, versioned capabilities object so the UI/runtime can adapt safely when schema evolves.

Fields (suggested):
- `schema_version: str`
- `provider_name: str`
- `supports_streaming: bool`
- `max_context_tokens: int`
- `roles_supported: list[str]` (e.g. `["system","user","assistant"]`)
- `model_list: list[ModelMetadata]`
- `tokenizer: TokenizerInfo | None`

ModelMetadata should include `model_name`, `context_window`, optional `rate_limit`, and `cost_estimate_per_token` when available.

## 5. TokenizerInfo

Provide a small tokenizer adapter returning:
- encoding name
- a `count_tokens(messages)` helper
- encode/decode hooks (optional)

This lets RAG and UI reliably budget token usage across providers.

## 6. Model Manager (separate module)

Responsibilities (not owned by provider):
- download and verify models
- maintain filesystem layout and consistent paths
- LRU eviction / disk-space policy
- per-model locks for concurrent load/preload
- provide preloaded model handles to in-process providers (llama-cpp)
- expose metrics (load time, size, last_used)

Rationale: keep providers focused on runtime integration, not artifact lifecycle.

## 7. Provider Factory vs Runtime Manager

- Factory: pure, side-effect-free construction (decide which provider class to instantiate, return descriptor). Always deterministic.
- Runtime manager: owns stateful concerns (cached provider instances, credential refresh, health polling, debug selection reason strings).

Add a `selection_debug` string in the runtime manager (structured JSON) that records the exact decision path (env var, auto-detect result, fallback). Redact secrets but keep keys and non-sensitive values.

## 8. Unified `generate()` API and Streaming Contract

- Signature: `generate(messages, model, stream=False, **kwargs)`
- If `stream=True`, providers MUST return a streaming iterator with a normalized event shape.

Event shape (single canonical example):

```json
{ "type": "token" | "delta" | "done" | "error",
  "content": "...",
  "token": "..." (optional),
  "meta": { ... } }
```

- Sync environments: provider may return a sync generator.
- Async environments: provider returns an async iterator (awaitable). The runtime manager should adapt or expose both to callers.

Backpressure and batching rules should be documented per provider (e.g., how tokens are flushed).

## 9. Error Normalization

All provider exceptions must be normalized to a `ProviderError` hierarchy with fields:
- `provider_name`
- `model_name`
- `underlying_error` (message)
- `retryable: bool`
- `code` or `http_status` (when applicable)
- `remediation_hint` (optional short text)

This lets UI and pipelines make consistent retry and fallback decisions.

## 10. Health Checks

`health()` should be fast and predictable. Suggested return shape:

```json
{
  "ok": true,
  "provider": "ollama",
  "models": ["model-a","model-b"],
  "version": "v1.2.3",
  "last_checked": "2026-03-03T12:00:00Z",
  "retryable": false
}
```

Distinguish cached last-known state vs active probe. The runtime manager can expose both `health()` (cached) and `probe()` (active async probe).

## 11. Optional Dependencies & Runtime Checks

- Keep `llm` and heavy libs optional.
- On startup/runtime selection, warn (but do not crash) if a provider is selected but the optional dependency is missing.

Example: if `llama-cpp` selected but missing, runtime manager returns a clear debug string and `health().ok == false` with remediation.

## 12. UI Integration

UI should query the runtime manager for:
- available providers and their `capabilities()`
- `models()` including per-model metadata
- `health()` summary

Avoid hardcoding provider names or model lists in UI; read capabilities and adapt feature flags (e.g., streaming toggle, context slider).

## 13. Architectural Boundaries

Provider layer must only implement text generation and metadata. Do NOT implement retrieval, embeddings, chunking, or RAG pipelines. Maintain the following stack:

```
Provider Layer
Embedding Layer
Vector DB Layer
Retrieval Layer
Prompt Assembly Layer
Pipeline Layer
UI Layer
```

## 14. Debugging & Developer DX

- Add `--llm-dry-run` mode to print assembled prompts without sending them.
- Add structured debug logs for selection and request metadata; make the format machine-parseable JSON.

## 15. Testing & CI

Add focused tests as part of this work:
- capabilities schema conformance
- streaming iterator conformance across providers (mocked)
- model manager locking / eviction tests
- provider factory deterministic selection tests

## 16. Quick Example (python dataclasses)

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TokenizerInfo:
    encoding: str
    def count_tokens(self, texts: List[str]) -> int: ...

@dataclass
class ModelMetadata:
    model_name: str
    context_window: int
    cost_estimate_per_1k: Optional[float] = None

@dataclass
class ProviderCapabilities:
    schema_version: str
    provider_name: str
    supports_streaming: bool
    max_context_tokens: int
    roles_supported: List[str]
    model_list: List[ModelMetadata]
    tokenizer: Optional[TokenizerInfo]
```

## 17. Next Steps

1. Implement `ProviderCapabilities` dataclass and tests.
2. Add model manager module and simple LRU eviction implementation.
3. Implement streaming event type and cross-provider conformance tests.
4. Add runtime manager selection debug logging and `--llm-dry-run` CLI.

---

## Refinements and Clarifications

### Provider instance lifecycle

Clarify provider lifetime and state expectations to avoid implementation ambiguity:

- Long‑lived singletons: providers are expected to be long‑lived instances managed by the runtime manager in most cases. This allows providers to maintain internal state such as HTTP sessions, cached auth tokens, and connection pools.
- Recreated per request: only allowed for lightweight providers where construction is cheap; avoid per-request recreation for providers that maintain native resources (e.g., in‑process runtimes).
- Internal state: providers MAY maintain internal state (persistent HTTP sessions, sockets, model handles) but MUST document thread-safety guarantees and expose a `close()`/`shutdown()` method when applicable.

Runtime manager behavior: the runtime manager decides whether to reuse or recreate providers and documents the policy in logs (`selection_debug`). Implementations should assume providers are reusable unless explicitly documented otherwise.

### Concrete `generate()` example

Provide a concrete callsite example to anchor expectations:

```python
resp = provider.generate(
    messages=[{"role": "user", "content": "Explain vector search"}],
    model="llama-3.1",
    stream=False,
    temperature=0.2,
)
```

If `stream=True`, the caller receives an iterator (sync or async depending on runtime) that yields the normalized streaming events described below.

### Expanded streaming event examples

Canonical event shape is small and consistent. Example event sequence:

```json
{ "type": "delta", "content": "vec", "meta": {"index": 0} }
{ "type": "delta", "content": "tor", "meta": {"index": 1} }
{ "type": "done",  "content": "",    "meta": {"finish_reason": "stop"} }
```

- `delta` vs `token`: `delta` is the recommended name for incremental text fragments (may be sub-token or grouped tokens) emitted by providers.
- `token` may be used when the provider emits discrete token objects; both must be handled by consumers.
- `done` signals completion and may include `finish_reason` metadata.

Document per-provider flushing/backpressure notes where necessary (e.g., llama-cpp may batch tokens differently than HTTP providers).

### Thread safety and concurrency

Set clear expectations to avoid subtle races:

- `llama-cpp` concurrency: document whether the provider supports concurrent `generate()` calls. If not, the runtime manager must serialize access or spawn isolated processes.
- Model manager locking: the model manager must provide per-model locks to ensure only one load/eviction operation occurs concurrently for a model.
- Runtime manager: may choose to serialize requests per in‑process provider or allow concurrent requests depending on provider capabilities — this policy must be surfaced in `capabilities()` (e.g., `concurrency: "single-threaded" | "multi"`).

### Configuration discovery rules

Make provider selection deterministic and debuggable. Suggested discovery rules (high-level):

1. Explicit config entry in application settings (highest precedence).
2. Environment variables (e.g., `VI_LLM_PROVIDER`, `VI_LLM_MODEL`, `VI_OLLAMA_URL`).
3. Auto-detection (e.g., Ollama endpoint reachable, local llama runtime available).
4. Fallback default (e.g., `openai` compatibility when API key present).

On conflict, the runtime manager must prefer higher precedence sources and record the decision path in `selection_debug` (structured JSON), including which env var or config entry led to selection. Secrets must be redacted in logs.

---

Document created as a foundation to implement the recommendations in the `llm-providers` branch. For follow-ups I can add the dataclass module and migration shim code.

## Additional refinements

### Responsibility matrix

Short, prescriptive mapping of responsibilities to avoid ambiguity across layers:

- Runtime Manager: provider selection, selection reason recording, global retries and circuit-breaking policies, traffic shaping and rate limiting orchestration, provider instance lifecycle management.
- Provider: transport-level retries, error normalization, per-request timeouts, connection/session management.
- Model Manager: model artifact lifecycle (download, verify, eviction), per-model locks, capacity-aware loading.
- Pipeline / UI: high-level retry policies (user-visible attempts), user-facing fallbacks, budget/cost decisions.

Keep this matrix small and authoritative — prefer a single source-of-truth in code/docs when behavior is implemented.

### ProviderCapabilities additions

Add the following fields to `ProviderCapabilities`:

- `supports_tools: bool` — indicates whether the provider supports tool invocation or structured JSON modes.
- `concurrency: str` — one of `"single-threaded" | "multi" | "process-isolated"` describing how the runtime should treat concurrent requests.

Example augmented `ProviderCapabilities` entry:

```python
ProviderCapabilities(
        schema_version="1",
        provider_name="ollama",
        supports_streaming=True,
        supports_tools=False,
        concurrency="multi",
        max_context_tokens=32768,
        roles_supported=["system","user","assistant"],
        model_list=[...],
)
```

### Streaming & error model (refinements)

- Canonical stream event: use `delta` for incremental text fragments; `token` is optional for providers that emit token objects.
- Each streaming event `meta` MUST include `request_id` or `trace_id` for log correlation, and may include `timestamp` and `seq`/`index` for ordering.
- Example streaming event sequence:

```json
{ "type": "delta", "content": "vec", "meta": {"request_id": "r-123", "index": 0} }
{ "type": "delta", "content": "tor", "meta": {"request_id": "r-123", "index": 1} }
{ "type": "done",  "content": "",    "meta": {"request_id": "r-123", "finish_reason": "stop"} }
```

Include `retryable` boolean in normalized error objects and provide short `remediation_hint` strings where applicable.

### Structured selection reason

Runtime manager must record a structured selection reason rather than free-form text. Suggested schema:

```json
{
    "source": "env" | "config" | "auto" | "default",
    "key": "VI_LLM_PROVIDER",
    "value": "ollama",
    "timestamp": "2026-03-03T12:00:00Z",
    "precedence_rank": 1
}
```

This object should be included in `selection_debug` and redacted where values contain secrets.

### Fake provider spec (for tests & demos)

Provide a minimal fake provider implementation used for CI, local dev, and demos. Requirements:

- Deterministic behavior: given a `seed` and `messages`, return deterministic outputs.
- Modes:
    - `echo`: returns concatenated user messages as the assistant response.
    - `streaming`: yields `delta` fragments deterministically (configurable fragment size and latency).
    - `error_inject`: simulate transient or permanent errors for retry/fallback tests.
- Config options: `latency_ms`, `fragment_size`, `seed`, `error_rate`, `default_model`.
- API: implement the full provider interface: `generate()`, `stream()`, `models()`, `capabilities()`, `health()`.

Example fake provider behaviors make tests simpler and eliminate the need for network deps in CI.

Link implementation note: add `tests/utils/fake_provider.py` in a follow-up PR implementing these modes.
