"""Unified background task runner with progress signals and cancellation support."""

from collections.abc import Callable
from typing import Any, Optional

from PySide6.QtCore import QObject, QThread, Signal

from vector_inspector.core.logging import log_error


class TaskRunner(QThread):
    """
    Generic background task runner.

    Signals:
        result_ready: Emitted when task completes successfully (result)
        error: Emitted when task fails (error_message)
        progress: Emitted to report progress (message, percent)
    """

    result_ready = Signal(object)  # result
    error = Signal(str)  # error message
    progress = Signal(str, int)  # (message, percent)

    def __init__(self, task_func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """
        Initialize task runner.

        Args:
            task_func: Function to run in background
            *args: Positional arguments for task_func
            **kwargs: Keyword arguments for task_func
        """
        super().__init__()
        self.task_func = task_func
        self.args = args
        self.kwargs = kwargs
        self._cancelled = False

    def run(self) -> None:
        """Execute the task."""
        try:
            if self._cancelled:
                return

            # Execute task
            result = self.task_func(*self.args, **self.kwargs)

            if not self._cancelled:
                self.result_ready.emit(result)
        except Exception as e:
            if not self._cancelled:
                log_error("TaskRunner encountered an exception", exc_info=True)
                self.error.emit(str(e))

    def cancel(self) -> None:
        """Cancel the task."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if task was cancelled."""
        return self._cancelled

    def report_progress(self, message: str, percent: int = 0) -> None:
        """Report progress from within task (call from task_func if needed)."""
        if not self._cancelled:
            self.progress.emit(message, percent)


class ThreadedTaskRunner(QObject):
    """
    Centralized task runner for all background operations.

    Features:
        - Single API for running background tasks
        - Automatic thread cleanup
        - Cancellation support
        - Progress reporting
        - Error handling

    Usage:
        runner = ThreadedTaskRunner()
        runner.run_task(
            my_function,
            arg1, arg2,
            on_finished=handle_result,
            on_error=handle_error,
            on_progress=handle_progress
        )
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._active_tasks: dict[str, TaskRunner] = {}

    def run_task(
        self,
        task_func: Callable[..., Any],
        *args: Any,
        task_id: Optional[str] = None,
        on_finished: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[str, int], None]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Run a task in the background.

        Args:
            task_func: Function to run in background
            *args: Positional arguments for task_func
            task_id: Optional unique identifier for the task
            on_finished: Callback for successful completion (receives result)
            on_error: Callback for errors (receives error message)
            on_progress: Callback for progress updates (receives message, percent)
            **kwargs: Keyword arguments for task_func

        Returns:
            task_id: Unique identifier for this task
        """
        # Generate task ID if not provided
        if task_id is None:
            import uuid

            task_id = str(uuid.uuid4())

        # Cancel existing task with same ID if any
        if task_id in self._active_tasks:
            self.cancel_task(task_id)

        # Create task runner
        runner = TaskRunner(task_func, *args, **kwargs)

        # Connect signals
        if on_finished:
            runner.result_ready.connect(on_finished)
        if on_error:
            runner.error.connect(on_error)
        if on_progress:
            runner.progress.connect(on_progress)

        # Auto-cleanup when thread finishes or errored
        def cleanup() -> None:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
                runner.deleteLater()

        runner.finished.connect(cleanup)  # QThread.finished
        runner.error.connect(lambda _: cleanup())

        # Store and start
        self._active_tasks[task_id] = runner
        runner.start()

        return task_id

    def cancel_task(self, task_id: str) -> None:
        """
        Cancel a running task.

        Args:
            task_id: Identifier of task to cancel
        """
        if task_id in self._active_tasks:
            runner = self._active_tasks[task_id]
            runner.cancel()
            runner.wait(1000)  # Wait up to 1 second
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
            runner.deleteLater()

    def cancel_all(self) -> None:
        """Cancel all running tasks."""
        task_ids = list(self._active_tasks.keys())
        for task_id in task_ids:
            self.cancel_task(task_id)

    def is_running(self, task_id: str) -> bool:
        """Check if a task is currently running."""
        return task_id in self._active_tasks

    def get_active_count(self) -> int:
        """Get number of active tasks."""
        return len(self._active_tasks)
