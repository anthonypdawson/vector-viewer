from PySide6.QtWidgets import QDialog, QInputDialog

from vector_inspector.core.connection_manager import ConnectionManager
from vector_inspector.ui.components.connection_manager_panel import ConnectionManagerPanel


class DummyConn:
    def __init__(self, name="dummy", provider="chromadb"):
        self.name = name
        self.provider = provider
        self.state = None
        self.active_collection = None
        self.collections = []
        self.profile_name = name

    def get_display_name(self):
        return f"{self.name} ({self.provider})"


def test_on_connection_opened_and_collections_update(qtbot):
    manager = ConnectionManager()
    conn = DummyConn(name="C1")
    conn_id = manager.create_connection("C1", "chromadb", conn, {})

    panel = ConnectionManagerPanel(manager)
    qtbot.addWidget(panel)

    # Mark opened should add tree item
    manager.mark_connection_opened(conn_id)
    assert conn_id in panel._connection_items

    # Update collections
    manager.update_collections(conn_id, ["colA", "colB"])
    item = panel._connection_items[conn_id]
    assert item.childCount() == 2


def test_rename_connection_updates_tree(monkeypatch, qtbot):
    manager = ConnectionManager()
    conn = DummyConn(name="OldName")
    conn_id = manager.create_connection("OldName", "chromadb", conn, {})

    panel = ConnectionManagerPanel(manager)
    qtbot.addWidget(panel)
    manager.mark_connection_opened(conn_id)

    # Simulate user input for rename
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("NewName", True))

    panel._rename_connection(conn_id)
    inst = manager.get_connection(conn_id)
    assert inst.name == "NewName"


def test_delete_collection_dialog_rejected(monkeypatch, qtbot):
    manager = ConnectionManager()
    conn = DummyConn(name="C2")
    conn_id = manager.create_connection("C2", "chromadb", conn, {})

    panel = ConnectionManagerPanel(manager)
    qtbot.addWidget(panel)
    manager.mark_connection_opened(conn_id)

    # Ensure dialog.exec returns Rejected so no deletion proceeds
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)

    # Call delete; should return early without raising
    panel._delete_collection(conn_id, "no_such_collection")
