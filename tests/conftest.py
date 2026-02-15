import pytest

from tests.fakes.fake_provider import FakeProvider


@pytest.fixture
def fake_provider():
    """Provide a fresh FakeProvider instance for tests."""
    provider = FakeProvider()
    # Populate with a default collection for convenience
    provider.create_collection(
        "test_collection",
        ["doc1", "doc2", "doc3"],  # docs (positional)
        [{"name": "a"}, {"name": "b"}, {"name": "c"}],  # metadatas
        [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],  # embeddings
    )
    return provider


# Add a second fixture for an *empty* provider
# Useful for tests that need to assert "no collections" or "create first collection".


@pytest.fixture
def empty_fake_provider():
    return FakeProvider()


# Add a fixture that returns both provider + preloaded collection name
# This reduces magic strings in tests and keeps things DRY.


@pytest.fixture
def fake_provider_with_name():
    provider = FakeProvider()
    name = "test_collection"
    provider.create_collection(
        name,
        ["doc1", "doc2", "doc3"],  # docs (positional)
        [{"name": "a"}, {"name": "b"}, {"name": "c"}],  # metadatas
        [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],  # embeddings
    )
    return provider, name
