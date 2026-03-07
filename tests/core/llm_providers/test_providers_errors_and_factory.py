from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# Ensure tests/utils is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests"))

import pytest

from tests.core.llm_providers.conftest import _make_settings
from tests.utils.fake_llm_provider import FakeLLMProvider
from vector_inspector.core.llm_providers import (
    FAKE,
    LLMProviderFactory,
    ProviderError,
)


def _import_raiser(module_name: str):
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _raiser(name, *args, **kwargs):
        if name == module_name or name.startswith(module_name + "."):
            raise ImportError(f"Mocked missing: {name}")
        return real_import(name, *args, **kwargs)

    return _raiser


def _passthrough_except(substring: str):
    real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

    def _passthrough(name, *args, **kwargs):
        return real_import(name, *args, **kwargs)

    return _passthrough


class TestInvalidModelName:
    def test_ollama_invalid_model_raises_provider_error(self):
        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

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
            list(p.stream_messages([{"role": "user", "content": "hi"}], model="nonexistent-model"))
        assert exc_info.value.model_name == "nonexistent-model"
        assert exc_info.value.retryable is False

    def test_openai_invalid_model_raises_provider_error(self):
        from vector_inspector.core.llm_providers.openai_compatible_provider import OpenAICompatibleProvider

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


class TestProviderFactory:
    def test_factory_creates_fake_provider(self):
        s = _make_settings(**{"llm.provider": FAKE})
        with patch("tests.utils.fake_llm_provider.FakeLLMProvider", FakeLLMProvider):
            provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, FakeLLMProvider)

    def test_factory_no_io_for_known_types(self):
        import socket

        s = _make_settings(**{"llm.provider": "llama-cpp"})
        original_connect = socket.socket.connect

        calls: list[str] = []

        def _spy_connect(self, *args):
            calls.append(repr(args))
            return original_connect(self, *args)

        with patch.object(socket.socket, "connect", _spy_connect):
            _provider = LLMProviderFactory.create_from_settings(s)

        assert not calls, f"Factory made network calls: {calls}"


class TestProviderFactoryEdgeCases:
    def test_make_fake_raises_clear_error_when_not_importable(self):
        s = _make_settings(**{"llm.provider": FAKE})
        with patch.dict(
            "sys.modules",
            {"tests.utils.fake_llm_provider": None, "fake_llm_provider": None},
        ):
            with pytest.raises(ImportError, match="FakeLLMProvider not importable"):
                LLMProviderFactory.create_from_settings(s)

    def test_unknown_provider_type_is_tolerated(self):
        s = _make_settings(**{"llm.provider": "definitely-unknown-backend"})
        provider = LLMProviderFactory.create_from_settings(s)
        assert provider is not None

    def test_auto_detect_returns_llama_cpp_when_ollama_unavailable(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        s = _make_settings(**{"llm.provider": "auto"})
        with patch.object(
            __import__(
                "vector_inspector.core.llm_providers.ollama_provider", fromlist=["OllamaProvider"]
            ).OllamaProvider,
            "is_available",
            return_value=False,
        ):
            provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, LlamaCppProvider)


class TestProviderErrorAttributes:
    def test_retryable_true_is_preserved(self):
        exc = ProviderError("overloaded", provider_name="ollama", retryable=True)
        assert exc.retryable is True

    def test_retryable_false_is_default(self):
        exc = ProviderError("bad model", provider_name="ollama")
        assert exc.retryable is False

    def test_http_status_stored(self):
        exc = ProviderError("rate limited", provider_name="openai-compatible", http_status=429, retryable=True)
        assert exc.http_status == 429

    def test_code_attribute_stored(self):
        exc = ProviderError("err", provider_name="ollama", code="context_overflow")
        assert exc.code == "context_overflow"

    def test_remediation_hint_stored(self):
        hint = "Run: ollama serve"
        exc = ProviderError("err", provider_name="ollama", remediation_hint=hint)
        assert exc.remediation_hint == hint

    def test_underlying_error_stored(self):
        cause = OSError("connection refused")
        exc = ProviderError("err", provider_name="ollama", underlying_error=cause)
        assert exc.underlying_error is cause
