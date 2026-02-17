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
    ) -> None:
        super().__init__()
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
                    documents=[self.updated_data["document"]] if self.updated_data["document"] else None,
                    metadatas=[self.updated_data["metadata"]] if self.updated_data["metadata"] else None,
                )
            else:
                success = self.connection.update_items(
                    self.collection,
                    ids=[self.updated_data["id"]],
                    documents=[self.updated_data["document"]] if self.updated_data["document"] else None,
                    metadatas=[self.updated_data["metadata"]] if self.updated_data["metadata"] else None,
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
    ) -> None:
        """
        Initialize data import thread.

        Args:
            connection: The ConnectionInstance
            collection_name: Name of the collection to import into
            file_path: Path to the file to import
            format_type: Import format ('json', 'csv', 'parquet')
        """
        super().__init__()
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

            # Handle Qdrant-specific requirements
            from vector_inspector.core.connections.qdrant_connection import QdrantConnection

            if isinstance(self.connection, QdrantConnection):
                # Check if embeddings are missing and need to be generated
                if not imported_data.get("embeddings"):
                    self.progress.emit("Generating embeddings for Qdrant...")
                    try:
                        from sentence_transformers import SentenceTransformer

                        model = SentenceTransformer("all-MiniLM-L6-v2")
                        documents = imported_data.get("documents", [])
                        imported_data["embeddings"] = model.encode(
                            documents, show_progress_bar=False
                        ).tolist()
                    except Exception as e:
                        self.error.emit(f"Qdrant requires embeddings. Failed to generate: {e}")
                        return

                # Convert IDs to Qdrant-compatible format
                original_ids: list[Any] = imported_data.get("ids", [])
                qdrant_ids: list[int] = []
                metadatas: list[dict[str, Any]] = imported_data.get("metadatas", [])

                for i, orig_id in enumerate(original_ids):
                    # Try to convert to integer, otherwise use index
                    try:
                        if isinstance(orig_id, str) and "_" in orig_id:
                            qdrant_id = int(orig_id.split("_")[-1])
                        else:
                            qdrant_id = int(orig_id)
                    except (ValueError, AttributeError):
                        qdrant_id = i

                    qdrant_ids.append(qdrant_id)

                    # Store original ID in metadata
                    if i < len(metadatas):
                        if metadatas[i] is None:
                            metadatas[i] = {}
                        metadatas[i]["original_id"] = orig_id
                    else:
                        metadatas.append({"original_id": orig_id})

                imported_data["ids"] = qdrant_ids
                imported_data["metadatas"] = metadatas

            # Add items to collection
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
