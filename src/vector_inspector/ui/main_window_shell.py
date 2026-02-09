"""Reusable UI shell for Vector Inspector applications."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class InspectorShell(QMainWindow):
    """Base shell for Inspector applications with splitter, tab widget, and left panel.

    This provides the basic UI structure that can be reused by Vector Inspector
    and Vector Fusion Studio. Subclasses customize behavior and add domain logic.
    """

    left_tabs: QTabWidget
    tab_widget: QTabWidget
    main_splitter: QSplitter

    def __init__(self):
        super().__init__()

        # Main UI components that subclasses will interact with
        self.left_tabs = None
        self.tab_widget = None
        self.main_splitter = None

        self._setup_shell_ui()

    def _setup_shell_ui(self):
        """Setup the main UI shell layout."""
        # Central widget with splitter
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Main splitter (left panel | right tabs)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel container (will hold tabs)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget for left panel
        self.left_tabs = QTabWidget()
        left_layout.addWidget(self.left_tabs)

        # Right panel - main content tabs
        self.tab_widget = QTabWidget()

        # Add panels to splitter
        self.main_splitter.addWidget(left_panel)
        self.main_splitter.addWidget(self.tab_widget)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 4)

        layout.addWidget(self.main_splitter)

    def add_left_panel(self, widget: QWidget, title: str, index: int = -1):
        """Add a panel to the left tab widget.

        Args:
            widget: The panel widget to add
            title: Display title for the tab
            index: Optional position (default appends to end)
        """
        if index < 0:
            self.left_tabs.addTab(widget, title)
        else:
            self.left_tabs.insertTab(index, widget, title)

    def add_main_tab(self, widget: QWidget, title: str, index: int = -1):
        """Add a tab to the main content area.

        Args:
            widget: The tab widget to add
            title: Display title for the tab
            index: Optional position (default appends to end)
        """
        if index < 0:
            self.tab_widget.addTab(widget, title)
        else:
            self.tab_widget.insertTab(index, widget, title)

    def set_left_panel_active(self, index: int):
        """Switch to a specific left panel tab."""
        if 0 <= index < self.left_tabs.count():
            self.left_tabs.setCurrentIndex(index)

    def set_main_tab_active(self, index: int):
        """Switch to a specific main content tab."""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)

    def get_main_tab_count(self) -> int:
        """Get the number of main content tabs."""
        return self.tab_widget.count()

    def remove_main_tab(self, index: int):
        """Remove a main content tab."""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.removeTab(index)
