import json
import platform
import sys
import threading
import uuid
from pathlib import Path

import requests

from vector_inspector import get_version
from vector_inspector.core.logging import log_error, log_info
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.utils.hardware_info import get_hardware_info

TELEMETRY_ENDPOINT = "https://api.divinedevops.com/api/v1/telemetry"

# Module-level singleton and its initialisation lock
_instance: "TelemetryService | None" = None
_instance_lock = threading.Lock()


class TelemetryService:
    """Singleton telemetry client.

    Lifecycle
    ---------
    * Call ``TelemetryService.initialize(app_version=...)`` **once** at app
      startup (in ``main.py``) before any background threads fire.
    * Everywhere else use the static helpers:
        - ``TelemetryService.queue_event_static(event)`` — one-liner queue
        - ``TelemetryService.send_event(name, payload)``  — queue + async flush
        - ``TelemetryService.get_instance()``           — full instance

    Backwards compatibility
    -----------------------
    Constructing ``TelemetryService()`` / ``TelemetryService(app_version=x)``
    is still supported; it initialises the singleton on first call and returns
    it on subsequent calls (ignoring later ``app_version`` overrides).
    Use ``TelemetryService.reset_for_tests()`` in test teardown.
    """

    # ------------------------------------------------------------------ #
    # Singleton management                                                 #
    # ------------------------------------------------------------------ #

    def __new__(cls, settings_service=None, app_version=None, client_type="vector-inspector"):
        global _instance
        with _instance_lock:
            if _instance is None:
                inst = super().__new__(cls)
                inst._initialised = False
                _instance = inst
            return _instance

    def __init__(self, settings_service=None, app_version=None, client_type="vector-inspector"):
        if self._initialised:
            return
        self._initialised = True
        self._lock = threading.Lock()
        self.settings = settings_service or SettingsService()
        self.queue_file = Path.home() / ".vector-inspector" / "telemetry_queue.json"
        self.app_version = app_version or get_version()
        self.client_type = client_type
        self.session_id: str | None = self.settings.get("telemetry.session_id")
        # Cache OS and runtime context to avoid repeated platform calls
        try:
            self._cached_os = platform.platform()
        except Exception:
            self._cached_os = ""
        # Cached provider / collection (set by UI when they change)
        self._cached_provider: str | None = None
        self._cached_collection: str | None = None
        # Cache hwid to avoid repeated settings access; persisted if missing
        try:
            hwid = self.settings.get("telemetry.hwid")
            if not hwid:
                hwid = str(uuid.uuid4())
                self.settings.set("telemetry.hwid", hwid)
            self._cached_hwid: str = hwid
        except Exception:
            # Best-effort fallback
            self._cached_hwid = str(uuid.uuid4())
        # Disable telemetry if running under pytest or unittest, but only
        # if the setting isn't already present. Tests may explicitly enable
        # telemetry on the settings object prior to constructing the
        # service; respect that to allow controlled test behavior.
        if "pytest" in sys.modules or "unittest" in sys.modules:
            try:
                if self.settings.get("telemetry.enabled", None) is None:
                    self.settings.set("telemetry.enabled", False)
            except Exception:
                # Best-effort: ignore settings errors during test-time init
                pass
        self._load_queue()

        # Background worker to flush telemetry periodically or when signalled.
        # Use a non-daemon thread so we can join it during shutdown and
        # ensure queued events have a chance to send.
        self._worker_stop = threading.Event()
        self._worker_wake = threading.Event()
        try:
            self._worker = threading.Thread(target=self._worker_loop, daemon=False, name="telemetry-worker")
            self._worker.start()
        except Exception:
            # Best-effort: if thread creation fails, telemetry still queues locally
            self._worker = None

    @classmethod
    def initialize(
        cls, app_version: str, settings_service=None, client_type: str = "vector-inspector"
    ) -> "TelemetryService":
        """Initialise (or return) the singleton with a known app version.

        Call this once at app startup before any telemetry is emitted.
        """
        return cls(settings_service=settings_service, app_version=app_version, client_type=client_type)

    @classmethod
    def get_instance(cls) -> "TelemetryService":
        """Return the singleton, creating a default instance if necessary."""
        global _instance
        if _instance is None:
            return cls()
        return _instance

    @classmethod
    def reset_for_tests(cls) -> None:
        """Destroy the singleton so tests get a clean slate.

        Must only be called from test teardown / conftest fixtures.
        """
        global _instance
        with _instance_lock:
            # Stop worker thread if running
            try:
                if _instance is not None and getattr(_instance, "_worker_stop", None) is not None:
                    try:
                        _instance._worker_stop.set()
                        _instance._worker_wake.set()
                        if getattr(_instance, "_worker", None) is not None:
                            _instance._worker.join(timeout=1)
                    except Exception:
                        pass
            finally:
                _instance = None

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _load_queue(self):
        if self.queue_file.exists():
            try:
                with open(self.queue_file, encoding="utf-8") as f:
                    self.queue = json.load(f)
            except Exception:
                self.queue = []
        else:
            self.queue = []

    def _worker_loop(self) -> None:
        """Background worker: periodically flush queued telemetry.

        Wakes when `_worker_wake` is set or every 5 seconds. Exits when
        `_worker_stop` is set; performs a final flush before returning.
        """
        try:
            while not self._worker_stop.is_set():
                # Wait to be woken or timeout
                try:
                    self._worker_wake.wait(timeout=5)
                except Exception:
                    pass
                # Clear the wake flag and attempt a flush
                try:
                    self._worker_wake.clear()
                except Exception:
                    pass
                try:
                    self.send_batch()
                except Exception as e:
                    log_error(f"[Telemetry] worker send_batch failed: {e}")
            # Final flush on exit
            try:
                self.send_batch()
            except Exception:
                pass
        except Exception:
            # Swallow errors to avoid crashing the host process
            pass

    def _save_queue(self):
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(self.queue, f, indent=2)

    # ------------------------------------------------------------------ #
    # Instance API                                                         #
    # ------------------------------------------------------------------ #

    def is_enabled(self) -> bool:
        return bool(self.settings.get("telemetry.enabled", True))

    def get_hwid(self) -> str:
        # Return cached hwid set during initialization to avoid I/O.
        # Fallback to a generated UUID if the cached value is not present.
        return getattr(self, "_cached_hwid", str(uuid.uuid4()))

    def get_cached_os(self) -> str:
        """Return cached OS string."""
        return getattr(self, "_cached_os", "")

    def set_provider(self, provider_name: str | None) -> None:
        """Cache the active database provider name for telemetry."""
        try:
            self._cached_provider = provider_name
        except Exception:
            pass

    def set_collection(self, collection_name: str | None) -> None:
        """Cache the active collection name for telemetry."""
        try:
            self._cached_collection = collection_name
        except Exception:
            pass

    def set_session_id(self, session_id: str) -> None:
        """Set the active session id and persist it to settings."""
        try:
            self.session_id = session_id
            self.settings.set("telemetry.session_id", session_id)
        except Exception as e:
            log_error(f"[Telemetry] Failed to set session_id: {e}")

    def queue_event(self, event: dict) -> None:
        """Queue an event for batch sending.

        Automatically populates ``app_version``, ``hwid``, ``client_type``,
        and injects ``session_id`` into ``metadata`` when available.
        """
        # If telemetry is disabled, do not record or persist events. This
        # avoids collecting data while the user has telemetry turned off.
        if not self.is_enabled():
            log_info("[Telemetry] Telemetry disabled; not queuing event.")
            return

        # Persist queued events locally. Sending is gated by
        # `send_batch()` which also checks `is_enabled()` so tests can
        # control whether the worker actually posts events by toggling
        # settings.

        if "app_version" not in event:
            event["app_version"] = self.app_version
        if "hwid" not in event:
            event["hwid"] = self.get_hwid()
        if "client_type" not in event:
            event["client_type"] = self.client_type

        metadata = event.get("metadata")
        if metadata is None:
            metadata = {}
            event["metadata"] = metadata
        try:
            if self.session_id and "session_id" not in metadata:
                metadata["session_id"] = self.session_id
        except Exception:
            pass
        # Inject cached context when not provided explicitly
        try:
            if self._cached_provider and "db_provider" not in metadata:
                metadata["db_provider"] = self._cached_provider
        except Exception:
            pass
        try:
            if self._cached_collection and "collection_name" not in metadata:
                metadata["collection_name"] = self._cached_collection
        except Exception:
            pass

        with self._lock:
            self.queue.append(event)
            self._save_queue()
            # Do not automatically wake the background worker here; callers
            # who want an immediate flush should call `send_event` or set the
            # wake event themselves. Avoids races in tests that assert the
            # queue is non-empty immediately after `queue_event`.

    def send_batch(self) -> None:
        """Send all queued events to the telemetry endpoint."""
        with self._lock:
            if not self.is_enabled() or not self.queue:
                return
            to_send = list(self.queue)

        sent = []
        for event in to_send:
            try:
                log_info(f"[Telemetry] Sending to {TELEMETRY_ENDPOINT}\nPayload: {json.dumps(event, indent=2)}")
                resp = requests.post(TELEMETRY_ENDPOINT, json=event, timeout=5)
                log_info(f"[Telemetry] Response: {resp.status_code} {resp.text}")
                if resp.status_code in (200, 201):
                    sent.append(event)
            except Exception as e:
                log_error(f"[Telemetry] Exception: {e}")

        with self._lock:
            self.queue = [e for e in self.queue if e not in sent]
            self._save_queue()

    def send_launch_ping(self, app_version: str, client_type: str = "vector-inspector") -> None:
        log_info("[Telemetry] send_launch_ping called")
        if not self.is_enabled():
            log_info("[Telemetry] Telemetry is not enabled; skipping launch ping.")
            return
        try:
            hardware = get_hardware_info()
        except Exception as e:
            hardware = {"error": str(e)}
        event = {
            "hwid": self.get_hwid(),
            "event_name": "app_launch",
            "app_version": app_version,
            "client_type": client_type,
            "metadata": {
                "os": self.get_cached_os(),
                "hardware": hardware,
            },
        }
        log_info(f"[Telemetry] Launch event payload: {json.dumps(event, indent=2)}")
        self.queue_event(event)
        self.send_batch()

    def send_error_event(
        self,
        message: str,
        tb: str,
        app_version=None,
        event_name: str = "Error",
        extra: dict | None = None,
        client_type=None,
    ) -> None:
        """Send an error-style telemetry event (best-effort, never raises)."""
        log_info("[Telemetry] send_error_event called")
        try:
            if not self.is_enabled():
                log_info("[Telemetry] Telemetry is not enabled; skipping error event.")
                return
            metadata = {"message": message, "traceback": tb}
            if extra and isinstance(extra, dict):
                metadata.update(extra)
            event = {
                "hwid": self.get_hwid(),
                "event_name": event_name,
                "app_version": app_version or self.app_version,
                "client_type": client_type or self.client_type,
                "metadata": metadata,
            }
            log_info(f"[Telemetry] Error event payload: {json.dumps(event, indent=2)}")
            self.queue_event(event)
            self.send_batch()
        except Exception as e:
            log_error(f"[Telemetry] send_error_event failed: {e}")

    def flush_on_shutdown(self) -> None:
        """Synchronously flush all queued events. Call from the app closeEvent."""
        try:
            # Signal worker to stop and wake it so it can exit promptly
            try:
                if getattr(self, "_worker_stop", None) is not None:
                    self._worker_stop.set()
                if getattr(self, "_worker_wake", None) is not None:
                    self._worker_wake.set()
                if getattr(self, "_worker", None) is not None:
                    # Wait briefly for worker to finish
                    self._worker.join(timeout=5)
            except Exception:
                pass

            # Final synchronous flush on the calling thread to ensure events
            # are attempted before process exit.
            self.send_batch()
        except Exception as e:
            log_error(f"[Telemetry] flush_on_shutdown failed: {e}")

    def purge(self) -> None:
        with self._lock:
            self.queue = []
            self._save_queue()

    def get_queue(self) -> list:
        with self._lock:
            return list(self.queue)

    # ------------------------------------------------------------------ #
    # Static one-liner API (preferred at call sites)                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def queue_event_static(event: dict) -> None:
        """One-liner: queue a single event on the singleton (best-effort).

        Usage::

            TelemetryService.queue_event_static({"event_name": "foo", "metadata": {...}})
        """
        try:
            TelemetryService.get_instance().queue_event(event)
        except Exception as e:
            log_error(f"[Telemetry] queue_event_static failed: {e}")

    @staticmethod
    def send_event(event_name: str, payload: dict) -> None:
        """One-liner: queue an event and flush immediately (best-effort).

        Usage::

            TelemetryService.send_event("clustering.run", {"metadata": {...}})

        ``payload`` may be a bare metadata dict **or** a full event envelope
        that already contains ``event_name`` — both are handled.
        """
        try:
            svc = TelemetryService.get_instance()
            event = payload if "event_name" in payload else {"event_name": event_name, **(payload or {})}
            svc.queue_event(event)
            # Wake the background worker to process the new event promptly.
            try:
                if getattr(svc, "_worker_wake", None) is not None:
                    svc._worker_wake.set()
            except Exception:
                pass
        except Exception as e:
            log_error(f"[Telemetry] send_event failed: {e}")
