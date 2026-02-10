"""Plot panel for displaying vector visualizations."""

from typing import Any, Optional

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget


class PlotPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_html = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.web_view = QWebEngineView()
        layout.addWidget(self.web_view, stretch=10)
        self.setLayout(layout)

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

        # Lazy import plotly
        from vector_inspector.utils.lazy_imports import get_plotly

        go = get_plotly()

        ids = current_data.get("ids", [])
        documents = current_data.get("documents", [])

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
            )

        # Display in embedded web view
        html = fig.to_html(include_plotlyjs="cdn")
        self._current_html = html
        self.web_view.setHtml(html)

    def get_current_html(self) -> Optional[str]:
        """Get the current plot HTML for saving/export."""
        return self._current_html
