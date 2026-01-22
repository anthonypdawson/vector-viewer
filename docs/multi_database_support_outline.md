# Multi-Database Support & Saved Connections Outline

## Overview
This document outlines the design and implementation plan for supporting multiple open database connections and reusable saved connection profiles in Vector Inspector.

---

## Goals
- Allow users to open and interact with multiple vector databases simultaneously.
- Enable saving, editing, and reusing connection profiles for quick access.
- Provide a user-friendly UI for managing active and saved connections.
- Ensure thread safety and efficient resource management.

---

## Key Features

### 1. Multiple Active Connections
- Refactor connection manager to support a list/dictionary of active connections.
- Each connection has its own state, collections, and query context.
- UI displays all open connections (sidebar, tabs, or dropdown).
- Users can switch between databases or view them side-by-side.
- Support cross-database operations (e.g., migration, comparison).

### 2. Saved Connection Profiles
- Users can save connection details (provider, host, port, credentials, options).
- Saved profiles are listed in a dedicated UI section.
- Profiles can be edited, deleted, or renamed.
- Quick connect: select a profile to open a new connection instantly.
- Profiles stored securely (encrypted if possible) in user config directory.

### 3. UI/UX Considerations
- Sidebar or tabbed interface for managing open connections.
- Dialog for creating/editing connection profiles.
- Visual indicators for active, idle, or failed connections.
- Option to close connections without losing saved profiles.
- Tooltips and help for connection options.

### 4. Technical Design
- ConnectionManager class manages active and saved connections.
- Each connection instance encapsulates provider-specific logic.
- Saved profiles stored as JSON in ~/.vector-viewer/connections.json.
- Thread-safe operations for concurrent queries and updates.
- Event-driven updates to UI when connections change.

### 5. Implementation Steps
1. Refactor ConnectionManager to support multiple connections.
2. Design and implement UI for managing connections and profiles.
3. Add logic for saving/loading connection profiles.
4. Update all views to support context switching between databases.
5. Test with multiple providers and large datasets.
6. Document usage and troubleshooting.

---

## Future Enhancements
- Connection groups (organize profiles by project/team).
- Connection sharing (export/import profiles).
- Auto-reconnect and connection health monitoring.
- Integration with cloud provider authentication flows.

---

## References
- [README.md](README.md)
- [FEATURES.md](FEATURES.md)
- [docs/architecture.md](docs/architecture.md)

---

## Status
Draft – for review and iteration.
