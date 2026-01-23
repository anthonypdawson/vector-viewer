# Multi-Database Support - Developer Guide

## Architecture Overview

The multi-database support is built on several key components that work together to provide seamless management of multiple vector database connections.

### Core Components

#### 1. ConnectionManager (`core/connection_manager.py`)

The central coordinator for all database connections.

**Key Responsibilities:**
- Manages a dictionary of active `ConnectionInstance` objects
- Tracks the currently active connection
- Tracks the active collection for each connection
- Enforces connection limits (default: 10)
- Emits signals for UI updates

**Key Methods:**
```python
create_connection(name, provider, connection, config) -> str
get_connection(connection_id) -> Optional[ConnectionInstance]
get_active_connection() -> Optional[ConnectionInstance]
set_active_connection(connection_id) -> bool
set_active_collection(connection_id, collection_name)
close_connection(connection_id) -> bool
```

**Signals:**
```python
connection_opened(connection_id)
connection_closed(connection_id)
connection_state_changed(connection_id, state)
active_connection_changed(connection_id)
active_collection_changed(connection_id, collection_name)
collections_updated(connection_id, collections)
```

#### 2. ConnectionInstance (`core/connection_manager.py`)

Represents a single active database connection.

**Properties:**
- `id`: Unique UUID identifier
- `name`: User-friendly display name
- `provider`: Provider type (chromadb, qdrant, etc.)
- `connection`: The actual VectorDBConnection instance
- `config`: Connection configuration dict
- `state`: Current connection state (disconnected, connecting, connected, error)
- `active_collection`: Currently selected collection name
- `collections`: List of available collections
- `error_message`: Last error message if any

#### 3. ProfileService (`services/profile_service.py`)

Manages saved connection profiles.

**Key Methods:**
```python
create_profile(name, provider, config, credentials) -> str
get_profile(profile_id) -> Optional[ConnectionProfile]
get_all_profiles() -> List[ConnectionProfile]
update_profile(profile_id, name, config, credentials) -> bool
delete_profile(profile_id) -> bool
duplicate_profile(profile_id, new_name) -> Optional[str]
get_profile_with_credentials(profile_id) -> Optional[Dict]
migrate_legacy_connection(config) -> str
```

**Storage:**
- Non-sensitive data: `~/.vector-inspector/profiles.json`
- Credentials: System keychain

#### 4. CredentialService (`services/credential_service.py`)

Handles secure credential storage using system keychains.

**Supported Backends:**
- Windows: Credential Manager
- macOS: Keychain Access
- Linux: Secret Service (libsecret)

**Key Methods:**
```python
store_credentials(profile_id, credentials) -> bool
get_credentials(profile_id) -> Optional[dict]
delete_credentials(profile_id) -> bool
is_keyring_available() -> bool
```

### UI Components

#### 1. ConnectionManagerPanel (`ui/components/connection_manager_panel.py`)

Displays and manages active connections in a tree view.

**Features:**
- Shows all open connections with status indicators
- Expands to show collections under each connection
- Highlights active connection and collection
- Context menu for connection actions
- Drag-and-drop reordering (coming soon)

#### 2. ProfileManagerPanel (`ui/components/profile_manager_panel.py`)

Manages saved connection profiles.

**Features:**
- Lists all saved profiles
- Create, edit, delete, duplicate profiles
- Quick connect via double-click
- Import/export profiles

#### 3. MainWindowMultiDB (`ui/main_window_multi.py`)

The main application window with multi-database support.

**Key Differences from Legacy:**
- Uses ConnectionManager instead of single connection
- Context switching updates all views
- Breadcrumb shows active connection > collection
- Left panel has tabs for Active connections and Profiles

## Data Flow

### Connecting to a Profile

```
User clicks "Connect" on profile
    ↓
Profile data loaded (including credentials from keychain)
    ↓
Connection object created (ChromaDBConnection, QdrantConnection, etc.)
    ↓
ConnectionManager.create_connection() called
    ↓
Connection registered with unique ID
    ↓
Background thread starts connection
    ↓
On success: State → CONNECTED, collections loaded
    ↓
ConnectionManagerPanel updates UI
    ↓
If first connection: automatically set as active
```

### Switching Active Connection

```
User clicks connection in ConnectionManagerPanel
    ↓
ConnectionManager.set_active_connection(id)
    ↓
Signal: active_connection_changed(id)
    ↓
MainWindow receives signal
    ↓
All views updated with new connection
    ↓
Breadcrumb updated
    ↓
If connection has active collection: views load that collection
```

### Selecting a Collection

```
User clicks collection in ConnectionManagerPanel
    ↓
ConnectionManager.set_active_collection(conn_id, coll_name)
    ↓
Signal: active_collection_changed(conn_id, coll_name)
    ↓
MainWindow receives signal
    ↓
If connection is active: all views updated with collection
    ↓
Breadcrumb updated to show conn > collection
```

## Extending the System

### Adding a New Provider

1. **Create Connection Class** in `core/connections/`:

```python
from .base_connection import VectorDBConnection

class NewDBConnection(VectorDBConnection):
    def __init__(self, **kwargs):
        self._client = None
        # Store connection parameters
    
    def connect(self) -> bool:
        # Implement connection logic
        pass
    
    # Implement all abstract methods...
```

2. **Export in `__init__.py`**:

```python
from .new_db_connection import NewDBConnection
__all__ = [..., "NewDBConnection"]
```

3. **Update UI** in `ProfileEditorDialog` and `MainWindowMultiDB`:

```python
# Add to provider combo
self.provider_combo.addItem("NewDB", "newdb")

# Add connection creation logic
elif provider == "newdb":
    connection = self._create_newdb_connection(config, credentials)
```

### Adding Custom Profile Fields

If a provider needs special configuration fields:

1. **Update ProfileEditorDialog** to show/hide fields based on provider:

```python
def _on_provider_changed(self):
    provider = self.provider_combo.currentData()
    
    if provider == "newdb":
        self.special_field.setVisible(True)
    else:
        self.special_field.setVisible(False)
```

2. **Store in config dict**:

```python
def _get_config(self) -> dict:
    config = {}
    # ... existing logic
    
    if provider == "newdb":
        config["special_option"] = self.special_field.text()
    
    return config
```

### Adding Cross-Database Operations

Create a new dialog in `ui/dialogs/`:

```python
class MyCustomOperationDialog(QDialog):
    def __init__(self, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self.connection_manager = connection_manager
        # Setup UI, get connections, perform operations
```

Add to menu in `MainWindowMultiDB`:

```python
custom_action = QAction("My Operation...", self)
custom_action.triggered.connect(self._show_custom_operation)
connection_menu.addAction(custom_action)
```

## Testing

### Unit Tests

Test core components in isolation:

```python
# test_connection_manager.py
def test_create_connection():
    manager = ConnectionManager()
    mock_conn = Mock(spec=VectorDBConnection)
    
    conn_id = manager.create_connection(
        name="Test",
        provider="chromadb",
        connection=mock_conn,
        config={}
    )
    
    assert conn_id in manager._connections
    assert manager.get_connection_count() == 1
```

### Integration Tests

Test with real database connections:

```python
# test_integration.py
def test_multi_connection_workflow():
    # Create ChromaDB connection
    chroma = ChromaDBConnection()
    # Create Qdrant connection
    qdrant = QdrantConnection()
    
    # Test simultaneous operations
    # Test data migration
    # etc.
```

### UI Tests

Test UI components with pytest-qt:

```python
# test_connection_panel.py
def test_connection_panel(qtbot):
    manager = ConnectionManager()
    panel = ConnectionManagerPanel(manager)
    qtbot.addWidget(panel)
    
    # Simulate connection creation
    # Verify UI updates
```

## Performance Considerations

### Connection Pooling

For providers that support it, consider implementing connection pooling:

```python
class OptimizedConnection(VectorDBConnection):
    def __init__(self):
        self._pool = ConnectionPool(max_connections=5)
    
    def query_collection(self, ...):
        with self._pool.get_connection() as conn:
            # Use pooled connection
```

### Lazy Loading

Collections are loaded lazily when connections are expanded in the UI:

```python
def _on_item_expanded(self, item: QTreeWidgetItem):
    if not item.childCount():
        # Load collections on first expansion
        self._load_collections_for_item(item)
```

### Async Operations

Long-running operations use background threads:

```python
class OperationThread(QThread):
    finished = Signal(bool, object)
    
    def run(self):
        # Perform operation
        self.finished.emit(success, result)
```

## Security Considerations

### Credential Storage

Always use CredentialService for sensitive data:

```python
# GOOD
credentials = {"api_key": api_key}
profile_service.create_profile(name, provider, config, credentials)

# BAD - Never do this
config["api_key"] = api_key
profile_service.create_profile(name, provider, config, None)
```

### Input Validation

Validate all user input:

```python
def _save_profile(self):
    name = self.name_input.text().strip()
    if not name:
        QMessageBox.warning(self, "Invalid", "Name required")
        return
    
    # Additional validation...
```

### Connection Limits

Enforce limits to prevent resource exhaustion:

```python
if manager.get_connection_count() >= ConnectionManager.MAX_CONNECTIONS:
    raise RuntimeError("Connection limit reached")
```

## Debugging

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# In connection manager
logger = logging.getLogger(__name__)
logger.debug(f"Creating connection {connection_id}")
```

### Inspect Connection State

```python
# In Python console
from vector_inspector.core.connection_manager import ConnectionManager
manager = app.connection_manager

# List all connections
for conn in manager.get_all_connections():
    print(f"{conn.name}: {conn.state}, {len(conn.collections)} collections")

# Get active connection
active = manager.get_active_connection()
print(f"Active: {active.name} > {active.active_collection}")
```

### Monitor Signals

```python
# Connect to all signals for debugging
manager.connection_opened.connect(lambda id: print(f"Opened: {id}"))
manager.active_connection_changed.connect(lambda id: print(f"Active: {id}"))
```

## Migration from Legacy Mode

### Backwards Compatibility

The legacy MainWindow is preserved for compatibility:

- `ui/main_window.py`: Original single-connection window
- `ui/main_window_multi.py`: New multi-connection window

Users can choose at startup or via command-line flags.

### Migrating Code

To update existing code from single connection to multi-connection:

**Before (Legacy):**
```python
self.connection = ChromaDBConnection()
self.connection.connect()
collections = self.connection.list_collections()
```

**After (Multi-DB):**
```python
conn_id = self.connection_manager.create_connection(
    name="My Connection",
    provider="chromadb",
    connection=ChromaDBConnection(),
    config={}
)
# Connection happens in background thread
# Collections accessed via ConnectionInstance
```

## Best Practices

1. **Always use ConnectionManager** - Don't create connections directly
2. **Use signals for updates** - Let components react to changes
3. **Background threads for I/O** - Keep UI responsive
4. **Validate early** - Check inputs before expensive operations
5. **Handle errors gracefully** - Show user-friendly messages
6. **Test with multiple providers** - Ensure compatibility
7. **Document provider-specific behavior** - Help users understand differences

## Contributing

When contributing to multi-database support:

1. Follow the existing architecture patterns
2. Add tests for new functionality
3. Update documentation
4. Consider backward compatibility
5. Test with multiple database providers
6. Ensure thread safety

## Resources

- **Abstract Base Class**: `core/connections/base_connection.py`
- **Provider Examples**: `core/connections/chroma_connection.py`, `qdrant_connection.py`
- **UI Components**: `ui/components/` and `ui/dialogs/`
- **Services**: `services/`
- **Documentation**: `docs/`

---

For questions or contributions, see the [GitHub repository](https://github.com/anthonypdawson/vector-inspector).

