## Release Notes (0.4.2)

This release finalizes the UI refactor and AppState migration. Key changes
focus on centralizing application state in `AppState`, restoring robust
singleton semantics for core services, and updating documentation and tests
to reflect the new patterns.

Highlights
- AppState: Introduced as the canonical, required application state container
	for UI views and services. Views now receive `app_state: AppState` and
	access shared services via `app_state.*` properties.
- Singleton core services: `SettingsService`, `CacheManager`, and
	`EmbeddingModelRegistry` now implement a safe singleton pattern. The
	initialization guard checks the instance dictionary to avoid false
	positives from class-level resets used in tests.
- Backward compatibility: Deprecated helper getters (e.g. `get_cache_manager()`)
	still return the same singleton instances to avoid state fragmentation,
	but new code should prefer `app_state.*`.
- Cache management: `CacheManager` is documented and examples updated to use
	`app_state.cache_manager` for get/set/invalidate operations.
- Settings: `SettingsService` persists to `~/.vector-inspector/settings.json`.
	Access via `app_state.settings_service`; signals available on the service
	for reactive UI updates.
- Tests: Full test suite run — all tests passing (281 passed, 2 skipped).
- Docs: Updated `.github/copilot-instructions.md` to describe the AppState
	pattern, singleton usage, preferred access patterns, and testing notes.

Migration notes
- All UI components should now require `app_state` (no `Optional[AppState]`
	fallbacks remain). If any legacy code still instantiates services directly,
	it will receive the same singleton instance to preserve behavior.

---