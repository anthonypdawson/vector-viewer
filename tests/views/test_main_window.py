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


def test_ingest_images_delegates_to_metadata_view(qtbot, monkeypatch):
    """_ingest_images calls metadata_view._run_ingestion('image')."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    calls = []

    class FakeMetadataView:
        connection_manager = None

        def _run_ingestion(self, kind):
            calls.append(kind)

    mw.metadata_view = FakeMetadataView()
    mw._ingest_images()
    assert calls == ["image"]

    mw.close()


def test_ingest_documents_delegates_to_metadata_view(qtbot, monkeypatch):
    """_ingest_documents calls metadata_view._run_ingestion('document')."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    calls = []

    class FakeMetadataView:
        connection_manager = None

        def _run_ingestion(self, kind):
            calls.append(kind)

    mw.metadata_view = FakeMetadataView()
    mw._ingest_documents()
    assert calls == ["document"]

    mw.close()


def test_ingest_no_metadata_view_shows_info(qtbot, monkeypatch):
    """_ingest_images/_ingest_documents shows an info box when metadata_view is None."""
    from unittest.mock import patch

    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.metadata_view = None

    with patch("vector_inspector.ui.main_window.QMessageBox.information") as mock_info:
        mw._ingest_images()
        assert mock_info.called

    with patch("vector_inspector.ui.main_window.QMessageBox.information") as mock_info:
        mw._ingest_documents()
        assert mock_info.called

    mw.close()


def test_tools_menu_has_import_actions(qtbot, monkeypatch):
    """Tools menu exposes 'Import Images' and 'Import Documents' actions."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    menu_bar = mw.menuBar()
    tools_menu = None
    for action in menu_bar.actions():
        if "Tools" in action.text():
            tools_menu = action.menu()
            break

    assert tools_menu is not None, "Tools menu not found"
    action_texts = [a.text() for a in tools_menu.actions()]
    assert any("Image" in t for t in action_texts), f"Import Images not found in {action_texts}"
    assert any("Document" in t for t in action_texts), f"Import Documents not found in {action_texts}"

    mw.close()


# ---------------------------------------------------------------------------
# _set_collection_tabs_enabled
# ---------------------------------------------------------------------------


def test_set_collection_tabs_enabled_true_calls_set_collection_ready(qtbot, monkeypatch):
    """_set_collection_tabs_enabled(True) calls set_collection_ready(True) on all views."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    calls = []

    class FakeView:
        def set_collection_ready(self, val):
            calls.append(val)

    mw.metadata_view = FakeView()
    mw.search_view = FakeView()
    mw.visualization_view = FakeView()

    mw._set_collection_tabs_enabled(True)

    assert calls.count(True) == 3
    mw.close()


def test_set_collection_tabs_enabled_false_calls_set_collection_ready(qtbot, monkeypatch):
    """_set_collection_tabs_enabled(False) calls set_collection_ready(False) on all views."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    calls = []

    class FakeView:
        def set_collection_ready(self, val):
            calls.append(val)

    mw.metadata_view = FakeView()
    mw.search_view = FakeView()
    mw.visualization_view = FakeView()

    mw._set_collection_tabs_enabled(False)

    assert calls.count(False) == 3
    mw.close()


def test_set_collection_tabs_enabled_skips_views_without_method(qtbot, monkeypatch):
    """_set_collection_tabs_enabled does not crash when a view lacks set_collection_ready."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    mw.metadata_view = object()  # no set_collection_ready
    mw.search_view = object()
    mw.visualization_view = None  # None is the guarded case

    # Should not raise
    mw._set_collection_tabs_enabled(True)
    mw.close()


# ---------------------------------------------------------------------------
# _update_views_for_collection empty-string branch
# ---------------------------------------------------------------------------


def test_update_views_for_collection_empty_disables_views(qtbot, monkeypatch):
    """_update_views_for_collection('') calls _set_collection_tabs_enabled(False)."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    calls = []

    class FakeView:
        def set_collection_ready(self, val):
            calls.append(val)

    mw.metadata_view = FakeView()
    mw.search_view = FakeView()
    mw.visualization_view = None

    mw._update_views_for_collection("")

    assert all(v is False for v in calls)
    mw.close()


# ---------------------------------------------------------------------------
# _new_connection_from_profile
# ---------------------------------------------------------------------------


def test_new_connection_from_profile_switches_tab_and_opens_dialog(qtbot, monkeypatch):
    """_new_connection_from_profile activates Profiles tab and calls _create_profile."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    activated = {}
    created = {}
    monkeypatch.setattr(mw, "set_left_panel_active", lambda idx: activated.__setitem__("idx", idx))
    monkeypatch.setattr(mw.profile_panel, "_create_profile", lambda: created.__setitem__("called", True))

    mw._new_connection_from_profile()

    assert activated.get("idx") == 1
    assert created.get("called") is True
    mw.close()


# ---------------------------------------------------------------------------
# _connect_to_profile
# ---------------------------------------------------------------------------


def test_connect_to_profile_success_switches_to_active_tab(qtbot, monkeypatch):
    """_connect_to_profile switches to the Active tab (index 0) when connection succeeds."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    activated = {}
    monkeypatch.setattr(mw.connection_controller, "connect_to_profile", lambda pid: True)
    monkeypatch.setattr(mw, "set_left_panel_active", lambda idx: activated.__setitem__("idx", idx))

    mw._connect_to_profile("p1")

    assert activated.get("idx") == 0
    mw.close()


def test_connect_to_profile_failure_does_not_switch_tab(qtbot, monkeypatch):
    """_connect_to_profile does NOT switch tabs when connection fails."""
    monkeypatch.setattr(MainWindow, "_maybe_show_splash", lambda self: None)
    mw = MainWindow()
    qtbot.addWidget(mw)

    activated = {}
    monkeypatch.setattr(mw.connection_controller, "connect_to_profile", lambda pid: False)
    monkeypatch.setattr(mw, "set_left_panel_active", lambda idx: activated.__setitem__("idx", idx))

    mw._connect_to_profile("p1")

    assert "idx" not in activated
    mw.close()
