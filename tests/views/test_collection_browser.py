"""Tests for CollectionBrowser widget."""

from vector_inspector.ui.views.collection_browser import CollectionBrowser


class FakeConnection:
    def __init__(self, connected=True, collections=None, path=None, collection_info=None):
        self.is_connected = connected
        self._collections = collections or []
        self.path = path
        self._collection_info = collection_info or {}
        self.deleted = []

    def list_collections(self):
        return list(self._collections)

    def get_collection_info(self, name):
        return self._collection_info.get(name)

    def delete_collection(self, name):
        self.deleted.append(name)
        self._collections = [c for c in self._collections if c != name]
        return True


# ---------------------------------------------------------------------------
# Initial render
# ---------------------------------------------------------------------------


def test_collection_browser_creates_without_connection(qtbot):
    browser = CollectionBrowser()
    qtbot.addWidget(browser)
    assert browser.collection_list is not None


def test_collection_browser_initial_info_label(qtbot):
    browser = CollectionBrowser()
    qtbot.addWidget(browser)
    assert "No collections" in browser.info_label.text()


# ---------------------------------------------------------------------------
# refresh()
# ---------------------------------------------------------------------------


def test_refresh_not_connected_sets_info_label(qtbot):
    conn = FakeConnection(connected=False)
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)

    browser.refresh()

    assert "Not connected" in browser.info_label.text()
    assert browser.collection_list.count() == 0


def test_refresh_empty_collections_no_path(qtbot):
    conn = FakeConnection(connected=True, collections=[])
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)

    browser.refresh()

    assert browser.collection_list.count() == 0
    assert "No collections found" in browser.info_label.text()


def test_refresh_empty_collections_with_path(qtbot):
    conn = FakeConnection(connected=True, collections=[], path="/data/lancedb")
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)

    browser.refresh()

    assert "/data/lancedb" in browser.info_label.text()


def test_refresh_populates_list(qtbot):
    conn = FakeConnection(connected=True, collections=["col_a", "col_b", "col_c"])
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)

    browser.refresh()

    assert browser.collection_list.count() == 3
    items = [browser.collection_list.item(i).text() for i in range(3)]
    assert "col_a" in items
    assert "col_b" in items
    assert "3 collection(s)" in browser.info_label.text()


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------


def test_clear_empties_list_and_resets_label(qtbot):
    conn = FakeConnection(connected=True, collections=["col_a", "col_b"])
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)
    browser.refresh()
    assert browser.collection_list.count() == 2

    browser.clear()

    assert browser.collection_list.count() == 0
    assert "No collections" in browser.info_label.text()


# ---------------------------------------------------------------------------
# _on_collection_clicked — signal emission and info update
# ---------------------------------------------------------------------------


def test_on_collection_clicked_emits_signal(qtbot):
    conn = FakeConnection(connected=True, collections=["col_a"])
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)
    browser.refresh()

    received = []
    browser.collection_selected.connect(lambda name: received.append(name))

    item = browser.collection_list.item(0)
    browser._on_collection_clicked(item)

    assert received == ["col_a"]


def test_on_collection_clicked_updates_info_with_collection_info(qtbot):
    info = {"count": 42, "metadata_fields": ["source", "year", "author"]}
    conn = FakeConnection(connected=True, collections=["col_a"], collection_info={"col_a": info})
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)
    browser.refresh()

    item = browser.collection_list.item(0)
    browser._on_collection_clicked(item)

    label_text = browser.info_label.text()
    assert "42" in label_text


def test_on_collection_clicked_no_info_does_not_crash(qtbot):
    conn = FakeConnection(connected=True, collections=["col_a"], collection_info={})
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)
    browser.refresh()

    item = browser.collection_list.item(0)
    browser._on_collection_clicked(item)  # should not raise


# ---------------------------------------------------------------------------
# _delete_collection
# ---------------------------------------------------------------------------


def test_delete_collection_calls_connection_and_refreshes(qtbot):
    conn = FakeConnection(connected=True, collections=["col_a", "col_b"])
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)
    browser.refresh()
    assert browser.collection_list.count() == 2

    browser._delete_collection("col_a")

    assert "col_a" in conn.deleted
    # After refresh: only col_b remains
    assert browser.collection_list.count() == 1
    assert browser.collection_list.item(0).text() == "col_b"


# ---------------------------------------------------------------------------
# context menu — show/hide on right-click
# ---------------------------------------------------------------------------


def test_show_context_menu_no_item_does_not_crash(qtbot):
    conn = FakeConnection(connected=True, collections=["col_a"])
    browser = CollectionBrowser(connection=conn)
    qtbot.addWidget(browser)
    browser.refresh()

    from PySide6.QtCore import QPoint

    # Position outside any item: should return without crashing
    browser._show_context_menu(QPoint(999, 999))
