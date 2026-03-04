"""Type definitions for the LLM provider interface.

These dataclasses define the canonical shapes for capabilities, health results,
streaming events, and model metadata across all LLM providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CAPABILITIES_SCHEMA_VERSION = "1"
"""Bump this constant (and document in CHANGELOG.md) when adding required
fields to ProviderCapabilities. Consumers should reject capabilities objects
with an unknown schema_version rather than silently ignoring unknown fields."""


@dataclass
class RateLimit:
    """Rate-limiting constraints for a model."""

    requests_per_minute: int | None = None
    tokens_per_minute: int | None = None


@dataclass
class ModelMetadata:
    """Metadata about a model available through a provider."""

    model_name: str
    context_window: int
    cost_estimate_per_token: float | None = None  # USD per token when known
    rate_limit: RateLimit | None = None


@dataclass
class TokenizerInfo:
    """Minimal tokenizer adapter for token budgeting.

    Providers that expose a real tokenizer should subclass this and override
    ``count_tokens()``. The default implementation uses whitespace splitting as
    an approximation suitable for rough budgeting only.
    """

    encoding: str

    def count_tokens(self, texts: list[str]) -> int:
        """Approximate token count using whitespace splitting."""
        return sum(len(t.split()) for t in texts)


@dataclass
class ProviderCapabilities:
    """Versioned capabilities object returned by ``LLMProvider.get_capabilities()``.

    Set ``schema_version`` to ``CAPABILITIES_SCHEMA_VERSION``. Consumers should
    reject capabilities objects with an unknown ``schema_version`` rather than
    silently ignoring unrecognized fields.

    Fields:
        schema_version:      Set to CAPABILITIES_SCHEMA_VERSION.
        provider_name:       Provider id (e.g. ``"ollama"``, ``"llama-cpp"``).
        supports_streaming:  True if the provider supports streaming generation.
        supports_tools:      True if the provider supports tool invocation / JSON mode.
        concurrency:         ``"single-threaded"`` | ``"multi"`` | ``"process-isolated"``.
        max_context_tokens:  Maximum number of tokens in a single context window.
        roles_supported:     Message roles accepted, e.g. ``["system","user","assistant"]``.
        model_list:          Per-model metadata.
        tokenizer:           Optional tokenizer adapter.
    """

    schema_version: str
    provider_name: str
    supports_streaming: bool
    supports_tools: bool
    concurrency: str
    max_context_tokens: int
    roles_supported: list[str]
    model_list: list[ModelMetadata]
    tokenizer: TokenizerInfo | None = None


@dataclass
class HealthResult:
    """Return value of ``LLMProvider.get_health()``.

    Fields:
        ok:               True if the provider is reachable and at least one model
                          is available.
        provider:         Provider id (e.g. ``"ollama"``).
        models:           Available model names; may be empty when unhealthy.
        version:          Provider or API version string if available; else None.
        last_checked:     ISO-8601 timestamp of the last health probe.
        retryable:        True if the failure is likely transient (e.g. network
                          timeout); False for hard errors (missing deps, bad creds).
        remediation_hint: Human-readable fix suggestion; non-null only when
                          ``ok == False``. Format:
                          ``"<action>: <command> (see <docs link>)"``
                          Max 200 characters. No stack traces or internal paths.
    """

    ok: bool
    provider: str
    models: list[str]
    version: str | None
    last_checked: str  # ISO-8601
    retryable: bool
    remediation_hint: str | None


@dataclass
class StreamEvent:
    """A single event in a streaming LLM response.

    Fields:
        type:    ``"delta"`` | ``"done"`` | ``"error"``
        content: Text fragment for delta events; empty string for done/error.
        meta:    Must include ``request_id`` (injected by the runtime manager)
                 and ``index`` (0-based, strictly monotonically increasing within
                 one streaming response). On ``"done"`` events, meta includes
                 ``finish_reason``. On ``"error"`` events, meta includes
                 ``error_message``.
    """

    type: str
    content: str
    meta: dict[str, Any] = field(default_factory=dict)
