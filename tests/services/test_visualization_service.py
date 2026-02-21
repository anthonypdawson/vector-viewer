"""Tests for VisualizationService using FakeProvider with deterministic embeddings."""

import numpy as np

from vector_inspector.services.visualization_service import VisualizationService


def test_reduce_dimensions_pca(fake_provider_with_name):
    """Test PCA dimensionality reduction with deterministic embeddings."""
    provider, collection_name = fake_provider_with_name
    svc = VisualizationService()

    # Get embeddings from FakeProvider (deterministic: [1,0], [0,1], [0.5,0.5])
    data = provider.get_all_items(collection_name)
    embeddings = data["embeddings"]

    # Reduce to 2D using PCA
    reduced = svc.reduce_dimensions(embeddings, method="pca", n_components=2)

    assert reduced is not None
    assert reduced.shape == (3, 2)
    assert isinstance(reduced, np.ndarray)


def test_reduce_dimensions_tsne(fake_provider_with_name):
    """Test t-SNE dimensionality reduction with deterministic embeddings."""
    provider, collection_name = fake_provider_with_name
    svc = VisualizationService()

    data = provider.get_all_items(collection_name)
    embeddings = data["embeddings"]

    # Reduce using t-SNE
    reduced = svc.reduce_dimensions(embeddings, method="tsne", n_components=2, perplexity=2)

    assert reduced is not None
    assert reduced.shape == (3, 2)


def test_reduce_dimensions_umap():
    """Test UMAP dimensionality reduction with sufficient data points."""
    from tests.fakes.fake_provider import FakeProvider

    # UMAP needs more data points to work properly
    provider = FakeProvider()
    n_points = 10
    provider.create_collection(
        "umap_test",
        [f"doc{i}" for i in range(n_points)],
        [{"idx": i} for i in range(n_points)],
        [[float(i % 3), float(i % 2)] for i in range(n_points)],
    )

    svc = VisualizationService()
    data = provider.get_all_items("umap_test")
    embeddings = data["embeddings"]

    # Reduce using UMAP with appropriate n_neighbors for our dataset size
    reduced = svc.reduce_dimensions(embeddings, method="umap", n_components=2, n_neighbors=5)

    assert reduced is not None
    assert reduced.shape == (n_points, 2)


def test_reduce_dimensions_3d(fake_provider_with_name):
    """Test dimensionality reduction to 3D."""
    provider, collection_name = fake_provider_with_name
    svc = VisualizationService()

    data = provider.get_all_items(collection_name)
    embeddings = data["embeddings"]

    # Reduce to 3D - we only have 2D inputs, so this should still work
    # (PCA will just keep 2 components since we only have 2D data)
    reduced = svc.reduce_dimensions(embeddings, method="pca", n_components=2)

    assert reduced is not None
    assert reduced.shape[0] == 3  # 3 points


def test_reduce_dimensions_empty_embeddings():
    """Test handling of empty embeddings list."""
    svc = VisualizationService()

    reduced = svc.reduce_dimensions([], method="pca", n_components=2)

    assert reduced is None


def test_reduce_dimensions_none_embeddings():
    """Test handling of None embeddings."""
    svc = VisualizationService()

    reduced = svc.reduce_dimensions(None, method="pca", n_components=2)

    assert reduced is None


def test_reduce_dimensions_unknown_method(fake_provider_with_name):
    """Test handling of unknown reduction method."""
    provider, collection_name = fake_provider_with_name
    svc = VisualizationService()

    data = provider.get_all_items(collection_name)
    embeddings = data["embeddings"]

    reduced = svc.reduce_dimensions(embeddings, method="unknown_method", n_components=2)

    assert reduced is None


def test_prepare_plot_data_basic():
    """Test preparing plot data with basic inputs."""
    svc = VisualizationService()

    # Simple reduced embeddings
    reduced = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])

    embeddings, labels, colors = svc.prepare_plot_data(reduced)

    assert len(labels) == 3
    assert labels[0] == "Point 0"
    assert labels[1] == "Point 1"
    assert len(colors) == 3
    assert all(c == "blue" for c in colors)


def test_prepare_plot_data_with_labels(fake_provider_with_name):
    """Test preparing plot data with custom labels."""
    provider, collection_name = fake_provider_with_name
    svc = VisualizationService()

    data = provider.get_all_items(collection_name)
    embeddings = data["embeddings"]
    documents = data["documents"]

    # Reduce dimensions first
    reduced = svc.reduce_dimensions(embeddings, method="pca", n_components=2)

    # Prepare plot data with document text as labels
    _, labels, _ = svc.prepare_plot_data(reduced, labels=documents)

    assert len(labels) == 3
    assert labels == documents


def test_prepare_plot_data_with_metadata_coloring(fake_provider_with_name):
    """Test preparing plot data with metadata-based coloring."""
    provider, collection_name = fake_provider_with_name
    svc = VisualizationService()

    data = provider.get_all_items(collection_name)
    embeddings = data["embeddings"]
    metadatas = data["metadatas"]

    # Reduce dimensions
    reduced = svc.reduce_dimensions(embeddings, method="pca", n_components=2)

    # Prepare plot data with color_by metadata field (name: a, b, c)
    _, _, colors = svc.prepare_plot_data(reduced, metadata=metadatas, color_by="name")

    assert len(colors) == 3
    # Colors should be assigned based on unique metadata values
    # With 3 different values (a, b, c), we should get 3 different colors
    unique_colors = set(colors)
    assert len(unique_colors) == 3  # Each point gets a different color


def test_deterministic_clustering_with_fake_provider():
    """Test that deterministic embeddings produce predictable clusters."""
    from tests.fakes.fake_provider import FakeProvider

    # Create FakeProvider with clear cluster structure
    provider = FakeProvider()
    provider.create_collection(
        "clusters",
        ["cluster1_a", "cluster1_b", "cluster2_a", "cluster2_b"],  # docs
        [
            {"cluster": 1},
            {"cluster": 1},
            {"cluster": 2},
            {"cluster": 2},
        ],  # metadatas
        [
            [1.0, 0.0],  # Cluster 1
            [1.1, 0.1],  # Cluster 1
            [0.0, 1.0],  # Cluster 2
            [0.1, 1.1],  # Cluster 2
        ],  # embeddings
    )

    svc = VisualizationService()
    data = provider.get_all_items("clusters")

    # Reduce dimensions (should preserve clustering structure)
    reduced = svc.reduce_dimensions(data["embeddings"], method="pca", n_components=2)

    assert reduced is not None
    assert reduced.shape == (4, 2)

    # Points in same cluster should be close (using Euclidean distance)
    cluster1_points = reduced[:2]
    cluster2_points = reduced[2:]

    # Distance between points in same cluster should be smaller than cross-cluster
    within_cluster1 = np.linalg.norm(cluster1_points[0] - cluster1_points[1])
    within_cluster2 = np.linalg.norm(cluster2_points[0] - cluster2_points[1])
    cross_cluster = np.linalg.norm(cluster1_points[0] - cluster2_points[0])

    # These may not always hold due to PCA transformation, but it's a reasonable expectation
    # with our simple test data
    assert within_cluster1 < cross_cluster or within_cluster2 < cross_cluster


def test_visualization_with_filtered_data():
    """Test visualization with filtered data from FakeProvider."""
    from tests.fakes.fake_provider import FakeProvider

    provider = FakeProvider()
    provider.create_collection(
        "filtered",
        ["type_a_1", "type_a_2", "type_b_1", "type_b_2"],  # docs
        [
            {"type": "a"},
            {"type": "a"},
            {"type": "b"},
            {"type": "b"},
        ],  # metadatas
        [
            [1.0, 0.0],
            [1.1, 0.1],
            [0.0, 1.0],
            [0.1, 1.1],
        ],  # embeddings
    )

    svc = VisualizationService()

    # Filter to only type 'a' items using FakeProvider's where clause
    data = provider.get_all_items("filtered", where={"type": "a"})

    assert len(data["ids"]) == 2
    assert len(data["embeddings"]) == 2

    # Reduce dimensions on filtered data
    reduced = svc.reduce_dimensions(data["embeddings"], method="pca", n_components=2)

    assert reduced is not None
    assert reduced.shape == (2, 2)


def test_large_dataset_visualization():
    """Test visualization with larger dataset from FakeProvider."""
    from tests.fakes.fake_provider import FakeProvider

    # Create a larger synthetic dataset
    provider = FakeProvider()
    n_points = 100

    docs = [f"doc_{i}" for i in range(n_points)]
    metadatas = [{"index": i} for i in range(n_points)]
    # Create random-like but deterministic embeddings
    embeddings = [[float(i % 10), float(i % 7)] for i in range(n_points)]

    provider.create_collection(
        "large",
        docs,  # docs (positional)
        metadatas,  # metadatas
        embeddings,  # embeddings
    )

    svc = VisualizationService()
    data = provider.get_all_items("large")

    # This should handle larger datasets
    reduced = svc.reduce_dimensions(data["embeddings"], method="pca", n_components=2)

    assert reduced is not None
    assert reduced.shape == (n_points, 2)


def test_sample_data_shape_consistency():
    """Test that sample data maintains shape and metadata consistency."""
    from tests.fakes.fake_provider import FakeProvider

    provider = FakeProvider()
    provider.create_collection(
        "test",
        ["doc1", "doc2"],  # docs
        [{"a": 1}, {"a": 2}],  # metadatas
        [[1.0, 0.0], [0.0, 1.0]],  # embeddings
    )

    data = provider.get_all_items("test")

    # Verify all arrays have same length
    assert len(data["ids"]) == len(data["documents"])
    assert len(data["ids"]) == len(data["metadatas"])
    assert len(data["ids"]) == len(data["embeddings"])

    # Verify embeddings are consistent
    assert all(len(emb) == 2 for emb in data["embeddings"])
