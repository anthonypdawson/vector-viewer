import numpy as np

from vector_inspector.services.cluster_runner import ClusterRunner


def test_cluster_runner_stats_and_centers_and_assignment():
    cr = ClusterRunner()
    labels = np.array([0, 0, 1, -1])
    embeddings = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.5, 0.5]])

    stats = cr.get_cluster_stats(labels)
    assert stats["n_clusters"] == 2
    assert stats["n_noise"] == 1

    summary = cr.format_summary(labels, "kmeans")
    assert "clusters" in summary

    centers = cr.get_cluster_centers(embeddings, labels)
    assert 0 in centers and 1 in centers

    emb = np.array([1.0, 0.0])
    assigned = cr.assign_to_nearest_cluster(emb, centers)
    assert assigned in centers
