"""Vector visualization view with dimensionality reduction (modular panels)."""

from __future__ import annotations

import tempfile
import traceback
import webbrowser
from typing import Any, Optional

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.connection_manager import ConnectionInstance
from vector_inspector.core.feature_flags import are_advanced_features_enabled, get_feature_tooltip
from vector_inspector.core.logging import log_error
from vector_inspector.services.visualization_service import VisualizationService
from vector_inspector.ui.components.loading_dialog import LoadingDialog
from vector_inspector.ui.views.visualization import ClusteringPanel, DRPanel, PlotPanel


class VisualizationThread(QThread):
    """Background thread for dimensionality reduction."""

    finished = Signal(np.ndarray)
    error = Signal(str)

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


class ClusteringThread(QThread):
    """Background thread for clustering."""

    finished = Signal(object)  # cluster_labels, algorithm
    error = Signal(str)

    def __init__(self, embeddings, algorithm, params):
        super().__init__()
        self.embeddings = embeddings
        self.algorithm = algorithm
        self.params = params

    def run(self):
        """Run clustering."""
        try:
            from vector_inspector.core.clustering import run_clustering

            labels, algorithm = run_clustering(self.embeddings, self.algorithm, self.params)
            self.finished.emit((labels, algorithm))
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


class VisualizationView(QWidget):
    """View for visualizing vectors in 2D/3D using modular panels."""

    def __init__(self, connection: Optional[ConnectionInstance] = None, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.current_collection = ""
        self.current_data = None
        self.reduced_data = None
        self.visualization_thread = None
        self.clustering_thread = None
        self.temp_html_files = []
        self.cluster_labels = None
        self._last_temp_html = None
        self.loading_dialog = LoadingDialog("Loading visualization...", self)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Shared controls (sample size + use all data)
        shared_layout = QHBoxLayout()
        shared_layout.addWidget(QLabel("Sample size:"))
        self.sample_spin = QSpinBox()
        self.sample_spin.setMinimum(10)
        # Feature gating: limit sample size in free version
        if are_advanced_features_enabled():
            self.sample_spin.setMaximum(10000)
        else:
            self.sample_spin.setMaximum(500)
        self.sample_spin.setValue(500)
        self.sample_spin.setSingleStep(100)
        shared_layout.addWidget(self.sample_spin)
        self.use_all_checkbox = QCheckBox("Use all data")
        shared_layout.addWidget(self.use_all_checkbox)
        shared_layout.addStretch()
        layout.addLayout(shared_layout)

        # Feature gating: disable "Use all data" in free version
        if not are_advanced_features_enabled():
            self.use_all_checkbox.setEnabled(False)
            self.use_all_checkbox.setToolTip(get_feature_tooltip())

        def on_use_all_changed():
            self.sample_spin.setEnabled(not self.use_all_checkbox.isChecked())

        self.use_all_checkbox.stateChanged.connect(on_use_all_changed)

        # Modular panels
        self.clustering_panel = ClusteringPanel(self)
        layout.addWidget(self.clustering_panel)

        self.dr_panel = DRPanel(self)
        layout.addWidget(self.dr_panel)

        self.plot_panel = PlotPanel(self)
        layout.addWidget(self.plot_panel, stretch=10)

        self.status_label = QLabel("No collection selected")
        self.status_label.setStyleSheet("color: gray;")
        self.status_label.setMaximumHeight(30)
        layout.addWidget(self.status_label)

        # Connect DRPanel generate button
        self.dr_panel.generate_button.clicked.connect(self._generate_visualization)
        self.dr_panel.open_browser_button.clicked.connect(self._open_in_browser)

        # Connect ClusteringPanel run button
        self.clustering_panel.cluster_button.clicked.connect(self._run_clustering)

    def _generate_visualization(self):
        """Generate visualization of vectors."""
        # Disable browser button until plot is generated
        self.dr_panel.open_browser_button.setEnabled(False)

        if not self.current_collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first.")
            return

        # Load data with embeddings (show loading immediately)
        self.loading_dialog.show_loading("Loading data for visualization...")
        QApplication.processEvents()

        if self.use_all_checkbox.isChecked():
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
        self.dr_panel.generate_button.setEnabled(False)

        # Get parameters
        method = self.dr_panel.method_combo.currentText().lower()
        if method == "t-sne":
            method = "tsne"
        n_components = 2 if self.dr_panel.dimensions_combo.currentText() == "2D" else 3

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
        self.plot_panel.create_plot(
            reduced_data=reduced_data,
            current_data=self.current_data,
            cluster_labels=self.cluster_labels,
            method_name=self.dr_panel.method_combo.currentText(),
        )
        self._save_temp_html()
        self.dr_panel.generate_button.setEnabled(True)
        self.dr_panel.open_browser_button.setEnabled(True)
        self.status_label.setText("Visualization complete")

    def _on_reduction_error(self, error_msg: str):
        """Handle dimensionality reduction error."""
        self.loading_dialog.hide_loading()
        log_error("Visualization failed: %s", error_msg)
        QMessageBox.warning(self, "Error", f"Visualization failed: {error_msg}")
        self.dr_panel.generate_button.setEnabled(True)
        self.status_label.setText("Visualization failed")

    def _save_temp_html(self):
        """Save current plot HTML to temp file for browser viewing."""
        html = self.plot_panel.get_current_html()
        if html:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".html", mode="w", encoding="utf-8"
            ) as temp_file:
                temp_file.write(html)
                temp_file.flush()
                self.temp_html_files.append(temp_file.name)
                self._last_temp_html = temp_file.name

    def _open_in_browser(self):
        """Open the last generated plot in a web browser."""
        if self._last_temp_html:
            webbrowser.open(f"file://{self._last_temp_html}")

    def _run_clustering(self):
        """Run clustering on current data."""
        if not self.current_collection:
            QMessageBox.warning(self, "No Collection", "Please select a collection first.")
            return

        # Load data if not already loaded
        if self.current_data is None:
            self.loading_dialog.show_loading("Loading data for clustering...")
            QApplication.processEvents()
            if self.use_all_checkbox.isChecked():
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
                    "No embeddings found in collection.",
                )
                return
            self.current_data = data

        # Get algorithm and parameters from panel
        algorithm = self.clustering_panel.cluster_algorithm_combo.currentText()
        params = self.clustering_panel.get_clustering_params()

        # Run clustering in background thread
        self.loading_dialog.show_loading("Running clustering...")
        QApplication.processEvents()
        self.clustering_panel.cluster_button.setEnabled(False)

        self.clustering_thread = ClusteringThread(
            self.current_data["embeddings"], algorithm, params
        )
        self.clustering_thread.finished.connect(self._on_clustering_finished)
        self.clustering_thread.error.connect(self._on_clustering_error)
        self.clustering_thread.start()

    def _on_clustering_finished(self, result):
        """Handle clustering completion."""
        self.loading_dialog.hide_loading()
        labels, algo = result
        self.cluster_labels = labels

        # Count clusters
        unique_labels = set(self.cluster_labels)
        if algo in ["HDBSCAN", "DBSCAN", "OPTICS"]:
            # These algorithms use -1 for noise
            n_clusters = len([label for label in unique_labels if label != -1])
            n_noise = list(self.cluster_labels).count(-1)
            self.status_label.setText(f"Found {n_clusters} clusters, {n_noise} noise points")
        else:
            # KMeans doesn't have noise
            n_clusters = len(unique_labels)
            self.status_label.setText(f"Found {n_clusters} clusters")

        self.status_label.setStyleSheet("color: green;")
        self.clustering_panel.cluster_button.setEnabled(True)

        # Recreate plot with cluster colors if we have reduced data
        if self.reduced_data is not None:
            self.plot_panel.create_plot(
                reduced_data=self.reduced_data,
                current_data=self.current_data,
                cluster_labels=self.cluster_labels,
                method_name=self.dr_panel.method_combo.currentText(),
            )
            self._save_temp_html()

    def _on_clustering_error(self, error_msg: str):
        """Handle clustering error."""
        self.loading_dialog.hide_loading()
        log_error("Clustering failed: %s", error_msg)
        QMessageBox.warning(self, "Error", f"Clustering failed: {error_msg}")
        self.clustering_panel.cluster_button.setEnabled(True)
        self.status_label.setText("Clustering failed")

    def set_collection(self, collection_name: str):
        """Set the current collection to visualize."""
        self.current_collection = collection_name
        self.current_data = None
        self.reduced_data = None
        self.cluster_labels = None
        self.status_label.setText(f"Collection: {collection_name}")

    def cleanup_temp_html(self):
        """Clean up temporary HTML files."""
        import contextlib
        import os

        for f in getattr(self, "temp_html_files", []):
            with contextlib.suppress(Exception):
                os.remove(f)
        self.temp_html_files = []
