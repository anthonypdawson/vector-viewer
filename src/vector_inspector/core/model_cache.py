"""Disk-based cache for embedding models to speed up repeated loads.

This module provides persistent caching of embedding models that support
local save/load operations (e.g., sentence-transformers, HuggingFace transformers).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from vector_inspector.core.logging import log_error, log_info


def _get_default_cache_dir() -> Path:
    """Get default cache directory (~/.vector-inspector/embed_cache)."""
    return Path.home() / ".vector-inspector" / "embed_cache"


def _sanitize_model_name(model_name: str) -> str:
    """Convert model name to safe directory name.

    Args:
        model_name: Original model name (e.g., "openai/clip-vit-base-patch32")

    Returns:
        Safe directory name (e.g., "openai_clip-vit-base-patch32")
    """
    # Replace path separators and special chars with underscores
    safe = model_name.replace("/", "_").replace("\\", "_").replace(":", "_")
    # Also create a short hash for uniqueness in case of collisions
    name_hash = hashlib.md5(model_name.encode()).hexdigest()[:8]
    return f"{safe}_{name_hash}"


def get_cache_dir() -> Path:
    """Get the configured cache directory.

    Returns:
        Path to cache directory (may not exist yet)
    """
    try:
        from vector_inspector.services.settings_service import SettingsService

        settings = SettingsService()
        custom_dir = settings.get("embedding_cache_dir")
        if custom_dir:
            return Path(custom_dir)
    except Exception:
        pass
    return _get_default_cache_dir()


def ensure_cache_dir() -> Path:
    """Ensure cache directory exists and return it.

    Returns:
        Path to cache directory
    """
    cache_dir = get_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def is_cache_enabled() -> bool:
    """Check if model caching is enabled in settings.

    Returns:
        True if caching is enabled, False otherwise
    """
    try:
        from vector_inspector.services.settings_service import SettingsService

        settings = SettingsService()
        return settings.get("embedding_cache_enabled", True)
    except Exception:
        return True  # Default to enabled


def get_model_cache_path(model_name: str) -> Path:
    """Get cache path for a specific model.

    Args:
        model_name: Name of the model

    Returns:
        Path where model should be cached
    """
    cache_dir = ensure_cache_dir()
    safe_name = _sanitize_model_name(model_name)
    return cache_dir / safe_name


def is_cached(model_name: str) -> bool:
    """Check if a model is already cached.

    Args:
        model_name: Name of the model

    Returns:
        True if model is cached and valid
    """
    if not is_cache_enabled():
        return False

    cache_path = get_model_cache_path(model_name)

    # Check if directory exists and has metadata
    if not cache_path.exists() or not cache_path.is_dir():
        return False

    metadata_file = cache_path / "cache_metadata.json"
    if not metadata_file.exists():
        return False

    try:
        with open(metadata_file, encoding="utf-8") as f:
            metadata = json.load(f)

        # Verify it's the right model
        if metadata.get("original_name") != model_name:
            return False

        # Check if model files exist (config.json is a good indicator)
        config_file = cache_path / "config.json"
        if not config_file.exists():
            # Some models might not have config.json, check for other files
            has_model_files = any(cache_path.glob("*.bin")) or any(cache_path.glob("*.safetensors"))
            if not has_model_files:
                return False

        return True
    except Exception as e:
        log_error(f"Error checking cache for {model_name}: {e}")
        return False


def load_cached_path(model_name: str) -> Optional[Path]:
    """Get path to cached model if it exists.

    Args:
        model_name: Name of the model

    Returns:
        Path to cached model directory, or None if not cached
    """
    if not is_cache_enabled():
        return None

    if is_cached(model_name):
        cache_path = get_model_cache_path(model_name)
        log_info(f"Using cached model: {model_name} from {cache_path}")

        # Update last accessed time
        try:
            _update_access_time(cache_path)
        except Exception:
            pass

        return cache_path

    return None


def _update_access_time(cache_path: Path):
    """Update the last accessed timestamp in metadata.

    Args:
        cache_path: Path to cached model directory
    """
    metadata_file = cache_path / "cache_metadata.json"
    if not metadata_file.exists():
        return

    try:
        with open(metadata_file, encoding="utf-8") as f:
            metadata = json.load(f)

        metadata["last_accessed"] = datetime.now().isoformat()

        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    except Exception as e:
        log_error(f"Failed to update access time: {e}")


def save_model_to_cache(model: Any, model_name: str, model_type: str = "unknown") -> bool:
    """Save a model to cache using its save_pretrained or similar method.

    Args:
        model: The loaded model object
        model_name: Original model name/identifier
        model_type: Type of model ("sentence-transformer", "clip", etc.)

    Returns:
        True if successfully cached, False otherwise
    """
    if not is_cache_enabled():
        return False

    try:
        cache_path = get_model_cache_path(model_name)

        # Use atomic save: write to temp dir first, then rename
        temp_dir = Path(tempfile.mkdtemp(prefix="model_cache_", dir=cache_path.parent))

        try:
            # Try to save the model
            saved = False

            # Method 1: save_pretrained (transformers, sentence-transformers)
            if hasattr(model, "save_pretrained"):
                model.save_pretrained(str(temp_dir))
                saved = True
                log_info(f"Cached model using save_pretrained: {model_name}")

            # Method 2: save (for some torch models)
            elif hasattr(model, "save"):
                model.save(str(temp_dir))
                saved = True
                log_info(f"Cached model using save: {model_name}")

            # Method 3: For tuples (e.g., CLIP model + processor)
            elif isinstance(model, tuple) and len(model) == 2:
                model_obj, processor = model
                if hasattr(model_obj, "save_pretrained") and hasattr(processor, "save_pretrained"):
                    model_obj.save_pretrained(str(temp_dir))
                    # Save processor in subdirectory to avoid conflicts
                    processor_dir = temp_dir / "processor"
                    processor_dir.mkdir(exist_ok=True)
                    processor.save_pretrained(str(processor_dir))
                    saved = True
                    log_info(f"Cached model and processor: {model_name}")

            if not saved:
                log_info(f"Model {model_name} does not support caching (no save_pretrained method)")
                shutil.rmtree(temp_dir)
                return False

            # Write metadata
            metadata = {
                "original_name": model_name,
                "model_type": model_type,
                "cached_at": datetime.now().isoformat(),
                "last_accessed": datetime.now().isoformat(),
            }

            metadata_file = temp_dir / "cache_metadata.json"
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2)

            # Atomic move: remove old cache if exists, then rename temp to final
            if cache_path.exists():
                shutil.rmtree(cache_path)

            temp_dir.rename(cache_path)
            log_info(f"Successfully cached model: {model_name} to {cache_path}")
            return True

        except Exception as e:
            log_error(f"Failed to cache model {model_name}: {e}")
            # Clean up temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            return False

    except Exception as e:
        log_error(f"Error setting up cache for {model_name}: {e}")
        return False


def clear_cache(model_name: Optional[str] = None) -> bool:
    """Clear cached models.

    Args:
        model_name: If provided, clear only this model. If None, clear all.

    Returns:
        True if successfully cleared
    """
    try:
        cache_dir = get_cache_dir()

        if not cache_dir.exists():
            log_info("Cache directory does not exist, nothing to clear")
            return True

        if model_name:
            # Clear specific model
            cache_path = get_model_cache_path(model_name)
            if cache_path.exists():
                shutil.rmtree(cache_path)
                log_info(f"Cleared cache for model: {model_name}")
            else:
                log_info(f"Model not cached: {model_name}")
            return True

        # Clear all models
        shutil.rmtree(cache_dir)
        log_info(f"Cleared all model cache at: {cache_dir}")
        return True

    except Exception as e:
        log_error(f"Failed to clear cache: {e}")
        return False


def get_cache_info() -> dict[str, Any]:
    """Get information about the cache.

    Returns:
        Dictionary with cache statistics
    """
    cache_dir = get_cache_dir()

    if not cache_dir.exists():
        return {
            "enabled": is_cache_enabled(),
            "location": str(cache_dir),
            "exists": False,
            "model_count": 0,
            "total_size_mb": 0,
        }

    try:
        # Count models and calculate size
        model_count = 0
        total_size = 0

        for item in cache_dir.iterdir():
            if item.is_dir():
                # Check if it's a valid cache entry
                metadata_file = item / "cache_metadata.json"
                if metadata_file.exists():
                    model_count += 1
                    # Calculate directory size
                    total_size += sum(f.stat().st_size for f in item.rglob("*") if f.is_file())

        return {
            "enabled": is_cache_enabled(),
            "location": str(cache_dir),
            "exists": True,
            "model_count": model_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }
    except Exception as e:
        log_error(f"Error getting cache info: {e}")
        return {
            "enabled": is_cache_enabled(),
            "location": str(cache_dir),
            "exists": True,
            "model_count": 0,
            "total_size_mb": 0,
            "error": str(e),
        }
