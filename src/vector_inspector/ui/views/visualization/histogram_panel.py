"""Histogram / distribution panel for vector inspection."""

from __future__ import annotations

import traceback
from typing import Optional

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.utils import has_embedding
from vector_inspector.utils.lazy_imports import get_plotly

# ---------------------------------------------------------------------------
# Background threads
# ---------------------------------------------------------------------------


class _CollectionDimScanThread(QThread):
    """Scan all live connections for collections whose embedding dim matches target_dim.

    Emits a list of (display_label, collection_name, connection) tuples so the
    panel can show "ConnectionName / collection" and route the load to the right
    connection object.
    """

    # list[tuple[str, str, ConnectionInstance]]
    finished = Signal(object)

    def __init__(
        self,
        connections: list,
        exclude_collection: str,
        target_dim: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._connections = connections  # snapshot taken at scan time
        self._exclude = exclude_collection
        self._target_dim = target_dim

    def run(self) -> None:
        compatible: list[tuple[str, str, object]] = []
        for conn in self._connections:
            try:
                all_collections: list[str] = conn.list_collections()
            except Exception:
                continue
            for name in all_collections:
                if name == self._exclude:
                    continue
                try:
                    sample = conn.get_all_items(name, limit=1)
                    embeddings = sample.get("embeddings") if sample else None
                    if embeddings is None:
                        continue
                    for emb in embeddings:
                        if has_embedding(emb):
                            if len(emb) == self._target_dim:
                                label = f"{conn.name} / {name}"
                                compatible.append((label, name, conn))
                            break
                except Exception:
                    pass
        self.finished.emit(compatible)


class _CompareLoadThread(QThread):
    """Load embeddings for a comparison collection from a specific connection."""

    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        connection,  # ConnectionInstance for *this* collection
        collection: str,
        sample_size: Optional[int],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._connection = connection
        self._collection = collection
        self._sample_size = sample_size

    def run(self) -> None:
        try:
            if self._sample_size is None:
                data = self._connection.get_all_items(self._collection)
            else:
                data = self._connection.get_all_items(self._collection, limit=self._sample_size)
            if data:
                self.finished.emit(data)
            else:
                self.error.emit("No data returned from comparison collection")
        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------


class HistogramPanel(QWidget):
    """Panel that renders Plotly histogram(s) of a chosen vector distribution metric.

    Supports optional overlay comparison with a second collection that shares the
    same embedding dimensionality as the primary collection.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._current_html: Optional[str] = None
        self._current_data: Optional[dict] = None
        self._compare_data: Optional[dict] = None
        self._connection = None
        self._connection_manager = None
        self._primary_collection: str = ""
        self._primary_dim: int = 0
        self._sample_size: Optional[int] = None
        # Maps combo display label → (collection_name, ConnectionInstance)
        self._compare_options: dict[str, tuple[str, object]] = {}
        self._dim_scan_thread: Optional[_CollectionDimScanThread] = None
        self._compare_load_thread: Optional[_CompareLoadThread] = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Row 1: metric controls ----
        metric_row = QHBoxLayout()

        metric_row.addWidget(QLabel("Metric:"))
        self.metric_combo = QComboBox()
        self.metric_combo.addItems(["Norm", "Dimension"])
        metric_row.addWidget(self.metric_combo)

        self.dim_label = QLabel("Dim index:")
        self.dim_label.setEnabled(False)
        metric_row.addWidget(self.dim_label)

        self.dim_spin = QSpinBox()
        self.dim_spin.setMinimum(0)
        self.dim_spin.setMaximum(9999)
        self.dim_spin.setEnabled(False)
        metric_row.addWidget(self.dim_spin)

        metric_row.addWidget(QLabel("Bins:"))
        self.bin_spin = QSpinBox()
        self.bin_spin.setMinimum(5)
        self.bin_spin.setMaximum(500)
        self.bin_spin.setValue(50)
        metric_row.addWidget(self.bin_spin)

        self.density_checkbox = QCheckBox("Density")
        metric_row.addWidget(self.density_checkbox)

        self.generate_button = QPushButton("Generate")
        self.generate_button.setEnabled(False)
        metric_row.addWidget(self.generate_button)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setToolTip("Reset comparison and clear the chart")
        metric_row.addWidget(self.clear_button)

        metric_row.addStretch()
        layout.addLayout(metric_row)

        # ---- Separator ----
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # ---- Row 2: comparison controls ----
        compare_row = QHBoxLayout()

        self.compare_checkbox = QCheckBox("Compare with:")
        self.compare_checkbox.setToolTip(
            "Overlay a second collection. Only collections with the same embedding dimension are listed."
        )
        compare_row.addWidget(self.compare_checkbox)

        self.compare_combo = QComboBox()
        self.compare_combo.setMinimumWidth(220)
        self.compare_combo.setEnabled(False)
        self.compare_combo.setPlaceholderText("(enable Compare to load collections)")
        compare_row.addWidget(self.compare_combo)

        self.compare_load_button = QPushButton("Load")
        self.compare_load_button.setEnabled(False)
        compare_row.addWidget(self.compare_load_button)

        self.compare_status_label = QLabel("")
        self.compare_status_label.setStyleSheet("color: gray;")
        compare_row.addWidget(self.compare_status_label)

        compare_row.addStretch()
        layout.addLayout(compare_row)

        # ---- Plotly web view ----
        self.web_view = QWebEngineView()
        web_settings = self.web_view.settings()
        web_settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        layout.addWidget(self.web_view, stretch=10)

        # ---- Status label ----
        self.status_label = QLabel(
            "Generate a visualization first to populate distribution data, then switch to this tab."
        )
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

        # ---- Signal connections ----
        self.metric_combo.currentTextChanged.connect(self._on_metric_changed)
        self.generate_button.clicked.connect(self.generate_histogram)
        self.clear_button.clicked.connect(self._on_clear)
        self.compare_checkbox.stateChanged.connect(self._on_compare_toggled)
        self.compare_load_button.clicked.connect(self._on_load_comparison)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_connection(self, connection) -> None:
        """Inform the panel of the active database connection (primary provider).

        Called by VisualizationView whenever the provider changes.
        Resets any in-progress comparison since the connection context changed.
        """
        self._connection = connection
        self._reset_comparison()

    def set_connection_manager(self, manager) -> None:
        """Inform the panel of the ConnectionManager so it can scan all live connections.

        Called by VisualizationView at construction and whenever the manager changes.
        """
        self._connection_manager = manager

    def set_data(self, data: dict, collection_name: str = "", sample_size: Optional[int] = None) -> None:
        """Accept loaded collection data and auto-regenerate the histogram.

        Called by VisualizationView whenever new data is loaded so the
        Distributions tab stays in sync without requiring manual action.
        """
        self._current_data = data
        self._primary_collection = collection_name
        self._sample_size = sample_size
        self.generate_button.setEnabled(True)

        # Derive and store the primary collection's embedding dim.
        embeddings = data.get("embeddings")
        if embeddings is None:
            embeddings = []
        for emb in embeddings:
            if has_embedding(emb):
                dim = len(emb)
                self.dim_spin.setMaximum(dim - 1)
                if dim != self._primary_dim:
                    # Dim changed (different collection) — reset comparison.
                    self._primary_dim = dim
                    self._reset_comparison()
                break

        self.generate_histogram()

    def generate_histogram(self) -> None:
        """Compute the selected metric for all valid embeddings and render."""
        if not self._current_data:
            self.status_label.setText("No data available. Generate a visualization from the Visualization tab first.")
            self.status_label.setStyleSheet("color: gray;")
            return

        primary_values = self._extract_values(self._current_data)
        if primary_values is None:
            return

        compare_values: Optional[list[float]] = None
        compare_name: str = ""
        if self._compare_data is not None:
            compare_values = self._extract_values(self._compare_data, for_comparison=True)
            compare_name = self.compare_combo.currentText()

        self._render(primary_values, compare_values, compare_name)

    def get_current_html(self) -> Optional[str]:
        """Return the current histogram HTML (for export / browser opening)."""
        return self._current_html

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _extract_values(self, data: dict, for_comparison: bool = False) -> Optional[list[float]]:
        """Extract metric values from a data dict. Returns None and sets status on error."""
        embeddings = data.get("embeddings")
        if embeddings is None:
            embeddings = []
        valid = [emb for emb in embeddings if has_embedding(emb)]

        if not valid:
            msg = "No valid embeddings found" + (" in comparison collection." if for_comparison else ".")
            self.status_label.setText(msg)
            self.status_label.setStyleSheet("color: orange;")
            return None

        metric = self.metric_combo.currentText()
        if metric == "Norm":
            return [float(np.linalg.norm(e)) for e in valid]

        dim_idx = self.dim_spin.value()
        try:
            return [float(e[dim_idx]) for e in valid]
        except (IndexError, TypeError):
            self.status_label.setText(
                f"Dimension index {dim_idx} is out of range"
                + (" for comparison collection." if for_comparison else ".")
            )
            self.status_label.setStyleSheet("color: orange;")
            return None

    def _render(self, primary: list[float], compare: Optional[list[float]], compare_name: str) -> None:
        """Build and display the Plotly histogram figure."""
        metric = self.metric_combo.currentText()
        dim_idx = self.dim_spin.value()
        bin_count = self.bin_spin.value()
        density = self.density_checkbox.isChecked()
        histnorm = "probability density" if density else ""

        if metric == "Norm":
            x_label = "Vector Norm (L2 magnitude)"
            base_title = "Distribution of Vector Norms"
        else:
            x_label = f"Dimension {dim_idx} Value"
            base_title = f"Distribution of Values at Dimension {dim_idx}"

        # Include source connection for primary collection when available
        if self._connection is not None and getattr(self._connection, "name", None):
            primary_name = f"{self._connection.name} / {self._primary_collection or 'Primary'}"
        else:
            primary_name = self._primary_collection or "Primary"
        title = base_title if compare is None else f"{base_title} — {primary_name} vs {compare_name}"

        go = get_plotly()
        traces = [
            go.Histogram(
                x=primary,
                name=primary_name,
                nbinsx=bin_count,
                histnorm=histnorm,
                marker_color="#636EFA",
                opacity=0.75 if compare is not None else 0.85,
            )
        ]
        if compare is not None:
            traces.append(
                go.Histogram(
                    x=compare,
                    name=compare_name,
                    nbinsx=bin_count,
                    histnorm=histnorm,
                    marker_color="#EF553B",
                    opacity=0.6,
                )
            )

        fig = go.Figure(data=traces)
        fig.update_layout(
            title=title,
            xaxis_title=x_label,
            yaxis_title="Density" if density else "Count",
            barmode="overlay" if compare is not None else "relative",
            bargap=0.05,
            height=600,
            width=1000,
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        )

        html = fig.to_html(include_plotlyjs="cdn")
        # Embed metadata comment with explicit trace names so tests can assert presence
        meta_comment = f"<!--VI_META primary:{primary_name} compare:{compare_name}-->\n"
        html = meta_comment + html
        self._current_html = html
        self.web_view.setHtml(html)

        n_primary = len(primary)
        suffix = " (density)" if density else ""
        if compare is not None:
            n_compare = len(compare)
            self.status_label.setText(f"{n_primary:,} primary | {n_compare:,} comparison | Metric: {metric}{suffix}")
        else:
            self.status_label.setText(f"{n_primary:,} vectors | Metric: {metric}{suffix}")
        self.status_label.setStyleSheet("color: green;")

    def _reset_comparison(self) -> None:
        """Clear comparison data and reset comparison UI to default state."""
        self._compare_data = None
        self.compare_checkbox.blockSignals(True)
        self.compare_checkbox.setChecked(False)
        self.compare_checkbox.blockSignals(False)
        self.compare_combo.clear()
        self.compare_combo.setEnabled(False)
        self.compare_load_button.setEnabled(False)
        self.compare_status_label.setText("")

    # ------------------------------------------------------------------
    # Private slots
    # ------------------------------------------------------------------

    def _on_metric_changed(self, text: str) -> None:
        is_dimension = text == "Dimension"
        self.dim_spin.setEnabled(is_dimension)
        self.dim_label.setEnabled(is_dimension)

    def _on_clear(self) -> None:
        """Reset comparison, clear the chart, and reset all state."""
        self._reset_comparison()
        self._compare_data = None
        self._current_data = None
        self.generate_button.setEnabled(False)
        self.web_view.setHtml("")
        self.status_label.setText("Cleared. Generate a visualization to repopulate.")
        self.status_label.setStyleSheet("color: gray;")
        self._current_html = None

    def _on_compare_toggled(self, state: int) -> None:
        enabled = bool(state)
        if not enabled:
            self._reset_comparison()
            if self._current_data:
                self.generate_histogram()
            return

        if self._primary_dim == 0:
            self.compare_status_label.setText("Load primary data first.")
            self.compare_checkbox.blockSignals(True)
            self.compare_checkbox.setChecked(False)
            self.compare_checkbox.blockSignals(False)
            return

        # Gather all live connections; fallback to the active single connection
        if self._connection_manager is not None:
            connections = self._connection_manager.get_all_connections()
        elif self._connection is not None:
            connections = [self._connection]
        else:
            connections = []

        if not connections:
            self.compare_status_label.setText("No active connections to scan.")
            self.compare_status_label.setStyleSheet("color: orange;")
            self.compare_checkbox.blockSignals(True)
            self.compare_checkbox.setChecked(False)
            self.compare_checkbox.blockSignals(False)
            return

        # Kick off background scan for same-dim collections across all connections
        self.compare_combo.clear()
        self.compare_combo.setEnabled(False)
        self.compare_load_button.setEnabled(False)
        self.compare_status_label.setText("Scanning connections…")
        self.compare_status_label.setStyleSheet("color: gray;")

        if self._dim_scan_thread and self._dim_scan_thread.isRunning():
            self._dim_scan_thread.quit()
            self._dim_scan_thread.wait()

        self._dim_scan_thread = _CollectionDimScanThread(
            connections,
            self._primary_collection,
            self._primary_dim,
            parent=self,
        )
        self._dim_scan_thread.finished.connect(self._on_dim_scan_finished)
        self._dim_scan_thread.start()

    def _on_dim_scan_finished(self, compatible: list) -> None:
        # compatible is list[tuple[label, collection_name, connection]]
        if not compatible:
            self.compare_status_label.setText(f"No other collections share dim={self._primary_dim}.")
            self.compare_status_label.setStyleSheet("color: orange;")
            self.compare_checkbox.blockSignals(True)
            self.compare_checkbox.setChecked(False)
            self.compare_checkbox.blockSignals(False)
            return

        self._compare_options.clear()
        self.compare_combo.clear()
        for label, coll_name, conn in compatible:
            self._compare_options[label] = (coll_name, conn)
            self.compare_combo.addItem(label)

        self.compare_combo.setEnabled(True)
        self.compare_load_button.setEnabled(True)
        self.compare_status_label.setText(f"{len(compatible)} compatible collection(s) found")
        self.compare_status_label.setStyleSheet("color: green;")

    def _on_load_comparison(self) -> None:
        label = self.compare_combo.currentText()
        if not label:
            return

        option = self._compare_options.get(label)
        if option is None:
            self.compare_status_label.setText("Invalid selection — please re-scan.")
            self.compare_status_label.setStyleSheet("color: orange;")
            return

        coll_name, conn = option

        self.compare_load_button.setEnabled(False)
        self.compare_status_label.setText(f"Loading '{label}'…")
        self.compare_status_label.setStyleSheet("color: gray;")

        if self._compare_load_thread and self._compare_load_thread.isRunning():
            self._compare_load_thread.quit()
            self._compare_load_thread.wait()

        self._compare_load_thread = _CompareLoadThread(
            conn,
            coll_name,
            self._sample_size,
            parent=self,
        )
        self._compare_load_thread.finished.connect(self._on_compare_loaded)
        self._compare_load_thread.error.connect(self._on_compare_error)
        self._compare_load_thread.start()

    def _on_compare_loaded(self, data: dict) -> None:
        self._compare_data = data
        self.compare_load_button.setEnabled(True)
        embeddings = data.get("embeddings")
        if embeddings is None:
            embeddings = []
        n = len([e for e in embeddings if has_embedding(e)])
        col = self.compare_combo.currentText()
        self.compare_status_label.setText(f"Loaded '{col}' ({n:,} vectors)")
        self.compare_status_label.setStyleSheet("color: green;")
        self.generate_histogram()

    def _on_compare_error(self, message: str) -> None:
        self._compare_data = None
        self.compare_load_button.setEnabled(True)
        self.compare_status_label.setText(f"Load failed: {message}")
        self.compare_status_label.setStyleSheet("color: red;")
