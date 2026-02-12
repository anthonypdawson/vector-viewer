"""Global exception handling and telemetry integration.

This module sets up sys.excepthook and Qt exception handlers to ensure
all uncaught exceptions are sent to telemetry.
"""

import sys
import traceback
import uuid

from vector_inspector.core.logging import log_error

# Module-level singleton to avoid creating TelemetryService on every exception
_telemetry_singleton = None
_app_version = None


def _get_telemetry_service():
    """Get or create the singleton TelemetryService instance.

    This avoids re-creating the service (which does I/O) on every exception,
    preventing re-entrancy issues during cascading failures.
    """
    global _telemetry_singleton
    if _telemetry_singleton is None:
        from vector_inspector.services.telemetry_service import TelemetryService

        _telemetry_singleton = TelemetryService(app_version=_app_version)
    return _telemetry_singleton


def setup_global_exception_handler(app_version: str):
    """Install global exception hooks to send all uncaught errors to telemetry.

    Args:
        app_version: Application version string for telemetry
    """
    global _app_version
    _app_version = app_version

    original_excepthook = sys.excepthook

    def global_exception_hook(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions and send to telemetry."""
        # Generate correlation ID for this exception
        correlation_id = str(uuid.uuid4())

        # Format the exception with clean message
        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        error_message = "".join(traceback.format_exception_only(exc_type, exc_value)).strip()

        # Log locally
        log_error(f"[Uncaught Exception] {error_message}\n{tb_text}")

        # Send to telemetry (best-effort, don't let telemetry failures break exception handling)
        try:
            telemetry = _get_telemetry_service()
            telemetry.send_error_event(
                message=error_message,
                tb=tb_text,
                event_name="UncaughtException",
                extra={"exception_type": exc_type.__name__, "correlation_id": correlation_id},
            )
        except Exception as telemetry_error:
            # Don't let telemetry failures break exception handling
            try:
                log_error(f"[Telemetry] Failed to send exception: {telemetry_error}")
            except Exception:
                pass

        # Call the original excepthook to preserve default behavior
        original_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = global_exception_hook


def setup_qt_exception_handler():
    """Install Qt-specific exception handler for slot/signal exceptions.

    This catches exceptions that occur in Qt slots and signals which might
    otherwise be silently swallowed.

    Note: Requires app_version to be set via setup_global_exception_handler first.
    """
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler

        def qt_message_handler(msg_type, context, message):
            """Handle Qt messages and errors."""
            # Only send critical/fatal messages to telemetry
            if msg_type in (QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                # Generate correlation ID for this Qt error
                correlation_id = str(uuid.uuid4())

                try:
                    telemetry = _get_telemetry_service()
                    telemetry.send_error_event(
                        message=message,
                        tb=f"Qt {msg_type.name} in {context.file}:{context.line}",
                        event_name="QtError",
                        extra={
                            "msg_type": msg_type.name,
                            "file": context.file,
                            "line": context.line,
                            "function": context.function,
                            "correlation_id": correlation_id,
                        },
                    )
                except Exception as telemetry_error:
                    try:
                        log_error(f"[Telemetry] Failed to send Qt error: {telemetry_error}")
                    except Exception:
                        pass

            # Log the message locally
            if msg_type == QtMsgType.QtDebugMsg:
                pass  # Skip debug messages
            elif msg_type == QtMsgType.QtWarningMsg:
                log_error(f"[Qt Warning] {message}")
            elif msg_type == QtMsgType.QtCriticalMsg:
                log_error(f"[Qt Critical] {message}")
            elif msg_type == QtMsgType.QtFatalMsg:
                log_error(f"[Qt Fatal] {message}")

        qInstallMessageHandler(qt_message_handler)

    except Exception as e:
        log_error(f"[Exception Handler] Failed to install Qt message handler: {e}")


def exception_telemetry(event_name: str = "CaughtException", **extra_fields):
    """Decorator to catch and report exceptions from functions to telemetry.

    Use this decorator on functions where you want to catch exceptions,
    send them to telemetry, and optionally re-raise.

    Args:
        event_name: Name for the telemetry event (default: "CaughtException")
        **extra_fields: Additional fields to include in telemetry metadata

    Example:
        @exception_telemetry(event_name="DataImportError", feature="data_import")
        def import_data():
            # ...code that might raise...
            pass
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Generate correlation ID for this exception
                correlation_id = str(uuid.uuid4())

                # Format the exception with clean message
                tb_text = traceback.format_exc()
                exc_type = type(e)
                error_message = "".join(traceback.format_exception_only(exc_type, e)).strip()

                # Log locally
                log_error(f"[Exception in {func.__name__}] {error_message}\n{tb_text}")

                # Send to telemetry (best-effort)
                try:
                    telemetry = _get_telemetry_service()
                    extra = {
                        "function": func.__name__,
                        "exception_type": exc_type.__name__,
                        "correlation_id": correlation_id,
                        **extra_fields,
                    }
                    telemetry.send_error_event(
                        message=error_message,
                        tb=tb_text,
                        event_name=event_name,
                        extra=extra,
                    )
                except Exception as telemetry_error:
                    try:
                        log_error(f"[Telemetry] Failed to send exception: {telemetry_error}")
                    except Exception:
                        pass

                # Re-raise the original exception
                raise

        return wrapper

    return decorator
