"""Fake LLM provider for unit tests, integration tests, and CI.

Implements the full LLMProvider interface with deterministic, configurable
behavior so it can be used without any external network or heavy binary.

Select via environment variable for full end-to-end testing:
    export VI_LLM_PROVIDER=fake

Modes:
    echo         — (default) concatenate message contents and return as response.
    streaming    — yield delta fragments per fragment_size / latency_ms config.
    error_inject — fail reproducibly based on error_rate or explicit triggers.

Config options:
    seed          int    Deterministic seed. When set, request_ids are
                         ``f"r-{seed}-{n}"`` (0-based). Without seed: ``f"r-{n}"``.
    fragment_size int    Characters per delta fragment (streaming mode).
    latency_ms    int    Per-fragment delay in ms (0 for fast tests).
    error_rate    float  Probability [0.0-1.0] to inject transient errors.
    default_model str    Reported model name from list_models().
    mode          str    "echo" | "streaming" | "error_inject"
    supports_tools bool  Set True to enable tool-testing mode.

See docs/upcoming/llm_providers/fake_provider.md for the full specification.
"""

from __future__ import annotations

import datetime
import random
import time
from collections.abc import Generator
from typing import Any

from vector_inspector.core.llm_providers.base_provider import LLMProvider
from vector_inspector.core.llm_providers.errors import ProviderError
from vector_inspector.core.llm_providers.types import (
    CAPABILITIES_SCHEMA_VERSION,
    HealthResult,
    ModelMetadata,
    ProviderCapabilities,
    StreamEvent,
)

_MODE_ECHO = "echo"
_MODE_STREAMING = "streaming"
_MODE_ERROR_INJECT = "error_inject"


class FakeLLMProvider(LLMProvider):
    """In-process fake LLM provider for tests and CI.

    All outputs are deterministic when ``seed`` is set.  Use the ``mode``
    parameter to select echo, streaming, or error-injection behavior.
    """

    def __init__(
        self,
        seed: int = 0,
        fragment_size: int = 2,
        latency_ms: int = 0,
        error_rate: float = 0.0,
        default_model: str = "fake-model",
        mode: str = _MODE_ECHO,
        supports_tools: bool = False,
    ) -> None:
        self._seed = seed
        self._fragment_size = max(1, fragment_size)
        self._latency_ms = latency_ms
        self._error_rate = error_rate
        self._default_model = default_model
        self._mode = mode
        self._supports_tools = supports_tools
        self._request_count = 0
        self._rng = random.Random(seed) if seed else random.Random()

    # ------------------------------------------------------------------
    # request_id generation (deterministic with seed, sequential without)
    # ------------------------------------------------------------------

    def _next_request_id(self) -> str:
        n = self._request_count
        self._request_count += 1
        if self._seed:
            return f"r-{self._seed}-{n}"
        return f"r-{n}"

    # ------------------------------------------------------------------
    # Error injection helper
    # ------------------------------------------------------------------

    def _maybe_inject_error(self, model: str, request_id: str) -> None:
        """Raise ProviderError at the configured error_rate probability."""
        if self._error_rate > 0 and self._rng.random() < self._error_rate:
            raise ProviderError(
                "Injected error from FakeLLMProvider",
                provider_name="fake",
                model_name=model,
                retryable=True,
                code="FAKE_ERROR",
            )

    # ------------------------------------------------------------------
    # Response generation
    # ------------------------------------------------------------------

    def _build_response(self, messages: list[dict[str, str]]) -> str:
        """Build the fake echo response from messages."""
        if self._mode == _MODE_ECHO:
            return "".join(msg.get("content", "") for msg in messages)
        # fallback for other modes
        return "".join(msg.get("content", "") for msg in messages)

    def is_available(self) -> bool:
        return True

    def get_model_name(self) -> str:
        return self._default_model

    def get_provider_name(self) -> str:
        return "fake"

    def generate_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | Generator[StreamEvent, None, None]:
        request_id = kwargs.get("request_id", self._next_request_id())
        self._maybe_inject_error(model, request_id)
        if stream or self._mode == _MODE_STREAMING:
            return self.stream_messages(messages, model, **{**kwargs, "request_id": request_id})
        response = self._build_response(messages)
        return response

    def stream_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        **kwargs: Any,
    ) -> Generator[StreamEvent, None, None]:
        """Yield StreamEvents, fragmenting the response per fragment_size."""
        request_id = kwargs.get("request_id", self._next_request_id())
        self._maybe_inject_error(model, request_id)
        response = self._build_response(messages)
        index = 0
        for i in range(0, len(response), self._fragment_size):
            fragment = response[i : i + self._fragment_size]
            if self._latency_ms > 0:
                time.sleep(self._latency_ms / 1000.0)
            yield StreamEvent(
                type="delta",
                content=fragment,
                meta={"request_id": request_id, "index": index},
            )
            index += 1
        yield StreamEvent(
            type="done",
            content="",
            meta={"request_id": request_id, "finish_reason": "stop"},
        )

    def list_models(self) -> list[ModelMetadata]:
        return [ModelMetadata(model_name=self._default_model, context_window=4096)]

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            schema_version=CAPABILITIES_SCHEMA_VERSION,
            provider_name="fake",
            supports_streaming=True,
            supports_tools=self._supports_tools,
            concurrency="multi",
            max_context_tokens=4096,
            roles_supported=["system", "user", "assistant"],
            model_list=self.list_models(),
        )

    def get_health(self) -> HealthResult:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        if self._mode == _MODE_ERROR_INJECT and self._error_rate >= 1.0:
            return HealthResult(
                ok=False,
                provider="fake",
                models=[],
                version="fake-1.0",
                last_checked=now,
                retryable=True,
                remediation_hint="FakeLLMProvider configured with error_rate=1.0",
            )
        return HealthResult(
            ok=True,
            provider="fake",
            models=[self._default_model],
            version="fake-1.0",
            last_checked=now,
            retryable=False,
            remediation_hint=None,
        )
