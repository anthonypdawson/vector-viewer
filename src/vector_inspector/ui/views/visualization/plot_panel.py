"""Plot panel for displaying vector visualizations."""

from typing import Any, Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from vector_inspector.services.telemetry_service import TelemetryService


class PlotEventBridge(QObject):
    """Bridge for receiving events from Plotly JavaScript."""

    point_selected = Signal(int, str)  # Signal(point_index, point_id)
    interaction = Signal(str, int)  # Signal(action, selected_count)

    def __init__(self, parent=None):
        super().__init__(parent)

    @Slot(int, str)
    def onPointSelected(self, point_index: int, point_id: str):
        """Called from JavaScript when a point is selected."""
        self.point_selected.emit(point_index, point_id)

    @Slot(str, int)
    def onInteraction(self, action: str, selected_count: int):
        """Called from JavaScript for interactions like zoom/pan/lasso."""
        try:
            self.interaction.emit(action, int(selected_count))
        except Exception:
            pass


class PlotPanel(QWidget):
    # Signal emitted when user clicks "View in Data Browser" button
    view_in_data_browser = Signal(int, str)  # point_index, point_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_html = None
        self._current_ids = []
        self._selected_index = None
        self._selected_id = None
        self._cluster_labels = None
        self._event_bridge = PlotEventBridge(self)
        self._event_bridge.point_selected.connect(self._on_point_selected)
        self._event_bridge.interaction.connect(self._on_interaction)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.web_view = QWebEngineView()

        # Set up web channel for JS-Qt communication
        self.channel = QWebChannel()
        self.channel.registerObject("plotBridge", self._event_bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Enable JavaScript
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        layout.addWidget(self.web_view, stretch=10)

        # Add button bar below plot (for 2D point selection)
        self.selection_container = QWidget()
        button_layout = QHBoxLayout(self.selection_container)
        button_layout.setContentsMargins(0, 0, 0, 0)

        self.selection_label = QLabel("No point selected")
        self.selection_label.setStyleSheet("color: gray; font-style: italic;")
        button_layout.addWidget(self.selection_label)

        button_layout.addStretch()

        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.setEnabled(False)
        self.clear_selection_button.clicked.connect(self._on_clear_selection_clicked)
        button_layout.addWidget(self.clear_selection_button)

        self.view_data_button = QPushButton("View Selected Point in Data Browser")
        self.view_data_button.setEnabled(False)
        self.view_data_button.clicked.connect(self._on_view_data_clicked)
        button_layout.addWidget(self.view_data_button)

        layout.addWidget(self.selection_container)
        self.setLayout(layout)

    def _on_point_selected(self, point_index: int, point_id: str):
        """Handle point selection/deselection from plot (toggle behavior)."""
        if point_index < 0:
            # Deselection
            self._selected_index = None
            self._selected_id = None
            self.selection_label.setText("No point selected")
            self.selection_label.setStyleSheet("color: gray; font-style: italic;")
            self.view_data_button.setEnabled(False)
            self.clear_selection_button.setEnabled(False)
        else:
            # Selection
            self._selected_index = point_index
            self._selected_id = point_id

            # Build label with cluster info if available
            label_text = f"Selected: Point #{point_index + 1} (ID: {point_id})"
            if self._cluster_labels is not None and point_index < len(self._cluster_labels):
                cluster_id = int(self._cluster_labels[point_index])
                cluster_text = "Noise" if cluster_id == -1 else str(cluster_id)
                label_text += f" | Cluster: {cluster_text}"

            self.selection_label.setText(label_text)
            self.selection_label.setStyleSheet("color: green;")
            self.view_data_button.setEnabled(True)
            self.clear_selection_button.setEnabled(True)

    def _on_clear_selection_clicked(self):
        """Handle Clear Selection button click."""
        # Clear selection in the plot
        js_code = """
        var plotDiv = document.getElementsByClassName('plotly-graph-div')[0];
        if (plotDiv && typeof Plotly !== 'undefined') {
            Plotly.restyle(plotDiv, {'selectedpoints': [null]});
        }
        """
        self.web_view.page().runJavaScript(js_code)

        # Trigger deselection in UI
        self._on_point_selected(-1, "")

    def _on_view_data_clicked(self):
        """Handle View in Data Browser button click."""
        if self._selected_index is not None and self._selected_id is not None:
            self.view_in_data_browser.emit(self._selected_index, self._selected_id)

    def _on_interaction(self, action: str, selected_count: int):
        """Handle generic plot interactions from JS bridge and emit telemetry."""
        try:
            collection = getattr(self.parent(), "current_collection", "") or ""
            TelemetryService.send_event(
                "ui.visualization_interacted",
                {"metadata": {"action": action, "selected_count": int(selected_count), "collection_name": collection}},
            )
        except Exception:
            pass

    def create_plot(
        self,
        reduced_data: Any,
        current_data: dict,
        cluster_labels: Optional[Any],
        method_name: str,
    ):
        """Create and display plotly visualization.

        Args:
            reduced_data: Dimensionality-reduced embeddings (2D or 3D numpy array)
            current_data: Dictionary with 'ids', 'documents', 'embeddings', etc.
            cluster_labels: Optional array of cluster labels for coloring points
            method_name: Name of DR method (PCA, t-SNE, UMAP) for titles
        """
        if reduced_data is None or current_data is None:
            return

        # Clear previous selection when creating new plot
        self._selected_index = None
        self._selected_id = None
        self._cluster_labels = cluster_labels
        self.selection_label.setText("No point selected")
        self.selection_label.setStyleSheet("color: gray; font-style: italic;")
        self.view_data_button.setEnabled(False)
        self.clear_selection_button.setEnabled(False)

        # Show/hide selection UI based on plot type (2D vs 3D)
        is_2d = reduced_data.shape[1] == 2
        self.selection_container.setVisible(is_2d)

        # Lazy import plotly
        from vector_inspector.utils.lazy_imports import get_plotly

        go = get_plotly()

        ids = current_data.get("ids", [])
        documents = current_data.get("documents", [])

        # Store IDs for event handling
        self._current_ids = ids

        # Prepare hover text
        hover_texts = []
        for i, (id_val, doc) in enumerate(zip(ids, documents, strict=True)):
            doc_preview = str(doc)[:100] if doc else "No document"
            cluster_info = ""
            # Add cluster info if clustering was performed
            if cluster_labels is not None and i < len(cluster_labels):
                cluster_id = int(cluster_labels[i])
                cluster_info = f"<br>Cluster: {cluster_id if cluster_id >= 0 else 'Noise'}"
            hover_texts.append(f"ID: {id_val}<br>Doc: {doc_preview}{cluster_info}")

        # Determine colors
        if cluster_labels is not None:
            # Color by cluster
            colors = cluster_labels
            colorscale = "Viridis"
        else:
            # Color by index (default gradient)
            colors = list(range(len(ids)))
            colorscale = "Viridis"

        # Create plot
        if reduced_data.shape[1] == 2:
            # 2D plot
            fig = go.Figure(
                data=[
                    go.Scatter(
                        x=reduced_data[:, 0],
                        y=reduced_data[:, 1],
                        mode="markers",
                        marker={
                            "size": 8,
                            "color": colors,
                            "colorscale": colorscale,
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
                clickmode="event+select",  # Enable selection on click
            )
        else:
            # 3D plot
            fig = go.Figure(
                data=[
                    go.Scatter3d(
                        x=reduced_data[:, 0],
                        y=reduced_data[:, 1],
                        z=reduced_data[:, 2],
                        mode="markers",
                        marker={
                            "size": 5,
                            "color": colors,
                            "colorscale": colorscale,
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
                clickmode="event+select",  # Enable selection on click
            )

        # Display in embedded web view
        html = fig.to_html(include_plotlyjs="cdn")

        # Inject JavaScript for selection tracking via QWebChannel (2D plots only)
        js_injection = """
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
        <script>
            var plotBridge = null;
            var selectedPointIndex = -1;

            // Initialize QWebChannel and wait for it to be ready
            new QWebChannel(qt.webChannelTransport, function(channel) {
                plotBridge = channel.objects.plotBridge;

                // Set up Plotly selection event handlers (2D plots only)
                var plotDiv = document.getElementsByClassName('plotly-graph-div')[0];
                if (plotDiv && plotDiv.on) {
                    // Use plotly_selected for 2D plots (works with clickmode="event+select")
                    plotDiv.on('plotly_selected', function(data) {
                        if (data && data.points && data.points.length > 0) {
                            var point = data.points[0];
                            if (!point || point.pointIndex === undefined || point.pointIndex === null) {
                                return;
                            }
                            var pointIndex = point.pointIndex;
                            
                            // Toggle: if clicking same point, deselect
                            if (selectedPointIndex === pointIndex) {
                                selectedPointIndex = -1;
                                if (plotBridge && plotBridge.onPointSelected) {
                                    plotBridge.onPointSelected(-1, '');
                                }
                                return;
                            }
                            
                            selectedPointIndex = pointIndex;
                            
                            // Extract ID from hover text
                            var pointId = String(pointIndex);
                            if (point.text) {
                                var match = point.text.match(/ID:\\s*([^<\\r\\n]+)/);
                                if (match && match[1]) {
                                    pointId = match[1].trim();
                                }
                            }

                            if (plotBridge && plotBridge.onPointSelected) {
                                plotBridge.onPointSelected(pointIndex, pointId);
                            }
                            // Notify interaction bridge with selected count
                            if (plotBridge && plotBridge.onInteraction) {
                                plotBridge.onInteraction('select', data.points.length);
                            }
                        }
                    });
                    
                    // Handle explicit deselection
                    plotDiv.on('plotly_deselect', function() {
                        selectedPointIndex = -1;
                        if (plotBridge && plotBridge.onPointSelected) {
                            plotBridge.onPointSelected(-1, '');
                        }
                        if (plotBridge && plotBridge.onInteraction) {
                            plotBridge.onInteraction('select', 0);
                        }
                    });
                    
                    // Handle zoom / pan via relayout event
                    plotDiv.on('plotly_relayout', function(layout) {
                        // Basic heuristic: presence of axis range keys indicates zoom
                        var action = 'pan';
                        try {
                            if (layout['xaxis.range'] || layout['xaxis.range[0]'] || layout['yaxis.range'] || layout['xaxis.autorange'] === false) {
                                action = 'zoom';
                            }
                        } catch (e) {
                            action = 'pan';
                        }
                        if (plotBridge && plotBridge.onInteraction) {
                            plotBridge.onInteraction(action, 0);
                        }
                    });
                }
            });
        </script>
        """

        # Insert JS before closing body tag
        html = html.replace("</body>", js_injection + "</body>")

        self._current_html = html
        self.web_view.setHtml(html)

    def get_current_html(self) -> Optional[str]:
        """Get the current plot HTML for saving/export."""
        return self._current_html

    def dispose(self) -> None:
        """Explicitly dispose of WebEngine objects to avoid profile-release warnings.

        This removes the web channel, requests deletion of the page and view,
        and clears references so Qt can tear them down in the correct order.
        """
        try:
            if hasattr(self, "web_view") and self.web_view is not None:
                try:
                    page = self.web_view.page()
                    # Disconnect web channel if set on the page
                    try:
                        page.setWebChannel(None)
                    except Exception:
                        pass
                    page.deleteLater()
                except Exception:
                    pass

                try:
                    self.web_view.setParent(None)
                except Exception:
                    pass
                try:
                    self.web_view.deleteLater()
                except Exception:
                    pass
                self.web_view = None

            if hasattr(self, "channel") and self.channel is not None:
                try:
                    self.channel.deleteLater()
                except Exception:
                    pass
                self.channel = None

            if hasattr(self, "_event_bridge") and self._event_bridge is not None:
                try:
                    self._event_bridge.deleteLater()
                except Exception:
                    pass
                self._event_bridge = None
        except Exception:
            # Best-effort disposal; do not raise during app shutdown
            pass
