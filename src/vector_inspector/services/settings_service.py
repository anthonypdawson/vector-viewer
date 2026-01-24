"""Service for persisting application settings."""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from vector_inspector.core.cache_manager import invalidate_cache_on_settings_change


class SettingsService:
    """Handles loading and saving application settings."""
    
    def __init__(self):
        """Initialize settings service."""
        self.settings_dir = Path.home() / ".vector-inspector"
        self.settings_file = self.settings_dir / "settings.json"
        self.settings: Dict[str, Any] = {}
        self._load_settings()
    
    def _load_settings(self):
        """Load settings from file."""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
        except Exception as e:
            print(f"Failed to load settings: {e}")
            self.settings = {}
    
    def _save_settings(self):
        """Save settings to file."""
        try:
            # Create settings directory if it doesn't exist
            self.settings_dir.mkdir(parents=True, exist_ok=True)
            
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save settings: {e}")
    
    def get_last_connection(self) -> Optional[Dict[str, Any]]:
        """Get the last connection configuration."""
        return self.settings.get("last_connection")
    
    def save_last_connection(self, config: Dict[str, Any]):
        """Save the last connection configuration."""
        self.settings["last_connection"] = config
        self._save_settings()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self.settings.get(key, default)
    
    def get_cache_enabled(self) -> bool:
        """Get whether caching is enabled (default: True)."""
        return self.settings.get("cache_enabled", True)
    
    def set_cache_enabled(self, enabled: bool):
        """Set whether caching is enabled."""
        self.set("cache_enabled", enabled)
        # Update cache manager state
        from vector_inspector.core.cache_manager import get_cache_manager
        cache = get_cache_manager()
        if enabled:
            cache.enable()
        else:
            cache.disable()
    
    def set(self, key: str, value: Any):
        """Set a setting value."""
        self.settings[key] = value
        self._save_settings()
        # Invalidate cache when settings change (only if cache is enabled)
        if key != "cache_enabled":  # Don't invalidate when toggling cache itself
            invalidate_cache_on_settings_change()
    
    def clear(self):
        """Clear all settings."""
        self.settings = {}
        self._save_settings()
    
    def save_embedding_model(self, connection_id: str, collection_name: str, model_name: str, model_type: str = "user-configured"):
        """Save embedding model mapping for a collection.
        
        Args:
            connection_id: Connection identifier
            collection_name: Collection name
            model_name: Embedding model name (e.g., 'sentence-transformers/all-MiniLM-L6-v2')
            model_type: Type of configuration ('user-configured', 'auto-detected', 'stored')
        """
        if "collection_embedding_models" not in self.settings:
            self.settings["collection_embedding_models"] = {}
        
        collection_key = f"{connection_id}:{collection_name}"
        self.settings["collection_embedding_models"][collection_key] = {
            "model": model_name,
            "type": model_type,
            "timestamp": self._get_timestamp()
        }
        self._save_settings()
    
    def get_embedding_model(self, connection_id: str, collection_name: str) -> Optional[Dict[str, Any]]:
        """Get embedding model mapping for a collection.
        
        Args:
            connection_id: Connection identifier
            collection_name: Collection name
            
        Returns:
            Dictionary with 'model', 'type', and 'timestamp' or None
        """
        collection_models = self.settings.get("collection_embedding_models", {})
        collection_key = f"{connection_id}:{collection_name}"
        return collection_models.get(collection_key)
    
    def remove_embedding_model(self, connection_id: str, collection_name: str):
        """Remove embedding model mapping for a collection.
        
        Args:
            connection_id: Connection identifier
            collection_name: Collection name
        """
        if "collection_embedding_models" not in self.settings:
            return
        
        collection_key = f"{connection_id}:{collection_name}"
        self.settings["collection_embedding_models"].pop(collection_key, None)
        self._save_settings()
    
    def _get_timestamp(self) -> str:
        """Get current timestamp as ISO string."""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def add_custom_embedding_model(self, model_name: str, dimension: int, model_type: str = "sentence-transformer", description: str = "Custom model"):
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
        self.settings["custom_embedding_models"].append({
            "name": model_name,
            "dimension": dimension,
            "type": model_type,
            "description": description,
            "added": self._get_timestamp(),
            "last_used": self._get_timestamp()
        })
        self._save_settings()
    
    def get_custom_embedding_models(self, dimension: Optional[int] = None) -> List[Dict[str, Any]]:
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
            m for m in self.settings["custom_embedding_models"]
            if not (m["name"] == model_name and m["dimension"] == dimension)
        ]
        self._save_settings()
