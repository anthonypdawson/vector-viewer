from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.core.llm_providers import ProviderError
from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider


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

    def test_list_models_fallback_on_error(self, caplog):
        p = OllamaProvider(model="llama3.2")
        with patch("urllib.request.urlopen", side_effect=OSError("unreachable")):
            with caplog.at_level(logging.INFO, logger="vector_inspector"):
                models = p.list_models()
        assert len(models) == 0
        assert any("unavailable" in r.getMessage().lower() for r in caplog.records)

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
            try:
                raise Exception()
            except Exception:
                pass
            from pytest import raises

            with raises(ProviderError) as exc_info:
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
            from pytest import raises

            with raises(ProviderError):
                list(p.stream_messages([{"role": "user", "content": "hi"}], model="llama3.2"))


class TestOllamaStreamMessagesExtra:
    def _make_mock_resp(self, lines: list[bytes]):
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = lambda s: iter(lines)
        return mock_resp

    def test_invalid_json_lines_are_silently_skipped(self):
        import json

        p = OllamaProvider(model="llama3.2")
        chunks = [b"not-json!!!\n", json.dumps({"message": {"content": "ok"}, "done": True}).encode()]
        with (
            patch.object(p, "_validate_model"),
            patch("urllib.request.urlopen", return_value=self._make_mock_resp(chunks)),
        ):
            events = list(p.stream_messages([{"role": "user", "content": "hi"}], model="llama3.2"))
        delta_events = [e for e in events if e.type == "delta"]
        done_events = [e for e in events if e.type == "done"]
        assert len(delta_events) == 1
        assert delta_events[0].content == "ok"
        assert len(done_events) == 1

    def test_request_id_propagated_to_delta_and_done(self):
        import json

        p = OllamaProvider(model="llama3.2")
        chunks = [json.dumps({"message": {"content": "hi"}, "done": True}).encode()]
        with (
            patch.object(p, "_validate_model"),
            patch("urllib.request.urlopen", return_value=self._make_mock_resp(chunks)),
        ):
            events = list(
                p.stream_messages([{"role": "user", "content": "x"}], model="llama3.2", request_id="test-req-99")
            )
        for ev in events:
            assert ev.meta.get("request_id") == "test-req-99"

    def test_done_flag_terminates_stream(self):
        import json

        p = OllamaProvider(model="llama3.2")
        chunks = [
            json.dumps({"message": {"content": "a"}, "done": True}).encode(),
            json.dumps({"message": {"content": "SHOULD_NOT_APPEAR"}, "done": False}).encode(),
        ]
        with (
            patch.object(p, "_validate_model"),
            patch("urllib.request.urlopen", return_value=self._make_mock_resp(chunks)),
        ):
            events = list(p.stream_messages([{"role": "user", "content": "x"}], model="llama3.2"))
        contents = [e.content for e in events if e.type == "delta"]
        assert "SHOULD_NOT_APPEAR" not in contents


class TestOllamaGenerateMessagesExtra:
    def test_invalid_json_response_raises_provider_error(self):
        p = OllamaProvider(model="llama3.2")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b"this is not json"
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(ProviderError):
                p.generate_messages([{"role": "user", "content": "hi"}], model="llama3.2")

    def test_missing_message_field_raises_provider_error(self):
        import json

        p = OllamaProvider(model="llama3.2")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({"done": True}).encode()
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(ProviderError):
                p.generate_messages([{"role": "user", "content": "hi"}], model="llama3.2")

    def test_underlying_error_is_chained(self):
        original = OSError("refused")
        p = OllamaProvider(model="llama3.2")
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=original):
            with pytest.raises(ProviderError) as exc_info:
                p.generate_messages([{"role": "user", "content": "hi"}], model="llama3.2")
        assert exc_info.value.underlying_error is original
