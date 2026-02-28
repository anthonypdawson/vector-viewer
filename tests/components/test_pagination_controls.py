"""Tests for PaginationControls widget."""

import pytest

from vector_inspector.ui.components.pagination_controls import PaginationControls


@pytest.fixture
def controls(qtbot):
    widget = PaginationControls()
    qtbot.addWidget(widget)
    widget.show()
    return widget


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_initial_state(controls):
    assert controls.current_page == 0
    assert controls.page_size == 50
    assert not controls.prev_button.isEnabled()
    assert not controls.next_button.isEnabled()


def test_initial_label(controls):
    # Page label is set to the literal "0 / 0" at construction before _update_ui
    assert controls.page_label.text() == "0 / 0"


# ---------------------------------------------------------------------------
# set_state
# ---------------------------------------------------------------------------


def test_set_state_enables_next_when_has_next(controls):
    controls.set_state(current_page=0, total_pages=3, has_next=True)
    assert controls.next_button.isEnabled()


def test_set_state_disables_prev_on_page_zero(controls):
    controls.set_state(current_page=0, total_pages=3, has_next=True)
    assert not controls.prev_button.isEnabled()


def test_set_state_enables_prev_on_later_pages(controls):
    controls.set_state(current_page=2, total_pages=5, has_next=False)
    assert controls.prev_button.isEnabled()


def test_set_state_updates_label(controls):
    controls.set_state(current_page=2, total_pages=5)
    assert "3" in controls.page_label.text()
    assert "5" in controls.page_label.text()


def test_set_state_unknown_total_pages(controls):
    controls.set_state(current_page=3, total_pages=0, has_next=True)
    label = controls.page_label.text()
    assert "4" in label  # 0-indexed+1


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


def test_reset_returns_to_page_zero(controls):
    controls.set_state(current_page=3, total_pages=10, has_next=True)
    controls.reset()
    assert controls.current_page == 0
    assert not controls.prev_button.isEnabled()
    assert not controls.next_button.isEnabled()


# ---------------------------------------------------------------------------
# Signal emission
# ---------------------------------------------------------------------------


def test_next_button_emits_next_clicked(qtbot, controls):
    controls.set_state(current_page=0, total_pages=5, has_next=True)
    with qtbot.waitSignal(controls.next_clicked, timeout=1000):
        controls.next_button.click()


def test_next_button_emits_page_changed(qtbot, controls):
    controls.set_state(current_page=0, total_pages=5, has_next=True)
    received = []
    controls.page_changed.connect(lambda new, old: received.append((new, old)))
    controls.next_button.click()
    assert received == [(1, 0)]


def test_prev_button_emits_previous_clicked(qtbot, controls):
    controls.set_state(current_page=2, total_pages=5, has_next=False)
    with qtbot.waitSignal(controls.previous_clicked, timeout=1000):
        controls.prev_button.click()


def test_prev_button_no_op_on_page_zero(qtbot, controls):
    controls.set_state(current_page=0, total_pages=5, has_next=True)
    received = []
    controls.page_changed.connect(lambda n, o: received.append((n, o)))
    # Manually enable and click (button is disabled on page 0 normally)
    controls.prev_button.setEnabled(True)
    controls.prev_button.click()
    # page was 0, so _on_previous does nothing when page <= 0
    assert received == []  # current_page is 0, condition not met


def test_page_size_changed_signal(qtbot, controls):
    received = []
    controls.page_size_changed.connect(lambda s: received.append(s))
    controls.page_size_spin.setValue(100)
    assert 100 in received


def test_set_page_size_programmatically(controls):
    controls.set_page_size(200)
    assert controls.page_size == 200
