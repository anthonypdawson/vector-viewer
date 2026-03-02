## Release Notes (0.5.3) — 2026-03-02

### CLI
- Added `--version` flag: prints the installed version and exits.
- Added `--help` / `-h` flag: prints usage, lists `--version`, explains that running without arguments starts the GUI, and links to https://github.com/anthonypdawson/vector-inspector for support.
- Added `--no-telemetry`: disables telemetry for the current run without modifying saved settings.
- Added `--log-level LEVEL` (`DEBUG`/`INFO`/`WARNING`/`ERROR`): sets logging verbosity for the current run without modifying saved settings.
- Added `--no-splash`: skips the loading splash screen for the current run without modifying saved settings.
- Added `--config PATH`: loads settings from an alternate file for the current run; does not overwrite `~/.vector-inspector/settings.json`.
- Added `--dump-settings`: prints current (or `--config`-specified) settings as JSON and exits without importing Qt.
- All runtime flags use environment variables (`VI_NO_TELEMETRY`, `VI_NO_SPLASH`, `VI_CONFIG_PATH`, `LOG_LEVEL`) so no function signatures needed changing.
- Console script entry point updated to go through the new lightweight CLI parser so Qt is never imported when only informational flags are requested.

### Testing
- Test coverage increased from ~75% to 80% (1380 tests). New test files added for `data_loaders`, `profile_service`, `task_runner`, `credential_service`, `embedding_utils`, and `model_cache`. Extended existing tests for `backup_restore_service`, `settings_service`, `template_connection`, `search_runner`, `collection_service`, `import_export_service`, and settings dialog.

---

