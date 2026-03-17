from __future__ import annotations

import time

from vector_inspector.services.telemetry_service import TelemetryService


class DummySettings:
    def __init__(self):
        self.settings = {}

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value


def test_worker_lifecycle_and_queue_processing(monkeypatch, tmp_path):
    # Reset singleton first
    TelemetryService.reset_for_tests()

    # Prevent real HTTP calls
    posts = []

    class DummyResp:
        def __init__(self):
            self.status_code = 200
            self.text = "ok"

    def fake_post(url, json=None, timeout=None):
        posts.append((url, json))
        return DummyResp()

    monkeypatch.setattr("vector_inspector.services.telemetry_service.requests.post", fake_post)

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")

    # Queue an event and wake the worker
    svc.queue_event({"event_name": "unittest.event", "metadata": {}})
    assert svc.get_queue()  # queued

    # Wake worker and wait for it to process
    if getattr(svc, "_worker_wake", None) is not None:
        svc._worker_wake.set()

    # Wait until queue empties or timeout
    deadline = time.time() + 3
    while svc.get_queue() and time.time() < deadline:
        time.sleep(0.05)

    assert not svc.get_queue()
    assert posts, "Expected at least one HTTP POST call"


def test_flush_on_shutdown_sends_remaining_events(monkeypatch):
    TelemetryService.reset_for_tests()

    posts = []

    class DummyResp:
        def __init__(self):
            self.status_code = 201
            self.text = "created"

    def fake_post(url, json=None, timeout=None):
        posts.append((url, json))
        return DummyResp()

    monkeypatch.setattr("vector_inspector.services.telemetry_service.requests.post", fake_post)

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")

    svc.queue_event({"event_name": "shutdown.event", "metadata": {}})
    # Call flush_on_shutdown which should join worker and then synchronously send
    svc.flush_on_shutdown()

    # After flush, queue should be empty and at least one POST occurred
    assert not svc.get_queue()
    assert posts
