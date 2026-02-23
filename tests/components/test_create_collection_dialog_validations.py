from PySide6.QtWidgets import QApplication

from vector_inspector.ui.components.create_collection_dialog import CreateCollectionDialog

if QApplication.instance() is None:
    _qapp = QApplication([])


def test_accept_rejects_empty_name(monkeypatch):
    dlg = CreateCollectionDialog()

    # Ensure warning is captured instead of showing a dialog
    called = {}

    def fake_warning(*args, **kwargs):
        called["warned"] = True

    monkeypatch.setattr("vector_inspector.ui.components.create_collection_dialog.QMessageBox.warning", fake_warning)

    dlg.name_input.setText("")
    dlg.accept()
    assert called.get("warned", False) is True


def test_accept_rejects_missing_model_when_sample_enabled(monkeypatch):
    dlg = CreateCollectionDialog()

    # Clear model list so currentData() is None
    dlg.model_combo.clear()

    called = {}

    def fake_warning(*args, **kwargs):
        called["warned"] = True

    monkeypatch.setattr("vector_inspector.ui.components.create_collection_dialog.QMessageBox.warning", fake_warning)

    dlg.name_input.setText("valid_name")
    dlg.add_sample_check.setChecked(True)
    # No model selected -> should trigger warning
    dlg.accept()
    assert called.get("warned", False) is True
