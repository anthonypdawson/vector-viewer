"""Factory and runtime instance wrapper for LLM providers."""

from __future__ import annotations

from typing import Optional

from vector_inspector.core.logging import log_error, log_info

from .base_provider import LLMProvider

# Provider type constants
AUTO = "auto"
FAKE = "fake"
LLAMA_CPP = "llama-cpp"
OLLAMA = "ollama"
OPENAI_COMPATIBLE = "openai-compatible"

PROVIDER_TYPES: tuple[str, ...] = (AUTO, FAKE, LLAMA_CPP, OLLAMA, OPENAI_COMPATIBLE)


class LLMProviderFactory:
    """Creates LLM provider instances based on a configured type or auto-detection.

    Auto-detection order (highest to lowest priority):
      1. User-configured provider (when not ``'auto'``).
      2. Ollama — probed at ``llm.ollama_url`` (default ``localhost:11434``).
      3. llama-cpp — in-process fallback (model must be present in cache).

    ``openai-compatible`` is never auto-detected; it must be set explicitly via
    ``llm.provider = 'openai-compatible'`` in settings or the
    ``VI_LLM_PROVIDER`` environment variable.

    When a provider is unavailable (``is_available() == False``) the factory
    still returns it; the runtime manager surfaces the unhealthy state via
    ``health()`` rather than silently falling back to another provider.
    """

    @classmethod
    def create_from_settings(cls, settings) -> Optional[LLMProvider]:
        """Create a provider from a ``SettingsService`` instance.

        Args:
            settings: ``SettingsService`` instance.

        Returns:
            An ``LLMProvider`` (may not yet be available — call
            ``is_available()`` to verify), or ``None`` if the requested type
            is completely unusable.
        """
        provider_type = settings.get("llm.provider", AUTO)
        if provider_type == FAKE:
            return cls._make_fake(settings)
        if provider_type == OLLAMA:
            return cls._make_ollama(settings)
        if provider_type == LLAMA_CPP:
            return cls._make_llama_cpp(settings)
        if provider_type == OPENAI_COMPATIBLE:
            return cls._make_openai_compatible(settings)
        if provider_type == AUTO:
            return cls._auto_detect(settings)
        log_error("Unknown LLM provider type '%s'; falling back to auto.", provider_type)
        return cls._auto_detect(settings)

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    @classmethod
    def _auto_detect(cls, settings) -> Optional[LLMProvider]:
        """Try Ollama first, then fall back to llama-cpp."""
        ollama = cls._make_ollama(settings)
        if ollama.is_available():
            log_info(
                "LLM auto-detect: Ollama available at %s (model: %s)",
                settings.get("llm.ollama_url", "http://localhost:11434"),
                settings.get("llm.ollama_model", "llama3.2"),
            )
            return ollama
        llama = cls._make_llama_cpp(settings)
        log_info(
            "LLM auto-detect: using llama-cpp (model available: %s)",
            llama.is_available(),
        )
        return llama

    # ------------------------------------------------------------------
    # Provider constructors
    # ------------------------------------------------------------------

    @classmethod
    def _make_fake(cls, settings) -> LLMProvider:
        """Return a FakeLLMProvider for tests and CI (VI_LLM_PROVIDER=fake)."""

        # The fake provider lives under tests/ to avoid shipping it with the
        # production package.  When running tests it will be importable.
        try:
            from tests.utils.fake_llm_provider import FakeLLMProvider
        except ImportError:
            # Fallback: look for it on sys.path (editable installs, tox, etc.)
            try:
                from fake_llm_provider import FakeLLMProvider  # type: ignore[no-redef]
            except ImportError as exc:
                raise ImportError(
                    "FakeLLMProvider not importable. Ensure tests/ is on sys.path when using VI_LLM_PROVIDER=fake."
                ) from exc
        return FakeLLMProvider(
            seed=int(settings.get("llm.fake_seed", 0) or 0),
            fragment_size=int(settings.get("llm.fake_fragment_size", 2) or 2),
            latency_ms=int(settings.get("llm.fake_latency_ms", 0) or 0),
            error_rate=float(settings.get("llm.fake_error_rate", 0.0) or 0.0),
            default_model=settings.get("llm.fake_default_model", "fake-model") or "fake-model",
        )

    @classmethod
    def _make_llama_cpp(cls, settings) -> LLMProvider:
        from .llama_cpp_provider import LlamaCppProvider

        return LlamaCppProvider(
            model_path=settings.get("llm.model_path") or None,
            context_length=int(settings.get("llm.context_length", 4096)),
            temperature=float(settings.get("llm.temperature", 0.1)),
        )

    @classmethod
    def _make_ollama(cls, settings) -> LLMProvider:
        from .ollama_provider import OllamaProvider

        return OllamaProvider(
            base_url=settings.get("llm.ollama_url", "http://localhost:11434"),
            model=settings.get("llm.ollama_model", "llama3.2"),
            context_length=int(settings.get("llm.context_length", 4096)),
            temperature=float(settings.get("llm.temperature", 0.1)),
        )

    @classmethod
    def _make_openai_compatible(cls, settings) -> LLMProvider:
        from .openai_compatible_provider import OpenAICompatibleProvider

        return OpenAICompatibleProvider(
            base_url=settings.get("llm.openai_url", ""),
            model=settings.get("llm.openai_model", ""),
            api_key=settings.get("llm.openai_api_key", ""),
            context_length=int(settings.get("llm.context_length", 4096)),
            temperature=float(settings.get("llm.temperature", 0.1)),
        )


class LLMProviderInstance:
    """Runtime wrapper that manages the currently active LLM provider.

    Call ``refresh()`` after the user changes LLM settings in the
    Settings dialog so the provider is re-created from updated values.
    All ``LLMProvider`` methods are forwarded to the active provider.

    .. note::
        Prefer ``LLMRuntimeManager`` (available via ``AppState.llm_provider``)
        for new code: it adds provider-selection precedence, env var support,
        health TTL caching, and request-id injection.  ``LLMProviderInstance``
        is retained as a lighter-weight alternative when those features are not
        needed.
    """

    def __init__(self, settings) -> None:
        self._settings = settings
        self._provider: Optional[LLMProvider] = None

    def _ensure(self) -> None:
        if self._provider is None:
            self._provider = LLMProviderFactory.create_from_settings(self._settings)

    def refresh(self) -> None:
        """Re-detect and rebuild the provider from current settings."""
        self._provider = None
        self._ensure()

    # ------------------------------------------------------------------
    # Forwarded LLMProvider interface
    # ------------------------------------------------------------------

    def generate(self, prompt: str, **opts) -> str:
        """Generate text from a plain-text prompt.

        The prompt is wrapped into a single user message and forwarded to
        ``generate_messages()``.  For multi-turn or system-prompt use cases
        call ``get_provider().generate_messages()`` directly.

        Args:
            prompt: Plain text prompt.
            **opts: Overrides forwarded to ``generate_messages()``
                    (e.g., ``temperature``, ``max_tokens``).
                    Pass ``model`` to override the active model name.
        """
        self._ensure()
        if self._provider is None:
            raise RuntimeError("No LLM provider is available.")
        messages = [{"role": "user", "content": prompt}]
        model = opts.pop("model", self._provider.get_model_name())
        result = self._provider.generate_messages(messages, model=model, stream=False, **opts)
        return result  # type: ignore[return-value]

    def is_available(self) -> bool:
        self._ensure()
        return self._provider is not None and self._provider.is_available()

    def get_model_name(self) -> str:
        self._ensure()
        return self._provider.get_model_name() if self._provider else "none"

    def get_provider_name(self) -> str:
        self._ensure()
        return self._provider.get_provider_name() if self._provider else "none"
