# Multi-Database Support - Quick Start

## Installation

```bash
# Install/update dependencies
pip install -e .

# Or with pdm
pdm install
```

## Launch

```bash
vector-inspector
```

## Quick Usage

### 1. Create Your First Profile

1. Launch in multi-database mode
2. Go to **Profiles** tab
3. Click **"+"** button
4. Fill in:
   - Name: "My Local Chroma"
   - Provider: ChromaDB
   - Type: Persistent
   - Path: `/path/to/chroma_data`
5. Click **Test Connection** → **Save**

### 2. Connect

1. Select your profile
2. Click **"Connect"** or double-click
3. Connection appears in **Active** tab

### 3. Work with Collections

1. Expand your connection
2. Click a collection to select it
3. Use Info, Data Browser, Search, and Visualization tabs

### 4. Add More Connections

Create more profiles and connect to multiple databases simultaneously!

### 5. Migrate Data

1. Connect to 2+ databases
2. **Connection → Migrate Data**
3. Select source and target
4. Click **Start Migration**

## Key Concepts

- **Profile**: Saved connection settings
- **Connection**: Active database connection
- **Active Connection**: The database you're currently working with
- **Active Collection**: The collection operations target

## File Locations

- **Profiles**: `~/.vector-inspector/profiles.json`
- **Credentials**: System keychain (Windows Credential Manager / macOS Keychain / Linux Secret Service)

## Documentation

- **User Guide**: [docs/MULTI_DATABASE_USER_GUIDE.md](MULTI_DATABASE_USER_GUIDE.md)
- **Developer Guide**: [docs/MULTI_DATABASE_DEVELOPER_GUIDE.md](MULTI_DATABASE_DEVELOPER_GUIDE.md)
- **Implementation Details**: [docs/MULTI_DATABASE_IMPLEMENTATION_COMPLETE.md](MULTI_DATABASE_IMPLEMENTATION_COMPLETE.md)

## Getting Help

- Check the documentation in `/docs`
- Report issues on GitHub
- See [README.md](../README.md) for project info

---

Happy exploring! 🚀

