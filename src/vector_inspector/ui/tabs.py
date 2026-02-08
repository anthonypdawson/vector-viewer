"""Tab registry for Inspector applications."""

from PySide6.QtWidgets import QWidget


class TabDefinition:
    """Definition for a tab in the main content area."""

    title: str
    widget_class: type
    lazy_load: bool

    def __init__(self, title: str, widget_class: type[QWidget], lazy_load: bool = False):
        self.title = title
        self.widget_class = widget_class
        self.lazy_load = lazy_load


class InspectorTabs:
    INFO_TAB: int
    DATA_TAB: int
    SEARCH_TAB: int
    VISUALIZATION_TAB: int
    """Registry of standard Inspector tabs.

    This allows both Vector Inspector and Vector Fusion Studio to use
    the same tab definitions and add their own custom tabs.
    """

    # Tab indices (for programmatic access)
    INFO_TAB = 0
    DATA_TAB = 1
    SEARCH_TAB = 2
    VISUALIZATION_TAB = 3

    @staticmethod
    def get_standard_tabs() -> list[TabDefinition]:
        """Get list of standard Inspector tabs.

        Returns:
            List of TabDefinition objects
        """
        from vector_inspector.ui.views.info_panel import InfoPanel
        from vector_inspector.ui.views.metadata_view import MetadataView
        from vector_inspector.ui.views.search_view import SearchView
        from vector_inspector.ui.views.visualization_view import VisualizationView

        return [
            TabDefinition("Info", InfoPanel, lazy_load=False),
            TabDefinition("Data Browser", MetadataView, lazy_load=False),
            TabDefinition("Search", SearchView, lazy_load=False),
            TabDefinition("Visualization", VisualizationView, lazy_load=True),
        ]

    @staticmethod
    def create_tab_widget(tab_def: TabDefinition, connection=None) -> QWidget:
        """Create a widget instance from a tab definition.

        Args:
            tab_def: Tab definition
            connection: Optional connection to pass to widget

        Returns:
            Widget instance
        """
        if tab_def.lazy_load:
            # Return placeholder for lazy-loaded tabs
            return QWidget()
        # Create widget with connection
        return tab_def.widget_class(connection)
