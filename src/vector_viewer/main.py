"""Main entry point for Vector Viewer application."""

import sys
from PySide6.QtWidgets import QApplication
from vector_viewer.ui.main_window import MainWindow


def main():
    """Launch the Vector Viewer application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Vector Viewer")
    app.setOrganizationName("Vector Viewer")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
