"""LLM Runtime Manager — provider selection, health caching, and selection debug.

The runtime manager is the single stateful owner of LLM provider lifecycle.
It handles:
- Deterministic provider selection with structured selection_debug output
- Health result caching (TTL-based) and on-demand probe()
- request_id generation (UUID4) injected into each call
- Environment variable discovery (VI_LLM_PROVIDER, VI_LLM_MODEL, VI_OLLAMA_URL)

Selection precedence (highest to lowest):
1. Explicit app config (settings object)
2. Environment variables
3. Auto-detection (reachable Ollama endpoint)
4. Fallback default (openai when API key present, otherwise ollama)
"""

from __future__ import annotations

import datetime
import os
import time
import uuid
from typing import Any

from vector_inspector.core.logging import log_error, log_info

from .base_provider import LLMProvider
from .types import HealthResult


class LLMRuntimeManager:
    """Stateful manager for LLM provider lifecycle, selection, and health caching.

    Selection precedence (deterministic):
    1. Explicit app config (passed as ``settings`` constructor argument)
    2. Environment variables (``VI_LLM_PROVIDER``, ``VI_LLM_MODEL``,
       ``VI_OLLAMA_URL``)
    3. Auto-detection (reachable Ollama endpoint)
    4. Fallback default

    Health results are cached for ``health_ttl`` seconds (default 30).
    Call ``probe()`` to bypass the cache.

    Auto-detection MUST NOT override an explicitly configured provider
    (precedence ranks 1-2), even if that provider is currently unhealthy.
    When an explicitly configured provider is unhealthy the manager surfaces
    the error via ``health()`` and ``get_selection_debug()`` rather than
    silently falling back.
    """

    HEALTH_TTL_SECONDS: int = 30

    def __init__(self, settings: Any = None, health_ttl: int = HEALTH_TTL_SECONDS) -> None:
        self._settings = settings
        self._health_ttl = health_ttl
        self._provider: LLMProvider | None = None
        self._health_cache: HealthResult | None = None
        self._health_cache_ts: float | None = None
        self._selection_debug: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Provider access
    # ------------------------------------------------------------------

    def get_provider(self) -> LLMProvider:
        """Return the active provider, selecting it on first call."""
        if self._provider is None:
            self._provider = self._select_provider_safe()
        return self._provider

    def _will_autodetect(self) -> bool:
        """Return True if provider selection will trigger a blocking network probe.

        Auto-detection only probes when no explicit provider has been configured
        via app settings or the ``VI_LLM_PROVIDER`` environment variable.
        """
        from .provider_factory import AUTO

        cfg_provider = self._settings.get("llm.provider", None) if self._settings else None
        env_provider = os.environ.get("VI_LLM_PROVIDER")
        return not (cfg_provider and cfg_provider != AUTO) and not env_provider

    def _select_provider_safe(self) -> LLMProvider:
        """Select the provider, showing a loading dialog when called on the UI thread.

        When a network probe is needed (auto-detect mode) and the call originates
        on the Qt main thread, the probe is offloaded to a background ``QThread``
        and a non-cancellable ``QProgressDialog`` keeps the UI responsive while
        waiting.  In all other contexts (background threads, tests, CLI) the
        standard blocking path is used.
        """
        try:
            import threading

            from PySide6.QtWidgets import QApplication

            on_ui_thread = QApplication.instance() is not None and threading.current_thread() is threading.main_thread()
        except Exception:
            on_ui_thread = False

        if not on_ui_thread or not self._will_autodetect():
            return self._select_provider()

        return self._select_provider_with_dialog()

    def _select_provider_with_dialog(self) -> LLMProvider:
        """Run ``_select_provider()`` in a background thread with a progress dialog."""
        from PySide6.QtCore import QEventLoop, QThread, Signal
        from PySide6.QtWidgets import QApplication, QProgressDialog

        result: list[LLMProvider | None] = [None]
        manager = self

        class _SelectThread(QThread):
            done = Signal(object)

            def run(self) -> None:
                try:
                    self.done.emit(manager._select_provider())
                except Exception as exc:
                    log_error("LLM provider selection failed: %s", exc)
                    from .provider_factory import LLMProviderFactory

                    self.done.emit(LLMProviderFactory._make_ollama(manager._settings))

        loop = QEventLoop()
        dialog = QProgressDialog("Detecting LLM provider…", "", 0, 0, QApplication.activeWindow())
        dialog.setWindowTitle("LLM Provider")
        dialog.setMinimumDuration(200)  # only show if the probe takes > 200 ms
        dialog.setModal(True)

        thread = _SelectThread()

        def _on_done(provider: LLMProvider) -> None:
            result[0] = provider
            dialog.close()
            loop.quit()

        thread.done.connect(_on_done)
        thread.start()
        loop.exec()
        thread.wait()

        if result[0] is None:  # safety net — should not happen
            from .provider_factory import LLMProviderFactory

            return LLMProviderFactory._make_ollama(self._settings)
        return result[0]

    def refresh(self) -> None:
        """Re-select the provider from current settings and env vars."""
        self._provider = None
        self._health_cache = None
        self._health_cache_ts = None
        self._selection_debug = None

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> HealthResult:
        """Return a health result, serving from cache when within TTL."""
        now_mono = time.monotonic()
        if (
            self._health_cache is not None
            and self._health_cache_ts is not None
            and now_mono - self._health_cache_ts < self._health_ttl
        ):
            return self._health_cache
        return self.probe()

    def probe(self) -> HealthResult:
        """Perform an active health check, bypassing the cache."""
        result = self.get_provider().get_health()
        self._health_cache = result
        self._health_cache_ts = time.monotonic()
        return result

    def invalidate_health_cache(self) -> None:
        """Force the next health() call to perform a live probe."""
        self._health_cache = None
        self._health_cache_ts = None

    # ------------------------------------------------------------------
    # Request ID
    # ------------------------------------------------------------------

    def generate_request_id(self) -> str:
        """Generate a globally unique request_id (UUID4)."""
        return str(uuid.uuid4())

    # ------------------------------------------------------------------
    # Selection debug
    # ------------------------------------------------------------------

    def get_selection_debug(self) -> dict[str, Any]:
        """Return the selection_debug from the last provider selection.

        The output is deterministic for identical configuration inputs:
        same configuration → same reasons array → same order. This property
        enables stable test assertions on selection_debug output.

        Secrets (API keys) are never included in values; ``api_key_present``
        indicates presence, and ``api_key_value`` is always ``"[REDACTED]"``.
        """
        if self._selection_debug is None:
            self.get_provider()  # trigger selection
        return self._selection_debug  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _select_provider(self) -> LLMProvider:
        from .provider_factory import AUTO, OLLAMA, OPENAI_COMPATIBLE, LLMProviderFactory

        reasons: list[dict[str, Any]] = []
        now = datetime.datetime.now(datetime.UTC).isoformat()
        selected_provider_id: str | None = None
        selected_model: str | None = None
        explicit = False  # True when provider was explicitly configured

        # --- Rank 1: Explicit app config ---
        cfg_provider = self._settings.get("llm.provider", None) if self._settings else None
        if cfg_provider and cfg_provider != AUTO:
            reasons.append(
                {
                    "source": "app_config",
                    "key": "llm.provider",
                    "value": cfg_provider,
                    "timestamp": now,
                    "precedence_rank": 1,
                    "outcome": "selected",
                }
            )
            selected_provider_id = cfg_provider
            explicit = True
        else:
            reasons.append(
                {
                    "source": "app_config",
                    "key": "llm.provider",
                    "value": None,
                    "timestamp": now,
                    "precedence_rank": 1,
                    "outcome": "skipped_not_set",
                }
            )

        # --- Rank 2: Environment variables ---
        if selected_provider_id is None:
            env_provider = os.environ.get("VI_LLM_PROVIDER")
            if env_provider:
                reasons.append(
                    {
                        "source": "env",
                        "key": "VI_LLM_PROVIDER",
                        "value": env_provider,
                        "timestamp": now,
                        "precedence_rank": 2,
                        "outcome": "selected",
                    }
                )
                selected_provider_id = env_provider
                explicit = True
            else:
                reasons.append(
                    {
                        "source": "env",
                        "key": "VI_LLM_PROVIDER",
                        "value": None,
                        "timestamp": now,
                        "precedence_rank": 2,
                        "outcome": "skipped_not_set",
                    }
                )

        env_model = os.environ.get("VI_LLM_MODEL")
        # If an explicit provider selection is present, prefer the matching
        # model setting so the chosen provider gets the intended model.
        if not env_model and self._settings:
            if selected_provider_id == OLLAMA:
                env_model = self._settings.get("llm.ollama_model") or self._settings.get("llm.openai_model")
            elif selected_provider_id == OPENAI_COMPATIBLE:
                env_model = self._settings.get("llm.openai_model") or self._settings.get("llm.ollama_model")
            else:
                # Auto/unspecified: prefer ollama model then openai model (legacy behaviour)
                env_model = self._settings.get("llm.ollama_model") or self._settings.get("llm.openai_model")
        if env_model:
            reasons.append(
                {
                    "source": "env",
                    "key": "VI_LLM_MODEL",
                    "value": env_model,
                    "timestamp": now,
                    "precedence_rank": 2,
                    "outcome": "selected",
                }
            )
            selected_model = env_model

        # --- Rank 3: Auto-detection (only when no explicit provider) ---
        fallbacks_considered: list[str] = []
        if selected_provider_id is None or selected_provider_id == AUTO:
            autodetected = self._autodetect(reasons, now)
            if autodetected:
                selected_provider_id = autodetected
            else:
                fallbacks_considered.append(OLLAMA)

        # --- Rank 4: Fallback default ---
        if selected_provider_id is None or selected_provider_id == AUTO:
            api_key = os.environ.get("OPENAI_API_KEY") or (
                self._settings.get("llm.openai_api_key", "") if self._settings else ""
            )
            api_key_present = bool(api_key)
            if api_key_present:
                selected_provider_id = OPENAI_COMPATIBLE
                reasons.append(
                    {
                        "source": "fallback",
                        "key": "OPENAI_API_KEY",
                        "value": None,
                        "api_key_present": True,
                        "api_key_value": "[REDACTED]",
                        "timestamp": now,
                        "precedence_rank": 4,
                        "outcome": "selected",
                    }
                )
            else:
                selected_provider_id = OLLAMA
                reasons.append(
                    {
                        "source": "fallback",
                        "key": "default",
                        "value": OLLAMA,
                        "timestamp": now,
                        "precedence_rank": 4,
                        "outcome": "selected",
                    }
                )

        api_key_present = bool(
            os.environ.get("OPENAI_API_KEY") or (self._settings.get("llm.openai_api_key", "") if self._settings else "")
        )
        self._selection_debug = {
            "selected_provider": selected_provider_id,
            "selected_model": selected_model,
            "reasons": reasons,
            "fallbacks_considered": fallbacks_considered,
            "api_key_present": api_key_present,
            "api_key_value": "[REDACTED]",
        }

        if os.environ.get("VI_LLM_DEBUG"):
            log_info("LLM selection_debug: %s", self._selection_debug)

        effective = _EffectiveSettings(self._settings, selected_provider_id, selected_model)
        return LLMProviderFactory.create_from_settings(effective)

    def _autodetect(self, reasons: list[dict[str, Any]], now: str) -> str | None:
        """Probe for a running Ollama server. Returns provider id or None."""
        import urllib.request

        from .provider_factory import OLLAMA

        ollama_url = os.environ.get("VI_OLLAMA_URL") or (
            self._settings.get("llm.ollama_url", "http://localhost:11434")
            if self._settings
            else "http://localhost:11434"
        )
        ollama_url = ollama_url.rstrip("/")
        reachable = False
        try:
            req = urllib.request.Request(
                f"{ollama_url}/api/tags",
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                reachable = resp.status == 200
        except Exception:
            pass

        if reachable:
            reasons.append(
                {
                    "source": "autodetect",
                    "key": "ollama_reachable",
                    "value": True,
                    "timestamp": now,
                    "precedence_rank": 3,
                    "outcome": "selected",
                }
            )
            return OLLAMA

        reasons.append(
            {
                "source": "autodetect",
                "key": "ollama_reachable",
                "value": False,
                "timestamp": now,
                "precedence_rank": 3,
                "outcome": "skipped_not_set",
            }
        )
        return None


class _EffectiveSettings:
    """Merges app settings with a resolved provider_id and model override."""

    def __init__(self, settings: Any, provider_id: str, model: str | None) -> None:
        self._settings = settings
        self._provider_id = provider_id
        self._model = model

    def get(self, key: str, default: Any = None) -> Any:
        if key == "llm.provider":
            return self._provider_id
        if self._model and key in ("llm.ollama_model", "llm.openai_model"):
            return self._model
        if self._settings is not None:
            return self._settings.get(key, default)
        return default
