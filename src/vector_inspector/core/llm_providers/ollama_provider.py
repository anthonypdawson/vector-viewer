"""LLM provider backed by a locally running Ollama server."""

from __future__ import annotations

import datetime
import json
import urllib.request
from collections.abc import Generator
from typing import Any

from vector_inspector.core.logging import log_error

from .base_provider import LLMProvider
from .errors import ProviderError
from .types import (
    CAPABILITIES_SCHEMA_VERSION,
    HealthResult,
    ModelMetadata,
    ProviderCapabilities,
    StreamEvent,
)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2"

# Short timeout for the availability probe so auto-detection doesn't hang.
_AVAILABILITY_TIMEOUT = 2


class OllamaProvider(LLMProvider):
    """LLM provider that calls a locally running Ollama server via its REST API.

    Ollama is detected and used opportunistically during auto-detection — if
    the server is already running the user gets it for free with no config.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        model: str = DEFAULT_OLLAMA_MODEL,
        context_length: int = 4096,
        temperature: float = 0.1,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._context_length = context_length
        self._temperature = temperature

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags",
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=_AVAILABILITY_TIMEOUT) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_model_name(self) -> str:
        return self._model

    def get_provider_name(self) -> str:
        return "ollama"

    def generate_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | Generator[StreamEvent, None, None]:
        """Generate using Ollama's native /api/chat endpoint (supports system messages)."""
        self._validate_model(model)
        if stream:
            return self.stream_messages(messages, model, **kwargs)
        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self._temperature),
                    "num_ctx": self._context_length,
                },
            }
        ).encode()
        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                return data["message"]["content"].strip()
        except Exception as exc:
            log_error("Ollama chat failed: %s", exc)
            raise ProviderError(
                str(exc),
                provider_name="ollama",
                model_name=model,
                underlying_error=exc,
                retryable=True,
            ) from exc

    def stream_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        **kwargs: Any,
    ) -> Generator[StreamEvent, None, None]:
        """Stream Ollama /api/chat response as StreamEvents."""
        self._validate_model(model)
        request_id = kwargs.get("request_id", "r-0")
        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": kwargs.get("temperature", self._temperature),
                    "num_ctx": self._context_length,
                },
            }
        ).encode()
        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                index = 0
                for line in resp:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("message", {}).get("content", "")
                    if delta:
                        yield StreamEvent(
                            type="delta",
                            content=delta,
                            meta={"request_id": request_id, "index": index},
                        )
                        index += 1
                    if chunk.get("done"):
                        yield StreamEvent(
                            type="done",
                            content="",
                            meta={"request_id": request_id, "finish_reason": "stop"},
                        )
                        return
        except Exception as exc:
            log_error("Ollama stream failed: %s", exc)
            raise ProviderError(
                str(exc),
                provider_name="ollama",
                model_name=model,
                underlying_error=exc,
                retryable=True,
            ) from exc

    def list_models(self) -> list[ModelMetadata]:
        """Return models available on the Ollama server."""
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags",
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=_AVAILABILITY_TIMEOUT) as resp:
                data = json.loads(resp.read())
            return [
                ModelMetadata(model_name=m["name"], context_window=self._context_length) for m in data.get("models", [])
            ]
        except Exception as exc:
            # If we can't reach the server or parse the tag list, treat this as
            # "model list unavailable" rather than pretending only the default
            # model exists. This allows subsequent requests to surface a
            # retryable connectivity error instead of a non-retryable
            # "model not available" error for non-default models.
            log_error("Ollama list_models failed: %s", exc)
            return []

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            schema_version=CAPABILITIES_SCHEMA_VERSION,
            provider_name="ollama",
            supports_streaming=True,
            supports_tools=False,
            concurrency="multi",
            max_context_tokens=self._context_length,
            roles_supported=["system", "user", "assistant"],
            model_list=self.list_models(),
        )

    def get_health(self) -> HealthResult:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        try:
            req = urllib.request.Request(
                f"{self._base_url}/api/tags",
                method="GET",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=_AVAILABILITY_TIMEOUT) as resp:
                data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            version = data.get("version")
            return HealthResult(
                ok=True,
                provider="ollama",
                models=models,
                version=version,
                last_checked=now,
                retryable=False,
                remediation_hint=None,
            )
        except Exception:
            return HealthResult(
                ok=False,
                provider="ollama",
                models=[],
                version=None,
                last_checked=now,
                retryable=True,
                remediation_hint=(
                    f"Ollama server not reachable at {self._base_url}. "
                    "Start Ollama with: ollama serve (see docs/llm_providers/quickstart-installing.md)"
                )[:200],
            )

    def _validate_model(self, model: str) -> None:
        """Raise ProviderError if model is not available on this server."""
        available = {m.model_name for m in self.list_models()}
        if available and model not in available:
            raise ProviderError(
                f"Model {model!r} is not available on Ollama at {self._base_url}. Available: {sorted(available)}",
                provider_name="ollama",
                model_name=model,
                retryable=False,
            )
