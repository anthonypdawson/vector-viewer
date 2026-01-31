import json
import platform
import uuid
import requests
from pathlib import Path
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.core.logging import log_info, log_error

TELEMETRY_ENDPOINT = "https://api.divinedevops.com/api/v1/telemetry"


class TelemetryService:
    def __init__(self, settings_service=None):
        self.settings = settings_service or SettingsService()
        self.queue_file = Path.home() / ".vector-inspector" / "telemetry_queue.json"
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

    def purge(self):
        self.queue = []
        self._save_queue()

    def get_queue(self):
        return list(self.queue)
