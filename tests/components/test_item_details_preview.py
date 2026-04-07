"""Tests for file preview functionality in ItemDetailsDialog."""

from unittest.mock import patch

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QTextEdit

from vector_inspector.ui.components.item_details_dialog import ItemDetailsDialog


class TestItemDetailsFilePreview:
    def test_preview_visible_for_image(self, qtbot, tmp_path):
        """Preview frame visible when _populate_file_preview finds an image path."""
        img = tmp_path / "photo.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        item = {
            "id": "img-1",
            "document": "",
            "metadata": {"file_path": str(img)},
            "embedding": [0.1, 0.2],
        }

        pixmap = QPixmap(10, 10)

        with (
            patch("vector_inspector.utils.file_preview_utils.find_preview_paths", return_value=[str(img)]),
            patch("vector_inspector.utils.file_preview_utils.file_type", return_value="image"),
            patch("vector_inspector.utils.file_preview_utils.load_image_pixmap", return_value=pixmap),
        ):
            dlg = ItemDetailsDialog(None, item_data=item, show_search_info=False)
            qtbot.addWidget(dlg)

        assert not dlg._preview_frame.isHidden()

    def test_preview_visible_for_text(self, qtbot, tmp_path):
        """Preview frame visible when _populate_file_preview finds a text path."""
        txt = tmp_path / "notes.txt"
        txt.write_text("Hello world")

        item = {
            "id": "txt-1",
            "document": "",
            "metadata": {"file_path": str(txt)},
            "embedding": [0.1, 0.2],
        }

        with (
            patch("vector_inspector.utils.file_preview_utils.find_preview_paths", return_value=[str(txt)]),
            patch("vector_inspector.utils.file_preview_utils.file_type", return_value="text"),
            patch("vector_inspector.utils.file_preview_utils.read_text_preview", return_value=("Hello world", False)),
        ):
            dlg = ItemDetailsDialog(None, item_data=item, show_search_info=False)
            qtbot.addWidget(dlg)

        assert not dlg._preview_frame.isHidden()
        text_edits = dlg._preview_frame.findChildren(QTextEdit)
        assert any("Hello" in te.toPlainText() for te in text_edits)

    def test_preview_hidden_when_no_path(self, qtbot):
        """Preview frame hidden when metadata has no file paths."""
        item = {
            "id": "no-path",
            "document": "Some text",
            "metadata": {"key": "value"},
            "embedding": [0.1, 0.2],
        }
        dlg = ItemDetailsDialog(None, item_data=item, show_search_info=False)
        qtbot.addWidget(dlg)
        assert dlg._preview_frame.isHidden()

    def test_preview_hidden_for_missing_file(self, qtbot, tmp_path):
        """Preview frame hidden when the file_path does not exist on disk."""
        item = {
            "id": "missing",
            "document": "",
            "metadata": {"file_path": str(tmp_path / "nonexistent.png")},
            "embedding": [0.1],
        }
        dlg = ItemDetailsDialog(None, item_data=item, show_search_info=False)
        qtbot.addWidget(dlg)
        assert dlg._preview_frame.isHidden()
