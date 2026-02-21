"""Clustering service for vector clustering operations."""

from typing import Any, Optional

import numpy as np

from vector_inspector.core.logging import log_error


class ClusterRunner:
    """
    Service for executing clustering algorithms on vectors.

    Responsibilities:
        - Run clustering algorithms (KMeans, DBSCAN, HDBSCAN, etc.)
        - Format clustering results
        - Calculate cluster statistics
    """

    def __init__(self) -> None:
        """Initialize cluster runner."""
        pass

    def cluster(
        self,
        embeddings: np.ndarray,
        algorithm: str = "kmeans",
        params: Optional[dict[str, Any]] = None,
    ) -> tuple[np.ndarray, str]:
        """
        Run clustering on embeddings.

        Args:
            embeddings: Array of embeddings (n_samples, n_features)
            algorithm: Clustering algorithm name
            params: Algorithm-specific parameters

        Returns:
            Tuple of (cluster_labels, algorithm_name)
        """
        if params is None:
            params = {}

        try:
            from vector_inspector.core.clustering import run_clustering

            labels, algo_name = run_clustering(embeddings, algorithm, params)
            return labels, algo_name

        except Exception as e:
            log_error(f"Clustering failed: {e}")
            raise

    def get_cluster_stats(self, labels: np.ndarray) -> dict[str, Any]:
        """
        Calculate statistics about clustering results.

        Args:
            labels: Cluster labels array

        Returns:
            Dictionary with cluster statistics
        """
        unique_labels = np.unique(labels)
        n_clusters = len(unique_labels[unique_labels >= 0])  # Exclude noise (-1)
        n_noise = np.sum(labels == -1)

        # Calculate cluster sizes
        cluster_sizes = {}
        for label in unique_labels:
            if label >= 0:  # Exclude noise
                cluster_sizes[int(label)] = int(np.sum(labels == label))

        stats = {
            "n_clusters": n_clusters,
            "n_noise": n_noise,
            "n_total": len(labels),
            "cluster_sizes": cluster_sizes,
            "noise_ratio": n_noise / len(labels) if len(labels) > 0 else 0.0,
        }

        return stats

    def format_summary(self, labels: np.ndarray, algorithm: str) -> str:
        """
        Format a human-readable summary of clustering results.

        Args:
            labels: Cluster labels array
            algorithm: Algorithm name

        Returns:
            Summary string
        """
        stats = self.get_cluster_stats(labels)

        n_clusters = stats["n_clusters"]
        n_noise = stats["n_noise"]

        if n_noise > 0:
            return f"Found {n_clusters} clusters, {n_noise} noise points ({algorithm})"
        return f"Found {n_clusters} clusters ({algorithm})"

    def get_cluster_centers(
        self, embeddings: np.ndarray, labels: np.ndarray
    ) -> dict[int, np.ndarray]:
        """
        Calculate cluster centroids.

        Args:
            embeddings: Array of embeddings
            labels: Cluster labels

        Returns:
            Dictionary mapping cluster label to centroid
        """
        unique_labels = np.unique(labels)
        centers = {}

        for label in unique_labels:
            if label >= 0:  # Exclude noise
                mask = labels == label
                centers[int(label)] = np.mean(embeddings[mask], axis=0)

        return centers

    def assign_to_nearest_cluster(
        self, embedding: np.ndarray, cluster_centers: dict[int, np.ndarray]
    ) -> int:
        """
        Assign a single embedding to nearest cluster.

        Args:
            embedding: Single embedding vector
            cluster_centers: Dictionary of cluster centroids

        Returns:
            Cluster label (or -1 if no clusters)
        """
        if not cluster_centers:
            return -1

        min_dist = float("inf")
        nearest_label = -1

        for label, center in cluster_centers.items():
            dist = np.linalg.norm(embedding - center)
            if dist < min_dist:
                min_dist = dist
                nearest_label = label

        return nearest_label
