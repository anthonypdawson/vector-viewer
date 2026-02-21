"""Vector visualization view with dimensionality reduction (modular panels)."""

from __future__ import annotations

import tempfile
import traceback
import webbrowser
from datetime import UTC
from typing import Any, Optional

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.connection_manager import ConnectionInstance

# Feature flags now accessed via app_state.advanced_features_enabled
from vector_inspector.core.logging import log_error, log_info
from vector_inspector.services import ClusterRunner, ThreadedTaskRunner
from vector_inspector.services.visualization_service import VisualizationService
from vector_inspector.state import AppState
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


class VisualizationDataLoadThread(QThread):
    """Background thread for loading visualization data."""

    finished = Signal(dict)  # data
    error = Signal(str)

    def __init__(self, connection, collection, sample_size, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.collection = collection
        self.sample_size = sample_size

    def run(self):
        """Load data from collection."""
        try:
            if not self.connection:
                self.error.emit("No database connection available")
                return

            if self.sample_size is None:
                data = self.connection.get_all_items(self.collection)
            else:
                data = self.connection.get_all_items(self.collection, limit=self.sample_size)

            if data:
                self.finished.emit(data)
            else:
                self.error.emit("Failed to load data")
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


class VisualizationView(QWidget):
    """View for visualizing vectors in 2D/3D using modular panels."""

    # Signal emitted when user wants to view a point in data browser
    view_in_data_browser_requested = Signal(str)  # item_id

    app_state: AppState
    task_runner: ThreadedTaskRunner
    cluster_runner: ClusterRunner

    def __init__(
        self,
        app_state: AppState,
        task_runner: ThreadedTaskRunner,
        parent=None,
    ):
        super().__init__(parent)

        # Store AppState and task runner
        self.app_state = app_state
        self.task_runner = task_runner
        self.cluster_runner = ClusterRunner()
        self.connection = self.app_state.provider

        self.current_collection = ""
        self.current_data = None
        self.reduced_data = None
        self.visualization_thread = None
        self.data_load_thread = None
        self.clustering_thread = None
        self.temp_html_files = []
        self.cluster_labels = None
        self._last_temp_html = None
        self.loading_dialog = LoadingDialog("Loading visualization...", self)
        self._setup_ui()
        self._connect_plot_signals()

        # Connect to AppState signals
        self._connect_state_signals()
        # Update services with current connection if available
        if self.app_state.provider:
            self._on_provider_changed(self.app_state.provider)

    def _connect_state_signals(self) -> None:
        """Subscribe to AppState changes."""
        # React to connection changes
        self.app_state.provider_changed.connect(self._on_provider_changed)

        # React to collection changes
        self.app_state.collection_changed.connect(self._on_collection_changed)

        # React to loading state
        self.app_state.loading_started.connect(self._on_loading_started)
        self.app_state.loading_finished.connect(self._on_loading_finished)

        # React to errors
        self.app_state.error_occurred.connect(self._on_error)

    def _on_provider_changed(self, connection: Optional[ConnectionInstance]) -> None:
        """React to provider/connection change."""
        # Update connection
        self.connection = connection

    def _on_collection_changed(self, collection: str) -> None:
        """React to collection change."""
        if collection:
            self.set_collection(collection)

    def _on_loading_started(self, message: str) -> None:
        """React to loading started."""
        self.loading_dialog.show_loading(message)

    def _on_loading_finished(self) -> None:
        """React to loading finished."""
        self.loading_dialog.hide()

    def _on_error(self, title: str, message: str) -> None:
        """React to error."""
        QMessageBox.critical(self, title, message)

    def _connect_plot_signals(self):
        """Connect plot panel signals."""
        self.plot_panel.view_in_data_browser.connect(self._on_view_in_data_browser)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Shared controls (sample size + use all data)
        shared_layout = QHBoxLayout()
        shared_layout.addWidget(QLabel("Sample size:"))
        self.sample_spin = QSpinBox()
        self.sample_spin.setMinimum(10)
        # Feature gating: limit sample size in free version
        if self.app_state.advanced_features_enabled:
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
        if not self.app_state.advanced_features_enabled:
            self.use_all_checkbox.setEnabled(False)
            self.use_all_checkbox.setToolTip(self.app_state.get_feature_tooltip())

        def on_use_all_changed():
            self.sample_spin.setEnabled(not self.use_all_checkbox.isChecked())

        self.use_all_checkbox.stateChanged.connect(on_use_all_changed)

        # Modular panels
        self.clustering_panel = ClusteringPanel(self, app_state=self.app_state)
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

        if self.use_all_checkbox.isChecked():
            sample_size = None
        else:
            sample_size = self.sample_spin.value()

        # Cancel any existing data load thread
        if self.data_load_thread and self.data_load_thread.isRunning():
            self.data_load_thread.quit()
            self.data_load_thread.wait()

        # Create and start data load thread
        self.data_load_thread = VisualizationDataLoadThread(
            self.connection,
            self.current_collection,
            sample_size,
            parent=self,
        )
        self.data_load_thread.finished.connect(self._on_data_loaded)
        self.data_load_thread.error.connect(self._on_data_load_error)

        # Show loading dialog during data load
        self.loading_dialog.show_loading("Loading data for visualization...")
        self.data_load_thread.start()

    def _on_data_loaded(self, data: dict) -> None:
        """Handle successful data load."""
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
        self.visualization_thread.start()

    def _on_data_load_error(self, error_message: str) -> None:
        """Handle data load error."""
        self.loading_dialog.hide_loading()
        QMessageBox.warning(
            self,
            "Load Error",
            f"Failed to load data: {error_message}",
        )

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
            with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as temp_file:
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
            if self.use_all_checkbox.isChecked():
                sample_size = None
            else:
                sample_size = self.sample_spin.value()

            # Cancel any existing data load thread
            if self.data_load_thread and self.data_load_thread.isRunning():
                self.data_load_thread.quit()
                self.data_load_thread.wait()

            # Create and start data load thread for clustering
            self.data_load_thread = VisualizationDataLoadThread(
                self.connection,
                self.current_collection,
                sample_size,
                parent=self,
            )
            self.data_load_thread.finished.connect(self._on_clustering_data_loaded)
            self.data_load_thread.error.connect(self._on_data_load_error)

            # Show loading dialog during data load
            self.loading_dialog.show_loading("Loading data for clustering...")
            self.data_load_thread.start()
        else:
            # Data already loaded, proceed with clustering
            self._start_clustering()

    def _on_clustering_data_loaded(self, data: dict) -> None:
        """Handle successful data load for clustering."""
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
        self._start_clustering()

    def _start_clustering(self) -> None:
        """Start clustering with already loaded data."""
        # Get algorithm and parameters from panel
        algorithm = self.clustering_panel.cluster_algorithm_combo.currentText()
        params = self.clustering_panel.get_clustering_params()

        # Run clustering in background thread
        self.loading_dialog.show_loading("Running clustering...")
        self.clustering_panel.cluster_button.setEnabled(False)

        self.clustering_thread = ClusteringThread(self.current_data["embeddings"], algorithm, params)
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
        # Update clustering result label in panel
        if algo in ["HDBSCAN", "DBSCAN", "OPTICS"]:
            n_clusters = len([label for label in unique_labels if label != -1])
            n_noise = list(self.cluster_labels).count(-1)
            msg = f"Found {n_clusters} clusters, {n_noise} noise points"
        else:
            n_clusters = len(unique_labels)
            msg = f"Found {n_clusters} clusters"

        self.clustering_panel.cluster_result_label.setText(msg)
        self.clustering_panel.cluster_result_label.setVisible(True)
        self.status_label.setText(msg)
        self.status_label.setStyleSheet("color: green;")
        self.clustering_panel.cluster_button.setEnabled(True)

        # Save cluster labels to metadata if checkbox is checked
        if self.clustering_panel.save_to_metadata_checkbox.isChecked():
            self._save_cluster_labels_to_metadata()

        # Recreate plot with cluster colors if we have reduced data
        if self.reduced_data is not None:
            self.plot_panel.create_plot(
                reduced_data=self.reduced_data,
                current_data=self.current_data,
                cluster_labels=self.cluster_labels,
                method_name=self.dr_panel.method_combo.currentText(),
            )
            self._save_temp_html()

    def _save_cluster_labels_to_metadata(self):
        """Save cluster labels to item metadata in the database."""
        if not self.current_data or not self.cluster_labels.any():
            return

        if not self.connection:
            log_error("Cannot save cluster labels: no database connection")
            return

        if not self.current_collection:
            log_error("Cannot save cluster labels: no collection selected")
            return

        try:
            from datetime import datetime

            ids = self.current_data.get("ids", [])
            metadatas = self.current_data.get("metadatas", [])

            # Update metadata with cluster labels
            updated_metadatas = []
            for i, (item_id, metadata) in enumerate(zip(ids, metadatas)):
                if i >= len(self.cluster_labels):
                    break

                # Create a copy of metadata to avoid modifying original
                updated_meta = dict(metadata) if metadata else {}
                updated_meta["cluster"] = int(self.cluster_labels[i])
                updated_meta["updated_at"] = datetime.now(UTC).isoformat()
                updated_metadatas.append(updated_meta)

            # Batch update all items with new cluster metadata
            success = self.connection.update_items(
                self.current_collection,
                ids=ids[: len(updated_metadatas)],
                metadatas=updated_metadatas,
            )

            if success:
                log_info("Successfully saved %d cluster labels to metadata", len(updated_metadatas))
                # Update local cache
                self.current_data["metadatas"] = updated_metadatas
            else:
                log_error("Failed to save cluster labels to metadata")
                QMessageBox.warning(
                    self,
                    "Warning",
                    "Clustering complete, but failed to save cluster labels to metadata.",
                )
        except Exception as e:
            log_error("Error saving cluster labels to metadata: %s", e)
            QMessageBox.warning(self, "Warning", f"Clustering complete, but error saving labels to metadata: {e!s}")

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
        # Clear clustering results when switching collection/provider
        try:
            if hasattr(self, "clustering_panel") and hasattr(self.clustering_panel, "cluster_result_label"):
                self.clustering_panel.cluster_result_label.setVisible(False)
                self.clustering_panel.cluster_result_label.setText("")
        except Exception:
            pass

        self.status_label.setText(f"Collection: {collection_name}")

    def _on_view_in_data_browser(self, _point_index: int, point_id: str):
        """Handle button click to view selected point in data browser.

        Args:
            _point_index: Index of the selected point (unused)
            point_id: ID of the selected point
        """
        if point_id:
            self.view_in_data_browser_requested.emit(point_id)

    def cleanup_temp_html(self):
        """Clean up temporary HTML files."""
        import contextlib
        import os

        for f in getattr(self, "temp_html_files", []):
            with contextlib.suppress(Exception):
                os.remove(f)
        self.temp_html_files = []
