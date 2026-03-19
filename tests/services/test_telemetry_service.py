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


def test_worker_lifecycle_and_queue_processing(monkeypatch):
    # Reset singleton first
    TelemetryService.reset_for_tests()

    # Prevent real HTTP calls
    posts = []

    class DummyResp:
        def __init__(self):
            self.status_code = 200
            self.text = "ok"

    def fake_post(url, json=None, **_):
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

    def fake_post(url, json=None, **_):
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


# ---------------------------------------------------------------------------
# is_enabled / disabled-by-default paths
# ---------------------------------------------------------------------------


def test_telemetry_disabled_by_default_in_tests():
    """Service created without explicit settings defaults to disabled in test env."""
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    # do NOT set telemetry.enabled
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    assert not svc.is_enabled()


def test_telemetry_queue_event_skipped_when_disabled():
    """queue_event must not add events when telemetry is disabled."""
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = False
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.queue_event({"event_name": "should_not_appear"})
    assert svc.get_queue() == []


# ---------------------------------------------------------------------------
# queue_event metadata enrichment
# ---------------------------------------------------------------------------


def test_queue_event_injects_app_version_and_client_type():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    # In test mode the service forces sentinel values regardless of what is
    # passed so any leaked event is identifiable on the backend.
    svc = TelemetryService(settings_service=settings)
    svc.queue_event({"event_name": "ping"})
    events = svc.get_queue()
    assert len(events) == 1
    assert events[0]["app_version"] == "0.0-test"
    assert events[0]["client_type"] == "unit-tests"
    assert "hwid" in events[0]
    svc.purge()
    TelemetryService.reset_for_tests()


def test_queue_event_injects_session_id_into_metadata():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.session_id = "sess-abc"
    svc.queue_event({"event_name": "test_event"})
    events = svc.get_queue()
    assert events[0]["metadata"].get("session_id") == "sess-abc"
    TelemetryService.reset_for_tests()


def test_queue_event_injects_cached_provider_and_collection():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.set_provider("chromadb")
    svc.set_collection("my_coll")
    svc.queue_event({"event_name": "test_event"})
    meta = svc.get_queue()[0]["metadata"]
    assert meta["db_provider"] == "chromadb"
    assert meta["collection_name"] == "my_coll"
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# send_batch — non-200 response does not remove from queue
# ---------------------------------------------------------------------------


def test_send_batch_non_200_keeps_event_in_queue(monkeypatch):
    TelemetryService.reset_for_tests()

    class DummyResp:
        status_code = 500
        text = "server error"

    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.requests.post",
        lambda _url, **_kw: DummyResp(),
    )

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.queue_event({"event_name": "retry_event"})
    svc.send_batch()
    # Event should still be in queue because server returned 500
    assert len(svc.get_queue()) == 1
    svc.purge()  # clear before reset so queue file is clean for next test
    TelemetryService.reset_for_tests()


def test_send_batch_exception_keeps_event_in_queue(monkeypatch):
    TelemetryService.reset_for_tests()

    def boom(_url=None, **_kw):
        raise ConnectionError("network down")

    monkeypatch.setattr("vector_inspector.services.telemetry_service.requests.post", boom)

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.purge()  # ensure any residual queue file is clean before this test
    svc.queue_event({"event_name": "fail_event"})
    svc.send_batch()
    assert len(svc.get_queue()) == 1
    svc.purge()
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# send_launch_ping
# ---------------------------------------------------------------------------


def test_send_launch_ping_posts_event(monkeypatch):
    TelemetryService.reset_for_tests()
    posts = []

    class OK:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.requests.post",
        lambda _url, **kw: (posts.append(kw.get("json")), OK())[1],
    )

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="ping-test")
    svc.send_launch_ping("ping-test")

    assert any(p["event_name"] == "app_launch" for p in posts if p)
    TelemetryService.reset_for_tests()


def test_send_launch_ping_skips_when_disabled():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = False
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.send_launch_ping("0.0-test")
    assert svc.get_queue() == []
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# send_error_event
# ---------------------------------------------------------------------------


def test_send_error_event_posts_event(monkeypatch):
    TelemetryService.reset_for_tests()
    posts = []

    class OK:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.requests.post",
        lambda _url, **kw: (posts.append(kw.get("json")), OK())[1],
    )

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.send_error_event("boom", "traceback here", extra={"context": "unit-test"})

    assert any(p and "boom" in str(p.get("metadata", {})) for p in posts)
    TelemetryService.reset_for_tests()


def test_send_error_event_skips_when_disabled():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = False
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.send_error_event("msg", "tb")
    assert svc.get_queue() == []
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# purge / set_session_id / get_hwid helpers
# ---------------------------------------------------------------------------


def test_purge_clears_queue():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.queue_event({"event_name": "e1"})
    svc.queue_event({"event_name": "e2"})
    assert len(svc.get_queue()) == 2
    svc.purge()
    assert svc.get_queue() == []
    TelemetryService.reset_for_tests()


def test_set_session_id_persists():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.set_session_id("my-session-123")
    assert svc.session_id == "my-session-123"
    assert settings.settings.get("telemetry.session_id") == "my-session-123"
    TelemetryService.reset_for_tests()


def test_get_hwid_returns_string():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    hwid = svc.get_hwid()
    assert isinstance(hwid, str) and len(hwid) > 0
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------


def test_queue_event_static_uses_singleton():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")

    TelemetryService.queue_event_static({"event_name": "static_test"})
    assert any(e["event_name"] == "static_test" for e in svc.get_queue())
    TelemetryService.reset_for_tests()


def test_send_event_static_wakes_worker():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")

    woken = []
    orig_set = svc._worker_wake.set

    def track_set():
        woken.append(True)
        orig_set()

    svc._worker_wake.set = track_set

    TelemetryService.send_event("myevent", {"metadata": {"k": "v"}})
    assert woken, "Worker wake event should have been set"
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# make_error_hash
# ---------------------------------------------------------------------------


def test_make_error_hash_is_stable():
    from vector_inspector.services.telemetry_service import make_error_hash

    h1 = make_error_hash("ValueError", "invalid value 42", "mymodule:10")
    h2 = make_error_hash("ValueError", "invalid value 42", "mymodule:10")
    assert h1 == h2
    assert len(h1) == 16


def test_make_error_hash_differs_by_exc_type():
    from vector_inspector.services.telemetry_service import make_error_hash

    h1 = make_error_hash("ValueError", "boom", None)
    h2 = make_error_hash("TypeError", "boom", None)
    assert h1 != h2


def test_make_error_hash_normalizes_numbers():
    from vector_inspector.services.telemetry_service import make_error_hash

    h1 = make_error_hash("ValueError", "index 10 out of range", None)
    h2 = make_error_hash("ValueError", "index 99 out of range", None)
    # Both reduce to "index #n out of range" so hashes match
    assert h1 == h2


def test_make_error_hash_normalizes_hex():
    from vector_inspector.services.telemetry_service import make_error_hash

    h1 = make_error_hash("RuntimeError", "address 0xDEADBEEF invalid", None)
    h2 = make_error_hash("RuntimeError", "address 0x0ABCDEF0 invalid", None)
    assert h1 == h2


# ---------------------------------------------------------------------------
# should_sample (deterministic)
# ---------------------------------------------------------------------------


def test_should_sample_rate_1_always_true():
    from vector_inspector.services.telemetry_service import should_sample

    for _ in range(20):
        assert should_sample("query.executed", 1.0, seed="s1")


def test_should_sample_rate_0_always_false():
    from vector_inspector.services.telemetry_service import should_sample

    for _ in range(20):
        assert not should_sample("query.executed", 0.0, seed="s1")


def test_should_sample_deterministic():
    from vector_inspector.services.telemetry_service import should_sample

    r1 = should_sample("embedding.request", 0.5, seed="fixed-seed")
    r2 = should_sample("embedding.request", 0.5, seed="fixed-seed")
    assert r1 == r2


def test_should_sample_differs_by_seed():
    from vector_inspector.services.telemetry_service import should_sample

    results = {should_sample("query.executed", 0.5, seed=str(i)) for i in range(50)}
    # With 50 seeds at 50% rate both True and False should appear
    assert True in results
    assert False in results


# ---------------------------------------------------------------------------
# queue_sampled_event
# ---------------------------------------------------------------------------


def test_queue_sampled_event_rate_1_always_queues():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.session_id = "sess-sample"
    sampled = svc.queue_sampled_event({"event_name": "query.executed"}, rate=1.0)
    assert sampled
    events = svc.get_queue()
    assert any(e["event_name"] == "query.executed" for e in events)
    meta = events[0]["metadata"]
    assert meta["sampling_rate"] == 1.0
    assert "sampling_version" in meta
    svc.purge()
    TelemetryService.reset_for_tests()


def test_queue_sampled_event_rate_0_never_queues():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.session_id = "sess-sample"
    sampled = svc.queue_sampled_event({"event_name": "embedding.request"}, rate=0.0)
    assert not sampled
    assert svc.get_queue() == []
    TelemetryService.reset_for_tests()


def test_queue_sampled_event_metadata_injected():
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.session_id = "sess-meta"
    svc.queue_sampled_event({"event_name": "query.executed"}, rate=1.0, sampling_version="v2")
    events = svc.get_queue()
    assert events
    meta = events[0]["metadata"]
    assert meta["sampling_version"] == "v2"
    assert meta["sampling_rate"] == 1.0
    assert "sampling_seed_type" in meta
    svc.purge()
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# Crash marker
# ---------------------------------------------------------------------------


def test_write_crash_marker_creates_file(tmp_path):
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    # Override marker path to use tmp_path for isolation
    svc.queue_file = tmp_path / "queue.json"
    svc.write_crash_marker(session_id="sess-crash-test")
    marker = svc._crash_marker_path()
    assert marker.exists()
    import json as _json

    data = _json.loads(marker.read_text())
    assert data["session_id"] == "sess-crash-test"
    assert "ts" in data
    TelemetryService.reset_for_tests()


def test_clear_crash_marker_removes_file(tmp_path):
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.queue_file = tmp_path / "queue.json"
    svc.write_crash_marker(session_id="sess-xyz")
    assert svc._crash_marker_path().exists()
    svc.clear_crash_marker()
    assert not svc._crash_marker_path().exists()
    TelemetryService.reset_for_tests()


def test_check_and_emit_crash_event_emits_session_end(monkeypatch, tmp_path):
    TelemetryService.reset_for_tests()
    posts = []

    class OK:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.requests.post",
        lambda _url, **kw: (posts.append(kw.get("json")), OK())[1],
    )

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.queue_file = tmp_path / "queue.json"

    # Plant a crash marker as if a previous session died
    svc.write_crash_marker(session_id="dead-session-id")

    detected = svc.check_and_emit_crash_event()

    assert detected
    assert not svc._crash_marker_path().exists()
    assert any(p and p.get("event_name") == "session.end" for p in posts)
    crash_event = next(p for p in posts if p and p.get("event_name") == "session.end")
    assert crash_event["metadata"]["exit_reason"] == "crash"
    assert crash_event["metadata"]["session_id"] == "dead-session-id"
    TelemetryService.reset_for_tests()


def test_check_and_emit_crash_event_no_marker(tmp_path):
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.queue_file = tmp_path / "queue.json"
    # No marker file — should return False
    result = svc.check_and_emit_crash_event()
    assert result is False
    TelemetryService.reset_for_tests()


def test_flush_on_shutdown_clears_crash_marker(tmp_path, monkeypatch):
    TelemetryService.reset_for_tests()

    class OK:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.requests.post",
        lambda _url, **_kw: OK(),
    )

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.queue_file = tmp_path / "queue.json"
    svc.write_crash_marker(session_id="active-session")
    assert svc._crash_marker_path().exists()

    svc.flush_on_shutdown()

    assert not svc._crash_marker_path().exists()
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# send_error_event includes error_hash
# ---------------------------------------------------------------------------


def test_send_error_event_includes_error_hash(monkeypatch):
    TelemetryService.reset_for_tests()
    posts = []

    class OK:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.requests.post",
        lambda _url, **kw: (posts.append(kw.get("json")), OK())[1],
    )

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.send_error_event("something went wrong", "Traceback...", extra={"exception_type": "RuntimeError"})

    assert posts
    meta = posts[0]["metadata"]
    assert "error_hash" in meta
    assert len(meta["error_hash"]) == 16


def test_send_error_event_hash_stable_for_same_exception(monkeypatch):
    TelemetryService.reset_for_tests()
    posts = []

    class OK:
        status_code = 200
        text = "ok"

    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.requests.post",
        lambda _url, **kw: (posts.append(kw.get("json")), OK())[1],
    )

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")

    svc.send_error_event("index 5 out of range", "tb1", extra={"exception_type": "IndexError"})
    svc.send_error_event("index 99 out of range", "tb2", extra={"exception_type": "IndexError"})

    hashes = [p["metadata"]["error_hash"] for p in posts if p]
    assert len(hashes) == 2
    # Numbers normalized, so hashes must match
    assert hashes[0] == hashes[1]
    TelemetryService.reset_for_tests()
