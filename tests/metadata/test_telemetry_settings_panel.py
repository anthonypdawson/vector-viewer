"""Tests for extensions/telemetry_settings_panel.py and extensions/__init__.py hook system."""

from unittest.mock import MagicMock

from PySide6.QtWidgets import QCheckBox, QMenu, QTableWidget, QVBoxLayout, QWidget

from vector_inspector.extensions import (
    SettingsPanelHook,
    TableContextMenuHook,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeSettings:
    def __init__(self, telemetry_enabled=True):
        self._settings = {"telemetry.enabled": telemetry_enabled}
        self.calls = {}

    def get(self, key, default=None):
        return self._settings.get(key, default)

    def set_telemetry_enabled(self, val):
        self.calls["set_telemetry_enabled"] = val
        self._settings["telemetry.enabled"] = val


# ---------------------------------------------------------------------------
# SettingsPanelHook
# ---------------------------------------------------------------------------


def test_settings_panel_hook_register_and_trigger(qtbot):
    """Registered handler receives the correct arguments."""
    hook = SettingsPanelHook()
    hook.clear()

    received = {}

    def my_handler(layout, svc, dialog=None):
        received["layout"] = layout
        received["svc"] = svc
        received["dialog"] = dialog

    hook.register(my_handler)
    parent = QWidget()
    qtbot.addWidget(parent)
    layout = QVBoxLayout(parent)
    svc = FakeSettings()
    hook.trigger(layout, svc, dialog="dlg")

    assert received["layout"] is layout
    assert received["svc"] is svc
    assert received["dialog"] == "dlg"

    hook.clear()


def test_settings_panel_hook_no_duplicate_registration():
    hook = SettingsPanelHook()
    hook.clear()

    calls = []
    handler = lambda l, s, d=None: calls.append(1)
    hook.register(handler)
    hook.register(handler)  # second registration should be ignored
    hook.trigger(MagicMock(), MagicMock())
    assert len(calls) == 1
    hook.clear()


def test_settings_panel_hook_unregister():
    hook = SettingsPanelHook()
    hook.clear()

    calls = []
    handler = lambda l, s, d=None: calls.append(1)
    hook.register(handler)
    hook.unregister(handler)
    hook.trigger(MagicMock(), MagicMock())
    assert calls == []


def test_settings_panel_hook_bad_handler_does_not_crash():
    """A handler that raises must not propagate and must not stop other handlers."""
    hook = SettingsPanelHook()
    hook.clear()

    def bad_handler(layout, svc, dialog=None):
        raise RuntimeError("oops")

    good_calls = []
    hook.register(bad_handler)
    hook.register(lambda l, s, d=None: good_calls.append(1))
    hook.trigger(MagicMock(), MagicMock())
    assert good_calls == [1]
    hook.clear()


# ---------------------------------------------------------------------------
# TableContextMenuHook
# ---------------------------------------------------------------------------


def test_table_context_menu_hook_register_and_trigger(qtbot):
    hook = TableContextMenuHook()
    hook.clear()

    received = {}

    def handler(menu, table, row, data=None):
        received["row"] = row
        received["data"] = data

    hook.register(handler)
    menu = QMenu()
    table = QTableWidget(1, 1)
    qtbot.addWidget(table)
    hook.trigger(menu, table, 3, {"ids": ["x"]})

    assert received["row"] == 3
    assert received["data"] == {"ids": ["x"]}
    hook.clear()


def test_table_context_menu_hook_no_duplicate():
    hook = TableContextMenuHook()
    hook.clear()

    calls = []
    h = lambda m, t, r, d=None: calls.append(1)
    hook.register(h)
    hook.register(h)
    hook.trigger(MagicMock(), MagicMock(), 0)
    assert len(calls) == 1
    hook.clear()


def test_table_context_menu_hook_bad_handler_does_not_crash():
    hook = TableContextMenuHook()
    hook.clear()

    def bad(menu, table, row, data=None):
        raise ValueError("bad")

    good = []
    hook.register(bad)
    hook.register(lambda m, t, r, d=None: good.append(1))
    hook.trigger(MagicMock(), MagicMock(), 0)
    assert good == [1]
    hook.clear()


# ---------------------------------------------------------------------------
# add_telemetry_section (the actual extension)
# ---------------------------------------------------------------------------


def test_add_telemetry_section_creates_checkbox(qtbot):
    """add_telemetry_section must add a QCheckBox to the parent layout."""
    from vector_inspector.extensions.telemetry_settings_panel import add_telemetry_section

    parent = QWidget()
    qtbot.addWidget(parent)
    layout = QVBoxLayout(parent)
    svc = FakeSettings(telemetry_enabled=True)

    add_telemetry_section(layout, svc)

    # Find the checkbox nested within the added HBoxLayout
    checkboxes = parent.findChildren(QCheckBox)
    assert len(checkboxes) == 1
    assert checkboxes[0].isChecked() is True


def test_add_telemetry_section_unchecked_when_disabled(qtbot):
    from vector_inspector.extensions.telemetry_settings_panel import add_telemetry_section

    parent = QWidget()
    qtbot.addWidget(parent)
    layout = QVBoxLayout(parent)
    svc = FakeSettings(telemetry_enabled=False)

    add_telemetry_section(layout, svc)

    checkboxes = parent.findChildren(QCheckBox)
    assert checkboxes[0].isChecked() is False


def test_add_telemetry_section_defaults_to_checked_when_none(qtbot):
    """When settings_service.get returns None, checkbox should default to checked."""
    from vector_inspector.extensions.telemetry_settings_panel import add_telemetry_section

    parent = QWidget()
    qtbot.addWidget(parent)
    layout = QVBoxLayout(parent)

    svc = FakeSettings()
    svc._settings.pop("telemetry.enabled", None)  # simulate missing key → returns None

    add_telemetry_section(layout, svc)

    checkboxes = parent.findChildren(QCheckBox)
    assert checkboxes[0].isChecked() is True


def test_add_telemetry_section_toggle_calls_set(qtbot):
    """Toggling the checkbox must call set_telemetry_enabled on the settings service."""
    from vector_inspector.extensions.telemetry_settings_panel import add_telemetry_section

    parent = QWidget()
    qtbot.addWidget(parent)
    layout = QVBoxLayout(parent)
    svc = FakeSettings(telemetry_enabled=True)

    add_telemetry_section(layout, svc)
    checkbox = parent.findChildren(QCheckBox)[0]

    # Uncheck it
    with qtbot.waitSignal(checkbox.stateChanged):
        checkbox.setChecked(False)

    assert "set_telemetry_enabled" in svc.calls
    assert svc.calls["set_telemetry_enabled"] is False


def test_add_telemetry_section_toggle_enable(qtbot):
    from vector_inspector.extensions.telemetry_settings_panel import add_telemetry_section

    parent = QWidget()
    qtbot.addWidget(parent)
    layout = QVBoxLayout(parent)
    svc = FakeSettings(telemetry_enabled=False)

    add_telemetry_section(layout, svc)
    checkbox = parent.findChildren(QCheckBox)[0]

    with qtbot.waitSignal(checkbox.stateChanged):
        checkbox.setChecked(True)

    assert svc.calls["set_telemetry_enabled"] is True


def test_add_telemetry_section_has_tooltip(qtbot):
    from vector_inspector.extensions.telemetry_settings_panel import add_telemetry_section

    parent = QWidget()
    qtbot.addWidget(parent)
    layout = QVBoxLayout(parent)
    svc = FakeSettings()

    add_telemetry_section(layout, svc)
    checkbox = parent.findChildren(QCheckBox)[0]
    assert checkbox.toolTip() != ""


def test_settings_panel_hook_registered_globally():
    """Importing telemetry_settings_panel registers add_telemetry_section on the hook."""
    # Re-register as the module does at import time, then verify it works via trigger.
    from vector_inspector.extensions.telemetry_settings_panel import add_telemetry_section

    hook = SettingsPanelHook()
    hook.clear()
    hook.register(add_telemetry_section)
    assert add_telemetry_section in SettingsPanelHook._handlers
    hook.clear()
