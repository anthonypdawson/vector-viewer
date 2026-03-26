"""Status reporting service with an in-memory activity log.

StatusReporter centralises all status bar messages in a single service so they
are both displayed (via Qt signal) AND recorded in a bounded in-memory log.
The log can be surfaced to the user in a future "Activity Log" feature.

Usage::

    # From any view that holds an app_state reference:
    self.app_state.status_reporter.report("Ready")
    self.app_state.status_reporter.report_action(
        "Search", result_count=28, result_label="result", elapsed_seconds=0.43
    )
    # Produces: "Search complete \u2013 28 results in 0.43s"

Connect the status bar once in MainWindow::

    self.app_state.status_reporter.status_updated.connect(
        self.statusBar().showMessage
    )
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, Signal


@dataclass
class StatusLogEntry:
    """A single immutable entry in the status log."""

    message: str
    level: str  # "info" | "warning" | "error"
    timestamp: float  # time.time() at the moment of recording
    elapsed_seconds: Optional[float] = None  # duration of the triggering action
    result_count: Optional[int] = None  # e.g. number of search results or rows loaded


class StatusReporter(QObject):
    """Emits status bar messages and maintains a bounded in-memory activity log.

    Attributes:
        status_updated: Emitted whenever a new status message is recorded.
            First argument is the message string; second is the display
            timeout in milliseconds (0 = permanent until next message).
        DEFAULT_TIMEOUT_MS: Milliseconds that a status message stays visible.
        MAX_LOG_SIZE: Maximum number of entries retained in the log.
    """

    status_updated = Signal(str, int)  # (message, timeout_ms)

    DEFAULT_TIMEOUT_MS: int = 5_000
    MAX_LOG_SIZE: int = 100

    def __init__(
        self,
        max_log_size: int = MAX_LOG_SIZE,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._max_log_size = max_log_size
        self._log: list[StatusLogEntry] = []
        #: Mutable default timeout used when callers omit ``timeout_ms``.
        #: Updated at runtime by MainWindow when the user changes the preference.
        self._default_timeout_ms: int = StatusReporter.DEFAULT_TIMEOUT_MS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def report(
        self,
        message: str,
        level: str = "info",
        timeout_ms: Optional[int] = None,
    ) -> None:
        """Record and emit a plain status message.

        Args:
            message: The text to display in the status bar.
            level: Severity — "info", "warning", or "error".
            timeout_ms: How long the message stays visible (ms). 0 = permanent.
                Defaults to ``self._default_timeout_ms`` (user-configurable).
        """
        if timeout_ms is None:
            timeout_ms = self._default_timeout_ms
        entry = StatusLogEntry(
            message=message,
            level=level,
            timestamp=time.time(),
        )
        self._append_entry(entry)
        self.status_updated.emit(message, timeout_ms)

    def report_action(
        self,
        action: str,
        result_count: Optional[int] = None,
        result_label: str = "result",
        elapsed_seconds: Optional[float] = None,
        timeout_ms: Optional[int] = None,
        level: str = "info",
    ) -> None:
        """Record and emit a completed-action message with optional metrics.

        Produces human-friendly messages such as:

        * ``"Search complete \u2013 28 results in 0.43s"``
        * ``"Data loaded \u2013 1,000 items in 1.20s"``
        * ``"Clustering complete \u2013 5 clusters in 2.10s"``
        * ``"Visualization complete \u2013 in 3.51s"``

        Args:
            action: Short verb phrase, e.g. ``"Search"``, ``"Data loaded"``.
            result_count: Optional count to include in the message.
            result_label: Singular noun that describes a result, e.g.
                ``"result"``, ``"item"``, ``"cluster"``.
            elapsed_seconds: Duration of the action in seconds.
            timeout_ms: How long the status message stays visible (ms).
                Defaults to ``self._default_timeout_ms`` (user-configurable).
            level: Severity — "info", "warning", or "error".
        """
        if timeout_ms is None:
            timeout_ms = self._default_timeout_ms
        # Build the right-hand side detail string
        detail_parts: list[str] = []

        if result_count is not None:
            plural = "" if result_count == 1 else "s"
            detail_parts.append(f"{result_count:,} {result_label}{plural}")

        if elapsed_seconds is not None:
            detail_parts.append(f"in {elapsed_seconds:.2f}s")

        base = f"{action} complete"
        message = f"{base} \u2013 {', '.join(detail_parts)}" if detail_parts else base

        entry = StatusLogEntry(
            message=message,
            level=level,
            timestamp=time.time(),
            elapsed_seconds=elapsed_seconds,
            result_count=result_count,
        )
        self._append_entry(entry)
        self.status_updated.emit(message, timeout_ms)

    def get_log(self) -> list[StatusLogEntry]:
        """Return a shallow copy of the current activity log (oldest first)."""
        return list(self._log)

    def clear_log(self) -> None:
        """Discard all entries from the in-memory log."""
        self._log.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append_entry(self, entry: StatusLogEntry) -> None:
        """Append *entry* and evict the oldest entry if the log is full."""
        self._log.append(entry)
        if len(self._log) > self._max_log_size:
            # Drop oldest entries in one slice to stay O(n) not O(n²)
            excess = len(self._log) - self._max_log_size
            self._log = self._log[excess:]
