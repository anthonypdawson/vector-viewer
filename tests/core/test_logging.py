"""Tests for vector_inspector.core.logging helpers."""

import logging
from unittest.mock import patch


class TestLogTrackedError:
    def test_emits_error_log(self, caplog):
        """log_tracked_error forwards the message to the error logger."""
        from vector_inspector.core.logging import log_tracked_error

        with caplog.at_level(logging.ERROR, logger="vector_inspector"):
            log_tracked_error("something went wrong: %s", "detail", category="ingestion")

        assert "something went wrong: detail" in caplog.text

    def test_sends_telemetry_event(self):
        """log_tracked_error calls TelemetryService.send_event with the given category."""
        from vector_inspector.core.logging import log_tracked_error

        with patch(
            "vector_inspector.services.telemetry_service.TelemetryService.send_event"
        ) as mock_send:
            log_tracked_error("oops", category="connection")

        mock_send.assert_called_once()
        event_name, payload = mock_send.call_args[0]
        assert event_name == "tracked_error"
        assert payload["metadata"]["category"] == "connection"

    def test_telemetry_exception_does_not_propagate(self):
        """A broken TelemetryService must never raise from log_tracked_error."""
        from vector_inspector.core.logging import log_tracked_error

        with patch(
            "vector_inspector.services.telemetry_service.TelemetryService.send_event",
            side_effect=RuntimeError("telemetry down"),
        ):
            log_tracked_error("error")  # must not raise

    def test_category_defaults_to_general(self):
        """Omitting category sends 'general' in the telemetry payload."""
        from vector_inspector.core.logging import log_tracked_error

        with patch(
            "vector_inspector.services.telemetry_service.TelemetryService.send_event"
        ) as mock_send:
            log_tracked_error("bare error")

        _, payload = mock_send.call_args[0]
        assert payload["metadata"]["category"] == "general"
