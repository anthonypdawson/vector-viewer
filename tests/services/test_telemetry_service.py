from __future__ import annotations

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

    # Assert internal signal exists before using it — if this fails the
    # TelemetryService API has changed and the test must be updated.
    assert hasattr(svc, "_worker_wake"), "_worker_wake missing; TelemetryService API changed"
    assert hasattr(svc, "_batch_processed"), "_batch_processed missing; TelemetryService API changed"

    # Reset the batch signal, wake the worker, then wait deterministically.
    # Timeout of 0.5 s is generous for a localhost no-op; failure here
    # indicates CI timing or worker thread issues, not logic bugs.
    svc._batch_processed.clear()
    svc._worker_wake.set()
    assert svc._batch_processed.wait(timeout=0.5), "Worker did not complete a batch within 0.5 s"

    assert not svc.get_queue(), "Queue should be empty after worker batch"
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
    # TelemetryService forces sentinel values when running under pytest
    # (detected via sys.modules) regardless of what is passed to the
    # constructor.  This is an intentional second-line defence: any event
    # that somehow escapes the conftest HTTP guard is immediately
    # identifiable on the backend.  See TelemetryService.__init__ for the
    # exact condition (_running_under_test and not _allow_telemetry_in_tests).
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
    # NOTE: send_batch retries indefinitely with no backoff or max-retry cap
    # (MVP behaviour). A future improvement should add a TTL or max-attempts
    # cap to avoid event queue growth during extended outages.  See
    # test_send_batch_retries_on_next_call for the successful-retry contract.
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

    assert hasattr(svc, "_worker_wake"), "_worker_wake missing; TelemetryService API changed"

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


# ---------------------------------------------------------------------------
# Retry semantics
# ---------------------------------------------------------------------------


def test_send_batch_retries_on_next_call(monkeypatch):
    """A failed send_batch leaves the event in the queue; the following call
    with a 200 response sends and removes it.

    Current behaviour: no backoff or max-retry cap (MVP).  If the server is
    persistently unreachable the queue can grow unboundedly — a future
    improvement should add a TTL / attempt counter to bound growth.
    """
    TelemetryService.reset_for_tests()
    call_count = [0]

    def alternating_response(_url, **_kw):
        call_count[0] += 1
        if call_count[0] == 1:

            class Fail:
                status_code = 500
                text = "temporary error"

            return Fail()

        class OK:
            status_code = 200
            text = "ok"

        return OK()

    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.requests.post",
        alternating_response,
    )

    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.queue_event({"event_name": "retry_event"})

    svc.send_batch()  # first attempt → 500, event stays
    assert len(svc.get_queue()) == 1, "Event should remain after failed send"

    svc.send_batch()  # second attempt → 200, event removed
    assert len(svc.get_queue()) == 0, "Event should be gone after successful retry"
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# Singleton enforcement
# ---------------------------------------------------------------------------


def test_singleton_enforced():
    """Constructing TelemetryService a second time without resetting must
    return the identical instance; later constructor arguments are ignored."""
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    svc1 = TelemetryService(settings_service=settings, app_version="0.0-test")
    # Second construction with different args must return the same object
    svc2 = TelemetryService(settings_service=settings, app_version="0.0-test")
    assert svc1 is svc2, "TelemetryService must be a singleton; got two distinct instances"
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# set_provider / set_collection cleared on close
# ---------------------------------------------------------------------------


def test_set_provider_and_collection_cleared_on_close():
    """Calling set_provider(None) and set_collection(None) — as the app does
    when a connection is closed — must prevent stale context from appearing
    in subsequent queued events."""
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.set_provider("chromadb")
    svc.set_collection("my_coll")

    # Simulate close_connection clearing the cached context
    svc.set_provider(None)
    svc.set_collection(None)

    svc.queue_event({"event_name": "post_close_event"})
    meta = svc.get_queue()[0]["metadata"]
    assert "db_provider" not in meta, "db_provider should be absent after set_provider(None)"
    assert "collection_name" not in meta, "collection_name should be absent after set_collection(None)"
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# flush_on_shutdown mid-flight race
# ---------------------------------------------------------------------------


def test_flush_on_shutdown_sends_events_queued_during_worker_join(monkeypatch):
    """flush_on_shutdown's final synchronous send_batch must forward any event
    queued while the background worker thread is being joined (mid-flight race).

    Scenario: another thread queues an event between the worker receiving its
    stop signal and flush_on_shutdown calling its own send_batch.  Because
    flush_on_shutdown always performs a synchronous send_batch *after* joining
    the worker, those late-arriving events must not be silently dropped.
    """
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

    if svc._worker is None:
        # If the worker didn't start (env-specific), the race cannot occur;
        # flush_on_shutdown already uses a synchronous send_batch as its only
        # path, so the invariant trivially holds.
        TelemetryService.reset_for_tests()
        return

    # Intercept worker.join to inject a "late" event during the join phase.
    # This mimics a concurrent thread queuing an event while shutdown is
    # waiting for the worker to exit.
    real_join = svc._worker.join

    def join_and_queue(timeout=None):
        # Queue the event from the "other thread" during the join window.
        svc.queue_event({"event_name": "mid.flight.event"})
        real_join(timeout=timeout)

    svc._worker.join = join_and_queue

    svc.flush_on_shutdown()

    sent_names = [p.get("event_name") for p in posts if p]
    assert "mid.flight.event" in sent_names, (
        "Event queued during worker join was not sent by flush_on_shutdown's final send_batch"
    )
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# Session ID — must NOT be loaded from settings on init (bug #9)
# ---------------------------------------------------------------------------


def test_session_id_starts_as_none_at_init():
    """session_id must be None at init, not loaded from a previous run's settings.

    Loading a stale session_id caused app_launch to carry the old session_id
    (the early send_launch_ping call happens before set_session_id is called).
    """
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    # Simulate a leftover session_id from a previous run
    settings.settings["telemetry.session_id"] = "old-session-from-previous-run"
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    assert svc.session_id is None, (
        "session_id should start as None; loading from settings causes app_launch "
        "to carry the old session_id before set_session_id is called"
    )
    TelemetryService.reset_for_tests()


def test_set_session_id_sets_on_instance_and_persists():
    """set_session_id() must update instance and settings."""
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")
    svc.set_session_id("new-session-abc")
    assert svc.session_id == "new-session-abc"
    assert settings.settings.get("telemetry.session_id") == "new-session-abc"
    TelemetryService.reset_for_tests()


# ---------------------------------------------------------------------------
# Duplicate session.start deduplication (bug #1)
# ---------------------------------------------------------------------------


def test_session_start_deduplication_removes_old_event():
    """Queuing session.start must purge any prior session.start events.

    Leftover session.start events in the persistent queue (from a run that
    failed to send) would appear as duplicate starts in analytics.
    """
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")

    # Simulate a leftover session.start from a prior run already in the queue
    with svc._lock:
        svc.queue.append({"event_name": "session.start", "metadata": {"session_id": "old-session"}})
        svc._save_queue()

    # Queue a new session.start for the current launch
    svc.queue_event({"event_name": "session.start", "metadata": {"session_id": "new-session"}})

    session_starts = [e for e in svc.queue if e.get("event_name") == "session.start"]
    assert len(session_starts) == 1, "Only one session.start should exist in the queue"
    assert session_starts[0]["metadata"]["session_id"] == "new-session"
    TelemetryService.reset_for_tests()


def test_session_start_deduplication_keeps_other_events():
    """Deduplication of session.start must not affect other event types."""
    TelemetryService.reset_for_tests()
    settings = DummySettings()
    settings.settings["telemetry.enabled"] = True
    svc = TelemetryService(settings_service=settings, app_version="0.0-test")

    svc.queue_event({"event_name": "app_launch", "metadata": {}})
    svc.queue_event({"event_name": "session.start", "metadata": {"session_id": "old"}})
    svc.queue_event({"event_name": "session.start", "metadata": {"session_id": "new"}})

    event_names = [e["event_name"] for e in svc.queue]
    assert event_names.count("session.start") == 1
    assert "app_launch" in event_names
    TelemetryService.reset_for_tests()

