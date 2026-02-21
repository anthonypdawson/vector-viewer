"""Extension points for Vector Inspector.

This module provides hooks and callbacks that allow pro versions
or plugins to extend core functionality without modifying the base code.

Note: The module-level hook instances are intentional architectural extension points,
not user state. They provide a plugin system similar to event emitters or decorators.
"""

from collections.abc import Callable
from typing import Any, ClassVar

from PySide6.QtWidgets import QMenu, QTableWidget


class TableContextMenuHook:
    """Hook for adding custom context menu items to table widgets.

    Uses class-level handler registry - this is an acceptable pattern for
    a hook/plugin system, not typical "global state"."""

    _handlers: ClassVar[list[Callable]] = []

    @classmethod
    def register(cls, handler: Callable):
        """Register a context menu handler.

        Args:
            handler: Callable that takes (menu: QMenu, table: QTableWidget, row: int, data: Dict)
                    and adds menu items to the menu.
        """
        if handler not in cls._handlers:
            cls._handlers.append(handler)

    @classmethod
    def unregister(cls, handler: Callable):
        """Unregister a context menu handler."""
        if handler in cls._handlers:
            cls._handlers.remove(handler)

    @classmethod
    def trigger(
        cls,
        menu: QMenu,
        table: QTableWidget,
        row: int,
        data: dict[str, Any] | None = None,
    ):
        """Trigger all registered handlers.

        Args:
            menu: The QMenu to add items to
            table: The QTableWidget that was right-clicked
            row: The row number that was clicked
            data: Optional data dictionary with context (ids, documents, metadatas, etc.)
        """
        for handler in cls._handlers:
            try:
                handler(menu, table, row, data)
            except Exception as e:
                # Log but don't break if a handler fails
                from vector_inspector.core.logging import log_error

                log_error("Context menu handler error: %s", e)

    @classmethod
    def clear(cls):
        """Clear all registered handlers."""
        cls._handlers.clear()


# Global singleton instance
table_context_menu_hook = TableContextMenuHook()


class SettingsPanelHook:
    """Hook for adding custom sections to the Settings/Preferences dialog.

    Uses class-level handler registry - this is an acceptable pattern for
    a hook/plugin system, not typical "global state"."""

    _handlers: ClassVar[list[Callable]] = []

    @classmethod
    def register(cls, handler: Callable):
        """Register a settings panel provider.

        Handler signature: (parent_layout, settings_service, dialog)
        where `parent_layout` is a QLayout the handler can add widgets to.
        """
        if handler not in cls._handlers:
            cls._handlers.append(handler)

    @classmethod
    def unregister(cls, handler: Callable):
        if handler in cls._handlers:
            cls._handlers.remove(handler)

    @classmethod
    def trigger(cls, parent_layout, settings_service, dialog=None):
        for handler in cls._handlers:
            try:
                handler(parent_layout, settings_service, dialog)
            except Exception as e:
                from vector_inspector.core.logging import log_error

                log_error("Settings panel handler error: %s", e)

    @classmethod
    def clear(cls):
        cls._handlers.clear()


# Global singleton instance
settings_panel_hook = SettingsPanelHook()

# Register built-in settings panel extensions
try:
    import vector_inspector.extensions.telemetry_settings_panel
except Exception:
    pass
