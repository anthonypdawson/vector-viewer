"""LLM provider for OpenAI-compatible REST APIs.

Supports OpenAI, LM Studio, Groq, LocalAI, or any server that implements
the ``/v1/chat/completions`` endpoint.
"""

from __future__ import annotations

import datetime
import json
import urllib.error
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


class OpenAICompatibleProvider(LLMProvider):
    """Provider for APIs that implement the OpenAI chat-completions interface."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        context_length: int = 4096,
        temperature: float = 0.1,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._context_length = context_length
        self._temperature = temperature

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def is_available(self) -> bool:
        if not self._base_url or not self._model:
            return False
        try:
            req = urllib.request.Request(
                f"{self._base_url}/models",
                method="GET",
                headers=self._headers(),
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_model_name(self) -> str:
        return self._model

    def get_provider_name(self) -> str:
        return "openai-compatible"

    def generate_messages(
        self,
        messages: list[dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs: Any,
    ) -> str | Generator[StreamEvent, None, None]:
        """Generate using the /v1/chat/completions endpoint natively."""
        self._validate_model(model)
        if stream:
            return self.stream_messages(messages, model, **kwargs)
        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self._temperature),
                "max_tokens": kwargs.get("max_tokens", 512),
            }
        ).encode()
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            method="POST",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            log_error("OpenAI-compatible chat HTTP %s: %s", exc.code, body[:500])
            raise ProviderError(
                f"API returned HTTP {exc.code}: {body[:200]}",
                provider_name="openai-compatible",
                model_name=model,
                underlying_error=exc,
                retryable=exc.code in (429, 500, 502, 503),
                http_status=exc.code,
            ) from exc
        except Exception as exc:
            raise ProviderError(
                str(exc),
                provider_name="openai-compatible",
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
        """Stream /v1/chat/completions response using SSE."""
        self._validate_model(model)
        request_id = kwargs.get("request_id", "r-0")
        payload = json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self._temperature),
                "max_tokens": kwargs.get("max_tokens", 512),
                "stream": True,
            }
        ).encode()
        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            method="POST",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                index = 0
                for line in resp:
                    line = line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line.removeprefix("data:").strip()
                    if data_str == "[DONE]":
                        yield StreamEvent(
                            type="done",
                            content="",
                            meta={"request_id": request_id, "finish_reason": "stop"},
                        )
                        return
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if delta:
                        yield StreamEvent(
                            type="delta",
                            content=delta,
                            meta={"request_id": request_id, "index": index},
                        )
                        index += 1
        except Exception as exc:
            log_error("OpenAI-compatible stream failed: %s", exc)
            raise ProviderError(
                str(exc),
                provider_name="openai-compatible",
                model_name=model,
                underlying_error=exc,
                retryable=True,
            ) from exc

    def list_models(self) -> list[ModelMetadata]:
        """Return models from the /models endpoint."""
        if not self._base_url:
            return [ModelMetadata(model_name=self._model, context_window=self._context_length)]
        try:
            req = urllib.request.Request(
                f"{self._base_url}/models",
                method="GET",
                headers=self._headers(),
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return [
                ModelMetadata(model_name=m["id"], context_window=self._context_length) for m in data.get("data", [])
            ]
        except Exception:
            return [ModelMetadata(model_name=self._model, context_window=self._context_length)]

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            schema_version=CAPABILITIES_SCHEMA_VERSION,
            provider_name="openai-compatible",
            supports_streaming=True,
            supports_tools=False,
            concurrency="multi",
            max_context_tokens=self._context_length,
            roles_supported=["system", "user", "assistant"],
            model_list=self.list_models(),
        )

    def get_health(self) -> HealthResult:
        now = datetime.datetime.now(datetime.UTC).isoformat()
        if not self._base_url or not self._model:
            return HealthResult(
                ok=False,
                provider="openai-compatible",
                models=[],
                version=None,
                last_checked=now,
                retryable=False,
                remediation_hint="Set llm.openai_url and llm.openai_model in Settings.",
            )
        try:
            req = urllib.request.Request(
                f"{self._base_url}/models",
                method="GET",
                headers=self._headers(),
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            models = [m["id"] for m in data.get("data", [])]
            return HealthResult(
                ok=True,
                provider="openai-compatible",
                models=models,
                version=None,
                last_checked=now,
                retryable=False,
                remediation_hint=None,
            )
        except urllib.error.HTTPError as exc:
            hint = None
            if exc.code == 401:
                hint = "Invalid API key. Set OPENAI_API_KEY or llm.openai_api_key in Settings."
            return HealthResult(
                ok=False,
                provider="openai-compatible",
                models=[],
                version=None,
                last_checked=now,
                retryable=exc.code in (429, 500, 502, 503),
                remediation_hint=hint,
            )
        except Exception:
            return HealthResult(
                ok=False,
                provider="openai-compatible",
                models=[],
                version=None,
                last_checked=now,
                retryable=True,
                remediation_hint=f"Cannot reach {self._base_url}. Check llm.openai_url in Settings.",
            )

    def _validate_model(self, model: str) -> None:
        """Raise ProviderError if model is not in the remote model list."""
        available = {m.model_name for m in self.list_models()}
        if available and model not in available:
            raise ProviderError(
                f"Model {model!r} is not available at {self._base_url}. Available: {sorted(available)}",
                provider_name="openai-compatible",
                model_name=model,
                retryable=False,
            )
