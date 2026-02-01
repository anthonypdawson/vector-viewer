"""Connection manager for handling multiple vector database connections."""

import uuid
from enum import Enum
from typing import Any

from PySide6.QtCore import QObject, Signal

from vector_inspector.core.logging import log_error

from .connections.base_connection import VectorDBConnection


class ConnectionState(Enum):
    """Possible connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectionInstance:
    """Represents a single active connection with its state and context."""

    def __init__(
        self,
        connection_id: str,
        name: str,
        provider: str,
        connection: VectorDBConnection,
        config: dict[str, Any],
    ):
        """
        Initialize a connection instance.

        Args:
            connection_id: Unique connection identifier
            name: User-friendly connection name
            provider: Provider type (chromadb, qdrant, etc.)
            connection: The actual connection object
            config: Connection configuration dict
        """
        self.id = connection_id
        self.name = name
        self.provider = provider
        self.database = connection
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.active_collection: str | None = None
        self.collections: list[str] = []
        self.error_message: str | None = None

        # Set profile_name on the underlying connection object so it can be used
        # for settings lookups (embedding models, etc.)
        # Note: This dynamically adds an attribute to the connection object
        self.database.profile_name = name  # type: ignore[attr-defined]

    def get_display_name(self) -> str:
        """Get a display-friendly connection name."""
        return f"{self.name} ({self.provider})"

    def get_breadcrumb(self) -> str:
        """Get breadcrumb showing connection > collection."""
        if self.active_collection:
            return f"{self.name} > {self.active_collection}"
        return self.name

    def __getattr__(self, name):
        """Forward unknown attribute lookups to the underlying database connection.

        This allows `ConnectionInstance` to act as a thin wrapper while
        exposing the provider-specific API (e.g. `get_all_items`,
        `query_collection`) without callers needing to access
        `.database` explicitly.
        """
        return getattr(self.database, name)

    # Convenience proxy methods to forward common operations to the underlying
    # VectorDBConnection. This prevents callers from needing to access
    # `instance.database` directly and centralizes error handling.
    def list_collections(self) -> list[str]:
        """Return list of collections from the underlying database connection.

        Falls back to the cached `collections` attribute on error.
        """
        try:
            return self.database.list_collections()
        except Exception:
            return self.collections or []

    def connect(self) -> bool:
        """Proxy to connect the underlying database connection."""
        return self.database.connect()

    def disconnect(self) -> None:
        """Proxy to disconnect the underlying database connection; logs errors."""
        try:
            self.database.disconnect()
        except Exception as e:
            log_error("Error disconnecting underlying database: %s", e)

    @property
    def is_connected(self) -> bool:
        """Whether the underlying database connection is currently connected."""
        return getattr(self.database, "is_connected", False)

    def get_collection_info(self, collection_name: str):
        """Proxy to get collection-specific information."""
        try:
            return self.database.get_collection_info(collection_name)
        except Exception:
            return None

    def delete_collection(self, collection_name: str) -> bool:
        """Proxy to delete a collection on the underlying database connection."""
        try:
            return self.database.delete_collection(collection_name)
        except Exception:
            return False


class ConnectionManager(QObject):
    """Manages multiple vector database connections and saved profiles.

    Signals:
        connection_opened: Emitted when a new connection is opened (connection_id)
        connection_closed: Emitted when a connection is closed (connection_id)
        connection_state_changed: Emitted when connection state changes (connection_id, state)
        active_connection_changed: Emitted when active connection changes (connection_id or None)
        active_collection_changed: Emitted when active collection changes (connection_id, collection_name or None)
        collections_updated: Emitted when collections list is updated (connection_id, collections)
    """

    # Signals
    connection_opened = Signal(str)  # connection_id
    connection_closed = Signal(str)  # connection_id
    connection_state_changed = Signal(str, ConnectionState)  # connection_id, state
    active_connection_changed = Signal(object)  # connection_id or None
    active_collection_changed = Signal(str, object)  # connection_id, collection_name or None
    collections_updated = Signal(str, list)  # connection_id, collections

    MAX_CONNECTIONS = 10  # Limit to prevent resource exhaustion

    def __init__(self):
        """Initialize the connection manager."""
        super().__init__()
        self._connections: dict[str, ConnectionInstance] = {}
        self._active_connection_id: str | None = None

    def get_active_collection(self) -> str | None:
        """
        Get the active collection name for the currently active connection.

        Returns:
            The active collection name, or None if no active connection or collection.
        """
        active_conn = self.get_active_connection()
        if active_conn:
            return active_conn.active_collection
        return None

    def create_connection(
        self,
        name: str,
        provider: str,
        connection: VectorDBConnection,
        config: dict[str, Any],
        connection_id: str | None = None,
    ) -> str:
        """
        Create a new connection instance (not yet connected).

        Args:
            name: User-friendly connection name
            provider: Provider type
            connection: The connection object
            config: Connection configuration
            connection_id: Optional. Use this ID instead of generating a new one (for profiles).

        Returns:
            The connection ID

        Raises:
            RuntimeError: If maximum connections limit reached
        """
        if len(self._connections) >= self.MAX_CONNECTIONS:
            raise RuntimeError(f"Maximum number of connections ({self.MAX_CONNECTIONS}) reached")

        if connection_id is None:
            connection_id = str(uuid.uuid4())
        instance = ConnectionInstance(connection_id, name, provider, connection, config)
        self._connections[connection_id] = instance

        # Set as active if it's the first connection
        if len(self._connections) == 1:
            self._active_connection_id = connection_id
            self.active_connection_changed.emit(connection_id)

        # Don't emit connection_opened yet - wait until actually connected
        return connection_id

    def mark_connection_opened(self, connection_id: str):
        """
        Mark a connection as opened (after successful connection).

        Args:
            connection_id: ID of connection that opened
        """
        if connection_id in self._connections:
            self.connection_opened.emit(connection_id)

    def get_connection(self, connection_id: str) -> ConnectionInstance | None:
        """Get a connection instance by ID."""
        return self._connections.get(connection_id)

    def get_active_connection(self) -> ConnectionInstance | None:
        """Get the currently active connection instance."""
        if self._active_connection_id:
            return self._connections.get(self._active_connection_id)
        return None

    def get_active_connection_id(self) -> str | None:
        """Get the currently active connection ID."""
        return self._active_connection_id

    def set_active_connection(self, connection_id: str) -> bool:
        """
        Set the active connection.

        Args:
            connection_id: ID of connection to make active

        Returns:
            True if successful, False if connection not found
        """
        if connection_id not in self._connections:
            return False

        self._active_connection_id = connection_id
        self.active_connection_changed.emit(connection_id)
        return True

    def close_connection(self, connection_id: str) -> bool:
        """
        Close and remove a connection.

        Args:
            connection_id: ID of connection to close

        Returns:
            True if successful, False if connection not found
        """
        instance = self._connections.get(connection_id)
        if not instance:
            return False

        # Disconnect the connection
        try:
            instance.disconnect()
        except Exception as e:
            log_error("Error disconnecting: %s", e)

        # Remove from connections dict
        del self._connections[connection_id]

        # If this was the active connection, set a new one or None
        if self._active_connection_id == connection_id:
            if self._connections:
                # Set first available connection as active
                self._active_connection_id = next(iter(self._connections.keys()))
                self.active_connection_changed.emit(self._active_connection_id)
            else:
                self._active_connection_id = None
                self.active_connection_changed.emit(None)

        self.connection_closed.emit(connection_id)
        return True

    def update_connection_state(
        self, connection_id: str, state: ConnectionState, error: str | None = None
    ):
        """
        Update the state of a connection.

        Args:
            connection_id: ID of connection
            state: New connection state
            error: Optional error message if state is ERROR
        """
        instance = self._connections.get(connection_id)
        if instance:
            instance.state = state
            if error:
                instance.error_message = error
            else:
                instance.error_message = None
            self.connection_state_changed.emit(connection_id, state)

    def update_collections(self, connection_id: str, collections: list[str]):
        """
        Update the collections list for a connection.

        Args:
            connection_id: ID of connection
            collections: List of collection names
        """
        instance = self._connections.get(connection_id)
        if instance:
            instance.collections = collections
            self.collections_updated.emit(connection_id, collections)

    def set_active_collection(self, connection_id: str, collection_name: str | None):
        """
        Set the active collection for a connection.

        Args:
            connection_id: ID of connection
            collection_name: Name of collection to make active, or None
        """
        instance = self._connections.get(connection_id)
        if instance:
            instance.active_collection = collection_name
            self.active_collection_changed.emit(connection_id, collection_name)

    def get_all_connections(self) -> list[ConnectionInstance]:
        """Get list of all connection instances."""
        return list(self._connections.values())

    def get_connection_count(self) -> int:
        """Get the number of active connections."""
        return len(self._connections)

    def close_all_connections(self):
        """Close all connections. Typically called on application exit."""
        connection_ids = list(self._connections.keys())
        for conn_id in connection_ids:
            self.close_connection(conn_id)

    def rename_connection(self, connection_id: str, new_name: str) -> bool:
        """
        Rename a connection.

        Args:
            connection_id: ID of connection
            new_name: New name for the connection

        Returns:
            True if successful, False if connection not found
        """
        instance = self._connections.get(connection_id)
        if instance:
            instance.name = new_name
            return True
        return False
