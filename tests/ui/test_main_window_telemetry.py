from __future__ import annotations

from unittest.mock import MagicMock


def test_close_event_calls_flush_on_shutdown(monkeypatch):
    # Patch TelemetryService.get_instance to a dummy object
    fake = MagicMock()
    fake.flush_on_shutdown = MagicMock()
    monkeypatch.setattr("vector_inspector.services.telemetry_service.TelemetryService.get_instance", lambda: fake)

    # Import MainWindow after patch so behavior is stable
    from vector_inspector.ui.main_window import MainWindow

    mw = MainWindow()
    # Create a dummy event object with accept method
    ev = MagicMock()
    mw.closeEvent(ev)

    fake.flush_on_shutdown.assert_called_once()
