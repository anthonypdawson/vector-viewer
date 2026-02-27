"""Tests for ProfileEditorDialog._set_field_and_label_visible.

This method belongs to ProfileEditorDialog (the profile create/edit dialog),
not ProfileManagerPanel. It shows/hides form rows — both plain-widget rows
and layout-based rows — together with their matching label.
"""

from PySide6.QtWidgets import QFormLayout, QLineEdit

from vector_inspector.ui.components.profile_manager_panel import ProfileEditorDialog


class FakeProfileService:
    """Minimal stub — ProfileEditorDialog only stores the reference at construction."""

    def get_all_profiles(self):
        return []

    def get_profile(self, profile_id):
        return None


def _make_editor(qtbot):
    """Return a fresh ProfileEditorDialog (new-profile mode)."""
    editor = ProfileEditorDialog(FakeProfileService())
    qtbot.addWidget(editor)
    return editor


# ---------------------------------------------------------------------------
# Widget-field rows (QWidget in FieldRole)
# ---------------------------------------------------------------------------


def test_widget_field_hides_field_and_label(qtbot):
    """Hiding a QWidget field also hides its row label."""
    editor = _make_editor(qtbot)

    # host_input is a QLineEdit in a FieldRole slot of details_layout
    editor.host_input.setVisible(True)
    editor._set_field_and_label_visible(editor.host_input, False)

    assert editor.host_input.isVisible() is False

    layout = editor.details_layout
    for row in range(layout.rowCount()):
        fi = layout.itemAt(row, QFormLayout.FieldRole)
        li = layout.itemAt(row, QFormLayout.LabelRole)
        if fi and fi.widget() is editor.host_input:
            if li and li.widget():
                assert li.widget().isHidden() is True
            break


def test_widget_field_shows_field_and_label(qtbot):
    """After hiding, showing a QWidget field clears the explicit-hide flag."""
    editor = _make_editor(qtbot)

    editor._set_field_and_label_visible(editor.host_input, False)
    assert editor.host_input.isHidden() is True

    editor._set_field_and_label_visible(editor.host_input, True)
    assert editor.host_input.isHidden() is False

    layout = editor.details_layout
    for row in range(layout.rowCount()):
        fi = layout.itemAt(row, QFormLayout.FieldRole)
        li = layout.itemAt(row, QFormLayout.LabelRole)
        if fi and fi.widget() is editor.host_input:
            if li and li.widget():
                assert li.widget().isHidden() is False
            break


# ---------------------------------------------------------------------------
# Layout-field rows (QHBoxLayout in FieldRole)
# ---------------------------------------------------------------------------


def test_layout_field_hides_child_widgets_and_label(qtbot):
    """Hiding a QLayout field hides all child widgets and its row label."""
    editor = _make_editor(qtbot)

    # path_layout is a QHBoxLayout row holding path_input + path_browse_btn.
    # The ChromaDB default provider hides path_layout; explicitly show it first
    # so we have a known baseline before testing the hide operation.
    editor._set_field_and_label_visible(editor.path_layout, True)
    assert not editor.path_input.isHidden()
    assert not editor.path_browse_btn.isHidden()

    editor._set_field_and_label_visible(editor.path_layout, False)

    assert editor.path_input.isHidden() is True
    assert editor.path_browse_btn.isHidden() is True


def test_layout_field_shows_child_widgets(qtbot):
    """After hiding, showing a QLayout field clears the explicit-hide flag on its children."""
    editor = _make_editor(qtbot)

    editor._set_field_and_label_visible(editor.path_layout, False)
    assert editor.path_input.isHidden() is True

    editor._set_field_and_label_visible(editor.path_layout, True)
    assert editor.path_input.isHidden() is False
    assert editor.path_browse_btn.isHidden() is False


# ---------------------------------------------------------------------------
# Edge case: field not in the layout
# ---------------------------------------------------------------------------


def test_missing_field_does_not_raise(qtbot):
    """A widget not present in details_layout falls back to setVisible without raising."""
    editor = _make_editor(qtbot)

    orphan = QLineEdit()
    # Should not raise; fallback path calls setVisible on the object itself
    editor._set_field_and_label_visible(orphan, False)
    assert orphan.isHidden() is True
