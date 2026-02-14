"""Tests for embedding model disk caching."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from vector_inspector.core.model_cache import (
    _sanitize_model_name,
    clear_cache,
    get_cache_info,
    get_model_cache_path,
    is_cache_enabled,
    is_cached,
    load_cached_path,
    save_model_to_cache,
)


@pytest.fixture
def temp_cache_dir(monkeypatch):
    """Create a temporary cache directory for testing."""
    temp_dir = Path(tempfile.mkdtemp(prefix="test_model_cache_"))

    # Mock the cache directory getter
    monkeypatch.setattr("vector_inspector.core.model_cache.get_cache_dir", lambda: temp_dir)

    yield temp_dir

    # Cleanup
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


@pytest.fixture
def mock_settings_enabled(monkeypatch):
    """Mock settings service to enable caching."""
    mock_settings = Mock()
    mock_settings.get.return_value = True

    # Patch where SettingsService is actually imported and used
    with patch("vector_inspector.services.settings_service.SettingsService") as MockSettings:
        MockSettings.return_value = mock_settings
        yield mock_settings


def test_sanitize_model_name():
    """Test model name sanitization."""
    # Test with slashes
    assert "_" in _sanitize_model_name("openai/clip-vit-base-patch32")

    # Test with backslashes
    assert "_" in _sanitize_model_name("models\\bert\\base")

    # Test that different names produce different outputs
    name1 = _sanitize_model_name("model-a")
    name2 = _sanitize_model_name("model-b")
    assert name1 != name2


def test_get_model_cache_path(temp_cache_dir):
    """Test getting cache path for a model."""
    model_name = "test-model"
    cache_path = get_model_cache_path(model_name)

    assert cache_path.parent == temp_cache_dir
    assert "test-model" in cache_path.name or "test_model" in cache_path.name


def test_is_cached_not_exists(temp_cache_dir, mock_settings_enabled):
    """Test is_cached returns False when model not cached."""
    assert not is_cached("nonexistent-model")


def test_is_cached_with_valid_cache(temp_cache_dir, mock_settings_enabled):
    """Test is_cached returns True for valid cached model."""
    model_name = "test-model"
    cache_path = get_model_cache_path(model_name)
    cache_path.mkdir(parents=True, exist_ok=True)

    # Create metadata
    metadata = {
        "original_name": model_name,
        "model_type": "sentence-transformer",
        "cached_at": "2024-01-01T00:00:00",
    }
    metadata_file = cache_path / "cache_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f)

    # Create a dummy model file (config.json)
    config_file = cache_path / "config.json"
    config_file.write_text("{}")

    assert is_cached(model_name)


def test_is_cached_disabled(temp_cache_dir):
    """Test is_cached returns False when caching is disabled."""
    # Mock settings to disable cache
    mock_settings = Mock()
    mock_settings.get.return_value = False

    with patch("vector_inspector.services.settings_service.SettingsService") as MockSettings:
        MockSettings.return_value = mock_settings
        assert not is_cached("any-model")


def test_load_cached_path_returns_path(temp_cache_dir, mock_settings_enabled):
    """Test load_cached_path returns path for cached model."""
    model_name = "test-model"
    cache_path = get_model_cache_path(model_name)
    cache_path.mkdir(parents=True, exist_ok=True)

    # Create metadata
    metadata = {
        "original_name": model_name,
        "model_type": "sentence-transformer",
        "cached_at": "2024-01-01T00:00:00",
    }
    metadata_file = cache_path / "cache_metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f)

    # Create model file
    config_file = cache_path / "config.json"
    config_file.write_text("{}")

    result = load_cached_path(model_name)
    assert result == cache_path


def test_load_cached_path_returns_none_not_cached(temp_cache_dir, mock_settings_enabled):
    """Test load_cached_path returns None for non-cached model."""
    assert load_cached_path("nonexistent-model") is None


def test_save_model_to_cache_with_save_pretrained(temp_cache_dir, mock_settings_enabled):
    """Test saving a model that has save_pretrained method."""
    model_name = "test-model"

    # Create mock model with save_pretrained that creates files
    mock_model = Mock()

    def mock_save(path):
        # Simulate save_pretrained creating model files
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "config.json").write_text("{}")
        (Path(path) / "model.safetensors").write_bytes(b"fake model data")

    mock_model.save_pretrained = Mock(side_effect=mock_save)

    result = save_model_to_cache(mock_model, model_name, "sentence-transformer")

    assert result
    assert is_cached(model_name)
    mock_model.save_pretrained.assert_called_once()


def test_save_model_to_cache_tuple(temp_cache_dir, mock_settings_enabled):
    """Test saving a tuple (model, processor) like CLIP."""
    model_name = "test-clip-model"

    # Create mock model and processor
    mock_model = Mock()
    mock_processor = Mock()

    def mock_model_save(path):
        # Simulate model save_pretrained
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "config.json").write_text("{}")
        (Path(path) / "model.safetensors").write_bytes(b"fake model")

    def mock_processor_save(path):
        # Simulate processor save_pretrained
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "preprocessor_config.json").write_text("{}")

    mock_model.save_pretrained = Mock(side_effect=mock_model_save)
    mock_processor.save_pretrained = Mock(side_effect=mock_processor_save)

    result = save_model_to_cache((mock_model, mock_processor), model_name, "clip")

    assert result
    assert is_cached(model_name)
    mock_model.save_pretrained.assert_called_once()
    mock_processor.save_pretrained.assert_called_once()


def test_save_model_to_cache_no_method(temp_cache_dir, mock_settings_enabled):
    """Test saving a model without save_pretrained returns False."""
    model_name = "unsupported-model"

    # Create mock model without save_pretrained
    mock_model = Mock(spec=[])  # No methods

    result = save_model_to_cache(mock_model, model_name, "unknown")

    assert not result
    assert not is_cached(model_name)


def test_save_model_to_cache_disabled(temp_cache_dir):
    """Test saving does nothing when caching is disabled."""
    # Mock settings to disable cache
    mock_settings = Mock()
    mock_settings.get.return_value = False

    with patch("vector_inspector.services.settings_service.SettingsService") as MockSettings:
        MockSettings.return_value = mock_settings

        mock_model = Mock()
        mock_model.save_pretrained = Mock()

        result = save_model_to_cache(mock_model, "test-model", "sentence-transformer")

        assert not result
        mock_model.save_pretrained.assert_not_called()


def test_clear_cache_all(temp_cache_dir, mock_settings_enabled):
    """Test clearing all cached models."""
    # Create some cached models
    for i in range(3):
        model_name = f"test-model-{i}"
        cache_path = get_model_cache_path(model_name)
        cache_path.mkdir(parents=True, exist_ok=True)

        metadata = {
            "original_name": model_name,
            "model_type": "sentence-transformer",
            "cached_at": "2024-01-01T00:00:00",
        }
        metadata_file = cache_path / "cache_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

    assert temp_cache_dir.exists()

    result = clear_cache()

    assert result
    assert not temp_cache_dir.exists()


def test_clear_cache_specific_model(temp_cache_dir, mock_settings_enabled):
    """Test clearing a specific cached model."""
    model1 = "test-model-1"
    model2 = "test-model-2"

    # Create two cached models
    for model_name in [model1, model2]:
        cache_path = get_model_cache_path(model_name)
        cache_path.mkdir(parents=True, exist_ok=True)

        metadata = {
            "original_name": model_name,
            "model_type": "sentence-transformer",
            "cached_at": "2024-01-01T00:00:00",
        }
        metadata_file = cache_path / "cache_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        config_file = cache_path / "config.json"
        config_file.write_text("{}")

    assert is_cached(model1)
    assert is_cached(model2)

    # Clear only model1
    result = clear_cache(model1)

    assert result
    assert not get_model_cache_path(model1).exists()
    assert is_cached(model2)  # model2 should still exist


def test_get_cache_info_empty(temp_cache_dir, mock_settings_enabled):
    """Test get_cache_info with empty cache."""
    info = get_cache_info()

    assert info["enabled"]
    assert info["location"] == str(temp_cache_dir)
    assert info["model_count"] == 0
    assert info["total_size_mb"] == 0


def test_get_cache_info_with_models(temp_cache_dir, mock_settings_enabled):
    """Test get_cache_info with cached models."""
    # Create some cached models
    for i in range(2):
        model_name = f"test-model-{i}"
        cache_path = get_model_cache_path(model_name)
        cache_path.mkdir(parents=True, exist_ok=True)

        metadata = {
            "original_name": model_name,
            "model_type": "sentence-transformer",
            "cached_at": "2024-01-01T00:00:00",
        }
        metadata_file = cache_path / "cache_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f)

        # Create a dummy file with known size
        dummy_file = cache_path / "model.bin"
        dummy_file.write_bytes(b"x" * 1024 * 100)  # 100 KB

    info = get_cache_info()

    assert info["enabled"]
    assert info["exists"]
    assert info["model_count"] == 2
    assert info["total_size_mb"] > 0


def test_is_cache_enabled_default():
    """Test is_cache_enabled returns True by default (no settings)."""
    with patch("vector_inspector.services.settings_service.SettingsService") as mock_service:
        mock_service.side_effect = Exception("No settings")
        assert is_cache_enabled()


def test_atomic_save_on_error(temp_cache_dir, mock_settings_enabled):
    """Test that failed save doesn't leave partial cache."""
    model_name = "failing-model"
    cache_path = get_model_cache_path(model_name)

    # Create mock model that fails during save
    mock_model = Mock()
    mock_model.save_pretrained = Mock(side_effect=Exception("Save failed"))

    result = save_model_to_cache(mock_model, model_name, "sentence-transformer")

    assert not result
    # No partial cache should exist
    assert not cache_path.exists() or not (cache_path / "cache_metadata.json").exists()
