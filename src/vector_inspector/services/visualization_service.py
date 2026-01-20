"""Visualization service for dimensionality reduction."""

from typing import Optional, List, Tuple
import numpy as np
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import umap


class VisualizationService:
    """Service for vector dimensionality reduction and visualization."""
    
    @staticmethod
    def reduce_dimensions(
        embeddings: List[List[float]],
        method: str = "pca",
        n_components: int = 2,
        **kwargs
    ) -> Optional[np.ndarray]:
        """
        Reduce dimensionality of embeddings.
        
        Args:
            embeddings: List of embedding vectors
            method: Reduction method ('pca', 'tsne', or 'umap')
            n_components: Target number of dimensions (2 or 3)
            **kwargs: Additional method-specific parameters
            
        Returns:
            Reduced embeddings as numpy array, or None if failed
        """
        if embeddings is None or len(embeddings) == 0:
            return None
            
        try:
            X = np.array(embeddings)
            
            if method == "pca":
                reducer = PCA(n_components=n_components)
                reduced = reducer.fit_transform(X)
                
            elif method == "tsne":
                perplexity = kwargs.get("perplexity", min(30, len(embeddings) - 1))
                reducer = TSNE(
                    n_components=n_components,
                    perplexity=perplexity,
                    random_state=42
                )
                reduced = reducer.fit_transform(X)
                
            elif method == "umap":
                n_neighbors = kwargs.get("n_neighbors", min(15, len(embeddings) - 1))
                reducer = umap.UMAP(
                    n_components=n_components,
                    n_neighbors=n_neighbors,
                    random_state=42
                )
                reduced = reducer.fit_transform(X)
                
            else:
                print(f"Unknown method: {method}")
                return None
                
            return reduced
            
        except Exception as e:
            print(f"Dimensionality reduction failed: {e}")
            return None
    
    @staticmethod
    def prepare_plot_data(
        reduced_embeddings: np.ndarray,
        labels: Optional[List[str]] = None,
        metadata: Optional[List[dict]] = None,
        color_by: Optional[str] = None
    ) -> Tuple[np.ndarray, List[str], List[str]]:
        """
        Prepare data for plotting.
        
        Args:
            reduced_embeddings: Reduced dimension embeddings
            labels: Text labels for each point
            metadata: Metadata dictionaries for each point
            color_by: Metadata field to use for coloring
            
        Returns:
            Tuple of (embeddings, labels, colors)
        """
        n_points = len(reduced_embeddings)
        
        # Prepare labels
        if labels is None:
            labels = [f"Point {i}" for i in range(n_points)]
        
        # Prepare colors
        colors = ["blue"] * n_points
        if color_by and metadata:
            unique_values = set()
            values = []
            for meta in metadata:
                value = meta.get(color_by, "unknown")
                values.append(str(value))
                unique_values.add(str(value))
            
            # Map values to colors
            color_map = {}
            color_palette = [
                "red", "blue", "green", "orange", "purple",
                "cyan", "magenta", "yellow", "pink", "brown"
            ]
            for i, val in enumerate(sorted(unique_values)):
                color_map[val] = color_palette[i % len(color_palette)]
            
            colors = [color_map[val] for val in values]
        
        return reduced_embeddings, labels, colors
