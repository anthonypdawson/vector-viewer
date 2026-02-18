"""Background threads for metadata view operations."""

from typing import Any, Optional

from PySide6.QtCore import QThread, Signal

from vector_inspector.ui.views.metadata.context import MetadataContext


class DataLoadThread(QThread):
    """Background thread for loading collection data."""

    finished = Signal(dict)
    error = Signal(str)

    ctx: MetadataContext
    req_limit: Optional[int]
    req_offset: Optional[int]

    def __init__(
        self,
        ctx: MetadataContext,
        req_limit: Optional[int],
        req_offset: Optional[int],
    ) -> None:
        super().__init__()
        self.ctx = ctx
        self.req_limit = req_limit
        self.req_offset = req_offset

    def run(self) -> None:
        """Load data from database."""
        try:
            if not self.ctx.connection:
                self.error.emit("No database connection available")
                return

            data = self.ctx.connection.get_all_items(
                self.ctx.current_collection,
                limit=self.req_limit,
                offset=self.req_offset,
                where=self.ctx.server_filter,
            )
            if data:
                self.finished.emit(data)
            else:
                self.error.emit("Failed to load data")
        except Exception as e:
            self.error.emit(str(e))


class ItemUpdateThread(QThread):
    """Background thread for updating an item in the collection."""

    finished = Signal(dict)  # Emits updated_data on success
    error = Signal(str)

    def __init__(
        self,
        connection: Any,
        collection: str,
        updated_data: dict[str, Any],
        embeddings_arg: Optional[list] = None,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.connection = connection
        self.collection = collection
        self.updated_data = updated_data
        self.embeddings_arg = embeddings_arg

    def run(self) -> None:
        """Update item in database."""
        try:
            if not self.connection:
                self.error.emit("No database connection available")
                return

            # Update item in collection
            if self.embeddings_arg is None:
                success = self.connection.update_items(
                    self.collection,
                    ids=[self.updated_data["id"]],
                    documents=[self.updated_data["document"]]
                    if self.updated_data["document"]
                    else None,
                    metadatas=[self.updated_data["metadata"]]
                    if self.updated_data["metadata"]
                    else None,
                )
            else:
                success = self.connection.update_items(
                    self.collection,
                    ids=[self.updated_data["id"]],
                    documents=[self.updated_data["document"]]
                    if self.updated_data["document"]
                    else None,
                    metadatas=[self.updated_data["metadata"]]
                    if self.updated_data["metadata"]
                    else None,
                    embeddings=self.embeddings_arg,
                )

            if success:
                self.finished.emit(self.updated_data)
            else:
                self.error.emit("Failed to update item")
        except Exception as e:
            self.error.emit(str(e))


class DataImportThread(QThread):
    """Background thread for importing data from file."""

    finished = Signal(dict, int)  # imported_data, item_count
    error = Signal(str)  # error_message
    progress = Signal(str)  # progress_message

    def __init__(
        self,
        connection: Any,
        collection_name: str,
        file_path: str,
        format_type: str,
        parent: Optional[Any] = None,
    ) -> None:
        """
        Initialize data import thread.

        Args:
            connection: The ConnectionInstance
            collection_name: Name of the collection to import into
            file_path: Path to the file to import
            format_type: Import format ('json', 'csv', 'parquet')
            parent: Parent QObject
        """
        super().__init__(parent)
        self.connection = connection
        self.collection_name = collection_name
        self.file_path = file_path
        self.format_type = format_type

    def run(self) -> None:
        """Import data from file in background."""
        try:
            from vector_inspector.services.import_export_service import ImportExportService

            service = ImportExportService()
            imported_data: Optional[dict[str, Any]] = None

            # Parse file
            self.progress.emit("Parsing file...")
            if self.format_type == "json":
                imported_data = service.import_from_json(self.file_path)
            elif self.format_type == "csv":
                imported_data = service.import_from_csv(self.file_path)
            elif self.format_type == "parquet":
                imported_data = service.import_from_parquet(self.file_path)

            if not imported_data:
                self.error.emit("Failed to parse import file")
                return

            # Add items to collection
            # Connection-specific preprocessing (e.g., embedding generation, ID conversion)
            # is handled by the connection's add_items method
            self.progress.emit("Adding items to collection...")
            success = self.connection.add_items(
                self.collection_name,
                documents=imported_data["documents"],
                metadatas=imported_data.get("metadatas"),
                ids=imported_data.get("ids"),
                embeddings=imported_data.get("embeddings"),
            )

            if success:
                item_count = len(imported_data.get("ids", []))
                self.finished.emit(imported_data, item_count)
            else:
                self.error.emit("Failed to add items to collection")

        except Exception as e:
            self.error.emit(f"Import error: {e}")
