# Multi-Database Support - Installation & Testing

## Installation

### 1. Install Dependencies

The new multi-database support requires the `keyring` package for secure credential storage:

```bash
# Using pip
pip install keyring

# Or reinstall the project with all dependencies
cd /path/to/vector-viewer
pip install -e .

# Or using pdm
pdm install
```

### 2. Verify Installation

```bash
python -c "import keyring; print('Keyring available')"
```

If you see "Keyring available", you're good to go!

### 3. Launch

```bash
vector-inspector
```

## Quick Test

### Test 1: Create and Connect to a Profile

1. Launch with `vector-inspector`
2. Go to **Profiles** tab
3. Click **+** to create a new profile
4. Fill in:
   - Name: "Test Chroma"
   - Provider: ChromaDB
   - Type: Ephemeral (no setup needed)
5. Click **Test Connection** (should succeed)
6. Click **Save**
7. Double-click the profile to connect
8. Connection should appear in **Active** tab with 🟢 indicator

### Test 2: Multiple Connections

1. Create another profile (e.g., "Test Chroma 2" ephemeral)
2. Connect to it
3. You should now see 2 connections in **Active** tab
4. Click between them to switch active connection
5. Breadcrumb at bottom should update

### Test 3: Profile Persistence

1. Create a profile and connect
2. Close the application
3. Relaunch the application
4. Go to **Profiles** tab
5. Your saved profile should still be there!

### Test 4: Data Migration (Advanced)

1. Create 2 ephemeral connections
2. In one connection, create a collection and add some data
3. Menu: **Connection → Migrate Data**
4. Select source and target
5. Click **Start Migration**
6. Verify data copied successfully

## Troubleshooting

### Issue: "keyring module not available" warning

**Solution**: Install keyring:
```bash
pip install keyring
```

On Linux, you may also need:
```bash
# Ubuntu/Debian
sudo apt-get install gnome-keyring

# Fedora/RHEL
sudo yum install gnome-keyring
```

### Issue: Connection fails

**Check:**
- Is the database server running?
- Are credentials correct?
- Can you reach the host/port?
- Check firewall settings

### Issue: Profiles not saving

**Check:**
- Is `~/.vector-inspector/` directory writable?
- Any error messages in console?

### Issue: Type checker errors in IDE

These are expected - the code uses PySide6 enums that type checkers may not fully understand. The code will run fine.

## File Structure

After running, you should see:

```
~/.vector-inspector/
├── profiles.json          # Saved connection profiles
└── settings.json          # Legacy settings (if applicable)
```

Credentials are stored in your system keychain:
- **Windows**: Credential Manager (search "Credential Manager" in Start)
- **macOS**: Keychain Access app
- **Linux**: Secret Service (via gnome-keyring or similar)

## Development Testing

### Run Unit Tests

```bash
# Install test dependencies
pip install pytest pytest-qt

# Run tests
pytest tests/
```

### Run Specific Test

```bash
pytest tests/test_connection_manager.py -v
```

### Manual Testing Checklist

- [ ] Create profile (ChromaDB)
- [ ] Create profile (Qdrant)
- [ ] Test connection before saving
- [ ] Connect to multiple profiles
- [ ] Switch active connection
- [ ] Select collections
- [ ] Verify breadcrumb updates
- [ ] Refresh collections
- [ ] Rename connection
- [ ] Edit profile
- [ ] Duplicate profile
- [ ] Delete profile
- [ ] Export profiles
- [ ] Import profiles
- [ ] Migrate data between connections
- [ ] Close connection
- [ ] Restart app (verify persistence)

## Performance Notes

- Each connection maintains its own database client
- Collections are loaded on-demand when expanded
- Large migrations use batching (configurable batch size)
- Background threads prevent UI blocking

## Next Steps

1. ✅ Install dependencies
2. ✅ Test basic functionality
3. ✅ Create your real profiles
4. ✅ Connect to your databases
5. ✅ Enjoy working with multiple databases!

## Documentation

- **User Guide**: [MULTI_DATABASE_USER_GUIDE.md](MULTI_DATABASE_USER_GUIDE.md)
- **Developer Guide**: [MULTI_DATABASE_DEVELOPER_GUIDE.md](MULTI_DATABASE_DEVELOPER_GUIDE.md)
- **Quick Start**: [MULTI_DATABASE_QUICKSTART.md](MULTI_DATABASE_QUICKSTART.md)
- **Implementation**: [MULTI_DATABASE_IMPLEMENTATION_COMPLETE.md](MULTI_DATABASE_IMPLEMENTATION_COMPLETE.md)

## Support

- Report issues on GitHub
- Check documentation for common questions
- See main [README.md](../README.md)

---

Happy testing! 🎉

