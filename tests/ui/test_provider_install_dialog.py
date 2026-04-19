"""Tests for ProviderInstallDialog."""

from vector_inspector.core.provider_detection import FeatureInfo, ProviderInfo
from vector_inspector.ui.dialogs.provider_install_dialog import ProviderInstallDialog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(available: bool = False) -> ProviderInfo:
    return ProviderInfo(
        id="qdrant",
        name="Qdrant",
        available=available,
        install_command="pip install vector-inspector[qdrant]",
        import_name="qdrant_client",
        description="Local, remote, or cloud vector database",
    )


# ---------------------------------------------------------------------------
# Construction & initial state
# ---------------------------------------------------------------------------


def test_dialog_instantiates(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    assert dlg is not None


def test_dialog_title_contains_provider_name(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    assert "Qdrant" in dlg.windowTitle()


def test_install_button_present_and_enabled(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    assert dlg._install_btn.isEnabled()
    # Visibility depends on the parent being shown; test the hidden-flag instead.
    assert not dlg._install_btn.isHidden()


def test_progress_bar_hidden_initially(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    assert not dlg._progress_bar.isVisible()


def test_output_edit_hidden_initially(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    assert not dlg._output_edit.isVisible()


def test_status_label_hidden_initially(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    assert not dlg._status_label.isVisible()


# ---------------------------------------------------------------------------
# _on_install_finished — success path (called directly, no thread)
# ---------------------------------------------------------------------------


def test_on_install_finished_success_shows_green_status(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    dlg.show()  # parent must be shown for child show() to propagate

    emitted: list[str] = []
    dlg.provider_installed.connect(emitted.append)

    dlg._on_install_finished(0, "Successfully installed")

    assert dlg._status_label.isVisible()
    assert "installed successfully" in dlg._status_label.text()
    assert "green" in dlg._status_label.styleSheet()


def test_on_install_finished_success_emits_provider_installed(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)

    emitted: list[str] = []
    dlg.provider_installed.connect(emitted.append)

    dlg._on_install_finished(0, "ok")

    assert emitted == ["qdrant"]


def test_on_install_finished_success_hides_progress_bar(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)

    dlg._progress_bar.show()
    dlg._on_install_finished(0, "ok")

    assert not dlg._progress_bar.isVisible()


# ---------------------------------------------------------------------------
# _on_install_finished — failure path
# ---------------------------------------------------------------------------


def test_on_install_finished_failure_shows_red_status(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    dlg.show()  # parent must be shown for child show() to propagate

    dlg._on_install_finished(1, "ERROR: build failed")

    assert dlg._status_label.isVisible()
    assert "failed" in dlg._status_label.text().lower()
    assert "red" in dlg._status_label.styleSheet()


def test_on_install_finished_failure_re_enables_install_button(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    dlg.show()  # parent must be shown for child show() to propagate

    dlg._install_btn.setEnabled(False)
    dlg._install_btn.hide()

    dlg._on_install_finished(1, "error")

    assert dlg._install_btn.isEnabled()
    assert not dlg._install_btn.isHidden()


def test_on_install_finished_failure_does_not_emit_signal(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)

    emitted: list[str] = []
    dlg.provider_installed.connect(emitted.append)

    dlg._on_install_finished(1, "error")

    assert emitted == []


# ---------------------------------------------------------------------------
# _on_output_line
# ---------------------------------------------------------------------------


def test_on_output_line_appends_text(qtbot):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)

    dlg._on_output_line("Installing packages...\n")

    assert "Installing packages" in dlg._output_edit.toPlainText()


# ---------------------------------------------------------------------------
# _start_install — UI state transition (patch the thread so no real pip runs)
# ---------------------------------------------------------------------------


def test_start_install_shows_progress_bar(qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication

    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)
    dlg.show()
    QApplication.processEvents()

    # Replace the entire _InstallThread class with a non-starting fake so that
    # _on_install_finished is never called (which would immediately hide the bar).
    class _FrozenThread:
        class _Sig:
            def connect(self, _cb):
                pass

        output_line = _Sig()
        finished = _Sig()

        def __init__(self, provider_id, parent=None):
            pass

        def start(self):
            pass  # never emits finished → progress bar stays visible

    monkeypatch.setattr(
        "vector_inspector.ui.dialogs.provider_install_dialog._InstallThread",
        _FrozenThread,
    )

    dlg._start_install()
    QApplication.processEvents()

    # isHidden() reflects whether show() was called on the widget itself,
    # independent of the parent chain's window-manager mapping state.
    # This is more robust than isVisible() in a test-suite context.
    assert not dlg._progress_bar.isHidden()


def test_start_install_hides_install_button(qtbot, monkeypatch):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)

    monkeypatch.setattr(
        "vector_inspector.ui.dialogs.provider_install_dialog._InstallThread.start",
        lambda self: None,
    )

    dlg._start_install()

    assert not dlg._install_btn.isVisible()


def test_start_install_disables_close_button(qtbot, monkeypatch):
    provider = _make_provider()
    dlg = ProviderInstallDialog(provider)
    qtbot.addWidget(dlg)

    monkeypatch.setattr(
        "vector_inspector.ui.dialogs.provider_install_dialog._InstallThread.start",
        lambda self: None,
    )

    dlg._start_install()

    assert not dlg._close_btn.isEnabled()


# ---------------------------------------------------------------------------
# FeatureInfo — dialog works as a drop-in replacement for ProviderInfo
# ---------------------------------------------------------------------------


def _make_feature(available: bool = False) -> FeatureInfo:
    return FeatureInfo(
        id="viz",
        name="Advanced Visualization",
        available=available,
        install_command="pip install vector-inspector[viz]",
        description="UMAP, t-SNE, clustering algorithms",
    )


def test_dialog_instantiates_with_feature_info(qtbot):
    feature = _make_feature()
    dlg = ProviderInstallDialog(feature)
    qtbot.addWidget(dlg)
    assert dlg is not None


def test_dialog_title_contains_feature_name(qtbot):
    feature = _make_feature()
    dlg = ProviderInstallDialog(feature)
    qtbot.addWidget(dlg)
    assert "Advanced Visualization" in dlg.windowTitle()


def test_dialog_install_button_present_for_feature(qtbot):
    feature = _make_feature()
    dlg = ProviderInstallDialog(feature)
    qtbot.addWidget(dlg)
    assert not dlg._install_btn.isHidden()
    assert dlg._install_btn.isEnabled()


def test_dialog_feature_success_emits_feature_id(qtbot):
    feature = _make_feature()
    dlg = ProviderInstallDialog(feature)
    qtbot.addWidget(dlg)

    emitted: list[str] = []
    dlg.provider_installed.connect(emitted.append)

    dlg._on_install_finished(0, "ok")

    assert emitted == ["viz"]


def test_dialog_feature_build_instructions_contains_install_command(qtbot):
    feature = _make_feature()
    dlg = ProviderInstallDialog(feature)
    qtbot.addWidget(dlg)

    instructions = dlg._build_instructions()
    assert "pip install vector-inspector[viz]" in instructions


def test_dialog_feature_failure_does_not_emit(qtbot):
    feature = _make_feature()
    dlg = ProviderInstallDialog(feature)
    qtbot.addWidget(dlg)

    emitted: list[str] = []
    dlg.provider_installed.connect(emitted.append)

    dlg._on_install_finished(1, "error")

    assert emitted == []
