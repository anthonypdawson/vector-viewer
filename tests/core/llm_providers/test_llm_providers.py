"""Tests for LLMProviderFactory and LLMProviderInstance."""

from unittest.mock import MagicMock, patch

import pytest

from tests.core.llm_providers.conftest import _make_settings
from vector_inspector.core.llm_providers import (
    AUTO,
    LLAMA_CPP,
    OLLAMA,
    OPENAI_COMPATIBLE,
    LLMProviderFactory,
    LLMProviderInstance,
)

# ---------------------------------------------------------------------------
# LLMProviderFactory
# ---------------------------------------------------------------------------


class TestLLMProviderFactoryExplicitTypes:
    def test_creates_ollama_when_configured(self):
        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

        s = _make_settings(**{"llm.provider": OLLAMA})
        provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, OllamaProvider)

    def test_creates_llama_cpp_when_configured(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        s = _make_settings(**{"llm.provider": LLAMA_CPP})
        provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, LlamaCppProvider)

    def test_creates_openai_when_configured(self):
        from vector_inspector.core.llm_providers.openai_compatible_provider import (
            OpenAICompatibleProvider,
        )

        s = _make_settings(**{"llm.provider": OPENAI_COMPATIBLE})
        provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, OpenAICompatibleProvider)

    def test_unknown_type_falls_back_to_auto(self):
        s = _make_settings(**{"llm.provider": "unknown-backend"})
        # Should not raise; falls back to auto-detection
        provider = LLMProviderFactory.create_from_settings(s)
        assert provider is not None


class TestLLMProviderFactoryAutoDetect:
    def test_auto_prefers_ollama_when_available(self):
        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

        s = _make_settings(**{"llm.provider": AUTO})
        with patch.object(OllamaProvider, "is_available", return_value=True):
            provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, OllamaProvider)

    def test_auto_falls_back_to_llama_when_ollama_unavailable(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider
        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

        s = _make_settings(**{"llm.provider": AUTO})
        with patch.object(OllamaProvider, "is_available", return_value=False):
            provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, LlamaCppProvider)

    def test_auto_passes_ollama_url_and_model(self):
        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

        s = _make_settings(
            **{
                "llm.provider": AUTO,
                "llm.ollama_url": "http://myhost:11434",
                "llm.ollama_model": "mistral",
            }
        )
        with patch.object(OllamaProvider, "is_available", return_value=True):
            provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, OllamaProvider)
        assert provider._base_url == "http://myhost:11434"
        assert provider._model == "mistral"

    def test_auto_passes_model_path_to_llama_cpp(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider
        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

        s = _make_settings(
            **{
                "llm.provider": AUTO,
                "llm.model_path": "/models/my.gguf",
            }
        )
        with patch.object(OllamaProvider, "is_available", return_value=False):
            provider = LLMProviderFactory.create_from_settings(s)
        assert isinstance(provider, LlamaCppProvider)
        assert provider._model_path == "/models/my.gguf"


# ---------------------------------------------------------------------------
# LLMProviderInstance
# ---------------------------------------------------------------------------


class TestLLMProviderInstance:
    def test_wraps_provider_and_forwards_generate(self):
        s = _make_settings(**{"llm.provider": OLLAMA})
        mock_provider = MagicMock()
        mock_provider.generate_messages.return_value = "hello"
        mock_provider.is_available.return_value = True
        mock_provider.get_model_name.return_value = "llama3.2"
        mock_provider.get_provider_name.return_value = "ollama"

        instance = LLMProviderInstance(s)
        with patch.object(LLMProviderFactory, "create_from_settings", return_value=mock_provider):
            instance.refresh()
            result = instance.generate("test prompt")

        assert result == "hello"
        mock_provider.generate_messages.assert_called_once_with(
            [{"role": "user", "content": "test prompt"}],
            model="llama3.2",
            stream=False,
        )

    def test_is_available_reflects_provider(self):
        s = _make_settings(**{"llm.provider": LLAMA_CPP})
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = False

        instance = LLMProviderInstance(s)
        with patch.object(LLMProviderFactory, "create_from_settings", return_value=mock_provider):
            instance.refresh()
            assert instance.is_available() is False

    def test_refresh_rebuilds_provider(self):
        s = _make_settings(**{"llm.provider": LLAMA_CPP})
        mock1 = MagicMock()
        mock2 = MagicMock()
        mock1.is_available.return_value = True
        mock2.is_available.return_value = False

        instance = LLMProviderInstance(s)
        with patch.object(LLMProviderFactory, "create_from_settings", return_value=mock1):
            instance.refresh()
            assert instance.is_available() is True

        with patch.object(LLMProviderFactory, "create_from_settings", return_value=mock2):
            instance.refresh()
            assert instance.is_available() is False

    def test_generate_raises_when_none_provider(self):
        s = _make_settings()
        instance = LLMProviderInstance(s)
        with patch.object(LLMProviderFactory, "create_from_settings", return_value=None):
            instance.refresh()
            with pytest.raises(RuntimeError, match="No LLM provider"):
                instance.generate("hi")


# ---------------------------------------------------------------------------
# OllamaProvider
# ---------------------------------------------------------------------------


class TestOllamaProvider:
    def test_is_available_returns_true_on_200(self):
        from unittest.mock import MagicMock

        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200

        with patch("urllib.request.urlopen", return_value=mock_resp):
            assert provider.is_available() is True

    def test_is_available_returns_false_on_connection_error(self):
        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            assert provider.is_available() is False

    def test_generate_messages_returns_response_text(self):
        import json

        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

        provider = OllamaProvider()
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        # /api/chat response shape
        mock_resp.read.return_value = json.dumps({"message": {"content": "  result text  "}}).encode()

        with patch("urllib.request.urlopen", return_value=mock_resp), patch.object(provider, "_validate_model"):
            result = provider.generate_messages(
                [{"role": "user", "content": "tell me a story"}],
                model="llama3.2",
            )

        assert result == "result text"

    def test_provider_name(self):
        from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

        assert OllamaProvider().get_provider_name() == "ollama"


# ---------------------------------------------------------------------------
# OpenAICompatibleProvider
# ---------------------------------------------------------------------------


class TestOpenAICompatibleProvider:
    def test_is_available_false_when_no_url(self):
        from vector_inspector.core.llm_providers.openai_compatible_provider import (
            OpenAICompatibleProvider,
        )

        provider = OpenAICompatibleProvider(base_url="", model="")
        assert provider.is_available() is False

    def test_generate_messages_parses_chat_completion(self):
        import json

        from vector_inspector.core.llm_providers.openai_compatible_provider import (
            OpenAICompatibleProvider,
        )

        provider = OpenAICompatibleProvider(base_url="https://api.example.com/v1", model="gpt-test")
        payload = {"choices": [{"message": {"content": "  hello world  "}}]}
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps(payload).encode()

        with patch("urllib.request.urlopen", return_value=mock_resp), patch.object(provider, "_validate_model"):
            result = provider.generate_messages(
                [{"role": "user", "content": "hi"}],
                model="gpt-test",
            )

        assert result == "hello world"

    def test_provider_name(self):
        from vector_inspector.core.llm_providers.openai_compatible_provider import (
            OpenAICompatibleProvider,
        )

        assert OpenAICompatibleProvider("url", "model").get_provider_name() == "openai-compatible"


# ---------------------------------------------------------------------------
# LlamaCppProvider (availability only — no actual llama-cpp required)
# ---------------------------------------------------------------------------


class TestLlamaCppProvider:
    def test_is_available_false_when_llama_cpp_not_installed(self):
        import sys

        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        provider = LlamaCppProvider()
        # Simulate llama_cpp not installed
        with patch.dict(sys.modules, {"llama_cpp": None}):
            assert provider.is_available() is False

    def test_is_available_false_when_model_file_missing(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        provider = LlamaCppProvider(model_path="/nonexistent/model.gguf")
        # Even if llama_cpp is importable (mock it), no model file → not available
        mock_llama_cpp = MagicMock()
        with patch.dict(__import__("sys").modules, {"llama_cpp": mock_llama_cpp}):
            assert provider.is_available() is False

    def test_provider_name(self):
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

        assert LlamaCppProvider().get_provider_name() == "llama-cpp"
