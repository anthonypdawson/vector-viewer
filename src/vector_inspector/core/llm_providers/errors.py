"""Normalized error hierarchy for LLM providers.

All provider-specific exceptions must be caught and re-raised as
``ProviderError`` (or a subclass) so callers can handle errors uniformly
without knowing provider implementation details.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Base exception for all LLM provider errors.

    Attributes:
        provider_name:    Identifies the provider that raised the error.
        model_name:       Model that was being used, if applicable.
        underlying_error: The original exception, if any.
        retryable:        True if the failure is likely transient and safe to
                          retry (e.g. network timeout, rate limit). False for
                          hard errors (missing deps, invalid credentials, bad
                          model name).
        code:             Provider-specific error code string, if available.
        http_status:      HTTP status code for REST-backed providers, if applicable.
        remediation_hint: Human-readable fix suggestion. Same format as
                          ``HealthResult.remediation_hint``.
    """

    def __init__(
        self,
        message: str,
        *,
        provider_name: str,
        model_name: str | None = None,
        underlying_error: Exception | None = None,
        retryable: bool = False,
        code: str | None = None,
        http_status: int | None = None,
        remediation_hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_name = provider_name
        self.model_name = model_name
        self.underlying_error = underlying_error
        self.retryable = retryable
        self.code = code
        self.http_status = http_status
        self.remediation_hint = remediation_hint

    def __repr__(self) -> str:
        return (
            f"ProviderError(provider={self.provider_name!r}, "
            f"model={self.model_name!r}, retryable={self.retryable}, "
            f"code={self.code!r}, http_status={self.http_status!r})"
        )


class ProviderCapabilityError(ProviderError):
    """Raised when a provider does not support a requested capability.

    Example: calling ``generate_messages()`` with a ``"system"`` role on a
    provider that does not include ``"system"`` in its ``roles_supported`` list.
    """
