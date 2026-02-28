import sys

import pytest


def test_setup_global_exception_handler_calls_original_and_telemetry(monkeypatch):
    import vector_inspector.utils.exception_handler as eh

    called = {}

    def original_hook(exc_type, exc_value, exc_tb):
        called["original"] = True

    # Replace sys.excepthook before setup so it gets captured
    monkeypatch.setattr(sys, "excepthook", original_hook)

    # Provide a fake telemetry service
    class FakeTelemetry:
        def __init__(self, *args, **kwargs):
            self.sent = []

        def send_error_event(self, message, tb, event_name, extra=None, **kwargs):
            self.sent.append((message, event_name, extra))

    monkeypatch.setattr(eh, "_get_telemetry_service", lambda: FakeTelemetry())

    # Install handler
    eh.setup_global_exception_handler("0.0")

    # Trigger the new excepthook (simulate uncaught exception)
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        # Call the installed handler (which should call original_hook)
        sys.excepthook(exc_type, exc_value, exc_tb)

    assert called.get("original") is True


def test_exception_decorator_sends_telemetry_and_reraises(monkeypatch):
    import vector_inspector.utils.exception_handler as eh

    recorded = {}

    class FakeTelemetry:
        def __init__(self, *args, **kwargs):
            pass

        def send_error_event(self, message, tb, event_name, extra=None, **kwargs):
            recorded["sent"] = (message, event_name, extra)

    monkeypatch.setattr(eh, "_get_telemetry_service", lambda: FakeTelemetry())

    @eh.exception_telemetry(event_name="TestEvent", feature="unit")
    def will_raise(x):
        raise ValueError("ouch")

    with pytest.raises(ValueError):
        will_raise(1)

    assert "sent" in recorded
    msg, event, extra = recorded["sent"]
    assert event == "TestEvent"
    assert extra.get("function") == "will_raise"


# ---------------------------------------------------------------------------
# Additional coverage: setup_qt_exception_handler, decorator success path,
# telemetry failure path in global hook
# ---------------------------------------------------------------------------


def test_setup_qt_exception_handler_does_not_raise():
    """setup_qt_exception_handler installs a message handler without raising."""
    import vector_inspector.utils.exception_handler as eh

    # Should not raise - just installs a Qt message handler
    eh.setup_qt_exception_handler()


def test_exception_decorator_success_path_returns_value(monkeypatch):
    """Decorator on a function that succeeds should return the value transparently."""
    import vector_inspector.utils.exception_handler as eh

    class FakeTelemetry:
        def send_error_event(self, *a, **k):
            pass

    monkeypatch.setattr(eh, "_get_telemetry_service", lambda: FakeTelemetry())

    @eh.exception_telemetry(event_name="TestOK")
    def succeeds(x, y):
        return x + y

    result = succeeds(2, 3)
    assert result == 5


def test_global_exception_hook_telemetry_failure_is_silenced(monkeypatch):
    """When telemetry raises during the exception hook, the original hook is still called."""
    import vector_inspector.utils.exception_handler as eh

    called = {}

    def original_hook(exc_type, exc_value, exc_tb):
        called["original"] = True

    monkeypatch.setattr(sys, "excepthook", original_hook)

    # Make telemetry raise to exercise the inner except path
    def failing_telemetry():
        raise RuntimeError("telemetry down")

    monkeypatch.setattr(eh, "_get_telemetry_service", failing_telemetry)

    eh.setup_global_exception_handler("0.1")

    try:
        raise ValueError("test error")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        sys.excepthook(exc_type, exc_value, exc_tb)

    assert called.get("original") is True


def test_qt_message_handler_routes_messages(monkeypatch):
    """Qt message handler logs warning/critical/fatal via log_error."""
    from PySide6.QtCore import QMessageLogContext, QtMsgType

    import vector_inspector.utils.exception_handler as eh

    logged = []
    monkeypatch.setattr(
        "vector_inspector.utils.exception_handler.log_error",
        lambda msg, *a, **k: logged.append(str(msg)),
    )

    class FakeTelemetry:
        def send_error_event(self, *a, **k):
            pass

    monkeypatch.setattr(eh, "_get_telemetry_service", lambda: FakeTelemetry())

    # Capture the qt_message_handler that gets installed
    installed_handler = {}

    def _patched_install(handler):
        installed_handler["fn"] = handler

    import PySide6.QtCore as qtcore

    monkeypatch.setattr(qtcore, "qInstallMessageHandler", _patched_install)

    eh.setup_qt_exception_handler()

    handler = installed_handler.get("fn")
    assert handler is not None, "Expected qInstallMessageHandler to be called"

    ctx = QMessageLogContext()

    # Debug message — should be silent
    handler(QtMsgType.QtDebugMsg, ctx, "debug msg")
    assert not any("debug" in l.lower() for l in logged)

    # Warning message
    handler(QtMsgType.QtWarningMsg, ctx, "a warning")
    assert any("[Qt Warning]" in l for l in logged)

    # Critical message
    handler(QtMsgType.QtCriticalMsg, ctx, "critical!")
    assert any("[Qt Critical]" in l for l in logged)

    # Fatal message
    handler(QtMsgType.QtFatalMsg, ctx, "fatal!")
    assert any("[Qt Fatal]" in l for l in logged)


def test_qt_message_handler_critical_sends_telemetry(monkeypatch):
    """Critical Qt messages are forwarded to telemetry."""
    from PySide6.QtCore import QMessageLogContext, QtMsgType

    import vector_inspector.utils.exception_handler as eh

    telemetry_calls = []

    class FakeTelemetry:
        def send_error_event(self, message, tb, event_name, extra=None, **kw):
            telemetry_calls.append(event_name)

    monkeypatch.setattr(eh, "_get_telemetry_service", lambda: FakeTelemetry())
    monkeypatch.setattr(
        "vector_inspector.utils.exception_handler.log_error",
        lambda *a, **k: None,
    )

    installed_handler = {}

    def _patched_install(handler):
        installed_handler["fn"] = handler

    import PySide6.QtCore as qtcore

    monkeypatch.setattr(qtcore, "qInstallMessageHandler", _patched_install)

    eh.setup_qt_exception_handler()

    handler = installed_handler["fn"]
    ctx = QMessageLogContext()

    handler(QtMsgType.QtCriticalMsg, ctx, "something went wrong")
    assert "QtError" in telemetry_calls


def test_qt_message_handler_telemetry_failure_silenced(monkeypatch):
    """Telemetry failure in Qt handler doesn't propagate."""
    from PySide6.QtCore import QMessageLogContext, QtMsgType

    import vector_inspector.utils.exception_handler as eh

    monkeypatch.setattr(eh, "_get_telemetry_service", lambda: (_ for _ in ()).throw(RuntimeError("telemetry dead")))
    monkeypatch.setattr(
        "vector_inspector.utils.exception_handler.log_error",
        lambda *a, **k: None,
    )

    installed_handler = {}

    def _patched_install(handler):
        installed_handler["fn"] = handler

    import PySide6.QtCore as qtcore

    monkeypatch.setattr(qtcore, "qInstallMessageHandler", _patched_install)

    eh.setup_qt_exception_handler()

    handler = installed_handler["fn"]
    ctx = QMessageLogContext()

    # Should NOT raise even though telemetry fails
    handler(QtMsgType.QtCriticalMsg, ctx, "critical with broken telemetry")


def test_exception_decorator_telemetry_failure_still_reraises(monkeypatch):
    """When telemetry send fails inside decorator, the original exception is still re-raised."""
    import vector_inspector.utils.exception_handler as eh

    monkeypatch.setattr(
        eh,
        "_get_telemetry_service",
        lambda: (_ for _ in ()).throw(RuntimeError("telemetry dead")),
    )
    monkeypatch.setattr(
        "vector_inspector.utils.exception_handler.log_error",
        lambda *a, **k: None,
    )

    @eh.exception_telemetry(event_name="FailEvent")
    def always_fails():
        raise ValueError("underlying error")

    with pytest.raises(ValueError, match="underlying error"):
        always_fails()


def test_get_telemetry_service_creates_singleton(monkeypatch):
    """_get_telemetry_service() creates and caches the TelemetryService."""
    import vector_inspector.utils.exception_handler as eh

    # Reset singleton so we exercise the creation path
    original_singleton = eh._telemetry_singleton
    eh._telemetry_singleton = None

    class FakeTelemetryService:
        def __init__(self, app_version=None):
            pass

    monkeypatch.setattr(
        "vector_inspector.utils.exception_handler.TelemetryService",
        FakeTelemetryService,
        raising=False,
    )

    try:
        # Import the TelemetryService into the module's namespace
        import vector_inspector.services.telemetry_service as ts_module

        monkeypatch.setattr(ts_module, "TelemetryService", FakeTelemetryService)
        service = eh._get_telemetry_service()
        assert service is not None
        # Second call should return the cached instance
        service2 = eh._get_telemetry_service()
        assert service is service2
    finally:
        eh._telemetry_singleton = original_singleton


def test_global_exception_hook_inner_log_error_failure_silenced(monkeypatch):
    """log_error raises inside telemetry-failure handler → silenced, original hook still called."""
    import vector_inspector.utils.exception_handler as eh

    called = {}

    def original_hook(exc_type, exc_value, exc_tb):
        called["original"] = True

    monkeypatch.setattr(sys, "excepthook", original_hook)

    def failing_telemetry():
        raise RuntimeError("telemetry down")

    monkeypatch.setattr(eh, "_get_telemetry_service", failing_telemetry)

    # log_error raises only when logging the telemetry failure message
    def failing_log_error(msg, *a, **k):
        if "Failed to send exception" in str(msg):
            raise RuntimeError("log_error dead")

    monkeypatch.setattr("vector_inspector.utils.exception_handler.log_error", failing_log_error)

    eh.setup_global_exception_handler("0.1")

    try:
        raise ValueError("test error")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        sys.excepthook(exc_type, exc_value, exc_tb)  # Must not raise

    assert called.get("original") is True


def test_qt_message_handler_inner_log_error_failure_silenced(monkeypatch):
    """log_error raises inside Qt handler telemetry-failure path → silenced."""
    import PySide6.QtCore as qtcore
    from PySide6.QtCore import QMessageLogContext, QtMsgType

    import vector_inspector.utils.exception_handler as eh

    installed_handler = {}

    def _patched_install(handler):
        installed_handler["fn"] = handler

    monkeypatch.setattr(qtcore, "qInstallMessageHandler", _patched_install)
    monkeypatch.setattr(eh, "_get_telemetry_service", lambda: (_ for _ in ()).throw(RuntimeError("telemetry dead")))

    # log_error raises only when logging the telemetry failure; succeeds for local logging
    def selective_failing_log_error(msg, *a, **k):
        if "Failed to send Qt error" in str(msg):
            raise RuntimeError("log_error dead")

    monkeypatch.setattr("vector_inspector.utils.exception_handler.log_error", selective_failing_log_error)

    eh.setup_qt_exception_handler()

    handler = installed_handler["fn"]
    ctx = QMessageLogContext()
    # Should NOT raise even though telemetry fails AND inner log_error also fails
    handler(QtMsgType.QtCriticalMsg, ctx, "critical msg")


def test_setup_qt_handler_install_failure_logs_error(monkeypatch):
    """qInstallMessageHandler raises → outer except logs error."""
    import PySide6.QtCore as qtcore

    import vector_inspector.utils.exception_handler as eh

    logged = []
    monkeypatch.setattr(
        "vector_inspector.utils.exception_handler.log_error",
        lambda msg, *a, **k: logged.append(str(msg)),
    )

    original_install = qtcore.qInstallMessageHandler
    call_count = [0]

    def failing_first_call(handler):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("cannot install handler")
        # Subsequent calls (e.g. pytest-qt teardown) use the real function
        return original_install(handler)

    monkeypatch.setattr(qtcore, "qInstallMessageHandler", failing_first_call)

    # Should not raise; outer except catches and logs the error
    eh.setup_qt_exception_handler()

    assert any("[Exception Handler]" in l for l in logged)


def test_exception_decorator_inner_log_error_failure_silenced(monkeypatch):
    """log_error raises inside decorator telemetry-failure handler → original exception still raised."""
    import vector_inspector.utils.exception_handler as eh

    monkeypatch.setattr(eh, "_get_telemetry_service", lambda: (_ for _ in ()).throw(RuntimeError("telemetry dead")))

    # log_error raises only when logging the telemetry failure
    def selective_failing_log_error(msg, *a, **k):
        if "Failed to send exception" in str(msg):
            raise RuntimeError("log_error dead")

    monkeypatch.setattr("vector_inspector.utils.exception_handler.log_error", selective_failing_log_error)

    @eh.exception_telemetry(event_name="TestEvent")
    def raises_value_error():
        raise ValueError("original error")

    with pytest.raises(ValueError, match="original error"):
        raises_value_error()
