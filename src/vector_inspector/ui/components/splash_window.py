from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton, QTextBrowser
from PySide6.QtCore import Qt


class SplashWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Vector Inspector!")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        # Welcome message
        label = QLabel("<h2>Thanks for trying <b>Vector Inspector</b>!</h2>")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        # Feedback prompt
        feedback = QLabel(
            "If you have thoughts, feature requests, or run into anything confusing,<br>"
            "I’d really appreciate hearing from you. Feedback helps shape the roadmap."
        )
        feedback.setTextFormat(Qt.RichText)
        feedback.setWordWrap(True)
        layout.addWidget(feedback)

        # GitHub link
        github = QLabel(
            '<a href="https://github.com/anthonypdawson/vector-inspector/issues">Submit feedback or issues on GitHub</a>'
        )
        github.setOpenExternalLinks(True)
        github.setAlignment(Qt.AlignCenter)
        layout.addWidget(github)

        # About info (reuse About dialog text)
        from vector_inspector.ui.main_window import get_about_html

        about = QTextBrowser()
        about.setHtml(get_about_html())
        about.setOpenExternalLinks(True)
        about.setMaximumHeight(160)
        layout.addWidget(about)

        # Do not show again checkbox
        self.hide_checkbox = QCheckBox("Do not show this again")
        layout.addWidget(self.hide_checkbox)

        # OK button
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

        layout.addStretch(1)

    def should_hide(self):
        return self.hide_checkbox.isChecked()
