"""Service for persisting application settings."""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class SettingsService:
    """Handles loading and saving application settings."""
    
    def __init__(self):
        """Initialize settings service."""
        self.settings_dir = Path.home() / ".vector-viewer"
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
    
    def set(self, key: str, value: Any):
        """Set a setting value."""
        self.settings[key] = value
        self._save_settings()
    
    def clear(self):
        """Clear all settings."""
        self.settings = {}
        self._save_settings()
