# Vector Inspector 0.6.1 (2026‑03‑19) — Session‑Aware Telemetry, LLM Runtime Fixes, and UI Polish

Vector Inspector 0.6.1 is a tightening pass across the entire stack:
more reliable LLM behavior, fully session‑aware telemetry, and a smoother, more predictable user interface.

---

## New & Improved

### Ask‑AI Enhancements
- Added a persistent **“Configure LLM…”** button inside the Ask‑AI dialog for easier access.
- Provider status now **refreshes automatically** when LLM settings change.
- Ask‑AI now **re‑reads the active provider’s model** before sending prompts.

### UI Improvements
- Data view now includes a **total record count** label.
- Closing the last connection now **clears cached provider/collection context**.

---

## LLM Runtime Fixes
- Fixed an issue where Ask‑AI could use a **stale model** if preferences changed while the dialog was open.
- Runtime manager now **respects provider‑specific model settings** and avoids cross‑provider leakage.

---

## Telemetry Overhaul

### Core Session Model
- Added full **session‑aware telemetry**: session start/end events, duration tracking, OS metadata, and provider/collection context caching.
- `TelemetryService` is now a **singleton**, initialized once at startup with the app version.
- Anonymous telemetry toggle now emits a **feature‑toggle event**.
- Closing the last DB connection **clears cached provider/collection** to prevent stale context from leaking into subsequent events.
- Documentation updated to match the new session‑aware model.

### Reliability & Sampling
- **Deterministic sampling:** SHA‑256‑based `should_sample()` helper produces stable, reproducible decisions per event type and seed — backend can reconstruct sampled populations reliably.
- **Error grouping:** canonical `error_hash` fingerprint normalizes numbers and hex addresses before hashing, grouping similar errors without transmitting raw traces.
- **Crash‑marker lifecycle:** on startup the app detects an un‑cleared crash marker from a previous run and emits `session.end` with `exit_reason: "crash"`. Clean shutdown clears the marker.
- **Sampled event metadata:** `queue_sampled_event()` attaches `sampling_rate`, `sampling_version`, and `sampling_seed_type` to every sampled event for backend aggregation.
- **Test safety:** `TelemetryService` forces test sentinel values (`app_version: "0.0-test"`, `client_type: "unit-tests"`) when running under pytest, making any escaped event immediately identifiable on the backend.

---

## Preferences & Settings Redesign
The Settings dialog has been restructured into a scalable, tabbed interface that better reflects Vector Inspector’s growing feature set.

- Settings are now organized into four tabs: **General**, **Embeddings**, **Appearance**, and **LLM**
- LLM provider configuration (provider selector, connection fields, model list, health check) now lives in its own dedicated **LLM** tab
- Action buttons (Apply, OK, Cancel, Reset to defaults) remain outside the tab widget for consistent visibility

### Extension API Updates
- `SettingsDialog.add_section(widget_or_layout, tab="General")` now accepts an optional `tab` keyword, allowing extensions to inject controls into any named tab (or create new tabs on demand)
- `SettingsDialog.get_tab_layout(tab_name)` is a new public API returning the `QVBoxLayout` for a named tab, creating it if needed
- `llm_settings_panel` hook handler updated to inject its group into the **LLM** tab when supported, with backward‑compatible fallback to `parent_layout`

---

## Testing & CI
- Replaced timing‑dependent polling with **deterministic worker synchronization** via `_batch_processed.wait()` — eliminates flakiness under CI load.
- **Global HTTP guard** in `conftest.py` returns synthetic 200 responses, preventing network leakage and ensuring batches clear cleanly across all tests.
- **Autouse singleton reset** plus test‑mode queue‑file purge guarantees clean state at every test boundary regardless of execution order.
- Added tests covering: sampling determinism, `error_hash` normalization, crash‑marker full lifecycle, singleton enforcement, retry semantics, stale‑context clearing on connection close, and the mid‑flight shutdown race condition.

---

## Summary
0.6.1 strengthens Vector Inspector’s identity as a **diagnostic, session‑aware intelligence console**.
Telemetry is now reconstructable end‑to‑end, Ask‑AI behaves consistently across providers,
and the user interface surfaces more context with less friction.

---