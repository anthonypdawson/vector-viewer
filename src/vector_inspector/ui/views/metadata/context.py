"""Context and state management for metadata view operations."""

from dataclasses import dataclass, field
from typing import Any, Optional

# Type aliases using modern built-in generic types (PEP 585)
MetadataDict = dict[str, Any]
FilterList = list[dict[str, Any]]


@dataclass
class MetadataContext:
    """Encapsulates state for metadata view operations.

    This context object reduces coupling between metadata view components
    and makes testing easier by providing a clear data boundary.
    """

    # Connection and collection info
    connection: Any  # ConnectionInstance
    current_database: str = ""
    current_collection: str = ""

    # Data state
    current_data: Optional[MetadataDict] = None
    current_data_full: Optional[MetadataDict] = None  # For client-side filtered data

    # Pagination state
    page_size: int = 50
    current_page: int = 0

    # Filter state
    client_filters: FilterList = field(default_factory=list)
    server_filter: Optional[dict[str, Any]] = None

    # UI selection state
    _select_id_after_load: Optional[str] = None

    # Cache manager
    cache_manager: Any = None

    def reset_pagination(self) -> None:
        """Reset pagination to first page."""
        self.current_page = 0

    def reset_data(self) -> None:
        """Clear all data state."""
        self.current_data = None
        self.current_data_full = None
        self._select_id_after_load = None

    def invalidate_cache(self) -> None:
        """Invalidate cache for current collection."""
        if self.cache_manager and self.current_database and self.current_collection:
            self.cache_manager.invalidate(self.current_database, self.current_collection)

    def get_item_count(self) -> int:
        """Get count of items in current data."""
        if not self.current_data:
            return 0
        ids = self.current_data.get("ids", [])
        return len(ids) if ids else 0

    def has_data(self) -> bool:
        """Check if context has loaded data."""
        return self.current_data is not None and bool(self.current_data.get("ids"))

    def set_collection(self, collection: str, database: str = "") -> None:
        """Set current collection and reset state."""
        self.current_collection = collection
        if database:
            self.current_database = database
        self.reset_data()
        self.reset_pagination()
