# Release Notes (0.6.2) — 2026-03-28

## UI
- Status bar now shows real-time feedback for key actions, including result counts and elapsed time (e.g. "Search complete – 28 results in 0.43s", "Data loaded – 1,000 items in 1.20s", "Clustering complete – 5 clusters in 2.10s", "Visualization complete – 500 points in 3.51s").
- All status bar messages are now routed through a centralised `StatusReporter` service so every message is recorded in a bounded in-memory activity log (up to 100 entries) — foundation for a future user-visible Activity Log.
- **New:** Status bar message duration is now user-configurable in Preferences → General → "Status Bar → Message duration" (0 = Permanent, 1–30 s).
- **change:** Default status bar message duration is now `0` (Permanent) by default — status messages stay visible until dismissed unless the user changes the preference.
- **fix:** Refresh Collections (F5 / menu) now runs in a background thread — the UI no longer freezes on slow or remote connections, and reports elapsed time on success.
- **fix:** "Check for Update" (Help menu) now runs in a background thread with a status bar progress message.
- **fix:** Add Item and Delete Items in the Data tab now run in background threads with a loading indicator and status bar completion messages (e.g. "Item added complete – 1 item in 0.12s").
- **feat:** Connection success now reports elapsed time in the status bar (e.g. "Connected complete – 42 collections in 0.95s").
- **feat:** Backup and Restore operations now report elapsed time in the status bar on completion.

## Internal
- Added `StatusReporter` service (`services/status_reporter.py`) with `report()` / `report_action()` APIs, a `StatusLogEntry` dataclass, configurable log size, and a `status_updated` Qt signal.
- `AppState` now owns a `status_reporter` instance accessible from any view via `app_state.status_reporter`.
- `StatusReporter._default_timeout_ms` is now mutable so the user preference is applied at runtime without restarting.
- Default status timeout updated to `0` ms (permanent) so important system messages remain visible by default.
- `connection_completed` signal extended to carry `duration_ms` (float) so the main window can display connection latency.
- 29 new unit tests cover message formatting, log trimming, signal emission, and reporter isolation.

---