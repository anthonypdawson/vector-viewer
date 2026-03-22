from tests.core.llm_providers.conftest import _make_settings
from vector_inspector.core.llm_providers import OLLAMA, OPENAI_COMPATIBLE
from vector_inspector.core.llm_providers.runtime_manager import LLMRuntimeManager


def test_runtime_manager_prefers_openai_model_when_openai_provider_selected():
    s = _make_settings(
        **{"llm.provider": OPENAI_COMPATIBLE, "llm.openai_model": "oai-model", "llm.ollama_model": "ollama-model"}
    )
    mgr = LLMRuntimeManager(s)
    debug = mgr.get_selection_debug()
    assert debug["selected_provider"] == OPENAI_COMPATIBLE
    assert debug["selected_model"] == "oai-model"


def test_runtime_manager_prefers_ollama_model_when_ollama_provider_selected():
    s = _make_settings(**{"llm.provider": OLLAMA, "llm.ollama_model": "ollama-model", "llm.openai_model": "oai-model"})
    mgr = LLMRuntimeManager(s)
    debug = mgr.get_selection_debug()
    assert debug["selected_provider"] == OLLAMA
    assert debug["selected_model"] == "ollama-model"
