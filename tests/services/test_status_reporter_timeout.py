"""Tests for StatusReporter mutable default timeout and settings integration.

These tests were added alongside the status-bar timeout preference feature.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from vector_inspector.services.status_reporter import StatusReporter


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _collect(reporter: StatusReporter) -> list[tuple[str, int]]:
    received: list[tuple[str, int]] = []
    reporter.status_updated.connect(lambda msg, ms: received.append((msg, ms)))
    return received


# ---------------------------------------------------------------------------
# Mutable _default_timeout_ms
# ---------------------------------------------------------------------------


class TestMutableDefaultTimeout:
    def test_default_is_5000(self, qapp):
        r = StatusReporter()
        assert r._default_timeout_ms == StatusReporter.DEFAULT_TIMEOUT_MS == 5000

    def test_report_uses_default_when_none_passed(self, qapp):
        r = StatusReporter()
        r._default_timeout_ms = 3000
        received = _collect(r)
        r.report("hello")
        assert received[0][1] == 3000

    def test_report_explicit_timeout_overrides_default(self, qapp):
        r = StatusReporter()
        r._default_timeout_ms = 3000
        received = _collect(r)
        r.report("hello", timeout_ms=0)
        assert received[0][1] == 0

    def test_report_action_uses_default_when_none_passed(self, qapp):
        r = StatusReporter()
        r._default_timeout_ms = 2500
        received = _collect(r)
        r.report_action("Search", result_count=5)
        assert received[0][1] == 2500

    def test_report_action_explicit_timeout_overrides_default(self, qapp):
        r = StatusReporter()
        r._default_timeout_ms = 2500
        received = _collect(r)
        r.report_action("Search", result_count=5, timeout_ms=10000)
        assert received[0][1] == 10000

    def test_changing_default_mid_session(self, qapp):
        """Changing _default_timeout_ms at runtime affects subsequent messages."""
        r = StatusReporter()
        received = _collect(r)

        r._default_timeout_ms = 1000
        r.report("first")
        assert received[0][1] == 1000

        r._default_timeout_ms = 9000
        r.report("second")
        assert received[1][1] == 9000

    def test_permanent_zero_default(self, qapp):
        r = StatusReporter()
        r._default_timeout_ms = 0
        received = _collect(r)
        r.report("permanent")
        assert received[0][1] == 0

    def test_instances_have_independent_defaults(self, qapp):
        r1 = StatusReporter()
        r2 = StatusReporter()
        r1._default_timeout_ms = 1111
        r2._default_timeout_ms = 2222
        recv1 = _collect(r1)
        recv2 = _collect(r2)
        r1.report("a")
        r2.report("b")
        assert recv1[0][1] == 1111
        assert recv2[0][1] == 2222


# ---------------------------------------------------------------------------
# SettingsService status timeout helpers
# ---------------------------------------------------------------------------


class TestSettingsServiceStatusTimeout:
    def test_default_returns_5000(self, tmp_path, monkeypatch):
        from pathlib import Path

        from vector_inspector.services.settings_service import SettingsService

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        SettingsService._instance = None
        SettingsService._initialized = False
        svc = SettingsService()
        assert svc.get_status_timeout_ms() == 5000

    def test_set_and_get_roundtrip(self, tmp_path, monkeypatch):
        from pathlib import Path

        from vector_inspector.services.settings_service import SettingsService

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        SettingsService._instance = None
        SettingsService._initialized = False
        svc = SettingsService()
        svc.set_status_timeout_ms(8000)
        assert svc.get_status_timeout_ms() == 8000

    def test_permanent_zero(self, tmp_path, monkeypatch):
        from pathlib import Path

        from vector_inspector.services.settings_service import SettingsService

        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        SettingsService._instance = None
        SettingsService._initialized = False
        svc = SettingsService()
        svc.set_status_timeout_ms(0)
        assert svc.get_status_timeout_ms() == 0
