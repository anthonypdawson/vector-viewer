import os

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget


class LoadingScreen(QWidget):
    def __init__(self, logo_path, version, app_name, tagline, loading_text):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)

        # Container with background
        container = QWidget()
        container.setStyleSheet("background-color: #222; border-radius: 10px; color: #fff;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(32, 32, 32, 32)
        container_layout.setSpacing(12)

        # Logo
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaled(
                128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo_label = QLabel()
            logo_label.setPixmap(pixmap)
            logo_label.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(logo_label)

        # App name
        app_name_label = QLabel(app_name)
        app_name_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
        app_name_label.setAlignment(Qt.AlignCenter)
        app_name_label.setStyleSheet("color: #fff;")
        container_layout.addWidget(app_name_label)

        # Tagline
        tagline_label = QLabel(tagline)
        tagline_label.setFont(QFont("Segoe UI", 10))
        tagline_label.setAlignment(Qt.AlignCenter)
        tagline_label.setStyleSheet("color: #aaa;")
        container_layout.addWidget(tagline_label)

        # Version
        version_label = QLabel(version)
        version_label.setFont(QFont("Segoe UI", 10))
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #aaa;")
        container_layout.addWidget(version_label)

        # Loading indicator
        self.loading_label = QLabel(loading_text)
        self.loading_label.setFont(QFont("Segoe UI", 10))
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("color: #6cf;")
        container_layout.addWidget(self.loading_label)

        # Skip loading screen checkbox
        self.skip_loading_checkbox = QCheckBox("Don't show this again")
        self.skip_loading_checkbox.setFont(QFont("Segoe UI", 9))
        self.skip_loading_checkbox.setStyleSheet("color: #aaa; margin-top: 10px;")
        self.skip_loading_checkbox.stateChanged.connect(self._on_skip_changed)
        container_layout.addWidget(self.skip_loading_checkbox, alignment=Qt.AlignCenter)

        layout.addWidget(container)
        self.setLayout(layout)
        self.resize(400, 400)

        # Center on screen
        self._center_on_screen()

    def _center_on_screen(self):
        """Center the loading screen on the primary screen."""
        from PySide6.QtWidgets import QApplication

        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2)

    def set_loading_text(self, text):
        self.loading_label.setText(text)

    def _on_skip_changed(self, state):
        """Save the skip loading screen preference."""
        from vector_inspector.services.settings_service import SettingsService

        settings = SettingsService()
        settings.set("hide_loading_screen", state == Qt.CheckState.Checked.value)

    def fade_out(self, duration=500):
        """Fade out the loading screen and close after animation."""
        animation = QPropertyAnimation(self, b"windowOpacity")
        animation.setDuration(duration)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.finished.connect(self.close)
        animation.start()
        self._fade_animation = animation  # Prevent garbage collection


def show_loading_screen(app_name, version, tagline, loading_text="Initializing providers…", logo_path=None):
    """Show the loading screen if not disabled in settings.
    
    This is a convenience function that handles checking settings, finding the logo,
    creating the loading screen, and showing it. Both vector-inspector and vector-studio
    should use this function to avoid code duplication.
    
    Args:
        app_name: Name of the application (e.g., "Vector Inspector", "Vector Studio")
        version: Version string (e.g., "v0.3.11")
        tagline: Tagline to display under app name
        loading_text: Initial loading message
        logo_path: Optional explicit path to logo. If None, will look for vector-inspector's logo.
    
    Returns:
        LoadingScreen instance if shown, None otherwise.
    """
    from vector_inspector.services.settings_service import SettingsService
    
    # Check if user wants to skip loading screen
    settings = SettingsService()
    show_loading = not settings.get("hide_loading_screen", False)
    
    if not show_loading:
        return None
    
    # Find logo path if not provided
    if logo_path is None:
        # Default to vector-inspector's logo
        module_dir = os.path.dirname(os.path.abspath(__file__))
        # Navigate from ui/loading_screen.py to vector_inspector/assets/logo.png
        logo_path = os.path.join(os.path.dirname(module_dir), "assets", "logo.png")
    
    # Create and show loading screen
    loading = LoadingScreen(
        logo_path=logo_path,
        version=version,
        app_name=app_name,
        tagline=tagline,
        loading_text=loading_text,
    )
    loading.show()
    
    # Force the loading screen to render
    from PySide6.QtWidgets import QApplication
    QApplication.instance().processEvents()
    
    return loading


# Example usage (to be called from main.py):
# from vector_inspector.ui.loading_screen import show_loading_screen
#
# loading = show_loading_screen(
#     app_name="Vector Inspector",
#     version="v0.3.11",
#     tagline="The missing toolset for your vector data"
# )
# if loading:
#     loading.set_loading_text("Loading main window...")
#     # ... do initialization ...
#     loading.fade_out()
