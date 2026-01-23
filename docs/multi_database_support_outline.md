# Multi-Database Support & Saved Connections Outline

## Overview
This document outlines the design and implementation plan for supporting multiple open database connections and reusable saved connection profiles in Vector Inspector.

---

## Goals
- Allow users to open and interact with multiple vector databases simultaneously.
- Enable saving, editing, and reusing connection profiles for quick access.
- Provide a user-friendly UI for managing active and saved connections.
- Ensure thread safety and efficient resource management.
- Handle connection failures gracefully with proper error reporting.
- Maintain backward compatibility with existing single-connection usage.
- Secure credential storage using platform-native keychains when available.

---

## Key Features

### 1. Multiple Active Connections
- Refactor connection manager to support a dictionary of active connections keyed by unique connection IDs.
- Each connection has its own state, collections, query context, and display name.
- **Active/Default Connection**: One connection is marked as the current active connection for operations.
- **Active Collection**: Each connection tracks its currently selected collection. All operations (queries, inserts, deletes, updates) apply to the active collection within the active connection.
- **Connection Naming**: Each connection has a user-editable name (e.g., "Production Chroma", "Dev Qdrant").
- **Connection Limits**: Enforce reasonable limit (e.g., 10 concurrent connections) to prevent resource exhaustion.
- UI displays all open connections (sidebar, tabs, or dropdown).
- Users can switch between databases or view them side-by-side.
- **Context Switching**: All operations (queries, vector CRUD, metadata filtering, etc.) are scoped to:
  1. The currently active connection
  2. The currently selected collection within that connection
- **Operation Scope**: Every query, insert, delete, or update always targets the active collection in the active connection.
- Support cross-database operations:
  - Vector migration/copying between databases
  - Schema/collection comparison
  - Synchronized queries across multiple databases
- **Connection State**: Track connection health (connected, disconnected, error) with visual indicators.
- **Graceful Shutdown**: Properly close all connections and cleanup resources on app exit.

### 2. Saved Connection Profiles
- Users can save connection details (provider, host, port, credentials, provider-specific options).
- **Provider-Specific Fields**: Dynamic form fields based on selected provider (API keys, auth tokens, etc.).
- **Connection Validation**: Test connection before saving to catch configuration errors early.
- Saved profiles are listed in a dedicated UI section with search/filter capabilities.
- Profiles can be edited, deleted, renamed, duplicated, and organized.
- Quick connect: select a profile to open a new connection instantly.
- **Secure Credential Storage**:
  - Use system keychain (Windows Credential Manager, macOS Keychain, Linux Secret Service) for passwords/API keys.
  - Store non-sensitive config (host, port, provider) in JSON.
  - Never store credentials in plain text.
  - Option to prompt for credentials on each connection instead of storing.
- **Import/Export**: Allow exporting profiles (without credentials) for sharing/backup.
- **Profile Templates**: Pre-configured templates for common setups (local Chroma, Qdrant cloud, etc.).

### 3. UI/UX Considerations
- **Connection Manager Panel**:
  - Sidebar section showing all open connections (reuse existing component).
  - Each connection shows name, provider type, status indicator (green/yellow/red).
  - Context menu for each connection (rename, disconnect, view info, set as active).
  - Allow each connection to expand/collapse collections.
  - Drag-and-drop to reorder connections.
- **Saved Profiles Section**:
  - Separate panel/tab for saved profiles.
  - Quick actions: connect, edit, delete, duplicate.
  - Visual distinction between active connections and saved profiles.
- **Connection Dialogs**:
  - Create/edit connection profile dialog with validation.
  - Test connection button with progress indicator and error details.
  - Provider-specific help text and examples.
- **Active Connection Indicator**: 
  - Highlight current active connection in sidebar.
  - Show active connection name in toolbar/status bar.
  - Show active collection breadcrumb (e.g., "Production Chroma > products_vectors").
  - Keyboard shortcuts for switching between connections (Ctrl+1-9).
- **Collection Selection**:
  - Each connection displays its collections in an expandable tree.
  - Clicking a collection sets it as active for that connection.
  - Visual indicator for the currently active collection.
  - All query panels, filters, and operations automatically target the active collection.
- **Error Handling UI**:
  - Non-intrusive notifications for connection failures.
  - Reconnect button for failed connections.
  - Connection health tooltips with detailed error messages.
- **Closing Connections**: Option to close connections without losing saved profiles.
- **Session Persistence**: Option to restore previously open connections on app restart.

### 4. Technical Design

#### Connection Management
- **ConnectionManager** class manages both active connections and saved profiles.
- **Connection Class Hierarchy**:
  ```
  BaseConnection (abstract)
    ├── ChromaConnection
    ├── QdrantConnection
    ├── PineconeConnection
    └── WeaviateConnection
  ```
- Each connection instance:
  - Has unique ID (UUID), user-visible name, and provider type.
  - Encapsulates provider-specific client and operations.
  - Maintains connection state (connected, connecting, disconnected, error).
  - Tracks collections/namespaces and metadata.
  - **Tracks active collection**: Stores currently selected collection for operation context.
  - Supports lazy loading of collections.
  - Implements health check and reconnection logic.
  - **Operation Context**: All operations (query, insert, delete, update) use the connection's active collection as the target.

#### Data Storage
- **Profiles Config**: `~/.vector-viewer/profiles.json` (non-sensitive data only).
  ```json
  {
    "profiles": [
      {
        "id": "uuid",
        "name": "Production Chroma",
        "provider": "chroma",
        "host": "localhost",
        "port": 8000,
        "use_ssl": false,
        "credential_key": "prod_chroma_key",  // Reference to keychain entry
        "options": {}  // Provider-specific options
      }
    ],
    "last_active_connections": ["uuid1", "uuid2"]  // For session restore
  }
  ```
- **Credentials**: Stored in system keychain with key format: `vector-inspector:profile:{profile_id}`.

#### Thread Safety & Concurrency
- Use thread locks for connection state modifications.
- Connection operations (queries, inserts) use provider's native thread safety.
- UI updates via Qt signals/slots for thread-safe communication.
- Async operations with proper cancellation support.

#### Event System
- Events emitted for:
  - Connection opened/closed
  - Connection state changed (connected → error)
  - Profile added/updated/deleted
  - Active connection changed
  - **Active collection changed** (within a connection)
  - Collections list updated
- Subscribers: UI components, status bar, connection manager panel, query panels, data views.
- **Context Propagation**: When active connection or collection changes, all UI components refresh to reflect new operation context.

#### Error Handling
- Structured error types: ConnectionError, AuthenticationError, TimeoutError, etc.
- Automatic retry with exponential backoff for transient failures.
- User-friendly error messages with actionable suggestions.
- Connection validation on profile creation/edit.
- Graceful degradation when a connection fails.

#### Backward Compatibility
- Legacy single-connection mode still supported.
- Auto-migration of existing connection settings to first profile.
- Fallback behavior for code expecting single connection.

### 5. Implementation Steps

#### Phase 1: Foundation (Core Architecture)
1. **Refactor ConnectionManager**:
   - Add connection dictionary and active connection tracking.
   - Implement connection lifecycle (open, close, health check).
   - Add unique ID generation for connections.
   - Create event system for connection state changes.

2. **Credential Management**:
   - Integrate with system keychain (keyring library).
   - Implement secure credential storage/retrieval.
   - Add fallback for systems without keychain support.

3. **Profile Storage**:
   - Design profiles.json schema.
   - Implement load/save logic with validation.
   - Add migration logic for existing single-connection setups.

#### Phase 2: UI Implementation
4. **Connection Manager UI**:
   - Update sidebar to show multiple connections.
   - Add connection status indicators.
   - Implement context menus and actions.
   - Add active connection highlighting.

5. **Profile Management UI**:
   - Create profile list/grid view.
   - Implement create/edit profile dialog.
   - Add connection test functionality with progress feedback.
   - Implement import/export dialogs.

6. **Context Switching**:
   - Update all views to respect active connection.
   - Add connection selector to toolbar/status bar.
   - Implement keyboard shortcuts.

#### Phase 3: Advanced Features
7. **Cross-Database Operations**:
   - Design and implement vector migration tool.
   - Add collection comparison view.
   - Implement synchronized query execution.

8. **Session Management**:
   - Add option to restore connections on startup.
   - Implement graceful shutdown with cleanup.
   - Add connection pooling for supported providers.

#### Phase 4: Testing & Documentation
9. **Testing**:
   - Unit tests for ConnectionManager and profile storage.
   - Integration tests with multiple providers.
   - UI tests for connection management flows.
   - Load tests with many concurrent connections.
   - Error handling and edge case testing.
   - Security testing for credential storage.

10. **Documentation**:
    - User guide for managing connections and profiles.
    - API documentation for connection classes.
    - Troubleshooting guide for common issues.
    - Security best practices.
    - Migration guide from single to multi-connection.

---

## Future Enhancements
- **Connection Organization**:
  - Connection groups/folders (organize profiles by project/team/environment).
  - Tags and custom metadata for profiles.
  - Favorites/pinning for frequently used profiles.
- **Advanced Sharing**:
  - Team profile sharing via URL or file.
  - Cloud sync for profiles across devices (opt-in).
  - Profile versioning and history.
- **Monitoring & Diagnostics**:
  - Connection health dashboard with metrics.
  - Query performance tracking per connection.
  - Connection usage statistics and logging.
  - Automatic failover for redundant connections.
- **Authentication**:
  - OAuth2/SSO integration for cloud providers.
  - Role-based access control awareness.
  - Certificate-based authentication for enterprise.
- **Advanced Operations**:
  - Batch operations across multiple connections.
  - Connection scripting/automation (Python API).
  - Scheduled connection testing/monitoring.
  - Connection presets based on detected local services.

---

## References
- [README.md](README.md)
- [FEATURES.md](FEATURES.md)
- [docs/architecture.md](docs/architecture.md)

---

## Status
Draft – for review and iteration.
