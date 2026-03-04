---
title: LLM Providers — Consolidated Design
---

# LLM Providers — Consolidated Design

This document captures the recommendations for the `llm-providers` branch: a minimal, consistent provider interface, a model manager separation, normalized errors and capabilities, and a deterministic, debuggable runtime.

Purpose: provide a single, well-documented provider layer for Vector Inspector / Vector Studio that is pluggable, testable, and consistent across local (llama-cpp), self-hosted (Ollama), and cloud (OpenAI-compatible) providers.

Audience: maintainers of `src/**` provider code, Vector Studio integration engineers, and UI authors.

---

## Quickstart (short)

See `docs/llm_providers/quickstart.md` for full examples. Example selection environment variables:

- `VI_LLM_PROVIDER` — preferred provider id (`llama-cpp`, `ollama`, `openai`).
- `VI_LLM_MODEL` — default model name.
- `VI_OLLAMA_URL` — Ollama endpoint (e.g., `http://localhost:11434`).

Enable debug selection with `VI_LLM_DEBUG=1`.

---

## Design Principles

- Keep the provider layer narrowly scoped to text generation and model metadata.
- Separate provider lifecycle and selection from model file management and caching.
- Normalize surface area: capabilities, health checks, a unified `generate()` signature, and a streaming contract.
- Treat optional deps (e.g., `llama-cpp`) as feature flags with runtime checks and clear warnings.

---

## Responsibility Matrix

Who owns what (high-level):

- Runtime Manager: provider selection, `selection_debug`, global retries and circuit-breaking orchestration, traffic shaping/rate-limiting orchestration, provider instance lifecycle.
- Provider: transport-level retries, error normalization, per-request timeouts, connection/session management.
- Model Manager: model artifact lifecycle (download, verify, eviction), per-model locks, capacity-aware loading.
- Pipeline / UI: high-level retry policies, user-facing fallbacks, budget/cost decisions.

This table is authoritative: implement behavior in code and update docs when changing responsibilities.

---

## Provider Interface (canonical)

Provide a minimal provider API surface so upper layers do not need provider-specific logic.

- `generate(messages, model, stream=False, **kwargs)` — single canonical call for completions/chat.
- `stream(messages, model, **kwargs)` — returns an async iterator or sync generator per runtime.
- `models()` — list available models + metadata.
- `capabilities()` — `ProviderCapabilities` object describing streaming, max context, tokenizer info, roles, concurrency.
- `health()` — lightweight probe of connectivity and model availability.

Keep the interface small so consumers only rely on stable, well-tested primitives.

### Contract Clarifications

- **System messages**: providers MUST pass system messages through to the underlying model when supported. When a provider does not support `"role": "system"` (e.g., older endpoints), it should merge system messages into the first user message or raise a `ProviderCapabilityError`, and document its behavior in `roles_supported`.
- **Invalid model names**: when the caller specifies a model name not returned by `models()`, the provider MUST raise `ProviderError` with a clear message. Providers must not silently fall back to a different model; call sites must handle `ProviderError` and decide the fallback strategy.
- **`request_id` ownership**: the runtime manager generates a globally unique `request_id` (UUID4) before calling the provider and injects it into the call context. The provider echoes this `request_id` in all streaming `meta` objects and in top-level `ProviderError`. Providers MUST NOT generate their own `request_id`s unless operating without a runtime manager. `request_id` is not deterministic and is not seed-based.

### Concrete `generate()` example

```python
resp = provider.generate(
    messages=[{"role": "user", "content": "Explain vector search"}],
    model="llama-3.1",
    stream=False,
    temperature=0.2,
)
```

If `stream=True`, the caller receives an iterator (sync or async depending on runtime) that yields normalized streaming events.

---

## Provider vs Model

- Provider identity: the runtime integration (llama-cpp process, Ollama HTTP endpoint, OpenAI-compatible HTTP).
- Model identity: a model artifact available through a provider (e.g., `ggml-vicuna-13b-q4_0`).

Providers should expose available models via `models()` and include per-model metadata such as `context_window`, tokenizer hints, optional `rate_limit` and `cost_estimate_per_token`. Keep provider logic focused on runtime behavior and model metadata, and move artifact lifecycle (download, cache, verify) to the model manager.

Do not conflate provider selection with model artifact management; this separation keeps providers lightweight and easier to test.


## Capabilities Schema

Include a small, versioned capabilities object so the UI/runtime can adapt safely when schema evolves.

Suggested `ProviderCapabilities` fields:
- `schema_version: str`
- `provider_name: str`
- `supports_streaming: bool`
- `supports_tools: bool` — supports tool invocation / JSON mode
- `concurrency: str` — `"single-threaded" | "multi" | "process-isolated"`
- `max_context_tokens: int`
- `roles_supported: list[str]` (e.g. `["system","user","assistant"]`)
- `model_list: list[ModelMetadata]`
- `tokenizer: TokenizerInfo | None`

`ModelMetadata` should include `model_name`, `context_window`, optional `rate_limit`, and `cost_estimate_per_token` when available.

### TokenizerInfo

Provide a small tokenizer adapter returning:
- encoding name
- a `count_tokens(messages)` helper
- encode/decode hooks (optional)

This lets RAG and UI reliably budget token usage across providers.

---

## Streaming & Error Model

Standardize streaming event shape and error normalization so consumers can be provider-agnostic.

Canonical event shape (recommended):

```json
{ "type": "delta" | "done" | "error", "content": "...", "meta": { ... } }
```

- Make `delta` the canonical stream type for incremental text fragments; `token` is optional for providers emitting discrete tokens.
- `meta` MUST include `request_id` (injected by the runtime manager before the call) for log correlation, and MUST include `index` (0-based, monotonically increasing) for ordering. Additional optional fields: `timestamp` (ISO-8601), `finish_reason` (on `done` events).
- `index` values MUST be strictly monotonically increasing within a single streaming response. Consumers may assert on `index` order to detect dropped events or provider bugs.

Example event sequence:

```json
{ "type": "delta", "content": "vec", "meta": {"request_id": "r-123", "index": 0} }
{ "type": "delta", "content": "tor", "meta": {"request_id": "r-123", "index": 1} }
{ "type": "done",  "content": "",    "meta": {"request_id": "r-123", "finish_reason": "stop"} }
```

Error normalization:
- All provider exceptions must be normalized to a `ProviderError` hierarchy with fields: `provider_name`, `model_name`, `underlying_error`, `retryable: bool`, `code`/`http_status`, and `remediation_hint`.

Include short `remediation_hint` strings and `retryable` booleans to help runtime manager and UI make consistent decisions.

---

## Lifecycle & Concurrency

Clarify provider lifetime and state expectations to avoid ambiguity:

- Long‑lived singletons: providers are expected to be long‑lived instances managed by the runtime manager in most cases. This allows providers to maintain internal state such as HTTP sessions, cached auth tokens, and connection pools.
- Recreated per request: only allowed for lightweight providers where construction is cheap; avoid per-request recreation for providers that manage native resources.
- Internal state: providers MAY maintain internal state but MUST document thread-safety guarantees and expose a `close()`/`shutdown()` method when applicable.

Runtime manager behavior: the runtime manager decides whether to reuse or recreate providers; implementations should assume providers are reusable unless explicitly documented otherwise. Surface `concurrency` in `capabilities()` so the runtime knows whether to serialize requests or allow concurrent calls.

Model manager locking: provide per-model locks to ensure only one load/eviction operation occurs concurrently for a model.

Provider-specific concurrency notes (example):
- `llama-cpp` may be single-threaded or process-isolated depending on build — document this in the provider implementation and capabilities.

---

## Runtime Manager: Selection & Health

Discovery precedence (deterministic):
1. Explicit application config (highest precedence)
2. Environment variables (`VI_LLM_PROVIDER`, `VI_LLM_MODEL`, `VI_OLLAMA_URL`)
3. Auto-detection (reachable endpoints, local runtime availability)
4. Fallback default (e.g., `openai` when API key present)

### `selection_debug` — Multi-Reason Example

`selection_debug` MUST be a structured object with `selected_provider`, `selected_model`, and a `reasons` array showing the full precedence path. Secrets MUST be redacted; use boolean flags (e.g., `api_key_present`) to indicate presence without exposing values. `selection_debug` output MUST be deterministic for identical configuration inputs (same reasons, same order), enabling stable test assertions.

```json
{
  "selected_provider": "ollama",
  "selected_model": "vicuna-13b",
  "reasons": [
    {
      "source": "app_config",
      "key": "VI_LLM_PROVIDER",
      "value": null,
      "timestamp": "2026-03-04T10:00:00Z",
      "precedence_rank": 1,
      "outcome": "skipped_not_set"
    },
    {
      "source": "env",
      "key": "VI_LLM_PROVIDER",
      "value": "ollama",
      "timestamp": "2026-03-04T10:00:00Z",
      "precedence_rank": 2,
      "outcome": "selected"
    },
    {
      "source": "env",
      "key": "VI_LLM_MODEL",
      "value": "vicuna-13b",
      "timestamp": "2026-03-04T10:00:00Z",
      "precedence_rank": 2,
      "outcome": "selected"
    },
    {
      "source": "autodetect",
      "key": "ollama_reachable",
      "value": true,
      "timestamp": "2026-03-04T10:00:00Z",
      "precedence_rank": 3,
      "outcome": "confirmed"
    }
  ],
  "fallbacks_considered": [],
  "api_key_present": false,
  "api_key_value": "[REDACTED]"
}
```

`outcome` values: `"selected"` (drove the choice), `"confirmed"` (consistent with selection), `"skipped_not_set"` (key not configured), `"skipped_unhealthy"` (candidate rejected due to unhealthy status).

### Full Selection Path Example

```
config    → (not set)
env       → VI_LLM_PROVIDER=ollama   ← selected at rank 2
env       → VI_LLM_MODEL=vicuna-13b  ← selected at rank 2
autodetect → ollama reachable: true  ← confirmed
fallback  → (not reached)
Result: provider=ollama, model=vicuna-13b
```

Auto-detection results MUST NOT override an explicitly configured provider (ranks 1–2), even if that provider is currently unhealthy.

### Health Checks

- `health()` should be fast and predictable. The runtime manager caches health results with a configurable TTL (default: 30 seconds). Call `probe()` to bypass the cache for on-demand checks.
- TTL cache bypass rules: (1) explicit `probe()` call, (2) provider transitions from healthy to unhealthy, (3) runtime manager restart.
- Active probing: the runtime manager probes on startup, then on a background schedule (default every 60 seconds). Probe frequency is reduced for consistently healthy providers.

**Exact `health()` return shape:**

```json
{
  "ok": true,
  "provider": "ollama",
  "models": ["vicuna-13b", "mistral-7b"],
  "version": "0.1.27",
  "last_checked": "2026-03-04T10:00:00Z",
  "retryable": false,
  "remediation_hint": null
}
```

Fields:
- `ok: bool` — true if the provider is reachable and at least one model is available.
- `provider: str` — provider id (e.g., `"ollama"`, `"openai"`, `"llama-cpp"`).
- `models: list[str]` — available model names; may be empty when unhealthy.
- `version: str | None` — provider or API version string if available.
- `last_checked: str` — ISO-8601 timestamp of the last health probe.
- `retryable: bool` — true if the failure is likely transient (e.g., network timeout); false for hard errors (missing deps, invalid credentials).
- `remediation_hint: str | None` — human-readable fix suggestion; non-null only when `ok == false`.

**Explicit but unhealthy provider:**
- If an explicitly configured provider returns `ok == false`, the runtime manager MUST NOT silently fall back to another provider. It surfaces the error via `health()` and `selection_debug` and lets the caller or UI decide whether to fall back.
- If `retryable == true`, the runtime manager may retry after the configured delay before declaring failure.

---

## Provider Factory vs Runtime Manager

- Factory: the provider factory is pure and side-effect-free. It returns a **constructor callable** (a class or factory function) that the runtime manager calls to create provider instances. The factory MUST NOT perform any I/O — no network calls, no file reads, no subprocess spawning, no lazy imports of optional packages. Validation of configuration shape (checking required keys, type assertions) is allowed; validation that requires I/O is not.
- Runtime Manager: owns stateful concerns — creating, caching, and tearing down provider instances, performing health polling, credential refresh, and selection debugging. It should also own deterministic provider selection and record a structured `selection_debug` explaining why a provider and model were chosen (env, config, autodetect, fallback).
- Provider instance mutation: the runtime manager MAY inject shared resources (e.g., a shared `httpx.Client` or connection pool) into a provider instance via explicit setter methods or constructor parameters. Providers MUST document which shared resources they accept. The runtime manager MUST NOT access private attributes of provider instances.

Include a machine-parseable `selection_debug` entry that records the exact decision path (which env var or config key, auto-detect result, fallback), the timestamp, and the precedence rank. Redact secrets but keep non-sensitive values.


## Model Manager (responsibilities)

- Download and verify model artifacts
- Maintain filesystem layout and consistent paths
- LRU eviction / disk-space policy
- Per-model locks for concurrent load/preload
- Provide preloaded model handles to in-process providers (llama-cpp)
- Expose metrics (load time, size, last_used)

Model manager responsibilities are intentionally separate from providers to avoid mixing artifact lifecycle with runtime integration.

### Filesystem Layout

```
~/.vector-inspector/models/
  <provider>/
    <model_name>/
      model.<ext>        # primary artifact (e.g., .gguf, .bin)
      metadata.json      # per-model metadata (see below)
      sha256.txt         # expected checksum for integrity verification
```

Example `metadata.json`:

```json
{
  "model_name": "ggml-vicuna-13b-q4_0",
  "provider": "llama-cpp",
  "context_window": 4096,
  "size_bytes": 7375182848,
  "last_used": "2026-03-04T09:30:00Z",
  "load_time_ms": 4200,
  "schema_version": "1"
}
```

### Load / Evict: Sync vs Async

- Load and eviction operations are **synchronous** by default. Callers that need non-blocking behavior must schedule them in a background thread or executor.
- Per-model locks prevent concurrent load + evict races. The manager exposes `is_loaded(model_name)` (non-blocking), `load(model_name)` (blocking, lock-guarded), and `evict(model_name)` (blocking, lock-guarded).

### Metadata Caching and Invalidation

- Model metadata is read from `metadata.json` on first access and cached in memory.
- Cache is invalidated when: (1) a model artifact is downloaded or updated, (2) `evict()` is called, or (3) `metadata.json` is modified externally (detected via mtime check on next access).
- The model manager does NOT watch the filesystem continuously; staleness is detected lazily on next read.

---

## Optional Dependencies & Runtime Checks

- Keep heavy LLM runtime dependencies optional and grouped under an `llm` extras group in packaging.
- Runtime manager must perform runtime checks: if a provider is selected but required optional dependencies are missing (for example selecting `llama-cpp` without the native bindings installed), do not crash the process. Instead:
    - mark the provider `health().ok == false`
    - include a `remediation_hint` in the health output
    - record the issue in `selection_debug` so the user can see why selection failed and what remediation is suggested
- Missing optional dependencies do **not** prevent provider selection; the provider is selected and registered but immediately reports `ok == false`. The runtime manager surfaces this at startup and via `health()` rather than blocking provider selection.

### `remediation_hint` Shape

`remediation_hint` MUST be a plain string (not a dict or object) when present. Format:

```
"<action>: <install command or config example> (see <docs link>)"
```

Example: `"Install llama-cpp-python: pip install 'vector-inspector[llm]' (see docs/llm_providers/quickstart.md)"`

Rules:
- Start with the action (what to install or configure).
- Include the install command or config example.
- Include a docs link when relevant.
- Do not include stack traces or internal module paths.
- Keep under 200 characters.

### Example `health()` Response for Missing Optional Deps

```json
{
  "ok": false,
  "provider": "llama-cpp",
  "models": [],
  "version": null,
  "last_checked": "2026-03-04T10:00:00Z",
  "retryable": false,
  "remediation_hint": "Install llama-cpp-python: pip install 'vector-inspector[llm]' (see docs/llm_providers/quickstart.md)"
}
```


## Fake Provider (tests & demos)

See `docs/llm_providers/fake_provider.md` for full spec. Summary:
- Modes: `echo`, `streaming`, `error_inject`
- Config: `seed`, `fragment_size`, `latency_ms`, `error_rate`, `default_model`
- Implements `generate()`, `stream()`, `models()`, `capabilities()`, `health()` so CI can run without external deps.
- Select via `VI_LLM_PROVIDER=fake` for full end-to-end testing without a real provider. The fake provider must be registered in the provider factory like any other provider.
- **`request_id` in fake provider**: when `seed` is set, the fake provider generates deterministic `request_id` values (`f"r-{seed}-{n}"` where `n` is the 0-based request count). Without a seed, IDs are sequential (`f"r-{n}"`). Tests using a fixed seed can assert on exact `request_id` values.

Use the fake provider to validate runtime manager selection, retry behavior, and streaming conformance in CI.

---

## Migration & Testing

Migration shim (recommended while rolling out):

```python
def legacy_generate(provider, prompt: str, **kwargs):
    messages = [{"role": "user", "content": prompt}]
    model = kwargs.pop("model", None) or provider.default_model()
    return provider.generate(messages=messages, model=model, **kwargs)
```

Tests to add:
- capabilities schema conformance
- streaming iterator conformance across providers (mocked)
- streaming `index` monotonicity: assert `index` values are strictly increasing per response
- model manager locking / eviction tests
- provider factory deterministic selection tests
- provider factory I/O prohibition: assert that calling the factory triggers no network or file I/O
- `selection_debug` stability: assert that identical configuration inputs produce identical `selection_debug` output across multiple runs
- fallback behavior when multiple providers are unhealthy: assert runtime manager surfaces all failures with structured `health()` responses; assert no silent success
- invalid model name: assert `generate()` and `stream()` raise `ProviderError` when the model is not in `models()`; assert no silent fallback
- missing optional deps: assert `health().ok == false` and `remediation_hint` is non-null when provider deps are absent; assert process does not crash
- shim mapping tests and backward-compat smoke tests

---

## Quick Example (python dataclasses)

`CAPABILITIES_SCHEMA_VERSION = "1"` — bump this constant (and document the change in `CHANGELOG.md`) when adding required fields to `ProviderCapabilities`. Consumers should reject capabilities objects with an unknown `schema_version` rather than silently ignoring unrecognized fields.

```python
from dataclasses import dataclass, field

@dataclass
class TokenizerInfo:
    encoding: str
    def count_tokens(self, texts: list[str]) -> int: ...

@dataclass
class RateLimit:
    requests_per_minute: int | None = None
    tokens_per_minute: int | None = None

@dataclass
class ModelMetadata:
    model_name: str
    context_window: int
    cost_estimate_per_token: float | None = None  # USD cost per token, if known
    rate_limit: RateLimit | None = None

@dataclass
class ProviderCapabilities:
    schema_version: str  # set to CAPABILITIES_SCHEMA_VERSION
    provider_name: str
    supports_streaming: bool
    supports_tools: bool
    concurrency: str  # "single-threaded" | "multi" | "process-isolated"
    max_context_tokens: int
    roles_supported: list[str]
    model_list: list[ModelMetadata]
    tokenizer: TokenizerInfo | None = None
```

---

## Next Steps / Checklist

1. Implement `ProviderCapabilities` dataclass and tests.
2. Add model manager module and simple LRU eviction implementation.
3. Implement streaming event type and cross-provider conformance tests.
4. Add runtime manager selection debug logging and `--llm-dry-run` CLI.
5. Implement `tests/utils/fake_provider.py` and CI tests using it.

---

Links:
- Quickstart: `docs/llm_providers/quickstart.md`
- Fake provider spec: `docs/llm_providers/fake_provider.md`
