"""Tiny logging wrapper for consistent logs across the project.

Provides `log_info`, `log_error`, and `log_debug` helpers that delegate
to the standard `logging` module but keep call sites concise.
"""

import logging
import os
from typing import Any

_logger = logging.getLogger("vector_inspector")
if not _logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    # Set log level from LOG_LEVEL env var if present, else default to WARNING
    log_level_str = os.environ.get("LOG_LEVEL", "WARNING").upper()
    try:
        _logger.setLevel(getattr(logging, log_level_str))
    except Exception:
        _logger.setLevel(logging.WARNING)

    # Silence verbose third-party libraries so their output doesn't bury our errors.
    for _noisy in ("chromadb", "sentence_transformers", "transformers", "httpx", "httpcore"):
        logging.getLogger(_noisy).setLevel(logging.WARNING)


def log_info(msg: str, *args: Any, **kwargs: Any) -> None:
    _logger.info(msg, *args, **kwargs)


def log_error(msg: str, *args: Any, **kwargs: Any) -> None:
    _logger.error(msg, *args, **kwargs)


def log_warning(msg: str, *args: Any, **kwargs: Any) -> None:
    _logger.warning(msg, *args, **kwargs)


def log_debug(msg: str, *args: Any, **kwargs: Any) -> None:
    _logger.debug(msg, *args, **kwargs)


def log_tracked_error(msg: str, *args: Any, category: str = "general", **kwargs: Any) -> None:
    """Log an error and emit an opt-in telemetry event for important failures.

    Use this instead of ``log_error`` for caught exceptions worth tracking in
    telemetry (e.g. ingestion failures, connection errors).  For routine
    expected errors (e.g. "no collection selected") use ``log_error`` only.

    The telemetry payload contains only the *category* tag — never the raw
    message or arguments — to avoid accumulating PII or file paths.
    """
    _logger.error(msg, *args, **kwargs)
    try:
        # Lazy import avoids a circular dependency (telemetry_service imports logging).
        from vector_inspector.services.telemetry_service import TelemetryService

        TelemetryService.send_event(
            "tracked_error",
            {"metadata": {"category": category}},
        )
    except Exception:
        pass
