"""Contract tests for LLM provider implementations.

Renamed from `test_new_interface.py` for clarity.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

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
