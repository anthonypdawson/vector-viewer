"""Background threads for backup and restore operations."""

from typing import Any, Optional

from PySide6.QtCore import QThread, Signal


class BackupThread(QThread):
    """Background thread for creating a backup."""

    finished = Signal(str)  # Emits backup_path on success
    error = Signal(str)

    def __init__(
        self,
        backup_service: Any,
        connection: Any,
        collection_name: str,
        backup_dir: str,
        include_embeddings: bool,
        profile_name: str,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.backup_service = backup_service
        self.connection = connection
        self.collection_name = collection_name
        self.backup_dir = backup_dir
        self.include_embeddings = include_embeddings
        self.profile_name = profile_name

    def run(self) -> None:
        """Create backup."""
        try:
            backup_path = self.backup_service.backup_collection(
                self.connection,
                self.collection_name,
                self.backup_dir,
                include_embeddings=self.include_embeddings,
                profile_name=self.profile_name,
            )

            if backup_path:
                self.finished.emit(backup_path)
            else:
                self.error.emit("Failed to create backup")
        except Exception as e:
            self.error.emit(str(e))


class RestoreThread(QThread):
    """Background thread for restoring a backup."""

    finished = Signal(str)  # Emits the collection name that was restored
    error = Signal(str)

    def __init__(
        self,
        backup_service: Any,
        connection: Any,
        backup_file: str,
        collection_name: Optional[str],
        overwrite: bool,
        recompute_embeddings: Optional[bool],
        profile_name: str,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.backup_service = backup_service
        self.connection = connection
        self.backup_file = backup_file
        self.collection_name = collection_name
        self.overwrite = overwrite
        self.recompute_embeddings = recompute_embeddings
        self.profile_name = profile_name

    def run(self) -> None:
        """Restore backup."""
        try:
            success = self.backup_service.restore_collection(
                self.connection,
                self.backup_file,
                collection_name=self.collection_name,
                overwrite=self.overwrite,
                recompute_embeddings=self.recompute_embeddings,
                profile_name=self.profile_name,
            )

            if success:
                # Determine the final collection name
                if self.collection_name:
                    final_name = self.collection_name
                else:
                    # Read from backup metadata
                    import json
                    import zipfile

                    with zipfile.ZipFile(self.backup_file, "r") as zipf:
                        metadata_str = zipf.read("metadata.json").decode("utf-8")
                        metadata = json.loads(metadata_str)
                        final_name = metadata.get("collection_name", "unknown")

                self.finished.emit(final_name)
            else:
                self.error.emit("Failed to restore backup")
        except Exception as e:
            self.error.emit(str(e))
