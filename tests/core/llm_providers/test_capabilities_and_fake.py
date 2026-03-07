from __future__ import annotations

import sys
from pathlib import Path

# Ensure tests/utils is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests"))

from unittest.mock import patch

from tests.core.llm_providers.conftest import _collect_stream
from tests.utils.fake_llm_provider import FakeLLMProvider
from vector_inspector.core.llm_providers import (
    CAPABILITIES_SCHEMA_VERSION,
    ProviderCapabilities,
)
from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider
from vector_inspector.core.llm_providers.openai_compatible_provider import OpenAICompatibleProvider


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


class TestStreamIndexMonotonicity:
    def test_fake_stream_index_is_strictly_increasing(self):
        p = FakeLLMProvider(seed=1, fragment_size=2)
        events = _collect_stream(p.stream_messages([{"role": "user", "content": "Hello World"}], model="fake-model"))
        deltas = [e for e in events if e.type == "delta"]
        indices = [e.meta["index"] for e in deltas]
        assert indices == list(range(len(indices)))

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
        for e in events:
            assert e.meta.get("request_id") == "r-7-0"

    def test_request_id_sequential_without_seed(self):
        p = FakeLLMProvider(seed=0, fragment_size=50)
        events = _collect_stream(p.stream_messages([{"role": "user", "content": "X"}], model="fake-model"))
        request_ids = {e.meta.get("request_id") for e in events}
        assert "r-0" in request_ids

    def test_generate_messages_echo_mode(self):
        p = FakeLLMProvider(seed=1, mode="echo")
        result = p.generate_messages([{"role": "user", "content": "Hello"}], model="fake-model")
        assert result == "Hello"

    def test_generate_messages_multi_turn_concatenates(self):
        p = FakeLLMProvider(seed=1, mode="echo")
        result = p.generate_messages(
            [{"role": "system", "content": "sys"}, {"role": "user", "content": " user"}],
            model="fake-model",
        )
        assert result == "sys user"


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
