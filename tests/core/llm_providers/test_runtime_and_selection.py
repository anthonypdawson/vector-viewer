from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure tests/utils is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests"))

from tests.core.llm_providers.conftest import _make_settings
from tests.utils.fake_llm_provider import FakeLLMProvider
from vector_inspector.core.llm_providers import (
    OLLAMA,
    OPENAI_COMPATIBLE,
    LLMRuntimeManager,
)


class TestRuntimeManagerSelection:
    def test_env_var_overrides_auto_when_no_explicit_config(self, monkeypatch):
        monkeypatch.setenv("VI_LLM_PROVIDER", OLLAMA)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = _make_settings(**{"llm.provider": "auto"})
        mgr = LLMRuntimeManager(settings=s)
        with patch.object(
            __import__(
                "vector_inspector.core.llm_providers.ollama_provider", fromlist=["OllamaProvider"]
            ).OllamaProvider,
            "is_available",
            return_value=False,
        ):
            debug = mgr.get_selection_debug()
        assert debug["selected_provider"] == OLLAMA

    def test_explicit_config_beats_env_var(self, monkeypatch):
        monkeypatch.setenv("VI_LLM_PROVIDER", OPENAI_COMPATIBLE)
        s = _make_settings(**{"llm.provider": OLLAMA})
        mgr = LLMRuntimeManager(settings=s)
        debug = mgr.get_selection_debug()
        assert debug["selected_provider"] == OLLAMA

    def test_autodetect_used_when_no_explicit_or_env(self, monkeypatch):
        monkeypatch.delenv("VI_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = _make_settings(**{"llm.provider": "auto"})
        mgr = LLMRuntimeManager(settings=s)
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock = patch  # type: ignore
        mgr.get_selection_debug()


class TestRuntimeManagerHealthCaching:
    def test_health_returns_cached_result_within_ttl(self):
        mgr = LLMRuntimeManager(settings=None, health_ttl=60)
        mgr._provider = FakeLLMProvider()

        first = mgr.probe()
        mgr._provider = FakeLLMProvider(mode="error_inject", error_rate=1.0)
        cached = mgr.health()

        assert cached.ok is True
        assert cached is first

    def test_invalidate_health_cache_forces_new_probe(self):
        mgr = LLMRuntimeManager(settings=None, health_ttl=60)
        mgr._provider = FakeLLMProvider()
        mgr.probe()
        mgr.invalidate_health_cache()
        mgr._provider = FakeLLMProvider(mode="error_inject", error_rate=1.0)
        fresh = mgr.health()

        assert fresh.ok is False

    def test_refresh_clears_health_cache(self):
        s = _make_settings(**{"llm.provider": OLLAMA})
        mgr = LLMRuntimeManager(settings=s)
        with patch.object(
            __import__(
                "vector_inspector.core.llm_providers.ollama_provider", fromlist=["OllamaProvider"]
            ).OllamaProvider,
            "get_health",
        ) as mock_health:
            mock_health.return_value = FakeLLMProvider().get_health()
            mgr.probe()
        assert mgr._health_cache is not None
        mgr.refresh()
        assert mgr._health_cache is None

    def test_generate_request_id_is_uuid4(self):
        import re

        mgr = LLMRuntimeManager(settings=None)
        rid = mgr.generate_request_id()
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            rid,
        )

    def test_generate_request_id_is_unique(self):
        mgr = LLMRuntimeManager(settings=None)
        ids = {mgr.generate_request_id() for _ in range(20)}
        assert len(ids) == 20


class TestRuntimeManagerHealthExpiry:
    def test_probe_always_calls_live_even_with_fresh_cache(self):
        from tests.utils.fake_llm_provider import FakeLLMProvider as FLP

        mgr = LLMRuntimeManager(settings=None, health_ttl=600)
        mgr._provider = FLP()
        first = mgr.probe()

        mgr._provider = FLP(mode="error_inject", error_rate=1.0)
        second = mgr.probe()

        assert first.ok is True
        assert second.ok is False

    def test_health_calls_probe_when_cache_expired(self, monkeypatch):
        import time

        from tests.utils.fake_llm_provider import FakeLLMProvider as FLP

        mgr = LLMRuntimeManager(settings=None, health_ttl=1)
        mgr._provider = FLP()
        first = mgr.probe()
        assert first.ok is True

        _original = time.monotonic
        monkeypatch.setattr(time, "monotonic", lambda: _original() + 2)

        mgr._provider = FLP(mode="error_inject", error_rate=1.0)
        after_expiry = mgr.health()

        assert after_expiry.ok is False


class TestEffectiveSettings:
    def _make(self, store: dict, provider_id: str, model: str | None = None):
        from vector_inspector.core.llm_providers.runtime_manager import _EffectiveSettings

        class _Store:
            def get(self, key, default=None):
                return store.get(key, default)

        return _EffectiveSettings(_Store(), provider_id, model)

    def test_provider_key_always_returns_selected_provider(self):
        eff = self._make({"llm.provider": "auto"}, provider_id="ollama")
        assert eff.get("llm.provider") == "ollama"

    def test_model_override_for_ollama_model_key(self):
        eff = self._make({}, provider_id="ollama", model="mistral")
        assert eff.get("llm.ollama_model") == "mistral"

    def test_model_override_for_openai_model_key(self):
        eff = self._make({}, provider_id="openai-compatible", model="gpt-4o")
        assert eff.get("llm.openai_model") == "gpt-4o"

    def test_no_model_override_falls_back_to_settings(self):
        eff = self._make({"llm.ollama_model": "phi3"}, provider_id="ollama", model=None)
        assert eff.get("llm.ollama_model") == "phi3"

    def test_non_model_key_delegates_to_settings(self):
        eff = self._make({"llm.ollama_url": "http://custom:11434"}, provider_id="ollama")
        assert eff.get("llm.ollama_url") == "http://custom:11434"

    def test_non_model_key_returns_default_when_not_set(self):
        eff = self._make({}, provider_id="ollama")
        assert eff.get("llm.ollama_url", "http://localhost:11434") == "http://localhost:11434"

    def test_none_settings_returns_default(self):
        from vector_inspector.core.llm_providers.runtime_manager import _EffectiveSettings

        eff = _EffectiveSettings(None, "ollama", None)
        assert eff.get("llm.anything", "fallback") == "fallback"


class TestRuntimeManagerAutodetectBranches:
    def test_autodetect_reachable_adds_selected_reason(self):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        with (
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch.dict("os.environ", {"VI_LLM_PROVIDER": ""}, clear=False),
        ):
            s = _make_settings(**{"llm.provider": "auto"})
            mgr = LLMRuntimeManager(settings=s)
            debug = mgr.get_selection_debug()
        autodetect_reason = next((r for r in debug["reasons"] if r.get("source") == "autodetect"), None)
        assert autodetect_reason is not None
        assert autodetect_reason["outcome"] == "selected"
        assert autodetect_reason["value"] is True

    def test_autodetect_unreachable_adds_skipped_reason(self):
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            s = _make_settings(**{"llm.provider": "auto", "llm.openai_api_key": ""})
            mgr = LLMRuntimeManager(settings=s)
            debug = mgr.get_selection_debug()
        autodetect_reason = next((r for r in debug["reasons"] if r.get("source") == "autodetect"), None)
        assert autodetect_reason is not None
        assert autodetect_reason["outcome"] == "skipped_not_set"
        assert autodetect_reason["value"] is False

    def test_autodetect_uses_vi_ollama_url_env_var(self):
        captured_urls: list[str] = []

        def _capturing_urlopen(req, timeout=None):
            captured_urls.append(req.full_url)
            raise OSError("refused")

        custom_url = "http://my-ollama-host:11999"
        with (
            patch("urllib.request.urlopen", side_effect=_capturing_urlopen),
            patch.dict("os.environ", {"VI_OLLAMA_URL": custom_url}),
        ):
            s = _make_settings(**{"llm.provider": "auto", "llm.openai_api_key": ""})
            mgr = LLMRuntimeManager(settings=s)
            mgr.get_selection_debug()
        assert any(custom_url in url for url in captured_urls)

    def test_vi_llm_model_env_var_sets_selected_model_in_debug(self):
        with (
            patch("urllib.request.urlopen", side_effect=OSError("refused")),
            patch.dict("os.environ", {"VI_LLM_MODEL": "my-env-model"}),
        ):
            s = _make_settings(**{"llm.provider": "auto", "llm.openai_api_key": ""})
            mgr = LLMRuntimeManager(settings=s)
            debug = mgr.get_selection_debug()
        assert debug["selected_model"] == "my-env-model"

    def test_api_key_value_is_always_redacted(self):
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            s = _make_settings(**{"llm.provider": "auto", "llm.openai_api_key": "sk-super-secret"})
            mgr = LLMRuntimeManager(settings=s)
            debug = mgr.get_selection_debug()
        assert debug["api_key_value"] == "[REDACTED]"
        assert "sk-super-secret" not in str(debug)
