"""Background threads for connection manager operations."""

from typing import Any

from PySide6.QtCore import QThread, Signal


class RefreshCollectionsThread(QThread):
    """Background thread for refreshing collections list."""

    finished = Signal(list)  # Emits collections list
    error = Signal(str)

    def __init__(self, connection_instance: Any) -> None:
        super().__init__()
        self.connection_instance = connection_instance

    def run(self) -> None:
        """Refresh collections."""
        try:
            collections = self.connection_instance.list_collections()
            self.finished.emit(collections)
        except Exception as e:
            self.error.emit(str(e))


class DeleteCollectionThread(QThread):
    """Background thread for deleting a collection."""

    finished = Signal(list)  # Emits updated collections list
    error = Signal(str)

    def __init__(
        self,
        connection_instance: Any,
        collection_name: str,
        profile_name: str,
    ) -> None:
        super().__init__()
        self.connection_instance = connection_instance
        self.collection_name = collection_name
        self.profile_name = profile_name

    def run(self) -> None:
        """Delete collection."""
        try:
            success = self.connection_instance.delete_collection(self.collection_name)

            if success:
                # Refresh collections list
                collections = self.connection_instance.list_collections()
                self.finished.emit(collections)
            else:
                self.error.emit(f"Failed to delete collection '{self.collection_name}'")
        except Exception as e:
            self.error.emit(str(e))
