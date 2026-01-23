"""
Cache manager for storing databrowser and search panel state by database and collection.
Provides fast switching between collections with automatic invalidation on refresh or settings changes.
"""
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CacheEntry:
    """Represents a cached state for a specific database and collection."""
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Browser state
    scroll_position: int = 0
    selected_indices: list = field(default_factory=list)
    
    # Search panel state
    search_query: str = ""
    search_filters: Dict[str, Any] = field(default_factory=dict)
    search_results: Optional[Any] = None
    
    # User inputs
    user_inputs: Dict[str, Any] = field(default_factory=dict)


class CacheManager:
    """
    Manages cache for databrowser and search panel by (database, collection) key.
    Supports invalidation on refresh or settings changes.
    """
    
    def __init__(self):
        self._cache: Dict[Tuple[str, str], CacheEntry] = {}
        self._enabled = True
        
    def get(self, database: str, collection: str) -> Optional[CacheEntry]:
        """Retrieve cached entry for a database and collection."""
        if not self._enabled:
            return None
        
        key = (database, collection)
        return self._cache.get(key)
    
    def set(self, database: str, collection: str, entry: CacheEntry) -> None:
        """Store a cache entry for a database and collection."""
        if not self._enabled:
            return
        
        key = (database, collection)
        entry.timestamp = datetime.now()
        self._cache[key] = entry
    
    def update(self, database: str, collection: str, **kwargs) -> None:
        """Update specific fields in an existing cache entry."""
        key = (database, collection)
        if key in self._cache:
            entry = self._cache[key]
            for field_name, value in kwargs.items():
                if hasattr(entry, field_name):
                    setattr(entry, field_name, value)
            entry.timestamp = datetime.now()
        else:
            # Create new entry with provided fields
            entry = CacheEntry(data=None)
            for field_name, value in kwargs.items():
                if hasattr(entry, field_name):
                    setattr(entry, field_name, value)
            self._cache[key] = entry
    
    def invalidate(self, database: Optional[str] = None, collection: Optional[str] = None) -> None:
        """
        Invalidate cache entries.
        - If both database and collection are provided, invalidate that specific entry.
        - If only database is provided, invalidate all collections in that database.
        - If neither is provided, invalidate all entries (global refresh).
        """
        if database is None and collection is None:
            # Clear all cache
            self._cache.clear()
        elif collection is None and database is not None:
            # Clear all collections in the specified database
            keys_to_remove = [key for key in self._cache.keys() if key[0] == database]
            for key in keys_to_remove:
                del self._cache[key]
        elif database is not None and collection is not None:
            # Clear specific database/collection combination
            key = (database, collection)
            if key in self._cache:
                del self._cache[key]
    
    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
    
    def enable(self) -> None:
        """Enable caching."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable caching and clear all entries."""
        self._enabled = False
        self._cache.clear()
    
    def is_enabled(self) -> bool:
        """Check if caching is enabled."""
        return self._enabled
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about the current cache state."""
        return {
            "enabled": self._enabled,
            "entry_count": len(self._cache),
            "entries": [
                {
                    "database": db,
                    "collection": coll,
                    "timestamp": entry.timestamp.isoformat(),
                    "has_data": entry.data is not None,
                    "has_search_results": entry.search_results is not None,
                }
                for (db, coll), entry in self._cache.items()
            ]
        }


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
        # Initialize from settings
        try:
            from vector_inspector.services.settings_service import SettingsService
            settings = SettingsService()
            if not settings.get_cache_enabled():
                _cache_manager.disable()
        except Exception:
            # If settings can't be loaded, default to enabled
            pass
    return _cache_manager


def invalidate_cache_on_settings_change() -> None:
    """Invalidate all cache when settings change."""
    cache = get_cache_manager()
    cache.invalidate()


def invalidate_cache_on_refresh(database: Optional[str] = None, collection: Optional[str] = None) -> None:
    """Invalidate cache on refresh action."""
    cache = get_cache_manager()
    cache.invalidate(database, collection)