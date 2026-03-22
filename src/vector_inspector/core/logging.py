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


def log_info(msg: str, *args: Any, **kwargs: Any) -> None:
    _logger.info(msg, *args, **kwargs)


def log_error(msg: str, *args: Any, **kwargs: Any) -> None:
    _logger.error(msg, *args, **kwargs)


def log_warning(msg: str, *args: Any, **kwargs: Any) -> None:
    _logger.warning(msg, *args, **kwargs)


def log_debug(msg: str, *args: Any, **kwargs: Any) -> None:
    _logger.debug(msg, *args, **kwargs)
