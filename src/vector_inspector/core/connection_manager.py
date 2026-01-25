"""Connection manager for handling multiple vector database connections."""

import uuid
from typing import Dict, Optional, List, Any
from enum import Enum
from PySide6.QtCore import QObject, Signal

from .connections.base_connection import VectorDBConnection
from vector_inspector.core.logging import log_error


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
        config: Dict[str, Any],
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
        self.connection = connection
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.active_collection: Optional[str] = None
        self.collections: List[str] = []
        self.error_message: Optional[str] = None

    def get_display_name(self) -> str:
        """Get a display-friendly connection name."""
        return f"{self.name} ({self.provider})"

    def get_breadcrumb(self) -> str:
        """Get breadcrumb showing connection > collection."""
        if self.active_collection:
            return f"{self.name} > {self.active_collection}"
        return self.name


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
        self._connections: Dict[str, ConnectionInstance] = {}
        self._active_connection_id: Optional[str] = None

    def create_connection(
        self,
        name: str,
        provider: str,
        connection: VectorDBConnection,
        config: Dict[str, Any],
        connection_id: str = None,
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

    def get_connection(self, connection_id: str) -> Optional[ConnectionInstance]:
        """Get a connection instance by ID."""
        return self._connections.get(connection_id)

    def get_active_connection(self) -> Optional[ConnectionInstance]:
        """Get the currently active connection instance."""
        if self._active_connection_id:
            return self._connections.get(self._active_connection_id)
        return None

    def get_active_connection_id(self) -> Optional[str]:
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
            instance.connection.disconnect()
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
        self, connection_id: str, state: ConnectionState, error: Optional[str] = None
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

    def update_collections(self, connection_id: str, collections: List[str]):
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

    def set_active_collection(self, connection_id: str, collection_name: Optional[str]):
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

    def get_all_connections(self) -> List[ConnectionInstance]:
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
