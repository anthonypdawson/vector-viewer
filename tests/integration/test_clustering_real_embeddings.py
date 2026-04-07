"""Integration tests for clustering using real sklearn on synthetic embeddings.

These tests verify that the clustering pipeline produces meaningful results
(at least one non-noise cluster) on well-separated synthetic data, without
mocking the clustering implementation.  This guards against regressions
where parameter changes cause all points to be classified as noise.
"""

import numpy as np


def _make_clusterable_embeddings(n_per_cluster: int = 10, n_clusters: int = 3, dims: int = 8, seed: int = 0):
    """Build clearly separated cluster blobs in `dims`-dimensional space.

    Each cluster centre is spaced `cluster_sep` apart so HDBSCAN, DBSCAN,
    KMeans, and OPTICS all find the structure without parameter tuning.
    """
    rng = np.random.RandomState(seed)
    cluster_sep = 20.0
    centres = rng.randn(n_clusters, dims) * cluster_sep
    noise_scale = 0.1
    chunks = [centres[i] + rng.randn(n_per_cluster, dims) * noise_scale for i in range(n_clusters)]
    return np.vstack(chunks)


# ──────────────────────────────────────────────────────────────────────────────
# Real KMeans
# ──────────────────────────────────────────────────────────────────────────────


class TestKMeansRealEmbeddings:
    """KMeans on well-separated blobs must recover all clusters."""

    def _run(self, embeddings, n_clusters=3):
        from vector_inspector.core.clustering import run_clustering

        labels, algo = run_clustering(embeddings, "KMeans", {"n_clusters": n_clusters})
        return labels, algo

    def test_finds_correct_number_of_clusters(self):
        embeddings = _make_clusterable_embeddings(n_per_cluster=10, n_clusters=3)
        labels, algo = self._run(embeddings, n_clusters=3)

        assert algo == "KMeans"
        # All 30 points must be assigned (KMeans never produces −1 noise)
        assert -1 not in labels
        unique_labels = set(labels)
        assert len(unique_labels) == 3

    def test_all_points_assigned(self):
        embeddings = _make_clusterable_embeddings(n_per_cluster=5, n_clusters=2)
        labels, _ = self._run(embeddings, n_clusters=2)

        # KMeans assigns every point to a cluster
        assert len(labels) == 10
        assert all(l >= 0 for l in labels)

    def test_consistent_across_runs(self):
        embeddings = _make_clusterable_embeddings(n_per_cluster=8, n_clusters=3)
        labels_a, _ = self._run(embeddings, n_clusters=3)
        labels_b, _ = self._run(embeddings, n_clusters=3)

        # Cluster membership must be identical (same data, deterministic init default)
        # We compare sorted per-cluster sizes rather than raw labels to be
        # invariant to label permutation.
        sizes_a = sorted(np.bincount(labels_a).tolist())
        sizes_b = sorted(np.bincount(labels_b).tolist())
        assert sizes_a == sizes_b


# ──────────────────────────────────────────────────────────────────────────────
# Real HDBSCAN — most likely to produce "all noise" if params are wrong
# ──────────────────────────────────────────────────────────────────────────────


class TestHDBSCANRealEmbeddings:
    """HDBSCAN on well-separated blobs must yield at least one real cluster."""

    def _run(self, embeddings, **params):
        from vector_inspector.core.clustering import run_clustering

        defaults = {"min_cluster_size": 3, "min_samples": 1}
        defaults.update(params)
        labels, algo = run_clustering(embeddings, "HDBSCAN", defaults)
        return labels, algo

    def test_produces_at_least_one_non_noise_cluster(self):
        embeddings = _make_clusterable_embeddings(n_per_cluster=12, n_clusters=3)
        labels, algo = self._run(embeddings)

        assert algo == "HDBSCAN"
        non_noise = [l for l in labels if l != -1]
        assert len(non_noise) > 0, "All points were classified as noise — check HDBSCAN params"

    def test_noise_points_are_minority(self):
        embeddings = _make_clusterable_embeddings(n_per_cluster=15, n_clusters=3)
        labels, _ = self._run(embeddings)

        noise_count = sum(1 for l in labels if l == -1)
        total = len(labels)
        # With well-separated blobs, fewer than 20 % should be noise
        assert noise_count / total < 0.2, f"Too many noise points: {noise_count}/{total}"

    def test_recovers_expected_cluster_count(self):
        """HDBSCAN should find approximately n_clusters real cluster ids."""
        n_clusters = 4
        embeddings = _make_clusterable_embeddings(n_per_cluster=10, n_clusters=n_clusters)
        labels, _ = self._run(embeddings)

        real_cluster_ids = {l for l in labels if l >= 0}
        assert len(real_cluster_ids) >= n_clusters - 1, (
            f"Expected ~{n_clusters} clusters, found {len(real_cluster_ids)}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Real DBSCAN
# ──────────────────────────────────────────────────────────────────────────────


class TestDBSCANRealEmbeddings:
    def test_produces_non_noise_clusters(self):
        from vector_inspector.core.clustering import run_clustering

        embeddings = _make_clusterable_embeddings(n_per_cluster=10, n_clusters=3, dims=4)
        labels, algo = run_clustering(embeddings, "DBSCAN", {"eps": 0.5, "min_samples": 2})

        assert algo == "DBSCAN"
        non_noise = [l for l in labels if l != -1]
        assert len(non_noise) > 0, "DBSCAN classified all points as noise"


# ──────────────────────────────────────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────────────────────────────────────


class TestClusteringEdgeCases:
    def test_single_point_kmeans(self):
        """Single-point collection should not crash KMeans (n_clusters=1)."""
        from vector_inspector.core.clustering import run_clustering

        embeddings = np.array([[1.0, 2.0, 3.0]])
        labels, algo = run_clustering(embeddings, "KMeans", {"n_clusters": 1})
        assert len(labels) == 1
        assert labels[0] == 0

    def test_image_like_512d_embeddings_kmeans(self):
        """Verify clustering works on 512-dim CLIP-like embeddings (image ingestion output)."""
        from vector_inspector.core.clustering import run_clustering

        # Simulate 30 images from 3 groups embedded with CLIP (512-dim)
        embeddings = _make_clusterable_embeddings(n_per_cluster=10, n_clusters=3, dims=512)
        labels, algo = run_clustering(embeddings, "KMeans", {"n_clusters": 3})

        assert algo == "KMeans"
        assert len(set(labels)) == 3

    def test_document_like_384d_embeddings_hdbscan(self):
        """Verify clustering works on 384-dim MiniLM-like embeddings (document ingestion output)."""
        from vector_inspector.core.clustering import run_clustering

        embeddings = _make_clusterable_embeddings(n_per_cluster=10, n_clusters=3, dims=384)
        labels, algo = run_clustering(embeddings, "HDBSCAN", {"min_cluster_size": 3, "min_samples": 1})

        assert algo == "HDBSCAN"
        non_noise = [l for l in labels if l != -1]
        assert len(non_noise) > 0
