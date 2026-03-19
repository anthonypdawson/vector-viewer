# Vector Inspector 0.6.1 (2026-03-19) — Session-Aware Telemetry, LLM Runtime Fixes, and UI Polish

Vector Inspector 0.6.1 is a tightening pass across the entire stack:  
more reliable LLM behavior, fully session-aware telemetry, and a smoother, more predictable UI.

---

## New & Improved

### Ask‑AI Enhancements
- Added a persistent **“Configure LLM…”** button inside the Ask‑AI dialog for easier access.
- Provider status now **refreshes automatically** when LLM settings change.
- Ask‑AI now **re-reads the active provider’s model** before sending prompts.

### UI Improvements
- Data view now includes a **total record count** label.
- Closing the last connection now **clears cached provider/collection context**.

---

## LLM Runtime Fixes
- Fixed an issue where Ask‑AI could use a **stale model** if preferences changed while the dialog was open.
- Runtime manager now **respects provider-specific model settings** and avoids cross-provider leakage.

---

## Telemetry Overhaul

### Core Session Model
- Added full **session-aware telemetry**: session start/end events, duration
  tracking, OS metadata, and provider/collection context caching.
- `TelemetryService` is now a **singleton**, initialized once at startup with
  the app version.
- Anonymous telemetry toggle now emits a **feature-toggle event**.
- Closing the last DB connection **clears cached provider/collection** to
  prevent stale context from leaking into subsequent events.
- Documentation updated to match the new session-aware model.

### Reliability & Sampling
- **Deterministic sampling:** SHA-256-based `should_sample()` helper produces
  stable, reproducible decisions per event type and seed — backend can
  reconstruct sampled populations reliably.
- **Error grouping:** canonical `error_hash` fingerprint normalizes numbers
  and hex addresses before hashing, grouping similar errors without
  transmitting raw traces.
- **Crash-marker lifecycle:** on startup the app detects an un-cleared crash
  marker from a previous run and emits `session.end` with
  `exit_reason: "crash"`. Clean shutdown clears the marker.
- **Sampled event metadata:** `queue_sampled_event()` attaches
  `sampling_rate`, `sampling_version`, and `sampling_seed_type` to every
  sampled event for backend aggregation.
- **Test safety:** `TelemetryService` forces test sentinel values
  (`app_version: "0.0-test"`, `client_type: "unit-tests"`) when running under
  pytest, making any escaped event immediately identifiable on the backend.

---

## Developer Tooling & Sample Data
- Added **subtitle (SRT) sample-data generation**:
  - New `SUBTITLES` data type  
  - `generate_subtitles_from_file` utility  
- Added **pdoc** as a dev dependency for documentation generation.

---

## Testing & CI
- Replaced timing-dependent polling with **deterministic worker
  synchronization** via `_batch_processed.wait()` — eliminates flakiness
  under CI load.
- **Global HTTP guard** in `conftest.py` returns synthetic 200 responses,
  preventing network leakage and ensuring batches clear cleanly across all
  tests.
- **Autouse singleton reset** plus test-mode queue-file purge guarantees
  clean state at every test boundary regardless of execution order.
- Added tests covering: sampling determinism, `error_hash` normalization,
  crash-marker full lifecycle, singleton enforcement, retry semantics,
  stale-context clearing on connection close, and the mid-flight shutdown
  race condition.

---

## Summary
0.6.1 strengthens Vector Inspector’s identity as a **diagnostic, session-aware intelligence console**.  
Telemetry is now reconstructable end-to-end, Ask‑AI behaves consistently across providers,  
and the UI surfaces more context with less friction.

---