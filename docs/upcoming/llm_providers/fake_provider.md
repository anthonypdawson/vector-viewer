---
title: Fake Provider — Spec
---

# Fake Provider Specification

This file describes a minimal fake provider implementation intended for tests, CI, and local demos. The fake provider implements the full provider interface but has deterministic, configurable behavior so it can be used in unit and integration tests.

## Goals

- No external network or heavy binary dependencies.
- Deterministic outputs given the same seed and inputs.
- Configurable latency and streaming fragmentation.
- Support error injection for retry/fallback tests.

## Modes

- `echo`: respond by concatenating user messages.
- `streaming`: yield `delta` fragments according to `fragment_size` and `latency_ms`.
- `error_inject`: fail reproducibly based on `error_rate` or explicit triggers.

## Config options

- `seed: int` — deterministic seed for pseudo-random behaviors.
- `fragment_size: int` — number of characters per `delta` fragment.
- `latency_ms: int` — per-fragment delay when streaming (can be zero for fast tests).
- `error_rate: float` — probability [0.0-1.0] to inject transient errors.
- `default_model: str` — reported model name from `models()`.

## Selection via environment variable

The fake provider can be selected like any real provider:

```bash
export VI_LLM_PROVIDER=fake
```

This registers the fake provider through the standard provider factory so the full runtime manager selection path is exercised in tests, including `selection_debug` output and `health()` probing.

## API surface

Implement the same interface as real providers:

- `generate(messages, model, stream=False, **kwargs)` — returns a string or a generator/iterator when `stream=True`.
- `stream(messages, model, **kwargs)` — returns async iterator (or sync generator) of events with canonical shape: `{type: 'delta'|'done'|'error', content: str, meta: {...}}`.
- `models()` — returns a list with `default_model` and metadata.
- `capabilities()` — reports `supports_streaming=True`, `concurrency='multi'`, and `supports_tools=False`.
- `health()` — returns healthy status unless `error_inject` forces unhealthy responses.

Note: the fake provider exposes `supports_tools: False` by default. To enable tool-testing mode, set the fake provider config option `supports_tools: True` (or `tool_mode: true`) and the fake provider will accept simple deterministic tool invocation patterns and return deterministic tool outputs for testing.

## Example behavior

Given `messages=[{"role":"user","content":"Hello"}]`, `fragment_size=2`:

Streaming events:

```
{type: 'delta', content: 'He', meta: {'request_id':'r-1', 'index':0}}
{type: 'delta', content: 'll', meta: {'request_id':'r-1', 'index':1}}
{type: 'delta', content: 'o',  meta: {'request_id':'r-1', 'index':2}}
{type: 'done',  content: '',  meta: {'request_id':'r-1', 'finish_reason':'stop'}}
```

## `request_id` behavior

- **With `seed` set**: `request_id` values are deterministic, formatted as `f"r-{seed}-{n}"` where `n` is the 0-based request count for this provider instance. Tests using a fixed seed can assert on exact `request_id` values.
- **Without `seed`**: `request_id` values are sequential (`f"r-{n}"`), incrementing per request. Not deterministic across provider instances.
- The fake provider echoes the `request_id` in all streaming `meta` objects and in any emitted `ProviderError`, matching the contract for real providers.

## Use in tests

- Unit tests should instantiate the fake provider with `seed` and assert deterministic outputs.
- Integration tests can use `error_inject` to validate retry and fallback behaviors in the runtime manager.
- Use `VI_LLM_PROVIDER=fake` in CI environment variables to exercise the full selection path without any real provider.

Implementation note: this spec is implemented by `tests/utils/fake_llm_provider.py`.
