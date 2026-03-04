"""Contract tests for LLM provider implementations.

Renamed from `test_new_interface.py` for clarity.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure tests/utils is importable so FakeLLMProvider can be imported directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests"))

from tests.utils.fake_llm_provider import FakeLLMProvider
from vector_inspector.core.llm_providers import (
    CAPABILITIES_SCHEMA_VERSION,
    FAKE,
    LLAMA_CPP,
    OLLAMA,
    OPENAI_COMPATIBLE,
    LLMProviderFactory,
    LLMRuntimeManager,
    ProviderCapabilities,
    ProviderError,
    StreamEvent,
)
from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider
from vector_inspector.core.llm_providers.openai_compatible_provider import OpenAICompatibleProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides):
    """Return a simple dict-backed settings stub."""
    defaults = {
        "llm.provider": "auto",
        "llm.model_path": "",
        "llm.cache_dir": "",
        "llm.ollama_url": "http://localhost:11434",
        "llm.ollama_model": "llama3.2",
        "llm.openai_url": "https://api.openai.com/v1",
        "llm.openai_api_key": "sk-test",
        "llm.openai_model": "gpt-4o-mini",
        "llm.context_length": 4096,
        "llm.temperature": 0.1,
    }
    defaults.update(overrides)

    class _FakeSettings:
        def get(self, key, default=None):
            return defaults.get(key, default)

    return _FakeSettings()


def _collect_stream(gen) -> list[StreamEvent]:
    return list(gen)


# ---------------------------------------------------------------------------
# ProviderCapabilities schema conformance
# ---------------------------------------------------------------------------


class TestCapabilitiesSchema:
    def test_fake_provider_schema_version(self):
        p = FakeLLMProvider()
        caps = p.get_capabilities()
        assert isinstance(caps, ProviderCapabilities)
        assert caps.schema_version == CAPABILITIES_SCHEMA_VERSION

    def test_capabilities_required_fields(self):
        p = FakeLLMProvider()
        caps = p.get_capabilities()
        assert caps.provider_name == "fake"
        assert isinstance(caps.supports_streaming, bool)
        assert isinstance(caps.supports_tools, bool)
        assert caps.concurrency in ("single-threaded", "multi", "process-isolated")
        assert isinstance(caps.max_context_tokens, int)
        assert isinstance(caps.roles_supported, list)
        assert isinstance(caps.model_list, list)

    def test_ollama_capabilities(self):
        p = OllamaProvider()
        with patch.object(p, "list_models", return_value=[]):
            caps = p.get_capabilities()
        assert caps.schema_version == CAPABILITIES_SCHEMA_VERSION
        assert caps.provider_name == "ollama"
        assert caps.supports_streaming is True
        assert "system" in caps.roles_supported

    def test_openai_capabilities(self):
        p = OpenAICompatibleProvider(base_url="http://localhost", model="gpt-4")
        with patch.object(p, "list_models", return_value=[]):
            caps = p.get_capabilities()
        assert caps.schema_version == CAPABILITIES_SCHEMA_VERSION
        assert caps.supports_streaming is True


# ---------------------------------------------------------------------------
# StreamEvent index monotonicity
# ---------------------------------------------------------------------------


class TestStreamIndexMonotonicity:
    def test_fake_stream_index_is_strictly_increasing(self):
        p = FakeLLMProvider(seed=1, fragment_size=2)
        events = _collect_stream(p.stream_messages([{"role": "user", "content": "Hello World"}], model="fake-model"))
        deltas = [e for e in events if e.type == "delta"]
        indices = [e.meta["index"] for e in deltas]
        assert indices == list(range(len(indices))), f"Indices not monotonic: {indices}"

    def test_fake_stream_ends_with_done(self):
        p = FakeLLMProvider(seed=1, fragment_size=3)
        events = _collect_stream(p.stream_messages([{"role": "user", "content": "test"}], model="fake-model"))
        assert events[-1].type == "done"
        assert events[-1].meta.get("finish_reason") == "stop"

    def test_fake_stream_includes_request_id(self):
        p = FakeLLMProvider(seed=5, fragment_size=1)
        events = _collect_stream(
            p.stream_messages(
                [{"role": "user", "content": "AB"}],
                model="fake-model",
                request_id="r-test",
            )
        )
        for e in events:
            assert e.meta.get("request_id") == "r-test"

    def test_base_provider_default_stream_is_monotonic(self):
        """Default stream_messages() in base class must also produce monotonic indices."""
        p = FakeLLMProvider(seed=2)
        # Bypass FakeLLMProvider.stream_messages to call base implementation via FakeLLMProvider
        # We test directly on a minimal concrete provider that relies on the base default
        from vector_inspector.core.llm_providers.base_provider import LLMProvider

        class _MinimalProvider(LLMProvider):
            def generate_messages(self, messages, model, stream=False, **kwargs):
                if stream:
                    return self.stream_messages(messages, model, **kwargs)
                return "hello"

            def is_available(self):
                return True

            def get_model_name(self):
                return "m"

            def get_provider_name(self):
                return "minimal"

        mp = _MinimalProvider()
        events = _collect_stream(mp.stream_messages([{"role": "user", "content": "x"}], model="m"))
        deltas = [e for e in events if e.type == "delta"]
        indices = [e.meta["index"] for e in deltas]
        assert indices == list(range(len(indices)))


# ---------------------------------------------------------------------------
# FakeLLMProvider determinism
# ---------------------------------------------------------------------------


class TestFakeProviderDeterminism:
    def test_deterministic_request_id_with_seed(self):
        p = FakeLLMProvider(seed=42, fragment_size=100)
        events1 = _collect_stream(p.stream_messages([{"role": "user", "content": "Hi"}], model="fake-model"))
        p2 = FakeLLMProvider(seed=42, fragment_size=100)
        events2 = _collect_stream(p2.stream_messages([{"role": "user", "content": "Hi"}], model="fake-model"))
        rids1 = [e.meta.get("request_id") for e in events1]
        rids2 = [e.meta.get("request_id") for e in events2]
        assert rids1 == rids2

    def test_request_id_format_with_seed(self):
        p = FakeLLMProvider(seed=7, fragment_size=50)
        events = _collect_stream(p.stream_messages([{"role": "user", "content": "X"}], model="fake-model"))
        # First request: n=0 → r-7-0
        for e in events:
            assert e.meta.get("request_id") == "r-7-0"

    def test_request_id_sequential_without_seed(self):
        p = FakeLLMProvider(seed=0, fragment_size=50)
        # seed=0 is treated as no seed (sequential)
        events = _collect_stream(p.stream_messages([{"role": "user", "content": "X"}], model="fake-model"))
        request_ids = {e.meta.get("request_id") for e in events}
        assert "r-0" in request_ids

    def test_generate_messages_echo_mode(self):
        p = FakeLLMProvider(seed=1, mode="echo")
        result = p.generate_messages(
            [{"role": "user", "content": "Hello"}],
            model="fake-model",
        )
        assert result == "Hello"

    def test_generate_messages_multi_turn_concatenates(self):
        p = FakeLLMProvider(seed=1, mode="echo")
        result = p.generate_messages(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": " user"},
            ],
            model="fake-model",
        )
        assert result == "sys user"


# ---------------------------------------------------------------------------
# FakeLLMProvider health
# ---------------------------------------------------------------------------


class TestFakeProviderHealth:
    def test_healthy_by_default(self):
        p = FakeLLMProvider()
        h = p.get_health()
        assert h.ok is True
        assert h.provider == "fake"
        assert h.remediation_hint is None

    def test_unhealthy_when_error_rate_is_1(self):
        p = FakeLLMProvider(mode="error_inject", error_rate=1.0)
        h = p.get_health()
        assert h.ok is False
        assert h.remediation_hint is not None


# ---------------------------------------------------------------------------
# Invalid model name raises ProviderError
# ---------------------------------------------------------------------------


class TestInvalidModelName:
    def test_ollama_invalid_model_raises_provider_error(self):
        p = OllamaProvider()
        with (
            patch.object(
                p,
                "list_models",
                return_value=[
                    __import__(
                        "vector_inspector.core.llm_providers.types",
                        fromlist=["ModelMetadata"],
                    ).ModelMetadata(model_name="llama3.2", context_window=4096)
                ],
            ),
            pytest.raises(ProviderError) as exc_info,
        ):
            # Use a non-streaming path that calls _validate_model
            list(p.stream_messages([{"role": "user", "content": "hi"}], model="nonexistent-model"))
        assert exc_info.value.model_name == "nonexistent-model"
        assert exc_info.value.retryable is False

    def test_openai_invalid_model_raises_provider_error(self):
        p = OpenAICompatibleProvider(base_url="http://localhost", model="gpt-4")
        with (
            patch.object(
                p,
                "list_models",
                return_value=[
                    __import__(
                        "vector_inspector.core.llm_providers.types",
                        fromlist=["ModelMetadata"],
                    ).ModelMetadata(model_name="gpt-4", context_window=4096)
                ],
            ),
            pytest.raises(ProviderError),
        ):
            list(p.stream_messages([{"role": "user", "content": "hi"}], model="gpt-999"))


# ---------------------------------------------------------------------------
# Missing optional deps → health().ok == False + remediation_hint
# ---------------------------------------------------------------------------


class TestMissingOptionalDeps:
    def test_llama_cpp_missing_bindings_health(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        p = LlamaCppProvider()
        with patch.dict("sys.modules", {"llama_cpp": None}):
            with patch("builtins.__import__", side_effect=_import_raiser("llama_cpp")):
                h = p.get_health()
        assert h.ok is False
        assert h.retryable is False
        assert h.remediation_hint is not None
        assert len(h.remediation_hint) <= 200

    def test_llama_cpp_missing_model_file_health(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        p = LlamaCppProvider(model_path="/nonexistent/path/model.gguf")
        with patch("builtins.__import__", side_effect=_passthrough_except("nonexistent")):
            try:
                import llama_cpp  # noqa: F401

                llama_available = True
            except ImportError:
                llama_available = False
        if not llama_available:
            pytest.skip("llama-cpp-python not installed; skipping model-path health test")

        h = p.get_health()
        assert h.ok is False
        assert h.remediation_hint is not None


def _import_raiser(module_name: str):
    """Return an __import__ side-effect that raises ImportError for module_name."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__  # type: ignore[union-attr]

    def _raiser(name, *args, **kwargs):
        if name == module_name or name.startswith(module_name + "."):
            raise ImportError(f"Mocked missing: {name}")
        return real_import(name, *args, **kwargs)

    return _raiser


def _passthrough_except(substring: str):
    """Return an __import__ that passes through everything (no-op mock)."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__  # type: ignore[union-attr]

    def _passthrough(name, *args, **kwargs):
        return real_import(name, *args, **kwargs)

    return _passthrough


# ---------------------------------------------------------------------------
# Provider factory: FAKE type + no I/O during construction
# ---------------------------------------------------------------------------


class TestProviderFactory:
    def test_factory_creates_fake_provider(self):
        s = _make_settings(**{"llm.provider": FAKE})
        with patch("tests.utils.fake_llm_provider.FakeLLMProvider", FakeLLMProvider):
            provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, FakeLLMProvider)

    def test_factory_no_io_for_known_types(self):
        """Factory must not perform I/O when constructing an explicit provider."""
        import socket

        s = _make_settings(**{"llm.provider": LLAMA_CPP})
        # Block all network to prove no I/O happens
        original_connect = socket.socket.connect

        calls: list[str] = []

        def _spy_connect(self, *args):
            calls.append(repr(args))
            return original_connect(self, *args)

        with patch.object(socket.socket, "connect", _spy_connect):
            _provider = LLMProviderFactory.create_from_settings(s)

        assert not calls, f"Factory made network calls: {calls}"


# ---------------------------------------------------------------------------
# selection_debug stability
# ---------------------------------------------------------------------------


class TestSelectionDebugStability:
    def test_selection_debug_is_deterministic(self, monkeypatch):
        """Identical configuration → identical selection_debug across runs."""
        monkeypatch.delenv("VI_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("VI_LLM_MODEL", raising=False)
        monkeypatch.delenv("VI_OLLAMA_URL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        s = _make_settings(**{"llm.provider": OLLAMA, "llm.ollama_model": "llama3.2"})
        mgr1 = LLMRuntimeManager(settings=s)
        mgr2 = LLMRuntimeManager(settings=s)

        with patch.object(
            __import__(
                "vector_inspector.core.llm_providers.ollama_provider", fromlist=["OllamaProvider"]
            ).OllamaProvider,
            "is_available",
            return_value=True,
        ):
            debug1 = mgr1.get_selection_debug()
            debug2 = mgr2.get_selection_debug()

        assert debug1["selected_provider"] == debug2["selected_provider"]
        assert debug1["selected_model"] == debug2["selected_model"]
        # reasons array must have same sources and outcomes
        assert [(r["source"], r["outcome"]) for r in debug1["reasons"]] == [
            (r["source"], r["outcome"]) for r in debug2["reasons"]
        ]

    def test_selection_debug_redacts_api_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret")
        monkeypatch.setenv("VI_LLM_PROVIDER", OPENAI_COMPATIBLE)
        s = _make_settings(**{"llm.provider": OPENAI_COMPATIBLE})
        mgr = LLMRuntimeManager(settings=s)
        with patch.object(
            __import__(
                "vector_inspector.core.llm_providers.openai_compatible_provider",
                fromlist=["OpenAICompatibleProvider"],
            ).OpenAICompatibleProvider,
            "is_available",
            return_value=True,
        ):
            debug = mgr.get_selection_debug()
        assert debug["api_key_value"] == "[REDACTED]"
        # The raw key must not appear anywhere in the debug dict
        import json

        debug_str = json.dumps(debug)
        assert "sk-super-secret" not in debug_str


# ---------------------------------------------------------------------------
# Fallback when providers are unhealthy
# ---------------------------------------------------------------------------


class TestUnhealthyProviderFallback:
    def test_explicit_unhealthy_provider_not_silently_replaced(self, monkeypatch):
        """Explicitly configured but unhealthy provider must surface the error,
        not be silently swapped for another provider."""
        import datetime

        from vector_inspector.core.llm_providers import HealthResult

        monkeypatch.delenv("VI_LLM_PROVIDER", raising=False)
        s = _make_settings(**{"llm.provider": OLLAMA})
        mgr = LLMRuntimeManager(settings=s)

        _unhealthy = HealthResult(
            ok=False,
            provider="ollama",
            models=[],
            version=None,
            last_checked=datetime.datetime.now(datetime.UTC).isoformat(),
            retryable=True,
            remediation_hint="Ollama is not running",
        )
        with patch.object(OllamaProvider, "get_health", return_value=_unhealthy):
            health = mgr.probe()

        assert health.provider == "ollama"
        assert health.ok is False
        # Must not silently switch to a different provider
        debug = mgr.get_selection_debug()
        assert debug["selected_provider"] == OLLAMA

    def test_health_result_has_all_required_fields(self):
        p = FakeLLMProvider()
        h = p.get_health()
        for field in ("ok", "provider", "models", "version", "last_checked", "retryable", "remediation_hint"):
            assert hasattr(h, field), f"HealthResult missing field: {field}"


# ---------------------------------------------------------------------------
# HealthResult remediation_hint length constraint
# ---------------------------------------------------------------------------


class TestRemediationHintConstraint:
    def test_remediation_hint_under_200_chars(self):
        p = FakeLLMProvider(mode="error_inject", error_rate=1.0)
        h = p.get_health()
        hint = h.remediation_hint
        if hint is not None:
            assert len(hint) <= 200, f"remediation_hint too long ({len(hint)} chars)"

    def test_ollama_unreachable_hint_under_200_chars(self):
        p = OllamaProvider(base_url="http://127.0.0.1:19999")
        h = p.get_health()
        if not h.ok and h.remediation_hint:
            assert len(h.remediation_hint) <= 200


# ---------------------------------------------------------------------------
# Item 12 — Provider list_models() and get_health() paths
# ---------------------------------------------------------------------------


class TestOllamaListModels:
    def test_list_models_returns_metadata_list(self):
        p = OllamaProvider(model="llama3.2")
        fake_response = b'{"models": [{"name": "llama3.2"}, {"name": "mistral"}]}'
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = fake_response
            mock_open.return_value = mock_resp
            models = p.list_models()
        assert len(models) == 2
        assert models[0].model_name == "llama3.2"
        assert models[1].model_name == "mistral"

    def test_list_models_fallback_on_error(self):
        p = OllamaProvider(model="llama3.2")
        with patch("urllib.request.urlopen", side_effect=OSError("unreachable")):
            models = p.list_models()
        assert len(models) == 1
        assert models[0].model_name == "llama3.2"

    def test_get_health_ok_path(self):
        p = OllamaProvider(model="llama3.2")
        fake_data = b'{"models": [{"name": "llama3.2"}], "version": "0.5.1"}'
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = fake_data
            mock_open.return_value = mock_resp
            h = p.get_health()
        assert h.ok is True
        assert h.provider == "ollama"
        assert "llama3.2" in h.models
        assert h.version == "0.5.1"

    def test_get_health_failure_path(self):
        p = OllamaProvider(base_url="http://127.0.0.1:19999")
        with patch("urllib.request.urlopen", side_effect=OSError("unreachable")):
            h = p.get_health()
        assert h.ok is False
        assert h.retryable is True
        assert h.remediation_hint is not None


class TestOpenAICompatibleListModels:
    def test_list_models_returns_metadata_list(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="gpt-4")
        fake_data = b'{"data": [{"id": "gpt-4"}, {"id": "gpt-3.5-turbo"}]}'
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = fake_data
            mock_open.return_value = mock_resp
            models = p.list_models()
        assert len(models) == 2
        assert models[0].model_name == "gpt-4"

    def test_list_models_fallback_on_error(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="gpt-4")
        with patch("urllib.request.urlopen", side_effect=OSError("unreachable")):
            models = p.list_models()
        assert len(models) == 1
        assert models[0].model_name == "gpt-4"

    def test_list_models_empty_base_url_returns_configured_model(self):
        p = OpenAICompatibleProvider(base_url="", model="gpt-4o")
        models = p.list_models()
        assert len(models) == 1
        assert models[0].model_name == "gpt-4o"

    def test_get_health_ok_path(self):

        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="gpt-4")
        fake_data = b'{"data": [{"id": "gpt-4"}]}'
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.read.return_value = fake_data
            mock_open.return_value = mock_resp
            h = p.get_health()
        assert h.ok is True
        assert h.provider == "openai-compatible"

    def test_get_health_401_gives_api_key_hint(self):
        import urllib.error

        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="gpt-4", api_key="bad")
        err = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=None)  # type: ignore[arg-type]
        err.read = lambda: b"Unauthorized"
        with patch("urllib.request.urlopen", side_effect=err):
            h = p.get_health()
        assert h.ok is False
        assert h.remediation_hint is not None
        assert "API key" in h.remediation_hint

    def test_get_health_no_url_returns_not_ok(self):
        p = OpenAICompatibleProvider(base_url="", model="")
        h = p.get_health()
        assert h.ok is False
        assert h.remediation_hint is not None

    def test_get_health_network_error_retryable(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:9999", model="m")
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            h = p.get_health()
        assert h.ok is False
        assert h.retryable is True


class TestLlamaCppListModels:
    def test_list_models_returns_single_configured_model(self, tmp_path):

        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        # Create a dummy GGUF file so _resolve_model_path() finds it
        model_file = tmp_path / "my-model.gguf"
        model_file.write_bytes(b"")
        p = LlamaCppProvider(model_path=str(model_file))
        models = p.list_models()
        assert len(models) == 1
        assert models[0].model_name == "my-model.gguf"

    def test_list_models_default_filename_when_no_path(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import (
            DEFAULT_MODEL_FILENAME,
            LlamaCppProvider,
        )

        p = LlamaCppProvider(model_path="")
        # No file exists → falls back to DEFAULT_MODEL_FILENAME
        models = p.list_models()
        assert len(models) == 1
        assert models[0].model_name == DEFAULT_MODEL_FILENAME


# ---------------------------------------------------------------------------
# Item 14 — LLMRuntimeManager: selection precedence, env vars, health caching
# ---------------------------------------------------------------------------


class TestRuntimeManagerSelection:
    def test_env_var_overrides_auto_when_no_explicit_config(self, monkeypatch):
        monkeypatch.setenv("VI_LLM_PROVIDER", OLLAMA)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = _make_settings(**{"llm.provider": "auto"})
        mgr = LLMRuntimeManager(settings=s)
        with patch.object(OllamaProvider, "is_available", return_value=False):
            debug = mgr.get_selection_debug()
        assert debug["selected_provider"] == OLLAMA
        env_reason = next(r for r in debug["reasons"] if r["source"] == "env" and r["key"] == "VI_LLM_PROVIDER")
        assert env_reason["outcome"] == "selected"

    def test_explicit_config_beats_env_var(self, monkeypatch):
        monkeypatch.setenv("VI_LLM_PROVIDER", OPENAI_COMPATIBLE)
        s = _make_settings(**{"llm.provider": OLLAMA})
        mgr = LLMRuntimeManager(settings=s)
        debug = mgr.get_selection_debug()
        assert debug["selected_provider"] == OLLAMA
        cfg_reason = next(r for r in debug["reasons"] if r["source"] == "app_config")
        assert cfg_reason["outcome"] == "selected"

    def test_autodetect_used_when_no_explicit_or_env(self, monkeypatch):
        monkeypatch.delenv("VI_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = _make_settings(**{"llm.provider": "auto"})
        mgr = LLMRuntimeManager(settings=s)
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_resp.status = 200
            mock_open.return_value = mock_resp
            debug = mgr.get_selection_debug()
        assert debug["selected_provider"] == OLLAMA
        autodetect_reason = next(r for r in debug["reasons"] if r["source"] == "autodetect")
        assert autodetect_reason["outcome"] == "selected"

    def test_fallback_to_openai_when_api_key_present(self, monkeypatch):
        monkeypatch.delenv("VI_LLM_PROVIDER", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        s = _make_settings(**{"llm.provider": "auto", "llm.openai_api_key": ""})
        mgr = LLMRuntimeManager(settings=s)
        with patch("urllib.request.urlopen", side_effect=OSError("no ollama")):
            debug = mgr.get_selection_debug()
        assert debug["selected_provider"] == OPENAI_COMPATIBLE
        assert debug["api_key_present"] is True

    def test_fallback_to_ollama_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("VI_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = _make_settings(**{"llm.provider": "auto", "llm.openai_api_key": ""})
        mgr = LLMRuntimeManager(settings=s)
        with patch("urllib.request.urlopen", side_effect=OSError("no ollama")):
            debug = mgr.get_selection_debug()
        assert debug["selected_provider"] == OLLAMA


class TestRuntimeManagerHealthCaching:
    def test_health_returns_cached_result_within_ttl(self):
        from tests.utils.fake_llm_provider import FakeLLMProvider as FLP

        mgr = LLMRuntimeManager(settings=None, health_ttl=60)
        mgr._provider = FLP()

        first = mgr.probe()
        # Replace provider with one that always fails — cache should still return ok
        mgr._provider = FLP(mode="error_inject", error_rate=1.0)
        cached = mgr.health()

        assert cached.ok is True
        assert cached is first

    def test_invalidate_health_cache_forces_new_probe(self):
        from tests.utils.fake_llm_provider import FakeLLMProvider as FLP

        mgr = LLMRuntimeManager(settings=None, health_ttl=60)
        mgr._provider = FLP()
        mgr.probe()
        mgr.invalidate_health_cache()
        mgr._provider = FLP(mode="error_inject", error_rate=1.0)
        fresh = mgr.health()

        assert fresh.ok is False

    def test_refresh_clears_health_cache(self):
        s = _make_settings(**{"llm.provider": OLLAMA})
        mgr = LLMRuntimeManager(settings=s)
        with patch.object(OllamaProvider, "get_health") as mock_health:
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
        ), f"Not a UUID4: {rid}"

    def test_generate_request_id_is_unique(self):
        mgr = LLMRuntimeManager(settings=None)
        ids = {mgr.generate_request_id() for _ in range(20)}
        assert len(ids) == 20


# ---------------------------------------------------------------------------
# Item 4 — BaseProvider default implementations
# ---------------------------------------------------------------------------


class TestBaseProviderDefaults:
    """Test the default method implementations in LLMProvider base class."""

    def _make_minimal(self, available: bool = True):
        from vector_inspector.core.llm_providers.base_provider import LLMProvider

        _avail = available

        class _Minimal(LLMProvider):
            def generate_messages(self, messages, model, stream=False, **kwargs):
                if stream:
                    return self.stream_messages(messages, model, **kwargs)
                return "response"

            def is_available(self):
                return _avail

            def get_model_name(self):
                return "minimal-model"

            def get_provider_name(self):
                return "minimal"

        return _Minimal()

    def test_get_info_returns_name_and_provider(self):
        p = FakeLLMProvider()
        info = p.get_info()
        assert info.name == p.get_model_name()
        assert info.provider == p.get_provider_name()

    def test_default_get_health_ok_when_available(self):
        p = self._make_minimal(available=True)
        h = p.get_health()
        assert h.ok is True
        assert h.provider == "minimal"
        assert "minimal-model" in h.models
        assert h.remediation_hint is None
        assert h.retryable is False

    def test_default_get_health_not_ok_when_unavailable(self):
        p = self._make_minimal(available=False)
        h = p.get_health()
        assert h.ok is False
        assert h.retryable is True
        assert h.remediation_hint is not None
        assert "minimal" in h.remediation_hint


# ---------------------------------------------------------------------------
# Ollama: streaming, error paths, model name
# ---------------------------------------------------------------------------


class TestOllamaProviderFull:
    def test_get_model_name(self):
        p = OllamaProvider(model="mistral")
        assert p.get_model_name() == "mistral"

    def test_generate_messages_stream_path_delegates(self):
        p = OllamaProvider(model="llama3.2")
        sentinel = object()
        with patch.object(p, "_validate_model"), patch.object(p, "stream_messages", return_value=sentinel):
            result = p.generate_messages([{"role": "user", "content": "hi"}], model="llama3.2", stream=True)
        assert result is sentinel

    def test_generate_messages_raises_provider_error_on_network_failure(self):
        p = OllamaProvider(model="llama3.2")
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=OSError("refused")):
            with pytest.raises(ProviderError) as exc_info:
                p.generate_messages([{"role": "user", "content": "hi"}], model="llama3.2")
        assert exc_info.value.provider_name == "ollama"
        assert exc_info.value.retryable is True

    def test_stream_messages_yields_delta_and_done(self):
        import json

        p = OllamaProvider(model="llama3.2")
        chunks = [
            json.dumps({"message": {"content": "Hello"}, "done": False}).encode(),
            json.dumps({"message": {"content": " world"}, "done": True}).encode(),
        ]
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = lambda s: iter(chunks)
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", return_value=mock_resp):
            events = list(p.stream_messages([{"role": "user", "content": "Hi"}], model="llama3.2"))
        delta_events = [e for e in events if e.type == "delta"]
        done_events = [e for e in events if e.type == "done"]
        assert delta_events[0].content == "Hello"
        assert delta_events[1].content == " world"
        assert done_events[0].meta["finish_reason"] == "stop"

    def test_stream_messages_skips_empty_lines(self):
        import json

        p = OllamaProvider(model="llama3.2")
        chunks = [
            b"",
            b"\n",
            json.dumps({"message": {"content": "x"}, "done": True}).encode(),
        ]
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = lambda s: iter(chunks)
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", return_value=mock_resp):
            events = list(p.stream_messages([{"role": "user", "content": "hi"}], model="llama3.2"))
        assert any(e.type == "done" for e in events)

    def test_stream_messages_raises_provider_error_on_network_failure(self):
        p = OllamaProvider(model="llama3.2")
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=OSError("refused")):
            with pytest.raises(ProviderError):
                list(p.stream_messages([{"role": "user", "content": "hi"}], model="llama3.2"))


# ---------------------------------------------------------------------------
# OpenAI-compatible: is_available, stream, error paths, model name
# ---------------------------------------------------------------------------


class TestOpenAICompatibleFull:
    def test_is_available_true_when_server_responds_200(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="gpt-4")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert p.is_available() is True

    def test_get_model_name(self):
        p = OpenAICompatibleProvider(base_url="http://localhost", model="gpt-4o")
        assert p.get_model_name() == "gpt-4o"

    def test_generate_messages_stream_path_delegates(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        sentinel = object()
        with patch.object(p, "_validate_model"), patch.object(p, "stream_messages", return_value=sentinel):
            result = p.generate_messages([{"role": "user", "content": "hi"}], model="m", stream=True)
        assert result is sentinel

    def test_generate_messages_raises_retryable_on_429(self):
        import urllib.error

        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        err = urllib.error.HTTPError(
            url="",
            code=429,
            msg="Rate limit",
            hdrs=None,
            fp=None,  # type: ignore[arg-type]
        )
        err.read = lambda: b"Too many requests"
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(ProviderError) as exc_info:
                p.generate_messages([{"role": "user", "content": "hi"}], model="m")
        assert exc_info.value.retryable is True
        assert exc_info.value.http_status == 429

    def test_generate_messages_raises_non_retryable_on_400(self):
        import urllib.error

        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        err = urllib.error.HTTPError(
            url="",
            code=400,
            msg="Bad request",
            hdrs=None,
            fp=None,  # type: ignore[arg-type]
        )
        err.read = lambda: b"Bad request"
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(ProviderError) as exc_info:
                p.generate_messages([{"role": "user", "content": "hi"}], model="m")
        assert exc_info.value.retryable is False

    def test_generate_messages_raises_provider_error_on_generic_exception(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=OSError("refused")):
            with pytest.raises(ProviderError) as exc_info:
                p.generate_messages([{"role": "user", "content": "hi"}], model="m")
        assert exc_info.value.retryable is True

    def test_stream_messages_yields_delta_and_done(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        sse_lines = [
            b'data: {"choices": [{"delta": {"content": "hello"}}]}\n',
            b'data: {"choices": [{"delta": {"content": " world"}}]}\n',
            b"data: [DONE]\n",
        ]
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = lambda s: iter(sse_lines)
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", return_value=mock_resp):
            events = list(p.stream_messages([{"role": "user", "content": "hi"}], model="m"))
        delta_events = [e for e in events if e.type == "delta"]
        done_events = [e for e in events if e.type == "done"]
        assert len(delta_events) == 2
        assert delta_events[0].content == "hello"
        assert done_events[0].meta["finish_reason"] == "stop"

    def test_stream_messages_skips_non_data_lines(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        sse_lines = [b": comment\n", b"\n", b"event: message\n", b"data: [DONE]\n"]
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = lambda s: iter(sse_lines)
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", return_value=mock_resp):
            events = list(p.stream_messages([{"role": "user", "content": "hi"}], model="m"))
        assert sum(1 for e in events if e.type == "done") == 1

    def test_stream_messages_raises_on_network_error(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=OSError("refused")):
            with pytest.raises(ProviderError):
                list(p.stream_messages([{"role": "user", "content": "hi"}], model="m"))


# ---------------------------------------------------------------------------
# LlamaCpp: cache helpers, download, generate paths, health, capabilities
# ---------------------------------------------------------------------------


class TestLlamaCppFull:
    def test_get_llm_cache_dir_uses_custom_dir(self, tmp_path):
        from vector_inspector.core.llm_providers.llama_cpp_provider import get_llm_cache_dir
        from vector_inspector.services.settings_service import SettingsService

        custom = str(tmp_path / "custom_cache")
        with patch.object(SettingsService, "get", return_value=custom):
            result = get_llm_cache_dir()
        assert result == tmp_path / "custom_cache"
        assert result.exists()

    def test_list_cached_models_empty_when_dir_missing(self, tmp_path):
        from vector_inspector.core.llm_providers.llama_cpp_provider import list_cached_models

        missing = tmp_path / "nonexistent"
        with patch("vector_inspector.core.llm_providers.llama_cpp_provider.get_llm_cache_dir", return_value=missing):
            assert list_cached_models() == []

    def test_list_cached_models_returns_sorted_gguf_names(self, tmp_path):
        from vector_inspector.core.llm_providers.llama_cpp_provider import list_cached_models

        (tmp_path / "model_b.gguf").write_bytes(b"")
        (tmp_path / "model_a.gguf").write_bytes(b"")
        (tmp_path / "other.txt").write_bytes(b"")
        with patch("vector_inspector.core.llm_providers.llama_cpp_provider.get_llm_cache_dir", return_value=tmp_path):
            result = list_cached_models()
        assert result == ["model_a.gguf", "model_b.gguf"]

    def test_download_default_model_returns_existing_if_cached(self, tmp_path):
        from vector_inspector.core.llm_providers.llama_cpp_provider import (
            DEFAULT_MODEL_FILENAME,
            download_default_model,
        )

        existing = tmp_path / DEFAULT_MODEL_FILENAME
        existing.write_bytes(b"cached")
        with patch("vector_inspector.core.llm_providers.llama_cpp_provider.get_llm_cache_dir", return_value=tmp_path):
            result = download_default_model()
        assert result == existing

    def test_download_default_model_calls_urlretrieve_and_progress(self, tmp_path):
        from vector_inspector.core.llm_providers.llama_cpp_provider import (
            DEFAULT_MODEL_FILENAME,
            DEFAULT_MODEL_HF_URL,
            download_default_model,
        )

        def _fake_retrieve(url, dest, callback):
            Path(dest).write_bytes(b"fake-model")
            if callback:
                callback(1, 512, 1024)

        progress_calls: list[tuple[int, int]] = []
        with patch("vector_inspector.core.llm_providers.llama_cpp_provider.get_llm_cache_dir", return_value=tmp_path):
            with patch("urllib.request.urlretrieve", side_effect=_fake_retrieve) as mock_retr:
                result = download_default_model(progress_callback=lambda d, t: progress_calls.append((d, t)))
        assert mock_retr.call_args[0][0] == DEFAULT_MODEL_HF_URL
        assert result.name == DEFAULT_MODEL_FILENAME
        assert len(progress_calls) > 0
        assert progress_calls[0] == (512, 1024)

    def test_generate_messages_stream_path_delegates(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        p = LlamaCppProvider()
        sentinel = object()
        with patch.object(p, "stream_messages", return_value=sentinel):
            result = p.generate_messages([{"role": "user", "content": "hi"}], model="m", stream=True)
        assert result is sentinel

    def test_generate_messages_raises_when_model_load_fails(self, tmp_path):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"")
        p = LlamaCppProvider(model_path=str(model_file))
        mock_llama = MagicMock()
        mock_llama.Llama.side_effect = RuntimeError("load failed")
        with patch.dict("sys.modules", {"llama_cpp": mock_llama}):
            with pytest.raises(RuntimeError, match="load failed"):
                p.generate_messages([{"role": "user", "content": "hi"}], model="m")

    def test_get_capabilities_returns_llama_cpp_caps(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        p = LlamaCppProvider()
        caps = p.get_capabilities()
        assert caps.provider_name == "llama-cpp"
        assert "system" in caps.roles_supported
        assert caps.supports_streaming is False

    def test_get_health_ok_when_llama_available_and_model_found(self, tmp_path):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"")
        p = LlamaCppProvider(model_path=str(model_file))
        mock_llama = MagicMock()
        with patch.dict("sys.modules", {"llama_cpp": mock_llama}):
            h = p.get_health()
        assert h.ok is True
        assert h.provider == "llama-cpp"
        assert "model.gguf" in h.models

    def test_get_health_not_ok_when_model_not_found(self, tmp_path):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        p = LlamaCppProvider(model_path=str(tmp_path / "missing.gguf"))
        mock_llama = MagicMock()
        with patch.dict("sys.modules", {"llama_cpp": mock_llama}):
            h = p.get_health()
        assert h.ok is False
        assert h.remediation_hint is not None
