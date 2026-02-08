from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QPushButton, QTextBrowser, QVBoxLayout


class SplashWindow(QDialog):
    hide_checkbox: QCheckBox

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Vector Inspector!")
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        label = QLabel("<h2>Thanks for trying <b>Vector Inspector</b>!</h2>")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        feedback = QLabel(
            "If you have thoughts, feature requests, or run into anything confusing,<br>"
            "I’d really appreciate hearing from you. Feedback helps shape the roadmap."
        )
        feedback.setTextFormat(Qt.RichText)
        feedback.setWordWrap(True)
        layout.addWidget(feedback)
        github = QLabel(
            '<a href="https://github.com/anthonypdawson/vector-inspector/issues">Submit feedback or issues on GitHub</a>'
        )
        github.setOpenExternalLinks(True)
        github.setAlignment(Qt.AlignCenter)
        layout.addWidget(github)
        from vector_inspector.utils.version import get_app_version

        about = QTextBrowser()
        version = get_app_version()
        version_html = (
            f"<h2>Vector Inspector {version}</h2>" if version else "<h2>Vector Inspector</h2>"
        )
        about_text = (
            version_html + "<p>A comprehensive desktop application for visualizing, "
            "querying, and managing multiple vector databases simultaneously.</p>"
            '<p><a href="https://github.com/anthonypdawson/vector-inspector" style="color:#2980b9;">GitHub Project Page</a></p>'
            "<hr />"
            "<p>Built with PySide6</p>"
            "<p><b>New:</b> Pinecone support!</p>"
        )
        about.setHtml(about_text)
        about.setOpenExternalLinks(True)
        about.setMaximumHeight(160)
        layout.addWidget(about)
        self.hide_checkbox = QCheckBox("Do not show this again")
        layout.addWidget(self.hide_checkbox)

        # OK button
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

        layout.addStretch(1)

    def should_hide(self):
        return self.hide_checkbox.isChecked()
