"""Tests for the IngestionDialog configuration dialog."""

from unittest.mock import MagicMock

from vector_inspector.ui.components.ingestion_dialog import IngestionDialog


def _make_connection(supports_vector_size=True, collections=None):
    conn = MagicMock()
    conn.supports_configurable_vector_size = supports_vector_size
    conn.list_collections.return_value = collections or []
    return conn


class TestIngestionDialogCreation:
    def test_creates_for_image(self, qtbot):
        conn = _make_connection()
        dlg = IngestionDialog(None, file_kind="image", connection=conn, current_collection="my_images")
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Import Images"
        assert dlg.collection_name == "my_images"
        assert dlg.batch_size == 16

    def test_creates_for_document(self, qtbot):
        conn = _make_connection()
        dlg = IngestionDialog(None, file_kind="document", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg.windowTitle() == "Import Documents"
        assert dlg.collection_name == ""

    def test_default_dim_image_512(self, qtbot):
        conn = _make_connection()
        dlg = IngestionDialog(None, file_kind="image", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg._default_dim == 512

    def test_default_dim_document_384(self, qtbot):
        conn = _make_connection()
        dlg = IngestionDialog(None, file_kind="document", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg._default_dim == 384


class TestIngestionDialogVectorSize:
    def test_supports_vector_size_flag(self, qtbot):
        conn = _make_connection(supports_vector_size=True)
        dlg = IngestionDialog(None, file_kind="image", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg._supports_vector_size is True

    def test_no_vector_size_flag(self, qtbot):
        conn = _make_connection(supports_vector_size=False)
        dlg = IngestionDialog(None, file_kind="image", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg._supports_vector_size is False

    def test_new_collection_vector_size_initially_none(self, qtbot):
        conn = _make_connection()
        dlg = IngestionDialog(None, file_kind="image", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg.new_collection_vector_size is None


class TestIngestionDialogDefaults:
    def test_overwrite_default_false(self, qtbot):
        conn = _make_connection()
        dlg = IngestionDialog(None, file_kind="image", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg.overwrite is False

    def test_recursive_default_false(self, qtbot):
        conn = _make_connection()
        dlg = IngestionDialog(None, file_kind="image", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg.recursive is False

    def test_folder_mode_default_true(self, qtbot):
        conn = _make_connection()
        dlg = IngestionDialog(None, file_kind="image", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg.folder_mode is True

    def test_max_chunk_size_default(self, qtbot):
        conn = _make_connection()
        dlg = IngestionDialog(None, file_kind="document", connection=conn)
        qtbot.addWidget(dlg)
        assert dlg.max_chunk_size == 1000
