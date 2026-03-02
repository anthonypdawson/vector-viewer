## Release Notes (0.5.2) — 2026-03-02

### CLI
- Added `--version` flag: prints the installed version and exits.
- Added `--help` / `-h` flag: prints usage, lists `--version`, explains that running without arguments starts the GUI, and links to https://github.com/anthonypdawson/vector-inspector for support.
- First-time use of `--version` or `--help` sends a one-time `cli_first_use` telemetry event (respects `telemetry.enabled` setting; never repeats after the first invocation).
- Console script entry point updated to go through the new lightweight CLI parser so Qt is never imported when only informational flags are requested.

### Testing
- Test coverage increased from ~75% to 80% (1380 tests). New test files added for `data_loaders`, `profile_service`, `task_runner`, `credential_service`, `embedding_utils`, and `model_cache`. Extended existing tests for `backup_restore_service`, `settings_service`, `template_connection`, `search_runner`, `collection_service`, `import_export_service`, and settings dialog.

---

