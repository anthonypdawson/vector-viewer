"""Main entry point for Vector Inspector application."""

import sys
from PySide6.QtWidgets import QApplication
from vector_inspector.ui.main_window import MainWindow


def main():
    """Launch the Vector Inspector application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Vector Inspector")
    app.setOrganizationName("Vector Inspector")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
