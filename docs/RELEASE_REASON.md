# Vector Inspector 0.7.1 — April 11, 2026

This release addresses a set of bugs surfaced by production telemetry data, including
duplicate analytics events, stale session IDs, misleading db_type values, and repeated
connection attempts. It also improves the UX when no collection is selected.

## UX

- Data, Search, and Visualization tabs are now always accessible; action buttons
  (Search, Generate Visualization, Cluster, data CRUD) are disabled with a tooltip
  until a collection is selected, preventing confusing no-op interactions.
- Empty-state messages ("Select a collection to begin") are shown consistently
  across Data, Search, and Visualization views when no collection is active.

## Bug Fixes

- Fixed `session.start` appearing twice in analytics: leftover queued events from a
  prior run are now purged before a new `session.start` is enqueued.
- Fixed `app_launch` carrying a stale `session_id` from a previous run. The
  `session_id` is no longer loaded from persisted settings at init; it is assigned
  fresh on each launch via `set_session_id()`.
- Fixed `db_type: "unknown"` in `query.executed` telemetry events. The code
  previously attempted to read `connection._connection` (which does not exist on
  `ConnectionInstance`); it now correctly reads `connection.provider`.
- Fixed repeated `db.connection_attempt` telemetry events caused by rapid or
  duplicate connect clicks. The connection controller now ignores a new connect
  request for a profile that already has an in-progress connection thread.

## Testing

- Added `tests/views/test_collection_ready_state.py` covering SearchView and
  MetadataView button-enable/disable lifecycle.
- Added telemetry regression tests for session_id init, session.start dedup,
  and db_type extraction.
- Added db_type tests to `test_search_view.py`.
- Updated existing tests affected by the new initial button state.

---
