"""Ingestion configuration dialog for image and document pipelines."""

import os
import re
from typing import Any, Literal, Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

_COLLECTION_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


class IngestionDialog(QDialog):
    """Config dialog launched before running an image or document ingestion.

    After exec(), inspect .accepted and read the result properties:
        .file_paths       - list of selected files/folders
        .folder_mode      - True if the user picked a folder
        .collection_name  - target collection name
        .overwrite        - whether to overwrite existing items
        .recursive        - whether to scan sub-folders (folder mode only)
        .batch_size       - chunk batch size
        .max_chunk_size   - document max chunk size (documents only)
    """

    def __init__(
        self,
        parent: Optional[QWidget],
        file_kind: Literal["image", "document"],
        connection: Any,
        current_collection: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self._file_kind = file_kind
        self._connection = connection
        self._default_dim = 512 if file_kind == "image" else 384
        self._supports_vector_size = getattr(connection, "supports_configurable_vector_size", True)

        title = "Import Images" if file_kind == "image" else "Import Documents"
        self.setWindowTitle(title)
        self.setMinimumWidth(480)

        # Public result properties
        self.file_paths: list[str] = []
        self.folder_mode: bool = True
        self.collection_name: str = current_collection or ""
        self.overwrite: bool = False
        self.recursive: bool = False
        self.batch_size: int = 16
        self.max_chunk_size: int = 1000
        # Set when the user requests a brand-new collection via "+ New".
        # The caller must create the collection before ingestion starts.
        self.new_collection_vector_size: int | None = None

        self._setup_ui(current_collection)

    def _setup_ui(self, current_collection: Optional[str]) -> None:
        layout = QVBoxLayout(self)

        # ── Source picker ──────────────────────────────────────────────
        source_group = QGroupBox("Source")
        source_layout = QVBoxLayout(source_group)

        folder_row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Folder or file(s)…")
        folder_row.addWidget(self._folder_edit)

        pick_folder_btn = QPushButton("Folder…")
        pick_folder_btn.clicked.connect(self._pick_folder)
        folder_row.addWidget(pick_folder_btn)

        pick_files_btn = QPushButton("Files…")
        pick_files_btn.clicked.connect(self._pick_files)
        folder_row.addWidget(pick_files_btn)

        source_layout.addLayout(folder_row)

        self._recursive_check = QCheckBox("Include sub-folders")
        source_layout.addWidget(self._recursive_check)
        layout.addWidget(source_group)

        # ── Target collection ──────────────────────────────────────────
        coll_group = QGroupBox("Target Collection")
        coll_form = QFormLayout(coll_group)

        coll_row = QHBoxLayout()
        self._collection_edit = QLineEdit(current_collection or "")
        self._collection_edit.setPlaceholderText("Select or create a collection…")
        coll_row.addWidget(self._collection_edit)

        new_coll_btn = QPushButton("+ New")
        new_coll_btn.setToolTip("Create a new collection")
        new_coll_btn.clicked.connect(self._create_new_collection)
        coll_row.addWidget(new_coll_btn)

        coll_form.addRow(QLabel("Collection:"), coll_row)
        layout.addWidget(coll_group)

        # ── Options ───────────────────────────────────────────────────
        opt_group = QGroupBox("Options")
        opt_form = QFormLayout(opt_group)

        self._overwrite_check = QCheckBox()
        opt_form.addRow(QLabel("Overwrite duplicates:"), self._overwrite_check)

        self._batch_spin = QSpinBox()
        self._batch_spin.setRange(1, 256)
        self._batch_spin.setValue(16)
        opt_form.addRow(QLabel("Batch size:"), self._batch_spin)

        if self._file_kind == "document":
            self._chunk_spin = QSpinBox()
            self._chunk_spin.setRange(200, 4096)
            self._chunk_spin.setValue(1000)
            self._chunk_spin.setSuffix(" chars")
            opt_form.addRow(QLabel("Max chunk size:"), self._chunk_spin)
        else:
            self._chunk_spin = None  # type: ignore[assignment]

        layout.addWidget(opt_group)

        # ── Buttons ───────────────────────────────────────────────────
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self._folder_edit.setText(folder)
            self.folder_mode = True
            self.file_paths = [folder]

    def _pick_files(self) -> None:
        if self._file_kind == "image":
            filters = "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp *.tiff *.tif)"
        else:
            filters = "Documents (*.pdf *.docx *.txt *.md *.py *.js *.ts *.rb *.go *.rs *.html *.xml *.csv *.log *.srt *.vtt);;All Files (*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Files", "", filters)
        if paths:
            self._folder_edit.setText("; ".join(paths))
            self.folder_mode = False
            self.file_paths = paths

    def _create_new_collection(self) -> None:
        """Inline mini-dialog to create a new collection."""
        dlg = QDialog(self)
        dlg.setWindowTitle("New Collection")
        dlg.setMinimumWidth(360)
        form = QFormLayout(dlg)

        name_edit = QLineEdit()
        name_edit.setPlaceholderText("collection_name")
        form.addRow(QLabel("Name:"), name_edit)

        # Dimension is known from the ingestion model (CLIP=512, MiniLM=384).
        # Only show an editable spinner for backends that require an explicit
        # vector size at creation time (e.g. Qdrant, Milvus, pgvector).
        # Backends like ChromaDB infer the dimension from the first insert, so
        # we just show it as an informational read-only label.
        if self._supports_vector_size:
            dim_spin = QSpinBox()
            dim_spin.setRange(1, 65536)
            dim_spin.setValue(self._default_dim)
            form.addRow(QLabel("Dimension:"), dim_spin)
        else:
            dim_spin = None
            dim_label = QLabel(f"{self._default_dim} (set automatically on first insert)")
            dim_label.setEnabled(False)
            form.addRow(QLabel("Dimension:"), dim_label)

        btn_row = QHBoxLayout()
        create_btn = QPushButton("Create")
        cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(create_btn)
        btn_row.addWidget(cancel_btn)
        form.addRow(btn_row)

        cancel_btn.clicked.connect(dlg.reject)

        def _do_create() -> None:
            name = name_edit.text().strip()
            if not name or not _COLLECTION_NAME_RE.match(name):
                QMessageBox.warning(
                    dlg, "Invalid Name", "Collection name must be non-empty and contain only A-Z, a-z, 0-9, _ or -."
                )
                return
            # Dimension is always known from the file_kind; use the spinner value
            # only when the backend exposes it as a configurable field.
            self._collection_edit.setText(name)
            self.new_collection_vector_size = dim_spin.value() if dim_spin is not None else self._default_dim
            dlg.accept()

        create_btn.clicked.connect(_do_create)
        dlg.exec()

    def _on_accept(self) -> None:
        # Validate source
        raw = self._folder_edit.text().strip()
        if not self.file_paths and raw:
            # User typed a path manually; split on semicolons for multiple files.
            self.file_paths = [p.strip() for p in raw.split(";") if p.strip()]
            if len(self.file_paths) == 1:
                # Use filesystem check rather than string heuristic so a single
                # file path is not mistakenly treated as a folder.
                self.folder_mode = os.path.isdir(self.file_paths[0])
            else:
                # Multiple entries are always file mode.
                self.folder_mode = False

        if not self.file_paths:
            QMessageBox.warning(self, "No Source", "Please select a folder or file(s) first.")
            return

        self.collection_name = self._collection_edit.text().strip()
        if not self.collection_name:
            QMessageBox.warning(self, "No Collection", "Please specify a target collection.")
            return

        self.overwrite = self._overwrite_check.isChecked()
        self.recursive = self._recursive_check.isChecked()
        self.batch_size = self._batch_spin.value()
        if self._chunk_spin is not None:
            self.max_chunk_size = self._chunk_spin.value()

        self.accept()
