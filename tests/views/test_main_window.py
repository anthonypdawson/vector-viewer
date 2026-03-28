from vector_inspector.ui.main_window import MainWindow


def test_main_window_initialization(qtbot, monkeypatch):
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)
    # Basic attributes created in __init__
    assert hasattr(mw, "app_state")
    assert mw.task_runner is not None
    assert mw.connection_manager is not None
    # Tabs should be created and metadata_view should exist
    assert mw.metadata_view is not None
    mw.close()


def test_toggle_cache_calls_cache_manager(qtbot, monkeypatch):
    calls = {}

    class FakeCacheSettings:
        def get_cache_enabled(self):
            return False

        def set_cache_enabled(self, val):
            calls["set"] = val

        def get(self, key, default=None):
            if key == "hide_splash_window":
                return True
            return default

    class FakeCache:
        def enable(self):
            calls["enable"] = True

        def disable(self):
            calls["disable"] = True

    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    mw.settings_service = FakeCacheSettings()
    qtbot.addWidget(mw)
    mw.app_state.cache_manager = FakeCache()

    mw._toggle_cache(True)
    assert calls.get("set") is True
    assert calls.get("enable") is True

    mw._toggle_cache(False)
    assert calls.get("set") is False
    assert calls.get("disable") is True

    mw.close()


def test_on_view_in_data_browser_requests_selection(qtbot, monkeypatch):
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    selected = {}

    class FakeMetadataView:
        def select_item_by_id(self, item_id):
            selected["id"] = item_id

    mw.metadata_view = FakeMetadataView()
    mw._on_view_in_data_browser_requested("item123")
    assert selected.get("id") == "item123"

    mw.close()


def test_on_setting_changed_status_timeout_ms_updates_reporter(qtbot, monkeypatch):
    """_on_setting_changed routes 'status.timeout_ms' to status_reporter._default_timeout_ms."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    mw._on_setting_changed("status.timeout_ms", 3000)
    assert mw.app_state.status_reporter._default_timeout_ms == 3000

    mw._on_setting_changed("status.timeout_ms", 0)
    assert mw.app_state.status_reporter._default_timeout_ms == 0

    mw.close()


def test_on_connection_completed_success_calls_report_action(qtbot, monkeypatch):
    """_on_connection_completed emits a report_action with duration when successful."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    received = {}

    def capture(msg, timeout_ms):
        received["msg"] = msg
        received["timeout_ms"] = timeout_ms

    mw.app_state.status_reporter.status_updated.connect(capture)

    mw._on_connection_completed(
        connection_id="c1",
        success=True,
        collections=["a", "b", "c"],
        error="",
        duration_ms=250.0,
    )

    assert "Connection" in received.get("msg", "")
    assert "3" in received.get("msg", "")  # 3 collections
    assert "0.25s" in received.get("msg", "")  # 250ms → 0.25s

    mw.close()


def test_on_connection_completed_failure_no_report_action(qtbot, monkeypatch):
    """_on_connection_completed does NOT emit status when success=False."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    received = []
    mw.app_state.status_reporter.status_updated.connect(lambda msg, ms: received.append(msg))

    mw._on_connection_completed(
        connection_id="c1",
        success=False,
        collections=[],
        error="timeout",
        duration_ms=100.0,
    )

    assert len(received) == 0

    mw.close()
