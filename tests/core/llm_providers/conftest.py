from __future__ import annotations

import sys
from pathlib import Path

# Ensure tests/utils is importable for FakeLLMProvider
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tests"))

from tests.utils.fake_llm_provider import FakeLLMProvider  # noqa: F401


def _make_settings(**overrides):
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


def _collect_stream(gen):
    return list(gen)
