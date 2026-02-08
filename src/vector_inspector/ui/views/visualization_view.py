"""Vector visualization view with dimensionality reduction."""

from __future__ import annotations

import traceback
from typing import Any, Optional

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.connection_manager import ConnectionInstance
from vector_inspector.core.logging import log_error
from vector_inspector.services.visualization_service import VisualizationService
from vector_inspector.ui.components.loading_dialog import LoadingDialog


class VisualizationThread(QThread):
    """Background thread for dimensionality reduction."""

    finished = Signal(np.ndarray)
    error = Signal(str)
    embeddings: Any
    method: Any
    n_components: Any

    def __init__(self, embeddings, method, n_components):
        super().__init__()
        self.embeddings = embeddings
        self.method = method
        self.n_components = n_components

    def run(self):
        """Run dimensionality reduction."""
        try:
            result = VisualizationService.reduce_dimensions(
                self.embeddings, method=self.method, n_components=self.n_components
            )
            if result is not None:
                self.finished.emit(result)
            else:
                self.error.emit("Dimensionality reduction failed")
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


class VisualizationView(QWidget):
    """View for visualizing vectors in 2D/3D."""

    connection: Optional[ConnectionInstance]
    current_collection: str
    current_data: dict[str, Any] | None
    reduced_data: Any
    visualization_thread: Any
    temp_html_files: list

    def __init__(self, connection: Optional[ConnectionInstance] = None, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.current_collection = ""
        self.current_data = None
        self.reduced_data = None
        self.visualization_thread = None
        self.temp_html_files = []
        self._setup_ui()

    def _setup_ui(self):
        """Setup widget UI."""
        layout = QVBoxLayout(self)

        # Shared controls (sample size + use all data) - left aligned
        shared_layout = QHBoxLayout()
        shared_layout.addWidget(QLabel("Sample size:"))
        self.sample_spin = QSpinBox()
        self.sample_spin.setMinimum(10)
        self.sample_spin.setMaximum(10000)
        self.sample_spin.setValue(500)
        self.sample_spin.setSingleStep(100)
        shared_layout.addWidget(self.sample_spin)
        self.use_all_checkbox = QCheckBox("Use all data")
        shared_layout.addWidget(self.use_all_checkbox)
        shared_layout.addStretch()
        layout.addLayout(shared_layout)

        def on_use_all_changed():
            self.sample_spin.setEnabled(not self.use_all_checkbox.isChecked())

        self.use_all_checkbox.stateChanged.connect(on_use_all_changed)

        # Controls
        controls_group = QGroupBox("Visualization Settings")
        controls_layout = QHBoxLayout()

        # Method selection
        controls_layout.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(["PCA", "t-SNE", "UMAP"])
        controls_layout.addWidget(self.method_combo)

        # Dimensions
        controls_layout.addWidget(QLabel("Dimensions:"))
        self.dimensions_combo = QComboBox()
        self.dimensions_combo.addItems(["2D", "3D"])
        controls_layout.addWidget(self.dimensions_combo)

        controls_layout.addStretch()

        # Generate button
        self.generate_button = QPushButton("Generate Visualization")
        self.generate_button.clicked.connect(self._generate_visualization)
        controls_layout.addWidget(self.generate_button)

        # Open in Browser button (next to generate)
        self.open_browser_button = QPushButton("Open in Browser")
        self.open_browser_button.setEnabled(False)
        self.open_browser_button.clicked.connect(self._open_in_browser)
        controls_layout.addWidget(self.open_browser_button)

        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)

        # Embedded web view for Plotly
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, stretch=10)

        # Status
        self.status_label = QLabel("No collection selected")
        self.status_label.setStyleSheet("color: gray;")
        self.status_label.setMaximumHeight(30)
        layout.addWidget(self.status_label)

        # Loading dialog for data fetch and reduction
        self.loading_dialog = LoadingDialog("Loading visualization...", self)

    def set_collection(self, collection_name: str):
        """Set the current collection to visualize."""
        self.current_collection = collection_name
        self.current_data = None
        self.reduced_data = None
        self.status_label.setText(f"Collection: {collection_name}")

    def _generate_visualization(self):
        # Disable browser button until plot is generated
        self.open_browser_button.setEnabled(False)
        """Generate visualization of vectors."""
        if not self.current_collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first.")
            return

        # Load data with embeddings (show loading immediately)
        self.loading_dialog.show_loading("Loading data for visualization...")
        QApplication.processEvents()
        if hasattr(self, "use_all_checkbox") and self.use_all_checkbox.isChecked():
            sample_size = None
        else:
            sample_size = self.sample_spin.value()
        try:
            if sample_size is None:
                data = self.connection.get_all_items(self.current_collection)
            else:
                data = self.connection.get_all_items(self.current_collection, limit=sample_size)
        finally:
            self.loading_dialog.hide_loading()

        if (
            data is None
            or not data
            or "embeddings" not in data
            or data["embeddings"] is None
            or len(data["embeddings"]) == 0
        ):
            QMessageBox.warning(
                self,
                "No Data",
                "No embeddings found in collection. Make sure the collection contains vector embeddings.",
            )
            return

        self.current_data = data
        self.status_label.setText("Reducing dimensions...")
        self.generate_button.setEnabled(False)

        # Get parameters
        method = self.method_combo.currentText().lower()
        if method == "t-sne":
            method = "tsne"
        n_components = 2 if self.dimensions_combo.currentText() == "2D" else 3

        # Run dimensionality reduction in background thread
        self.visualization_thread = VisualizationThread(data["embeddings"], method, n_components)
        self.visualization_thread.finished.connect(self._on_reduction_finished)
        self.visualization_thread.error.connect(self._on_reduction_error)
        # Show loading during reduction
        self.loading_dialog.show_loading("Reducing dimensions...")
        QApplication.processEvents()
        self.visualization_thread.start()

    def _on_reduction_finished(self, reduced_data: Any):
        """Handle dimensionality reduction completion."""
        self.loading_dialog.hide_loading()
        self.reduced_data = reduced_data
        self._create_plot()
        self.generate_button.setEnabled(True)
        self.open_browser_button.setEnabled(True)
        self.status_label.setText("Visualization complete")

    def _on_reduction_error(self, error_msg: str):
        """Handle dimensionality reduction error."""
        self.loading_dialog.hide_loading()
        log_error("Visualization failed: %s", error_msg)
        QMessageBox.warning(self, "Error", f"Visualization failed: {error_msg}")
        self.generate_button.setEnabled(True)
        self.status_label.setText("Visualization failed")

    def _create_plot(self):
        """Create plotly visualization."""
        if self.reduced_data is None or self.current_data is None:
            return

        # Lazy import plotly
        from vector_inspector.utils.lazy_imports import get_plotly

        go = get_plotly()

        ids = self.current_data.get("ids", [])
        documents = self.current_data.get("documents", [])

        # Prepare hover text
        hover_texts = []
        for _, (id_val, doc) in enumerate(zip(ids, documents, strict=True)):
            doc_preview = str(doc)[:100] if doc else "No document"
            hover_texts.append(f"ID: {id_val}<br>Doc: {doc_preview}")

        # Create plot
        method_name = self.method_combo.currentText()
        if self.reduced_data.shape[1] == 2:
            # 2D plot
            fig = go.Figure(
                data=[
                    go.Scatter(
                        x=self.reduced_data[:, 0],
                        y=self.reduced_data[:, 1],
                        mode="markers",
                        marker={
                            "size": 8,
                            "color": list(range(len(ids))),
                            "colorscale": "Viridis",
                            "showscale": True,
                        },
                        text=hover_texts,
                        hoverinfo="text",
                    )
                ]
            )

            fig.update_layout(
                title=f"Vector Visualization - {method_name}",
                xaxis_title=f"{method_name} Dimension 1",
                yaxis_title=f"{method_name} Dimension 2",
                hovermode="closest",
                height=800,
                width=1200,
            )
        else:
            # 3D plot
            fig = go.Figure(
                data=[
                    go.Scatter3d(
                        x=self.reduced_data[:, 0],
                        y=self.reduced_data[:, 1],
                        z=self.reduced_data[:, 2],
                        mode="markers",
                        marker={
                            "size": 5,
                            "color": list(range(len(ids))),
                            "colorscale": "Viridis",
                            "showscale": True,
                        },
                        text=hover_texts,
                        hoverinfo="text",
                    )
                ]
            )
            fig.update_layout(
                title=f"Vector Visualization - {method_name}",
                scene={
                    "xaxis_title": f"{method_name} Dimension 1",
                    "yaxis_title": f"{method_name} Dimension 2",
                    "zaxis_title": f"{method_name} Dimension 3",
                },
                height=800,
                width=1200,
            )

        # Display in embedded web view
        html = fig.to_html(include_plotlyjs="cdn")
        self.web_view.setHtml(html)

        # Save temp HTML file for browser
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp_file:
            temp_file.write(html.encode("utf-8"))
            temp_file.flush()
            self.temp_html_files.append(temp_file.name)
            self._last_temp_html = temp_file.name

    def _open_in_browser(self):
        import webbrowser

        if hasattr(self, "_last_temp_html") and self._last_temp_html:
            webbrowser.open(f"file://{self._last_temp_html}")

    def cleanup_temp_html(self):
        import contextlib
        import os

        for f in getattr(self, "temp_html_files", []):
            with contextlib.suppress(Exception):
                os.remove(f)
        self.temp_html_files = []
        self._last_temp_html = None
