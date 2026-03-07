from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vector_inspector.core.llm_providers import ProviderError
from vector_inspector.core.llm_providers.openai_compatible_provider import OpenAICompatibleProvider


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
            from pytest import raises

            with raises(ProviderError) as exc_info:
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
            from pytest import raises

            with raises(ProviderError) as exc_info:
                p.generate_messages([{"role": "user", "content": "hi"}], model="m")
        assert exc_info.value.retryable is False

    def test_generate_messages_raises_provider_error_on_generic_exception(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=OSError("refused")):
            from pytest import raises

            with raises(ProviderError) as exc_info:
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
            from pytest import raises

            with raises(ProviderError):
                list(p.stream_messages([{"role": "user", "content": "hi"}], model="m"))


class TestOpenAIStreamMessagesExtra:
    def _make_mock_resp(self, lines: list[bytes]) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.__iter__ = lambda s: iter(lines)
        return mock_resp

    def test_invalid_json_in_data_line_is_skipped(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        sse_lines = [b"data: {not-valid-json}\n", b"data: [DONE]\n"]
        with (
            patch.object(p, "_validate_model"),
            patch("urllib.request.urlopen", return_value=self._make_mock_resp(sse_lines)),
        ):
            events = list(p.stream_messages([{"role": "user", "content": "x"}], model="m"))
        assert sum(1 for e in events if e.type == "done") == 1

    def test_request_id_propagated_to_delta_and_done(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        sse_lines = [b'data: {"choices": [{"delta": {"content": "hi"}}]}\n', b"data: [DONE]\n"]
        with (
            patch.object(p, "_validate_model"),
            patch("urllib.request.urlopen", return_value=self._make_mock_resp(sse_lines)),
        ):
            events = list(p.stream_messages([{"role": "user", "content": "x"}], model="m", request_id="req-42"))
        for ev in events:
            assert ev.meta.get("request_id") == "req-42"

    def test_delta_without_content_field_produces_no_event(self):
        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        sse_lines = [b'data: {"choices": [{"delta": {}}]}\n', b"data: [DONE]\n"]
        with (
            patch.object(p, "_validate_model"),
            patch("urllib.request.urlopen", return_value=self._make_mock_resp(sse_lines)),
        ):
            events = list(p.stream_messages([{"role": "user", "content": "x"}], model="m"))
        assert [e for e in events if e.type == "delta"] == []


class TestOpenAIGenerateMessagesExtra:
    def test_http_500_is_retryable(self):
        import urllib.error

        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        err = urllib.error.HTTPError(url="", code=500, msg="Server Error", hdrs=None, fp=None)
        err.read = lambda: b"internal error"
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(ProviderError) as exc_info:
                p.generate_messages([{"role": "user", "content": "hi"}], model="m")
        assert exc_info.value.retryable is True

    def test_http_502_is_retryable(self):
        import urllib.error

        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        err = urllib.error.HTTPError(url="", code=502, msg="Bad Gateway", hdrs=None, fp=None)
        err.read = lambda: b"bad gateway"
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(ProviderError):
                p.generate_messages([{"role": "user", "content": "hi"}], model="m")

    def test_http_401_is_not_retryable(self):
        import urllib.error

        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m", api_key="bad")
        err = urllib.error.HTTPError(url="", code=401, msg="Unauthorized", hdrs=None, fp=None)
        err.read = lambda: b"unauthorized"
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(ProviderError) as exc_info:
                p.generate_messages([{"role": "user", "content": "hi"}], model="m")
        assert exc_info.value.retryable is False

    def test_missing_choices_field_raises_provider_error(self):
        import json

        p = OpenAICompatibleProvider(base_url="http://localhost:1234", model="m")
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = json.dumps({"id": "chatcmpl-123"}).encode()
        with patch.object(p, "_validate_model"), patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(ProviderError):
                p.generate_messages([{"role": "user", "content": "hi"}], model="m")
