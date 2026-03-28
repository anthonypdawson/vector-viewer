"""Unit tests for StatusReporter — the centralised status-bar message service."""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QApplication

from vector_inspector.services.status_reporter import StatusLogEntry, StatusReporter

# ---------------------------------------------------------------------------
# Shared QApplication fixture (required for QObject / Signal machinery)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Helper to collect signal payloads
# ---------------------------------------------------------------------------


def _collect_signals(reporter: StatusReporter) -> list[tuple[str, int]]:
    """Return a list collecting every (message, timeout_ms) emitted during the test."""
    received: list[tuple[str, int]] = []
    reporter.status_updated.connect(lambda msg, ms: received.append((msg, ms)))
    return received


# ===========================================================================
# StatusLogEntry dataclass
# ===========================================================================


class TestStatusLogEntry:
    def test_fields_set_correctly(self):
        entry = StatusLogEntry(message="hello", level="info", timestamp=1.0)
        assert entry.message == "hello"
        assert entry.level == "info"
        assert entry.timestamp == 1.0
        assert entry.elapsed_seconds is None
        assert entry.result_count is None

    def test_optional_fields(self):
        entry = StatusLogEntry(
            message="done",
            level="warning",
            timestamp=2.0,
            elapsed_seconds=0.5,
            result_count=42,
        )
        assert entry.elapsed_seconds == 0.5
        assert entry.result_count == 42


# ===========================================================================
# StatusReporter.report()
# ===========================================================================


class TestStatusReporterReport:
    def test_emits_signal(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report("Hello world")

        assert len(received) == 1
        assert received[0][0] == "Hello world"
        assert received[0][1] == StatusReporter.DEFAULT_TIMEOUT_MS

    def test_custom_timeout_forwarded(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report("Msg", timeout_ms=1234)

        assert received[0][1] == 1234

    def test_zero_timeout_allowed(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report("Permanent", timeout_ms=0)

        assert received[0][1] == 0

    def test_entry_appended_to_log(self, qapp):
        reporter = StatusReporter()
        reporter.report("First")
        reporter.report("Second")

        log = reporter.get_log()
        assert len(log) == 2
        assert log[0].message == "First"
        assert log[1].message == "Second"

    def test_level_stored(self, qapp):
        reporter = StatusReporter()
        reporter.report("Oops", level="error")

        assert reporter.get_log()[0].level == "error"

    def test_timestamp_is_recent(self, qapp):
        reporter = StatusReporter()
        before = time.time()
        reporter.report("Now")
        after = time.time()

        ts = reporter.get_log()[0].timestamp
        assert before <= ts <= after

    def test_elapsed_and_count_are_none_for_plain_report(self, qapp):
        reporter = StatusReporter()
        reporter.report("Plain")
        entry = reporter.get_log()[0]
        assert entry.elapsed_seconds is None
        assert entry.result_count is None


# ===========================================================================
# StatusReporter.report_action()
# ===========================================================================


class TestStatusReporterReportAction:
    def test_basic_action_no_metrics(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Search")

        assert received[0][0] == "Search complete"

    def test_with_result_count_singular(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Search", result_count=1, result_label="result")

        assert "1 result" in received[0][0]
        # Must NOT say "results" (plural guard)
        assert "1 results" not in received[0][0]

    def test_with_result_count_plural(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Search", result_count=28, result_label="result")

        assert "28 results" in received[0][0]

    def test_with_elapsed_seconds(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Search", elapsed_seconds=0.43)

        assert "in 0.43s" in received[0][0]

    def test_full_message_format(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Search", result_count=28, result_label="result", elapsed_seconds=0.43)

        msg = received[0][0]
        assert msg.startswith("Search complete")
        assert "28 results" in msg
        assert "in 0.43s" in msg
        # Check the em-dash separator
        assert "\u2013" in msg

    def test_custom_result_label(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Data loaded", result_count=1000, result_label="item")

        assert "1,000 items" in received[0][0]

    def test_cluster_label(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Clustering", result_count=5, result_label="cluster")

        assert "5 clusters" in received[0][0]

    def test_entry_stores_metrics(self, qapp):
        reporter = StatusReporter()

        reporter.report_action("Search", result_count=10, elapsed_seconds=1.5)

        entry = reporter.get_log()[0]
        assert entry.result_count == 10
        assert entry.elapsed_seconds == 1.5

    def test_thousands_separator_in_count(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Data loaded", result_count=1_234_567, result_label="item")

        assert "1,234,567" in received[0][0]

    def test_elapsed_two_decimal_places(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Search", elapsed_seconds=1.0)

        assert "in 1.00s" in received[0][0]

    def test_level_stored_in_entry(self, qapp):
        reporter = StatusReporter()
        reporter.report_action("Search", level="warning")
        assert reporter.get_log()[0].level == "warning"

    def test_subject_included_in_message(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action(
            "Connection",
            subject="MyDB",
            result_count=10,
            result_label="collection",
            elapsed_seconds=0.15,
        )

        msg = received[0][0]
        assert msg.startswith("Connection complete")
        assert "MyDB" in msg
        assert "MyDB:" in msg
        assert "10 collections" in msg
        assert "in 0.15s" in msg

    def test_subject_without_detail_parts(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Connection", subject="MyDB")

        msg = received[0][0]
        assert msg == "Connection complete \u2013 MyDB"

    def test_no_subject_preserves_original_format(self, qapp):
        reporter = StatusReporter()
        received = _collect_signals(reporter)

        reporter.report_action("Search", result_count=5, result_label="result", elapsed_seconds=1.0)

        msg = received[0][0]
        # No colon-separated subject should appear
        assert ":" not in msg
        assert "5 results" in msg
        assert "in 1.00s" in msg


# ===========================================================================
# Log management
# ===========================================================================


class TestStatusReporterLog:
    def test_get_log_returns_copy(self, qapp):
        reporter = StatusReporter()
        reporter.report("A")

        log1 = reporter.get_log()
        log1.append(StatusLogEntry("alien", "info", 0.0))

        log2 = reporter.get_log()
        # The internal log must not be affected by mutation of the copy
        assert len(log2) == 1

    def test_clear_log(self, qapp):
        reporter = StatusReporter()
        reporter.report("A")
        reporter.report("B")

        reporter.clear_log()

        assert reporter.get_log() == []

    def test_log_trimmed_when_full(self, qapp):
        max_size = 5
        reporter = StatusReporter(max_log_size=max_size)

        for i in range(max_size + 3):
            reporter.report(f"msg-{i}")

        log = reporter.get_log()
        assert len(log) == max_size
        # Oldest entries evicted, newest kept
        assert log[-1].message == f"msg-{max_size + 2}"

    def test_log_oldest_entries_evicted(self, qapp):
        reporter = StatusReporter(max_log_size=3)
        reporter.report("old-1")
        reporter.report("old-2")
        reporter.report("old-3")
        reporter.report("new-4")  # Should evict "old-1"

        messages = [e.message for e in reporter.get_log()]
        assert "old-1" not in messages
        assert "new-4" in messages

    def test_default_max_log_size(self, qapp):
        assert StatusReporter.MAX_LOG_SIZE == 100

    def test_empty_log_on_init(self, qapp):
        reporter = StatusReporter()
        assert reporter.get_log() == []

    def test_log_ordered_oldest_first(self, qapp):
        reporter = StatusReporter()
        reporter.report("first")
        reporter.report("second")
        reporter.report("third")

        messages = [e.message for e in reporter.get_log()]
        assert messages == ["first", "second", "third"]


# ===========================================================================
# Signal isolation — multiple reporters don't share state
# ===========================================================================


class TestStatusReporterIsolation:
    def test_separate_reporters_separate_logs(self, qapp):
        r1 = StatusReporter()
        r2 = StatusReporter()

        r1.report("only in r1")

        assert len(r1.get_log()) == 1
        assert len(r2.get_log()) == 0

    def test_multiple_signals_emitted_independently(self, qapp):
        r1 = StatusReporter()
        r2 = StatusReporter()
        recv1 = _collect_signals(r1)
        recv2 = _collect_signals(r2)

        r1.report("r1 msg")
        r2.report("r2 msg")

        assert recv1[0][0] == "r1 msg"
        assert recv2[0][0] == "r2 msg"
