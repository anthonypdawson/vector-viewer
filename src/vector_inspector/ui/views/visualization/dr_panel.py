"""Dimensionality reduction controls panel for vector visualization."""

from PySide6.QtWidgets import QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton


class DRPanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Visualization Settings", parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(["PCA", "t-SNE", "UMAP"])
        layout.addWidget(self.method_combo)

        layout.addWidget(QLabel("Dimensions:"))
        self.dimensions_combo = QComboBox()
        self.dimensions_combo.addItems(["2D", "3D"])
        layout.addWidget(self.dimensions_combo)

        layout.addStretch()

        self.generate_button = QPushButton("Generate Visualization")
        layout.addWidget(self.generate_button)

        self.open_browser_button = QPushButton("Open in Browser")
        self.open_browser_button.setEnabled(False)
        layout.addWidget(self.open_browser_button)

        self.setLayout(layout)
