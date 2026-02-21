"""Tests for ConnectionManager using FakeProvider."""

import pytest

from vector_inspector.core.connection_manager import (
    ConnectionManager,
    ConnectionState,
)


def test_create_connection(fake_provider):
    """Test creating a new connection."""
    manager = ConnectionManager()

    conn_id = manager.create_connection(
        name="test_conn",
        provider="fake",
        connection=fake_provider,
        config={"test": "config"},
    )

    assert conn_id is not None
    assert manager.get_connection_count() == 1

    instance = manager.get_connection(conn_id)
    assert instance is not None
    assert instance.name == "test_conn"
    assert instance.provider == "fake"
    assert instance.state == ConnectionState.DISCONNECTED


def test_first_connection_becomes_active(fake_provider):
    """Test that first connection automatically becomes active."""
    manager = ConnectionManager()

    conn_id = manager.create_connection(
        name="first_conn",
        provider="fake",
        connection=fake_provider,
        config={},
    )

    assert manager.get_active_connection_id() == conn_id
    assert manager.get_active_connection() is not None
    assert manager.get_active_connection().name == "first_conn"


def test_switching_providers(fake_provider, empty_fake_provider):
    """Test switching between multiple providers."""
    manager = ConnectionManager()

    # Create first connection
    conn1_id = manager.create_connection(
        name="provider1",
        provider="fake1",
        connection=fake_provider,
        config={},
    )

    # Create second connection
    conn2_id = manager.create_connection(
        name="provider2",
        provider="fake2",
        connection=empty_fake_provider,
        config={},
    )

    assert manager.get_connection_count() == 2
    assert manager.get_active_connection_id() == conn1_id

    # Switch to second provider
    success = manager.set_active_connection(conn2_id)
    assert success is True
    assert manager.get_active_connection_id() == conn2_id
    assert manager.get_active_connection().name == "provider2"

    # Switch back to first
    success = manager.set_active_connection(conn1_id)
    assert success is True
    assert manager.get_active_connection_id() == conn1_id


def test_connection_state_management(fake_provider):
    """Test updating connection states."""
    manager = ConnectionManager()

    conn_id = manager.create_connection(
        name="test",
        provider="fake",
        connection=fake_provider,
        config={},
    )

    instance = manager.get_connection(conn_id)
    assert instance.state == ConnectionState.DISCONNECTED

    # Update to connecting
    manager.update_connection_state(conn_id, ConnectionState.CONNECTING)
    assert instance.state == ConnectionState.CONNECTING

    # Update to connected
    manager.update_connection_state(conn_id, ConnectionState.CONNECTED)
    assert instance.state == ConnectionState.CONNECTED

    # Update to error with message
    manager.update_connection_state(conn_id, ConnectionState.ERROR, "Test error")
    assert instance.state == ConnectionState.ERROR
    assert instance.error_message == "Test error"


def test_reconnect_logic(fake_provider):
    """Test connection, disconnection, and reconnection."""
    manager = ConnectionManager()

    conn_id = manager.create_connection(
        name="test",
        provider="fake",
        connection=fake_provider,
        config={},
    )

    instance = manager.get_connection(conn_id)

    # Connect
    success = instance.connect()
    assert success is True
    assert instance.is_connected is True
    manager.update_connection_state(conn_id, ConnectionState.CONNECTED)

    # Disconnect
    instance.disconnect()
    assert instance.is_connected is False
    manager.update_connection_state(conn_id, ConnectionState.DISCONNECTED)

    # Reconnect
    success = instance.connect()
    assert success is True
    assert instance.is_connected is True


def test_collection_stats(fake_provider_with_name):
    """Test getting collection stats through ConnectionInstance."""
    provider, collection_name = fake_provider_with_name
    manager = ConnectionManager()

    conn_id = manager.create_connection(
        name="test",
        provider="fake",
        connection=provider,
        config={},
    )

    instance = manager.get_connection(conn_id)

    # Get collection info
    info = instance.get_collection_info(collection_name)
    assert info is not None
    assert info["name"] == collection_name
    assert info["count"] == 3
    assert "metadata_fields" in info


def test_update_collections_list(fake_provider_with_name):
    """Test updating collections list for a connection."""
    provider, collection_name = fake_provider_with_name
    manager = ConnectionManager()

    conn_id = manager.create_connection(
        name="test",
        provider="fake",
        connection=provider,
        config={},
    )

    instance = manager.get_connection(conn_id)

    # Get collections from provider
    collections = provider.list_collections()
    assert collection_name in collections

    # Update manager's collection list
    manager.update_collections(conn_id, collections)
    assert instance.collections == collections
    assert collection_name in instance.collections


def test_set_active_collection(fake_provider_with_name):
    """Test setting active collection for a connection."""
    provider, collection_name = fake_provider_with_name
    manager = ConnectionManager()

    conn_id = manager.create_connection(
        name="test",
        provider="fake",
        connection=provider,
        config={},
    )

    instance = manager.get_connection(conn_id)
    assert instance.active_collection is None

    # Set active collection
    manager.set_active_collection(conn_id, collection_name)
    assert instance.active_collection == collection_name

    # Clear active collection
    manager.set_active_collection(conn_id, None)
    assert instance.active_collection is None


def test_close_connection(fake_provider, empty_fake_provider):
    """Test closing a connection."""
    manager = ConnectionManager()

    conn1_id = manager.create_connection("conn1", "fake", fake_provider, {})
    conn2_id = manager.create_connection("conn2", "fake", empty_fake_provider, {})

    assert manager.get_connection_count() == 2

    # Close first connection
    success = manager.close_connection(conn1_id)
    assert success is True
    assert manager.get_connection_count() == 1
    assert manager.get_connection(conn1_id) is None

    # Active connection should switch to the remaining one
    assert manager.get_active_connection_id() == conn2_id


def test_close_active_connection_switches_to_next(fake_provider, empty_fake_provider):
    """Test that closing active connection switches to another."""
    manager = ConnectionManager()

    conn1_id = manager.create_connection("conn1", "fake", fake_provider, {})
    conn2_id = manager.create_connection("conn2", "fake", empty_fake_provider, {})

    # conn1 is active by default (first created)
    assert manager.get_active_connection_id() == conn1_id

    # Close active connection
    manager.close_connection(conn1_id)

    # Should switch to conn2
    assert manager.get_active_connection_id() == conn2_id
    assert manager.get_active_connection().name == "conn2"


def test_close_all_connections(fake_provider, empty_fake_provider):
    """Test closing all connections."""
    manager = ConnectionManager()

    manager.create_connection("conn1", "fake", fake_provider, {})
    manager.create_connection("conn2", "fake", empty_fake_provider, {})

    assert manager.get_connection_count() == 2

    manager.close_all_connections()

    assert manager.get_connection_count() == 0
    assert manager.get_active_connection() is None
    assert manager.get_active_connection_id() is None


def test_max_connections_limit(fake_provider):
    """Test that maximum connections limit is enforced."""
    manager = ConnectionManager()

    # Create up to max connections
    for i in range(manager.MAX_CONNECTIONS):
        manager.create_connection(f"conn{i}", "fake", fake_provider, {})

    assert manager.get_connection_count() == manager.MAX_CONNECTIONS

    # Try to create one more - should raise RuntimeError
    with pytest.raises(RuntimeError, match="Maximum number of connections"):
        manager.create_connection("overflow", "fake", fake_provider, {})


def test_connection_instance_proxy_methods(fake_provider_with_name):
    """Test that ConnectionInstance proxies methods to underlying provider."""
    provider, collection_name = fake_provider_with_name
    manager = ConnectionManager()

    conn_id = manager.create_connection("test", "fake", provider, {})
    instance = manager.get_connection(conn_id)

    # Test list_collections proxy
    collections = instance.list_collections()
    assert collection_name in collections

    # Test get_collection_info proxy
    info = instance.get_collection_info(collection_name)
    assert info is not None
    assert info["count"] == 3

    # Test query_collection through __getattr__ proxy
    result = instance.query_collection(collection_name, n_results=2)
    assert result is not None
    assert len(result["ids"]) == 2


def test_rename_connection(fake_provider):
    """Test renaming a connection."""
    manager = ConnectionManager()

    conn_id = manager.create_connection("original_name", "fake", fake_provider, {})
    instance = manager.get_connection(conn_id)
    assert instance.name == "original_name"

    # Rename
    success = manager.rename_connection(conn_id, "new_name")
    assert success is True
    assert instance.name == "new_name"

    # Try to rename non-existent connection
    success = manager.rename_connection("fake_id", "whatever")
    assert success is False


def test_get_breadcrumb(fake_provider_with_name):
    """Test breadcrumb generation for connection instances."""
    provider, collection_name = fake_provider_with_name
    manager = ConnectionManager()

    conn_id = manager.create_connection("MyConnection", "fake", provider, {})
    instance = manager.get_connection(conn_id)

    # Without active collection
    breadcrumb = instance.get_breadcrumb()
    assert breadcrumb == "MyConnection"

    # With active collection
    manager.set_active_collection(conn_id, collection_name)
    breadcrumb = instance.get_breadcrumb()
    assert breadcrumb == f"MyConnection > {collection_name}"


def test_error_paths(fake_provider):
    """Test error handling paths."""
    manager = ConnectionManager()

    # Get non-existent connection
    assert manager.get_connection("fake_id") is None

    # Set non-existent connection as active
    success = manager.set_active_connection("fake_id")
    assert success is False

    # Close non-existent connection
    success = manager.close_connection("fake_id")
    assert success is False

    # Update state of non-existent connection (should not crash)
    manager.update_connection_state("fake_id", ConnectionState.CONNECTED)

    # Update collections of non-existent connection (should not crash)
    manager.update_collections("fake_id", ["col1", "col2"])


def test_connection_instance_delete_collection(fake_provider_with_name):
    """Test deleting a collection through ConnectionInstance."""
    provider, collection_name = fake_provider_with_name
    manager = ConnectionManager()

    conn_id = manager.create_connection("test", "fake", provider, {})
    instance = manager.get_connection(conn_id)

    # Verify collection exists
    assert collection_name in provider.list_collections()

    # Delete through ConnectionInstance
    success = instance.delete_collection(collection_name)
    assert success is True

    # Verify it's gone
    assert collection_name not in provider.list_collections()
