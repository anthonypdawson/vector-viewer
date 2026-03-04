"""Base interface for LLM providers."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import HealthResult, ModelMetadata, ProviderCapabilities, StreamEvent


@dataclass
class LLMModelInfo:
    """Metadata about an active LLM model."""

    name: str
    provider: str
    context_length: int = 4096
    description: str = ""


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Concrete providers must be safe to construct even when their backend is not
    installed or running — availability is tested via ``is_available()``.
    Heavy dependencies must be lazy-loaded inside methods so that importing
    this module does not affect startup time.

    Required abstract methods:
        ``generate_messages()``, ``is_available()``,
        ``get_model_name()``, ``get_provider_name()``

    Optional (override for richer behaviour; defaults are provided):
        ``stream_messages()``, ``list_models()``,
        ``get_capabilities()``, ``get_health()``
    """

    @abstractmethod
    def generate_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | Generator[StreamEvent, None, None]:
        """Generate a completion from a list of chat messages.

        Providers MUST raise ``ProviderError`` when ``model`` is not returned by
        ``list_models()``.  Providers MUST pass system messages through to the
        underlying model, or raise ``ProviderCapabilityError`` if not supported.

        Args:
            messages: List of ``{"role": ..., "content": ...}`` dicts.
            model:    Model identifier.
            stream:   If True, returns a generator of ``StreamEvent`` objects.
            **kwargs: Optional overrides forwarded to the provider.
                      ``request_id`` (str) is injected by the runtime manager.

        Returns:
            Full response string when ``stream=False``, or a
            ``Generator[StreamEvent]`` when ``stream=True``.

        Raises:
            ProviderError: If the provider is unavailable or the request fails.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is operational right now.

        Must complete quickly (< 3 s) — called during auto-detection.
        """

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the active model identifier string."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return the provider type identifier, e.g. ``'llama-cpp'``, ``'ollama'``."""

    def get_info(self) -> LLMModelInfo:
        """Return structured metadata about the active model."""
        return LLMModelInfo(
            name=self.get_model_name(),
            provider=self.get_provider_name(),
        )

    # ------------------------------------------------------------------
    # Default implementations (override for richer behaviour)
    # ------------------------------------------------------------------

    def stream_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        **kwargs: Any,
    ) -> Generator[StreamEvent, None, None]:
        """Stream a response as ``StreamEvent`` objects.

        ``index`` values MUST be strictly monotonically increasing within a
        single streaming response.  ``meta`` MUST include ``request_id``
        (injected by the runtime manager before the call) and ``index``.

        The default implementation performs a non-streaming ``generate()`` and
        wraps the result in a minimal event sequence.
        """
        from .types import StreamEvent

        content = self.generate_messages(messages, model, stream=False, **kwargs)  # type: ignore[assignment]
        request_id = kwargs.get("request_id", "r-0")
        yield StreamEvent(type="delta", content=content, meta={"request_id": request_id, "index": 0})
        yield StreamEvent(type="done", content="", meta={"request_id": request_id, "finish_reason": "stop"})

    def list_models(self) -> list[ModelMetadata]:
        """Return available models with per-model metadata."""
        from .types import ModelMetadata

        return [ModelMetadata(model_name=self.get_model_name(), context_window=4096)]

    def get_capabilities(self) -> ProviderCapabilities:
        """Return a ``ProviderCapabilities`` object describing this provider."""
        from .types import CAPABILITIES_SCHEMA_VERSION, ProviderCapabilities

        return ProviderCapabilities(
            schema_version=CAPABILITIES_SCHEMA_VERSION,
            provider_name=self.get_provider_name(),
            supports_streaming=False,
            supports_tools=False,
            concurrency="single-threaded",
            max_context_tokens=4096,
            roles_supported=["user", "assistant"],
            model_list=self.list_models(),
        )

    def get_health(self) -> HealthResult:
        """Return the health status of this provider.

        The default implementation calls ``is_available()`` and wraps the
        result in a ``HealthResult``.  Override for richer version/model info.
        """
        from .types import HealthResult

        now = datetime.datetime.now(datetime.UTC).isoformat()
        available = self.is_available()
        models = [m.model_name for m in self.list_models()] if available else []
        return HealthResult(
            ok=available,
            provider=self.get_provider_name(),
            models=models,
            version=None,
            last_checked=now,
            retryable=not available,
            remediation_hint=None if available else f"Provider {self.get_provider_name()!r} is not reachable.",
        )
