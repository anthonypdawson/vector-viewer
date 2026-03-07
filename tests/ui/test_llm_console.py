"""Unit tests for LLMConsoleWindow and _GenerateWorker.

These tests cover the Qt UI tool in vector_inspector/tools/llm_console.py.
They use FakeLLMProvider to avoid real network calls and run headlessly
via pytest-qt.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.utils.fake_llm_provider import FakeLLMProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_window(qtbot, provider=None):
    """Return a fully-constructed LLMConsoleWindow with the given provider."""
    from vector_inspector.tools.llm_console import LLMConsoleWindow

    if provider is None:
        provider = FakeLLMProvider()
    win = LLMConsoleWindow(provider)
    qtbot.addWidget(win)
    return win


# ---------------------------------------------------------------------------
# _GenerateWorker — background thread unit tests
# (Runs synchronously via worker.run() to avoid real threads in tests)
# ---------------------------------------------------------------------------


class TestGenerateWorkerStreaming:
    """_GenerateWorker emits chunk + done when provider supports streaming."""

    def test_run_emits_chunks_and_done(self, qtbot):
        from vector_inspector.tools.llm_console import _GenerateWorker

        provider = FakeLLMProvider(mode="streaming", fragment_size=3, latency_ms=0)
        messages = [{"role": "user", "content": "hello"}]

        received_chunks: list[str] = []
        done_count = [0]

        worker = _GenerateWorker(provider, messages, provider.get_model_name())
        worker.chunk.connect(received_chunks.append)
        worker.done.connect(lambda: done_count.__setitem__(0, done_count[0] + 1))

        worker.run()  # run synchronously in test thread

        assert len(received_chunks) > 0
        assert done_count[0] == 1

    def test_run_full_response_contains_prompt_content(self, qtbot):
        """Streaming worker re-assembles all delta chunks into the original prompt content."""
        from vector_inspector.tools.llm_console import _GenerateWorker

        provider = FakeLLMProvider(mode="streaming", fragment_size=1)
        messages = [{"role": "user", "content": "abc"}]

        received: list[str] = []
        worker = _GenerateWorker(provider, messages, provider.get_model_name())
        worker.chunk.connect(received.append)
        worker.run()

        # FakeLLMProvider in streaming mode echoes the input content back
        assert "abc" in "".join(received)


class TestGenerateWorkerNonStreaming:
    """_GenerateWorker emits one chunk for non-streaming providers."""

    def test_run_emits_single_chunk_and_done(self, qtbot):
        from vector_inspector.tools.llm_console import _GenerateWorker

        provider = FakeLLMProvider(mode="echo")  # echo mode; streaming=False
        # Patch capabilities to report non-streaming
        caps = provider.get_capabilities()
        caps_no_stream = MagicMock()
        caps_no_stream.supports_streaming = False
        with patch.object(provider, "get_capabilities", return_value=caps_no_stream):
            messages = [{"role": "user", "content": "hi there"}]
            received: list[str] = []
            done_count = [0]

            worker = _GenerateWorker(provider, messages, provider.get_model_name())
            worker.chunk.connect(received.append)
            worker.done.connect(lambda: done_count.__setitem__(0, done_count[0] + 1))
            worker.run()

        assert len(received) == 1
        assert done_count[0] == 1
        assert "hi there" in received[0]


class TestGenerateWorkerError:
    """_GenerateWorker emits error + done when provider raises."""

    def test_run_emits_error_signal_and_done(self, qtbot):
        from vector_inspector.tools.llm_console import _GenerateWorker

        provider = FakeLLMProvider(mode="error_inject", error_rate=1.0)
        messages = [{"role": "user", "content": "fail me"}]

        errors: list[str] = []
        done_count = [0]

        worker = _GenerateWorker(provider, messages, provider.get_model_name())
        worker.error.connect(errors.append)
        worker.done.connect(lambda: done_count.__setitem__(0, done_count[0] + 1))
        worker.run()

        assert len(errors) == 1
        assert done_count[0] == 1  # done is always emitted

    def test_run_error_message_is_nonempty_string(self, qtbot):
        from vector_inspector.tools.llm_console import _GenerateWorker

        provider = FakeLLMProvider(mode="error_inject", error_rate=1.0)
        messages = [{"role": "user", "content": "x"}]

        errors: list[str] = []
        worker = _GenerateWorker(provider, messages, provider.get_model_name())
        worker.error.connect(errors.append)
        worker.run()

        assert errors and isinstance(errors[0], str) and len(errors[0]) > 0


# ---------------------------------------------------------------------------
# LLMConsoleWindow — construction and initial state
# ---------------------------------------------------------------------------


class TestLLMConsoleWindowInit:
    def test_window_title_contains_llm_console(self, qtbot):
        win = _make_window(qtbot)
        assert "LLM Console" in win.windowTitle()

    def test_status_label_shows_provider_info(self, qtbot):
        provider = FakeLLMProvider()
        win = _make_window(qtbot, provider)
        text = win._status.text()
        assert provider.get_provider_name() in text
        assert provider.get_model_name() in text

    def test_send_button_enabled_on_init(self, qtbot):
        win = _make_window(qtbot)
        assert win._send_btn.isEnabled()

    def test_busy_bar_hidden_on_init(self, qtbot):
        win = _make_window(qtbot)
        assert not win._busy_bar.isVisible()

    def test_history_is_empty_on_init(self, qtbot):
        win = _make_window(qtbot)
        assert win._history.toPlainText() == ""

    def test_messages_list_is_empty_on_init(self, qtbot):
        win = _make_window(qtbot)
        assert win._messages == []


# ---------------------------------------------------------------------------
# LLMConsoleWindow._send() — guard conditions
# ---------------------------------------------------------------------------


class TestLLMConsoleWindowSend:
    def test_send_ignores_empty_prompt(self, qtbot):
        win = _make_window(qtbot)
        win._input.setPlainText("")
        win._send()
        # No worker should have been created
        assert win._worker is None
        assert win._messages == []

    def test_send_ignores_whitespace_only_prompt(self, qtbot):
        win = _make_window(qtbot)
        win._input.setPlainText("   \n  ")
        win._send()
        assert win._worker is None

    def test_send_creates_worker_for_valid_prompt(self, qtbot):
        """When a valid prompt is given, a worker is started."""
        win = _make_window(qtbot)
        win._input.setPlainText("Hello!")

        with patch("vector_inspector.tools.llm_console._GenerateWorker.start"):
            win._send()

        # The user message must have been appended
        assert any(m["role"] == "user" and "Hello!" in m["content"] for m in win._messages)

    def test_send_while_busy_shows_message_box(self, qtbot):
        """When worker is running, _send() shows an info dialog instead of creating another worker."""
        win = _make_window(qtbot)
        win._input.setPlainText("second message")

        # Simulate an active running worker
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        win._worker = mock_worker

        with patch("vector_inspector.tools.llm_console.QMessageBox.information") as mock_info:
            win._send()
            mock_info.assert_called_once()


# ---------------------------------------------------------------------------
# LLMConsoleWindow._clear()
# ---------------------------------------------------------------------------


class TestLLMConsoleWindowClear:
    def test_clear_removes_history_text(self, qtbot):
        win = _make_window(qtbot)
        win._history.setPlainText("previous text")
        win._clear()
        assert win._history.toPlainText() == ""

    def test_clear_resets_messages_list(self, qtbot):
        win = _make_window(qtbot)
        win._messages = [{"role": "user", "content": "test"}]
        win._clear()
        assert win._messages == []

    def test_clear_resets_current_response(self, qtbot):
        win = _make_window(qtbot)
        win._current_response = "partial text"
        win._clear()
        assert win._current_response == ""


# ---------------------------------------------------------------------------
# LLMConsoleWindow._reconnect()
# ---------------------------------------------------------------------------


class TestLLMConsoleWindowReconnect:
    def test_reconnect_while_busy_shows_message_box(self, qtbot):
        win = _make_window(qtbot)
        mock_worker = MagicMock()
        mock_worker.isRunning.return_value = True
        win._worker = mock_worker

        with patch("vector_inspector.tools.llm_console.QMessageBox.information") as mock_info:
            win._reconnect()
            mock_info.assert_called_once()

    def test_reconnect_shows_critical_when_provider_creation_fails(self, qtbot):
        win = _make_window(qtbot)

        with (
            patch("vector_inspector.tools.llm_console._make_provider", return_value=None),
            patch("vector_inspector.tools.llm_console.QMessageBox.critical") as mock_crit,
        ):
            win._reconnect()
            mock_crit.assert_called_once()

    def test_reconnect_failure_re_enables_button(self, qtbot):
        win = _make_window(qtbot)
        with (
            patch("vector_inspector.tools.llm_console._make_provider", return_value=None),
            patch("vector_inspector.tools.llm_console.QMessageBox.critical"),
        ):
            win._reconnect()
        assert win._reconnect_btn.isEnabled()
        assert win._reconnect_btn.text() == "Reconnect Provider"

    def test_reconnect_success_updates_provider(self, qtbot):
        win = _make_window(qtbot)
        new_provider = FakeLLMProvider(default_model="new-model")

        with patch("vector_inspector.tools.llm_console._make_provider", return_value=new_provider):
            win._reconnect()

        assert win._provider is new_provider

    def test_reconnect_success_updates_status_label(self, qtbot):
        win = _make_window(qtbot)
        new_provider = FakeLLMProvider(default_model="new-model")

        with patch("vector_inspector.tools.llm_console._make_provider", return_value=new_provider):
            win._reconnect()

        assert new_provider.get_provider_name() in win._status.text()

    def test_reconnect_success_clears_messages(self, qtbot):
        win = _make_window(qtbot)
        win._messages = [{"role": "user", "content": "old"}]
        new_provider = FakeLLMProvider()

        with patch("vector_inspector.tools.llm_console._make_provider", return_value=new_provider):
            win._reconnect()

        assert win._messages == []

    def test_reconnect_success_re_enables_button(self, qtbot):
        win = _make_window(qtbot)
        new_provider = FakeLLMProvider()

        with patch("vector_inspector.tools.llm_console._make_provider", return_value=new_provider):
            win._reconnect()

        assert win._reconnect_btn.isEnabled()
        assert win._reconnect_btn.text() == "Reconnect Provider"


# ---------------------------------------------------------------------------
# LLMConsoleWindow private slot callbacks (_on_chunk, _on_done, _on_error)
# ---------------------------------------------------------------------------


class TestLLMConsoleWindowSlots:
    def test_on_chunk_appends_to_current_response(self, qtbot):
        win = _make_window(qtbot)
        win._on_chunk("Hello")
        win._on_chunk(" world")
        assert win._current_response == "Hello world"

    def test_on_chunk_appends_text_to_history(self, qtbot):
        win = _make_window(qtbot)
        win._on_chunk("ping")
        assert "ping" in win._history.toPlainText()

    def test_on_done_saves_assistant_message(self, qtbot):
        win = _make_window(qtbot)
        win._messages = [{"role": "user", "content": "hey"}]
        win._current_response = "hi!"
        win._on_done()
        assert any(m["role"] == "assistant" for m in win._messages)
        assert win._messages[-1]["content"] == "hi!"

    def test_on_done_does_not_save_empty_response(self, qtbot):
        win = _make_window(qtbot)
        win._messages = [{"role": "user", "content": "hey"}]
        win._current_response = ""
        win._on_done()
        # Only the user message should remain
        assert all(m["role"] == "user" for m in win._messages)

    def test_on_done_resets_current_response(self, qtbot):
        win = _make_window(qtbot)
        win._current_response = "response"
        win._on_done()
        assert win._current_response == ""

    def test_on_done_hides_busy_bar(self, qtbot):
        win = _make_window(qtbot)
        win._busy_bar.setVisible(True)
        win._on_done()
        assert not win._busy_bar.isVisible()

    def test_on_done_re_enables_send_button(self, qtbot):
        win = _make_window(qtbot)
        win._send_btn.setEnabled(False)
        win._on_done()
        assert win._send_btn.isEnabled()

    def test_on_error_appends_error_text_to_history(self, qtbot):
        win = _make_window(qtbot)
        win._on_error("something went wrong")
        assert "something went wrong" in win._history.toPlainText()

    def test_on_error_removes_pending_user_message(self, qtbot):
        win = _make_window(qtbot)
        win._messages = [{"role": "user", "content": "bad prompt"}]
        win._on_error("model crash")
        assert not any(m["role"] == "user" for m in win._messages)

    def test_on_error_does_not_remove_prior_messages(self, qtbot):
        win = _make_window(qtbot)
        win._messages = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "first reply"},
            {"role": "user", "content": "second (failed)"},
        ]
        win._on_error("error")
        # Only the last user message (the failing one) is removed
        assert len(win._messages) == 2

    def test_on_error_hides_busy_bar(self, qtbot):
        win = _make_window(qtbot)
        win._busy_bar.setVisible(True)
        win._on_error("boom")
        assert not win._busy_bar.isVisible()

    def test_on_error_re_enables_send_button(self, qtbot):
        win = _make_window(qtbot)
        win._send_btn.setEnabled(False)
        win._on_error("oops")
        assert win._send_btn.isEnabled()

    def test_on_error_resets_current_response(self, qtbot):
        win = _make_window(qtbot)
        win._current_response = "partial"
        win._on_error("broken")
        assert win._current_response == ""
