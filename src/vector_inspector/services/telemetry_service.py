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
        - ``TelemetryService.queue_event(event)``      — one-liner queue
        - ``TelemetryService.send_event(name, payload)`` — queue + flush
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
        # Disable telemetry if running under pytest or unittest
        if "pytest" in sys.modules or "unittest" in sys.modules:
            self.settings.set("telemetry.enabled", False)
        self._load_queue()

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
        hwid = self.settings.get("telemetry.hwid")
        if not hwid:
            hwid = str(uuid.uuid4())
            self.settings.set("telemetry.hwid", hwid)
        return hwid

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
        if not self.is_enabled():
            log_info("[Telemetry] Telemetry disabled; not queuing event.")
            return

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

        with self._lock:
            self.queue.append(event)
            self._save_queue()

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
                "os": platform.system() + "-" + platform.release(),
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
            svc.send_batch()
        except Exception as e:
            log_error(f"[Telemetry] send_event failed: {e}")
