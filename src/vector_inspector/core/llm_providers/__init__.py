"""LLM provider layer for Vector Inspector.

Provides a pluggable interface for text generation backed by:
- llama-cpp-python (in-process, zero-setup default)
- Ollama (local server, used opportunistically when running)
- OpenAI-compatible REST API (cloud or local proxy; provider id ``openai-compatible``)
- Fake provider (tests and CI: VI_LLM_PROVIDER=fake)

Auto-detection order (when provider is set to ``auto``):
  user-configured → env vars → Ollama (reachability probe) → llama-cpp.
  openai-compatible is NOT auto-detected; it must be configured explicitly.

Preferred entrypoint: ``LLMRuntimeManager`` (wired via ``AppState.llm_provider``).
``LLMProviderInstance`` is a simpler wrapper without env-var/health/request-id support.
"""

from .base_provider import LLMModelInfo, LLMProvider
from .errors import ProviderCapabilityError, ProviderError
from .provider_factory import (
    AUTO,
    FAKE,
    LLAMA_CPP,
    OLLAMA,
    OPENAI_COMPATIBLE,
    PROVIDER_TYPES,
    LLMProviderFactory,
    LLMProviderInstance,
)
from .runtime_manager import LLMRuntimeManager
from .types import (
    CAPABILITIES_SCHEMA_VERSION,
    HealthResult,
    ModelMetadata,
    ProviderCapabilities,
    RateLimit,
    StreamEvent,
    TokenizerInfo,
)

__all__ = [
    # Constants
    "AUTO",
    "CAPABILITIES_SCHEMA_VERSION",
    "FAKE",
    "LLAMA_CPP",
    "OLLAMA",
    "OPENAI_COMPATIBLE",
    "PROVIDER_TYPES",
    # Types
    "HealthResult",
    # Base
    "LLMModelInfo",
    "LLMProvider",
    # Factory / instance
    "LLMProviderFactory",
    "LLMProviderInstance",
    # Runtime manager
    "LLMRuntimeManager",
    "ModelMetadata",
    "ProviderCapabilities",
    "ProviderCapabilityError",
    # Errors
    "ProviderError",
    "RateLimit",
    "StreamEvent",
    "TokenizerInfo",
]
