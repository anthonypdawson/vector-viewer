"""Service for persisting application settings."""

import base64
import json
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, Signal

from vector_inspector.core.cache_manager import invalidate_cache_on_settings_change
from vector_inspector.core.logging import log_error


class SettingsService:
    """Handles loading and saving application settings.

    This should be owned by AppState to ensure a single instance per application.
    Legacy code may still create instances directly, but new code should use app_state.settings_service.

    Uses singleton pattern to ensure only one instance exists, preventing state inconsistencies
    when code creates instances directly vs using AppState.
    """

    _instance: Optional["SettingsService"] = None

    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize settings service (only runs once due to singleton)."""
        # Skip if already initialized (check instance dict only, not class dict)
        if "_initialized" in self.__dict__:
            return
        self._initialized = True

        # Expose a shared QObject-based signal emitter so UI can react to
        # settings changes without polling.
        class _Signals(QObject):
            setting_changed = Signal(str, object)

        self.signals = _Signals()

        self.settings_dir = Path.home() / ".vector-inspector"
        self.settings_file = self.settings_dir / "settings.json"
        self.settings: dict[str, Any] = {}
        self._load_settings()

    def _load_settings(self):
        """Load settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, encoding="utf-8") as f:
                    self.settings = json.load(f)
        except Exception as e:
            log_error("Failed to load settings: %s", e)
            self.settings = {}

    def _save_settings(self):
        """Save settings to file."""
        try:
            # Create settings directory if it doesn't exist
            self.settings_dir.mkdir(parents=True, exist_ok=True)

            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log_error("Failed to save settings: %s", e)

    def get_last_connection(self) -> Optional[dict[str, Any]]:
        """Get the last connection configuration."""
        return self.settings.get("last_connection")

    def save_last_connection(self, config: dict[str, Any]):
        """Save the last connection configuration."""
        self.settings["last_connection"] = config
        self._save_settings()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)

    # Convenience accessors for common settings
    def get_breadcrumb_enabled(self) -> bool:
        return bool(self.settings.get("breadcrumb.enabled", True))

    def set_breadcrumb_enabled(self, enabled: bool):
        self.set("breadcrumb.enabled", bool(enabled))

    def get_breadcrumb_elide_mode(self) -> str:
        return str(self.settings.get("breadcrumb.elide_mode", "left"))

    def set_breadcrumb_elide_mode(self, mode: str):
        if mode not in ("left", "middle"):
            mode = "left"
        self.set("breadcrumb.elide_mode", mode)

    def get_default_n_results(self) -> int:
        return int(self.settings.get("search.default_n_results", 10))

    def set_default_n_results(self, n: int):
        self.set("search.default_n_results", int(n))

    def get_auto_generate_embeddings(self) -> bool:
        return bool(self.settings.get("embeddings.auto_generate", True))

    def set_auto_generate_embeddings(self, enabled: bool):
        self.set("embeddings.auto_generate", bool(enabled))

    def get_window_restore_geometry(self) -> bool:
        return bool(self.settings.get("window.restore_geometry", True))

    def set_window_restore_geometry(self, enabled: bool):
        self.set("window.restore_geometry", bool(enabled))

    def set_window_geometry(self, geometry_bytes: bytes):
        """Save window geometry as base64 string."""
        try:
            if isinstance(geometry_bytes, str):
                # assume base64 already
                b64 = geometry_bytes
            else:
                b64 = base64.b64encode(bytes(geometry_bytes)).decode("ascii")
            self.set("window.geometry", b64)
        except Exception as e:
            log_error("Failed to set window geometry: %s", e)

    def get_window_geometry(self) -> Optional[bytes]:
        """Return geometry bytes or None."""
        try:
            b64 = self.settings.get("window.geometry")
            if not b64:
                return None
            return base64.b64decode(b64)
        except Exception as e:
            log_error("Failed to get window geometry: %s", e)
            return None

    def get_cache_enabled(self) -> bool:
        """Get whether caching is enabled (default: True)."""
        return self.settings.get("cache_enabled", True)

    def set_cache_enabled(self, enabled: bool):
        """Set whether caching is enabled.

        NOTE: The cache_manager state should be updated by AppState or MainWindow,
        not directly by SettingsService (to avoid circular dependency).
        """
        self.set("cache_enabled", enabled)
        # Cache manager state will be updated by the caller (AppState or MainWindow)
        # who has access to both settings_service and cache_manager

    def get_telemetry_enabled(self) -> bool:
        """Get whether telemetry is enabled (default: True)."""
        return bool(self.settings.get("telemetry.enabled", True))

    def set_telemetry_enabled(self, enabled: bool):
        """Set whether telemetry is enabled."""
        self.set("telemetry.enabled", bool(enabled))

    def set(self, key: str, value: Any):
        """Set a setting value."""
        self.settings[key] = value
        self._save_settings()
        # Invalidate cache when settings change (only if cache is enabled)
        if key != "cache_enabled":  # Don't invalidate when toggling cache itself
            invalidate_cache_on_settings_change()
        # Emit change signal for UI/reactive components
        try:
            # Emit the raw python object (value) for convenience
            self.signals.setting_changed.emit(key, value)
        except Exception:
            pass

    def clear(self):
        """Clear all settings."""
        self.settings = {}
        self._save_settings()

    def save_embedding_model(
        self,
        profile_name: str,
        collection_name: str,
        model_name: str,
        model_type: str = "user-configured",
    ):
        """Save embedding model mapping for a collection.

        Args:
            profile_name: Profile/connection name
            collection_name: Collection name
            model_name: Embedding model name (e.g., 'sentence-transformers/all-MiniLM-L6-v2')
            model_type: Type of configuration ('user-configured', 'auto-detected', 'stored')
        """
        if "collection_embedding_models" not in self.settings:
            self.settings["collection_embedding_models"] = {}

        collection_key = f"{profile_name}:{collection_name}"
        self.settings["collection_embedding_models"][collection_key] = {
            "model": model_name,
            "type": model_type,
            "timestamp": self._get_timestamp(),
        }
        self._save_settings()

    def get_embedding_model(
        self,
        profile_name: str,
        collection_name: str,
    ) -> Optional[dict[str, Any]]:
        """Get embedding model mapping for a collection.

        Args:
            profile_name: Profile/connection name
            collection_name: Collection name

        Returns:
            Dictionary with 'model', 'type', and 'timestamp' or None
        """
        collection_models = self.settings.get("collection_embedding_models", {})
        collection_key = f"{profile_name}:{collection_name}"
        return collection_models.get(collection_key)

    def remove_embedding_model(
        self,
        profile_name: str,
        collection_name: str,
    ):
        """Remove embedding model mapping for a collection.

        Args:
            profile_name: Profile/connection name
            collection_name: Collection name
        """
        if "collection_embedding_models" not in self.settings:
            return

        collection_key = f"{profile_name}:{collection_name}"
        self.settings["collection_embedding_models"].pop(collection_key, None)
        self._save_settings()

    def remove_profile_settings(self, profile_name: str):
        """Remove all settings for a profile (e.g., when profile is deleted).

        Args:
            profile_name: Profile/connection name
        """
        if "collection_embedding_models" not in self.settings:
            return

        # Remove all keys that start with profile_name:
        prefix = f"{profile_name}:"
        keys_to_remove = [key for key in self.settings["collection_embedding_models"] if key.startswith(prefix)]

        for key in keys_to_remove:
            self.settings["collection_embedding_models"].pop(key, None)

        if keys_to_remove:
            self._save_settings()
            from vector_inspector.core.logging import log_info

            log_info(
                "Removed %d embedding model settings for profile: %s",
                len(keys_to_remove),
                profile_name,
            )

    def _get_timestamp(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime

        return datetime.now().isoformat()

    def add_custom_embedding_model(
        self,
        model_name: str,
        dimension: int,
        model_type: str = "sentence-transformer",
        description: str = "Custom model",
    ):
        """Add a custom embedding model to the known models list.

        Args:
            model_name: Name of the embedding model
            dimension: Vector dimension
            model_type: Type of model (e.g., 'sentence-transformer', 'clip', 'openai')
            description: Brief description of the model
        """
        if "custom_embedding_models" not in self.settings:
            self.settings["custom_embedding_models"] = []

        # Check if already exists
        for model in self.settings["custom_embedding_models"]:
            if model["name"] == model_name and model["dimension"] == dimension:
                # Update existing entry
                model["type"] = model_type
                model["description"] = description
                model["last_used"] = self._get_timestamp()
                self._save_settings()
                return

        # Add new entry
        self.settings["custom_embedding_models"].append(
            {
                "name": model_name,
                "dimension": dimension,
                "type": model_type,
                "description": description,
                "added": self._get_timestamp(),
                "last_used": self._get_timestamp(),
            }
        )
        self._save_settings()

    def get_custom_embedding_models(self, dimension: Optional[int] = None) -> list[dict[str, Any]]:
        """Get list of custom embedding models.

        Args:
            dimension: Optional filter by dimension

        Returns:
            List of custom model dictionaries
        """
        models = self.settings.get("custom_embedding_models", [])
        if dimension is not None:
            return [m for m in models if m["dimension"] == dimension]
        return models

    def remove_custom_embedding_model(self, model_name: str, dimension: int):
        """Remove a custom embedding model.

        Args:
            model_name: Name of the model to remove
            dimension: Vector dimension
        """
        if "custom_embedding_models" not in self.settings:
            return

        self.settings["custom_embedding_models"] = [
            m
            for m in self.settings["custom_embedding_models"]
            if not (m["name"] == model_name and m["dimension"] == dimension)
        ]
        self._save_settings()

    def get_embedding_cache_enabled(self) -> bool:
        """Get whether embedding model disk caching is enabled.

        Returns:
            True if caching is enabled (default), False otherwise
        """
        return self.settings.get("embedding_cache_enabled", True)

    def set_embedding_cache_enabled(self, enabled: bool):
        """Set whether embedding model disk caching is enabled.

        Args:
            enabled: True to enable caching, False to disable
        """
        self.set("embedding_cache_enabled", enabled)

    def get_embedding_cache_dir(self) -> Optional[str]:
        """Get custom embedding cache directory path.

        Returns:
            Custom cache directory path, or None for default
        """
        return self.settings.get("embedding_cache_dir")

    def set_embedding_cache_dir(self, path: Optional[str]):
        """Set custom embedding cache directory path.

        Args:
            path: Directory path, or None to use default
        """
        if path:
            self.set("embedding_cache_dir", str(path))
        else:
            # Remove the key to use default
            self.settings.pop("embedding_cache_dir", None)
            self._save_settings()
