from vector_inspector.ui.main_window import MainWindow


def test_main_window_initialization(qtbot):
    mw = MainWindow()
    # Prevent splash dialog from blocking tests by injecting a FakeSettings
    orig_settings = mw.settings_service

    class FakeSettingsInit:
        def get(self, key, default=None):
            if key == "hide_splash_window":
                return True
            return default

    mw.settings_service = FakeSettingsInit()
    qtbot.addWidget(mw)
    # Basic attributes created in __init__
    assert hasattr(mw, "app_state")
    assert mw.task_runner is not None
    assert mw.connection_manager is not None
    # Tabs should be created and metadata_view should exist
    assert mw.metadata_view is not None
    mw.close()
    mw.settings_service = orig_settings


def test_toggle_cache_calls_cache_manager(qtbot):
    mw = MainWindow()
    # Inject FakeSettings to prevent splash dialog and avoid mutating singleton
    orig_settings = mw.settings_service

    class FakeSettings:
        def get_cache_enabled(self):
            return False

        def set_cache_enabled(self, val):
            calls["set"] = val

        def get(self, key, default=None):
            # Prevent splash dialog in tests
            if key == "hide_splash_window":
                return True
            return default

    mw.settings_service = FakeSettings()
    qtbot.addWidget(mw)

    calls = {}

    class FakeSettings:
        def get_cache_enabled(self):
            return False

        def set_cache_enabled(self, val):
            calls["set"] = val

        def get(self, key, default=None):
            # Prevent splash dialog in tests
            if key == "hide_splash_window":
                return True
            return default

    class FakeCache:
        def enable(self):
            calls["enable"] = True

        def disable(self):
            calls["disable"] = True

    # Inject fakes to avoid side-effects on real settings files
    mw.app_state.cache_manager = FakeCache()

    mw._toggle_cache(True)
    assert calls.get("set") is True
    assert calls.get("enable") is True

    mw._toggle_cache(False)
    assert calls.get("set") is False
    assert calls.get("disable") is True

    mw.close()
    # restore original settings service instance
    mw.settings_service = orig_settings


def test_on_view_in_data_browser_requests_selection(qtbot):
    mw = MainWindow()
    # Prevent splash dialog from blocking tests by injecting FakeSettings
    orig_settings = mw.settings_service

    class FakeSettingsView:
        def get(self, key, default=None):
            if key == "hide_splash_window":
                return True
            return default

    mw.settings_service = FakeSettingsView()
    qtbot.addWidget(mw)

    selected = {}

    class FakeMetadataView:
        def select_item_by_id(self, item_id):
            selected["id"] = item_id

    mw.metadata_view = FakeMetadataView()

    mw._on_view_in_data_browser_requested("item123")
    assert selected.get("id") == "item123"

    mw.close()
    mw.settings_service = orig_settings
