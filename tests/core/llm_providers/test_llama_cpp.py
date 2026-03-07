from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.core.llm_providers.llama_cpp_provider import (
    DEFAULT_MODEL_FILENAME,
    DEFAULT_MODEL_HF_URL,
    LlamaCppProvider,
    download_default_model,
)


class TestLlamaCppListModels:
    def test_list_models_returns_single_configured_model(self, tmp_path):
        # Create a dummy GGUF file so _resolve_model_path() finds it
        model_file = tmp_path / "my-model.gguf"
        model_file.write_bytes(b"")
        from vector_inspector.core.llm_providers.llama_cpp_provider import LlamaCppProvider

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
        existing = tmp_path / DEFAULT_MODEL_FILENAME
        existing.write_bytes(b"cached")
        with patch("vector_inspector.core.llm_providers.llama_cpp_provider.get_llm_cache_dir", return_value=tmp_path):
            result = download_default_model()
        assert result == existing

    def test_download_default_model_calls_urlretrieve_and_progress(self, tmp_path):
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


class TestLlamaCppGenerateMessagesDeep:
    def _make_provider_with_mock_llm(self, tmp_path, response_content: str = "  response text  "):
        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"")
        p = LlamaCppProvider(model_path=str(model_file))
        mock_llm = MagicMock()
        mock_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": response_content}}]}
        p._llm = mock_llm
        return p, mock_llm

    def test_happy_path_returns_stripped_content(self, tmp_path):
        p, mock_llm = self._make_provider_with_mock_llm(tmp_path, "  hello world  ")
        result = p.generate_messages([{"role": "user", "content": "hi"}], model="model.gguf")
        assert result == "hello world"

    def test_messages_passed_to_llm_unchanged(self, tmp_path):
        p, mock_llm = self._make_provider_with_mock_llm(tmp_path)
        messages = [{"role": "system", "content": "be helpful"}, {"role": "user", "content": "hi"}]
        p.generate_messages(messages, model="model.gguf")
        call_kwargs = mock_llm.create_chat_completion.call_args
        assert call_kwargs.kwargs["messages"] == messages

    def test_temperature_kwarg_overrides_default(self, tmp_path):
        p, mock_llm = self._make_provider_with_mock_llm(tmp_path)
        p.generate_messages([{"role": "user", "content": "x"}], model="model.gguf", temperature=0.99)
        call_kwargs = mock_llm.create_chat_completion.call_args
        assert call_kwargs.kwargs["temperature"] == pytest.approx(0.99)

    def test_create_chat_completion_failure_raises_provider_error(self, tmp_path):
        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"")
        p = LlamaCppProvider(model_path=str(model_file))
        mock_llm = MagicMock()
        mock_llm.create_chat_completion.side_effect = RuntimeError("out of memory")
        p._llm = mock_llm

        from vector_inspector.core.llm_providers.errors import ProviderError as PE

        with pytest.raises(PE) as exc_info:
            p.generate_messages([{"role": "user", "content": "hi"}], model="model.gguf")
        assert exc_info.value.provider_name == "llama-cpp"


class TestLlamaCppStreamMessages:
    def test_stream_messages_yields_delta_then_done(self, tmp_path):
        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"")
        p = LlamaCppProvider(model_path=str(model_file))
        mock_llm = MagicMock()
        mock_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": "streamed reply"}}]}
        p._llm = mock_llm

        events = list(p.stream_messages([{"role": "user", "content": "hi"}], model="model.gguf"))
        delta_events = [e for e in events if e.type == "delta"]
        done_events = [e for e in events if e.type == "done"]
        assert len(delta_events) == 1
        assert "streamed reply" in delta_events[0].content
        assert len(done_events) == 1

    def test_stream_messages_propagates_request_id(self, tmp_path):
        model_file = tmp_path / "model.gguf"
        model_file.write_bytes(b"")
        p = LlamaCppProvider(model_path=str(model_file))
        mock_llm = MagicMock()
        mock_llm.create_chat_completion.return_value = {"choices": [{"message": {"content": "hi"}}]}
        p._llm = mock_llm

        events = list(
            p.stream_messages([{"role": "user", "content": "x"}], model="model.gguf", request_id="req-llama-1")
        )
        for ev in events:
            assert ev.meta.get("request_id") == "req-llama-1"

    def test_stream_messages_caps_supports_streaming_false(self):
        p = LlamaCppProvider()
        caps = p.get_capabilities()
        assert caps.supports_streaming is False
