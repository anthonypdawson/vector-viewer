"""Tests for EmbeddingConfigDialog."""

from vector_inspector.ui.dialogs.embedding_config_dialog import EmbeddingConfigDialog


def test_embedding_config_dialog_no_provider(qtbot):
    """Instantiate with no provider_type — falls back to all available models."""
    dlg = EmbeddingConfigDialog(
        collection_name="my_collection",
        vector_dimension=384,
    )
    qtbot.addWidget(dlg)
    assert dlg is not None
    assert "my_collection" in dlg.windowTitle()


def test_embedding_config_dialog_title_no_provider(qtbot):
    dlg = EmbeddingConfigDialog(collection_name="test_col", vector_dimension=768)
    qtbot.addWidget(dlg)
    assert "Configure Embedding Model" in dlg.windowTitle()
    assert "test_col" in dlg.windowTitle()


def test_embedding_config_dialog_custom_provider(qtbot):
    """provider_type='custom' shows a QLineEdit for manual entry."""
    dlg = EmbeddingConfigDialog(
        collection_name="my_col",
        vector_dimension=512,
        provider_type="custom",
    )
    qtbot.addWidget(dlg)
    assert "Custom" in dlg.windowTitle() or "custom" in dlg.windowTitle().lower()
    assert hasattr(dlg, "custom_name_input")


def test_embedding_config_dialog_sentence_transformer(qtbot):
    """provider_type='sentence-transformer' shows filtered model list."""
    dlg = EmbeddingConfigDialog(
        collection_name="col1",
        vector_dimension=384,
        provider_type="sentence-transformer",
    )
    qtbot.addWidget(dlg)
    assert "Sentence" in dlg.windowTitle()


def test_embedding_config_dialog_known_dimension(qtbot):
    """Dialog builds model combo for a common dimension."""
    dlg = EmbeddingConfigDialog(
        collection_name="col",
        vector_dimension=1536,
        provider_type="openai",
    )
    qtbot.addWidget(dlg)
    assert dlg is not None


def test_embedding_config_dialog_unknown_dimension(qtbot):
    """Dialog handles gracefully when no models for dimension."""
    dlg = EmbeddingConfigDialog(
        collection_name="col",
        vector_dimension=9999,
        provider_type="sentence-transformer",
    )
    qtbot.addWidget(dlg)
    # model_combo may be None when no models found
    assert dlg is not None


def test_embedding_config_dialog_with_current_model(qtbot):
    """Current model info is shown."""
    dlg = EmbeddingConfigDialog(
        collection_name="col",
        vector_dimension=384,
        current_model="all-MiniLM-L6-v2",
        current_type="sentence-transformer",
    )
    qtbot.addWidget(dlg)
    assert dlg.current_model == "all-MiniLM-L6-v2"


def test_embedding_config_dialog_cancel(qtbot):
    dlg = EmbeddingConfigDialog(
        collection_name="col",
        vector_dimension=384,
    )
    qtbot.addWidget(dlg)
    dlg.reject()
    assert dlg.result() == 0
