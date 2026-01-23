# Multi-Database Support - User Guide

## Overview

Vector Inspector now supports connecting to multiple vector databases simultaneously! This powerful feature allows you to:

- Work with multiple databases at the same time
- Save and reuse connection profiles for quick access
- Migrate data between different vector databases
- Compare collections across different databases
- Switch seamlessly between connections without losing context

## Getting Started

### First Launch

On your first launch in multi-database mode, you'll see:

1. **Active Connections Tab**: Shows your currently open database connections (empty initially)
2. **Profiles Tab**: Shows your saved connection profiles (empty initially)

## Working with Connection Profiles

### Creating a Profile

Connection profiles allow you to save database connection settings for quick reuse.

1. Click the **"+"** button in the Profiles tab, or use **Connection → New Profile** from the menu
2. Fill in the profile details:
   - **Profile Name**: A friendly name (e.g., "Production Chroma", "Dev Qdrant")
   - **Provider**: Choose ChromaDB or Qdrant
   - **Connection Type**: Persistent (local file), HTTP (remote server), or Ephemeral (in-memory)
   - **Connection Details**: Depends on connection type
     - **Persistent**: Path to database directory
     - **HTTP**: Host, port, and optionally API key
     - **Ephemeral**: No additional settings needed

3. Click **"Test Connection"** to verify your settings
4. Click **"Save"** to save the profile

### Secure Credential Storage

Vector Inspector uses your system's secure keychain to store sensitive credentials:

- **Windows**: Windows Credential Manager
- **macOS**: Keychain Access
- **Linux**: Secret Service (libsecret)

Your passwords and API keys are never stored in plain text!

### Managing Profiles

From the Profiles tab, you can:

- **Connect**: Double-click a profile or select and click "Connect"
- **Edit**: Modify profile settings
- **Duplicate**: Create a copy of a profile with a new name
- **Delete**: Remove a profile and its saved credentials

### Connecting to a Profile

1. Switch to the **Profiles** tab
2. Select a profile from the list
3. Click **"Connect"** or double-click the profile
4. A connection will be established in the background
5. Once connected, you'll see it appear in the **Active** tab

## Working with Multiple Connections

### The Active Connections Panel

The Active Connections panel shows all your currently open database connections. Each connection displays:

- 🟢 **Green indicator**: Connected and ready
- 🟡 **Yellow indicator**: Connecting...
- 🔴 **Red indicator**: Connection error
- ⚪ **White indicator**: Disconnected

### Active Connection and Collection

At any time, you have:

- **One active connection**: The database you're currently working with
- **One active collection per connection**: The collection operations will target

The active connection and collection are shown in the **breadcrumb** at the bottom of the window:
```
Production Chroma > products_vectors
```

### Switching Connections

To switch to a different connection:

1. Click on the connection in the Active Connections panel
2. The connection becomes active
3. All panels (Info, Data Browser, Search, Visualization) update automatically

### Selecting a Collection

To work with a collection:

1. Expand a connection in the Active Connections panel
2. Click on a collection name
3. The collection becomes active for that connection
4. All data operations will target this collection

### Connection Context Menu

Right-click a connection for quick actions:

- **Set as Active**: Make this connection active
- **Rename**: Change the connection's display name
- **Refresh Collections**: Reload the list of collections
- **Disconnect**: Close this connection

### Connection Limits

To prevent resource exhaustion, Vector Inspector limits you to **10 simultaneous connections**. If you need to connect to another database, close an existing connection first.

## Cross-Database Operations

### Migrating Data Between Databases

Vector Inspector includes a powerful migration tool for copying data between different vector databases:

1. Connect to at least 2 databases
2. Select **Connection → Migrate Data** from the menu
3. In the Migration Dialog:
   - **Source**: Select connection and collection to copy from
   - **Target**: Select connection and collection to copy to
   - **Batch Size**: Number of items to process at once (default: 100)
   - **Include Embeddings**: Whether to copy vector embeddings
4. Click **"Start Migration"**
5. Monitor progress in real-time
6. Click **"Cancel"** if you need to stop the migration

**Use Cases:**
- Migrate from ChromaDB to Qdrant
- Copy data between development and production databases
- Backup collections to a different database
- Consolidate data from multiple sources

**Important Notes:**
- The target collection should already exist
- Migration is additive (items are added to the target)
- IDs from the source are preserved in the target
- Large migrations may take time; be patient!

### Comparing Collections

To compare collections across databases:

1. Connect to multiple databases
2. Open each collection in different connections
3. Use the Info panel to view:
   - Item counts
   - Metadata schemas
   - Vector dimensions
4. Use the Data Browser to inspect actual data

## Tips and Best Practices

### Profile Organization

- Use descriptive names: "Production Chroma (AWS)", "Dev Qdrant (Local)"
- Create separate profiles for different environments
- Use the duplicate feature to create variations quickly

### Session Management

Vector Inspector remembers:
- Your saved profiles (permanent)
- Your active connections can be optionally restored on next launch

### Working Efficiently

- **Keyboard Shortcuts:**
  - `Ctrl+N`: New connection
  - `F5`: Refresh collections for active connection
  - `Ctrl+Q`: Quit application

- **Quick Profile Connect:**
  - Double-click profiles to connect instantly
  - Recent profiles appear at the top

### Performance Considerations

- Close connections you're not actively using
- Use smaller batch sizes for migrations over slow networks
- Some operations (like full collection scans) may take time with large datasets

## Troubleshooting

### Connection Fails

- **Check credentials**: Ensure API keys and passwords are correct
- **Network connectivity**: Can you reach the database server?
- **Firewall**: Is the port open?
- **Provider running**: Is the database server actually running?

### "Keyring not available" warning

If you see this warning, credentials won't be saved securely between sessions. To fix:

```bash
# Install keyring support
pip install keyring

# On Linux, you may also need:
sudo apt-get install gnome-keyring  # Ubuntu/Debian
sudo yum install gnome-keyring       # Fedora/RHEL
```

### Migration Errors

- Ensure target collection exists before migrating
- Check that target database has enough space
- For large migrations, use smaller batch sizes
- Check console output for detailed error messages

### Profile Not Showing

- Profiles are stored in `~/.vector-inspector/profiles.json`
- If corrupted, you can delete this file (profiles will be lost)
- Credentials are in your system keychain

## Migrating from Previous Versions

If you have settings from a previous version:

1. Your old connection settings can be migrated to a profile
2. Create a new profile with your previous connection settings
3. Connect to the profile
4. All your data remains accessible!

## Security Best Practices

1. **Never share profiles with embedded credentials**
   - Export profiles without credentials for sharing
   - Recipients should add their own credentials

2. **Use API keys with limited permissions**
   - Create read-only keys for browsing
   - Use full-access keys only when needed

3. **Protect your credentials**
   - Credentials are stored in system keychain
   - Keep your system account secure
   - Consider password-protecting your machine

4. **Regular backups**
   - Export important profiles periodically
   - Keep profile exports (without credentials) in version control

## Advanced Features

### Profile Templates

Common profile templates (coming soon):

- Local ChromaDB (Persistent)
- Local Qdrant (Persistent)
- Qdrant Cloud
- ChromaDB HTTP Server
- Memory/Ephemeral Databases

### Profile Import/Export

Export profiles for backup or team sharing:

1. Go to Profiles tab
2. Right-click a profile → Export
3. Save the JSON file
4. Share with team (credentials are NOT included)

Team members can import:

1. Profiles tab → Import button
2. Select the JSON file
3. Add their own credentials to the profiles

## Getting Help

- **Documentation**: See `/docs` folder in the repository
- **GitHub Issues**: Report bugs and request features
- **Project Page**: https://github.com/anthonypdawson/vector-inspector

## What's Next?

Upcoming features:

- Connection health monitoring and auto-reconnect
- Batch operations across multiple connections
- Collection comparison view
- Profile groups and folders
- Cloud profile sync
- Enhanced migration with conflict resolution

---

**Happy database exploring!** 🚀

