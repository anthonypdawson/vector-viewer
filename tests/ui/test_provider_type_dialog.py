"""Tests for ProviderTypeDialog."""

from vector_inspector.ui.dialogs.provider_type_dialog import ProviderTypeDialog


def test_provider_type_dialog_instantiates(qtbot):
    dlg = ProviderTypeDialog(collection_name="my_col", vector_dimension=384)
    qtbot.addWidget(dlg)
    assert dlg is not None


def test_provider_type_dialog_title(qtbot):
    dlg = ProviderTypeDialog(collection_name="my_col", vector_dimension=384)
    qtbot.addWidget(dlg)
    assert "Provider" in dlg.windowTitle()


def test_provider_type_dialog_selected_type_initially_none(qtbot):
    dlg = ProviderTypeDialog(collection_name="my_col", vector_dimension=384)
    qtbot.addWidget(dlg)
    assert dlg.get_selected_type() is None


def test_provider_type_dialog_next_btn_disabled_initially(qtbot):
    dlg = ProviderTypeDialog(collection_name="my_col", vector_dimension=384)
    qtbot.addWidget(dlg)
    assert not dlg.next_btn.isEnabled()


def test_provider_type_dialog_selecting_radio_enables_next(qtbot):
    dlg = ProviderTypeDialog(collection_name="my_col", vector_dimension=384)
    qtbot.addWidget(dlg)
    buttons = dlg.button_group.buttons()
    if buttons:
        # Use click() which triggers buttonClicked signal
        buttons[0].click()
        assert dlg.next_btn.isEnabled()


def test_provider_type_dialog_on_next_sets_type(qtbot):
    dlg = ProviderTypeDialog(collection_name="my_col", vector_dimension=384)
    qtbot.addWidget(dlg)
    buttons = dlg.button_group.buttons()
    if buttons:
        buttons[0].setChecked(True)
        dlg._on_next()
        assert dlg.get_selected_type() is not None


def test_provider_type_dialog_unknown_dimension_has_custom(qtbot):
    """Dimension with no registry models should still show 'custom' option."""
    dlg = ProviderTypeDialog(collection_name="col", vector_dimension=9999)
    qtbot.addWidget(dlg)
    buttons = dlg.button_group.buttons()
    labels = [b.text() for b in buttons]
    assert any("Custom" in lbl or "custom" in lbl.lower() for lbl in labels)


def test_provider_type_dialog_reject_returns_none_type(qtbot):
    dlg = ProviderTypeDialog(collection_name="col", vector_dimension=384)
    qtbot.addWidget(dlg)
    dlg.reject()
    assert dlg.get_selected_type() is None
