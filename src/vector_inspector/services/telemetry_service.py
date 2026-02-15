import json
import platform
import uuid
from pathlib import Path

import requests

from vector_inspector import get_version
from vector_inspector.core.logging import log_error, log_info
from vector_inspector.services.settings_service import SettingsService

TELEMETRY_ENDPOINT = "https://api.divinedevops.com/api/v1/telemetry"


class TelemetryService:
    def __init__(self, settings_service=None, app_version=None, client_type="vector-inspector"):
        """Initialize TelemetryService.

        Args:
            settings_service: Optional SettingsService instance
            app_version: Optional app version (defaults to get_version())
            client_type: Client type identifier (default: "vector-inspector")
        """
        self.settings = settings_service or SettingsService()
        self.queue_file = Path.home() / ".vector-inspector" / "telemetry_queue.json"
        self.app_version = app_version or get_version()
        self.client_type = client_type
        self._load_queue()

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

    def is_enabled(self):
        return bool(self.settings.get("telemetry.enabled", True))

    def get_hwid(self):
        # Use a persistent UUID for this client
        hwid = self.settings.get("telemetry.hwid")
        if not hwid:
            hwid = str(uuid.uuid4())
            self.settings.set("telemetry.hwid", hwid)
        return hwid

    def queue_event(self, event):
        """Queue an event for sending to telemetry.

        Automatically populates app_version, hwid, and client_type if not provided.

        Args:
            event: Event dict with at least event_name and metadata fields
        """
        # Do not queue events when telemetry is disabled
        if not self.is_enabled():
            log_info("[Telemetry] Telemetry disabled; not queuing event.")
            return

        # Auto-populate standard fields if not present
        if "app_version" not in event:
            event["app_version"] = self.app_version
        if "hwid" not in event:
            event["hwid"] = self.get_hwid()
        if "client_type" not in event:
            event["client_type"] = self.client_type

        self.queue.append(event)
        self._save_queue()

    def send_batch(self):
        if not self.is_enabled() or not self.queue:
            return
        sent = []
        for event in self.queue:
            try:
                log_info(
                    f"[Telemetry] Sending to {TELEMETRY_ENDPOINT}\nPayload: {json.dumps(event, indent=2)}"
                )
                resp = requests.post(TELEMETRY_ENDPOINT, json=event, timeout=5)
                log_info(f"[Telemetry] Response: {resp.status_code} {resp.text}")
                if resp.status_code in (200, 201):
                    sent.append(event)
            except Exception as e:
                log_error(f"[Telemetry] Exception: {e}")
        # Remove sent events
        self.queue = [e for e in self.queue if e not in sent]
        self._save_queue()

    def send_launch_ping(self, app_version, client_type="vector-inspector"):
        log_info("[Telemetry] send_launch_ping called")
        if not self.is_enabled():
            log_info("[Telemetry] Telemetry is not enabled; skipping launch ping.")
            return
        event = {
            "hwid": self.get_hwid(),
            "event_name": "app_launch",
            "app_version": app_version,
            "client_type": client_type,
            "metadata": {"os": platform.system() + "-" + platform.release()},
        }
        log_info(f"[Telemetry] Launch event payload: {json.dumps(event, indent=2)}")
        self.queue_event(event)
        self.send_batch()

    def send_error_event(
        self,
        message,
        tb,
        app_version=None,
        event_name="Error",
        extra=None,
        client_type=None,
    ):
        """Send an error-style telemetry event containing a message and traceback.

        This is best-effort and will not raise; failures are logged.

        Args:
            message: Error message
            tb: Traceback string
            app_version: Optional override for app version (uses instance default if not provided)
            event_name: Event name (default: "Error")
            extra: Additional metadata dict
            client_type: Optional override for client type
        """
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

    def purge(self):
        self.queue = []
        self._save_queue()

    def get_queue(self):
        return list(self.queue)
