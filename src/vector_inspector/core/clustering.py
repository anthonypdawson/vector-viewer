"""Clustering algorithms for vector data visualization.

This module provides clustering functionality that can be used to group
similar vectors together. Basic algorithms are always available, while
advanced options are enabled in Vector Studio.
"""

import time
import uuid
from typing import Any

import numpy as np

from vector_inspector.services.telemetry_service import TelemetryService


def run_clustering(
    embeddings: np.ndarray, algorithm: str, params: dict[str, Any]
) -> tuple[np.ndarray, str]:
    """Run clustering on embeddings.

    Args:
        embeddings: Array of embeddings to cluster.
        algorithm: Name of clustering algorithm (HDBSCAN, KMeans, DBSCAN, OPTICS).
        params: Parameters for the algorithm.

    Returns:
        Tuple of (cluster_labels, algorithm_name).

    Raises:
        ValueError: If algorithm is unknown or import fails.
    """
    from vector_inspector.utils.lazy_imports import get_numpy, get_sklearn_model

    # Generate correlation ID and start timing
    correlation_id = str(uuid.uuid4())
    start_time = time.time()
    dataset_size = len(embeddings)
    success = False
    cluster_count = 0
    noise_count = 0

    try:
        np_module = get_numpy()
        X = np_module.array(embeddings)

        # Perform clustering based on algorithm
        if algorithm == "HDBSCAN":
            HDBSCAN = get_sklearn_model("HDBSCAN")
            kwargs = {
                "min_cluster_size": params.get("min_cluster_size", 5),
                "min_samples": params.get("min_samples", 5),
            }
            # Add advanced parameters if provided
            if "cluster_selection_epsilon" in params:
                kwargs["cluster_selection_epsilon"] = params["cluster_selection_epsilon"]
            if "allow_single_cluster" in params:
                kwargs["allow_single_cluster"] = params["allow_single_cluster"]
            if "metric" in params:
                kwargs["metric"] = params["metric"]
            if "alpha" in params:
                kwargs["alpha"] = params["alpha"]
            if "cluster_selection_method" in params:
                kwargs["cluster_selection_method"] = params["cluster_selection_method"]
            clusterer = HDBSCAN(**kwargs)
            labels = clusterer.fit_predict(X)

        elif algorithm == "KMeans":
            KMeans = get_sklearn_model("KMeans")
            kwargs = {"n_clusters": params.get("n_clusters", 5), "random_state": 42}
            # Add advanced parameters if provided
            if "init" in params:
                kwargs["init"] = params["init"]
            if "max_iter" in params:
                kwargs["max_iter"] = params["max_iter"]
            if "tol" in params:
                kwargs["tol"] = params["tol"]
            if "algorithm" in params:
                kwargs["algorithm"] = params["algorithm"]
            clusterer = KMeans(**kwargs)
            labels = clusterer.fit_predict(X)

        elif algorithm == "DBSCAN":
            DBSCAN = get_sklearn_model("DBSCAN")
            kwargs = {"eps": params.get("eps", 0.5), "min_samples": params.get("min_samples", 5)}
            # Add advanced parameters if provided
            if "metric" in params:
                kwargs["metric"] = params["metric"]
            if "algorithm" in params:
                kwargs["algorithm"] = params["algorithm"]
            if "leaf_size" in params:
                kwargs["leaf_size"] = params["leaf_size"]
            clusterer = DBSCAN(**kwargs)
            labels = clusterer.fit_predict(X)

        elif algorithm == "OPTICS":
            OPTICS = get_sklearn_model("OPTICS")
            kwargs = {
                "min_samples": params.get("min_samples", 5),
                "max_eps": params.get("max_eps", 10.0),
            }
            # Add advanced parameters if provided
            if "metric" in params:
                kwargs["metric"] = params["metric"]
            if "xi" in params:
                kwargs["xi"] = params["xi"]
            if "cluster_method" in params:
                kwargs["cluster_method"] = params["cluster_method"]
            if "algorithm" in params:
                kwargs["algorithm"] = params["algorithm"]
            if "leaf_size" in params:
                kwargs["leaf_size"] = params["leaf_size"]
            clusterer = OPTICS(**kwargs)
            labels = clusterer.fit_predict(X)

        else:
            raise ValueError(f"Unknown clustering algorithm: {algorithm}")

        # Calculate cluster statistics
        cluster_count = len(set(labels)) - (1 if -1 in labels else 0)
        noise_count = int((labels == -1).sum())
        success = True

        return labels, algorithm

    finally:
        duration_ms = int((time.time() - start_time) * 1000)

        # Send clustering telemetry
        try:
            # Create params summary (just key param names for privacy)
            params_summary = ",".join(sorted(params.keys()))
            telemetry = TelemetryService()
            telemetry.queue_event(
                {
                    "event_name": "clustering.run",
                    "metadata": {
                        "algorithm": algorithm,
                        "dataset_size": dataset_size,
                        "duration_ms": duration_ms,
                        "correlation_id": correlation_id,
                        "success": success,
                        "cluster_count": cluster_count,
                        "noise_count": noise_count,
                        "params_summary": params_summary,
                    },
                }
            )
            telemetry.send_batch()
        except Exception:
            pass  # Best effort telemetry
