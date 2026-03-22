import importlib
import sys


def test_early_telemetry_called(monkeypatch):
    # Ensure VI_NO_TELEMETRY doesn't suppress the early ping in this test.
    monkeypatch.delenv("VI_NO_TELEMETRY", raising=False)
    called = {}

    class FakeTelemetry:
        def __init__(self, *args, **kwargs):
            pass

        def send_launch_ping(self, app_version=None):
            called["launch"] = app_version

        @staticmethod
        def get_instance():
            return FakeTelemetry()

    # Patch the TelemetryService in the package before reloading main
    import vector_inspector.services.telemetry_service as ts

    monkeypatch.setattr(ts, "TelemetryService", FakeTelemetry)

    # Reload main to trigger the top-level early telemetry call
    if "vector_inspector.main" in sys.modules:
        importlib.reload(sys.modules["vector_inspector.main"])
    else:
        importlib.import_module("vector_inspector.main")

    assert "launch" in called
