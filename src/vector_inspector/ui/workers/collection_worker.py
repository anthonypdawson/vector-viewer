"""Worker thread for collection creation operations."""

import time
import uuid

from PySide6.QtCore import QThread, Signal

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.sample_data import SampleDataType
from vector_inspector.services.collection_service import CollectionService
from vector_inspector.services.telemetry_service import TelemetryService


class CollectionCreationWorker(QThread):
    """Worker thread for creating collections with optional sample data."""

    # Signals
    progress_update = Signal(str, int, int)  # message, current, total
    creation_complete = Signal(bool, str)  # success, message
    error_occurred = Signal(str)  # error_message

    def __init__(
        self,
        connection: VectorDBConnection,
        collection_name: str,
        dimension: int | None,
        add_sample: bool,
        sample_config: dict | None = None,
        parent=None,
    ):
        """Initialize worker.

        Args:
            connection: Database connection
            collection_name: Name for new collection
            dimension: Vector dimension (if known)
            add_sample: Whether to add sample data
            sample_config: Configuration for sample data (count, data_type, embedder_name, embedder_type)
            parent: Parent QObject
        """
        super().__init__(parent)
        self.connection = connection
        self.collection_name = collection_name
        self.dimension = dimension
        self.add_sample = add_sample
        self.sample_config = sample_config or {}
        self.collection_service = CollectionService()

        # Connect service signals to our signals
        self.collection_service.operation_progress.connect(self.progress_update)

    def run(self):
        """Execute the collection creation workflow."""
        from vector_inspector.core.logging import log_error, log_info

        # Generate correlation ID and start timing
        correlation_id = str(uuid.uuid4())
        start_time = time.time()
        rows_created = 0

        try:
            log_info(f"Starting collection creation: {self.collection_name}")

            # Get provider type
            provider_type = type(self.connection).__name__.replace("Connection", "").lower()

            # Send started event if sample data requested
            if self.add_sample:
                try:
                    telemetry = TelemetryService()
                    telemetry.queue_event(
                        {
                            "event_name": "sample_db.create_started",
                            "metadata": {
                                "db_type": provider_type,
                                "sample_db_id": self.collection_name,
                                "estimated_rows": self.sample_config.get("count", 0),
                                "correlation_id": correlation_id,
                            },
                        }
                    )
                except Exception:
                    pass  # Best effort telemetry

            # Step 1: Create collection
            self.progress_update.emit("Creating collection...", 1, 3)
            log_info(f"Creating collection with dimension: {self.dimension}")

            success = self.collection_service.create_collection(
                connection=self.connection,
                collection_name=self.collection_name,
                dimension=self.dimension,
            )

            if not success:
                error_msg = "Failed to create collection"
                log_error(error_msg)
                self.creation_complete.emit(False, error_msg)
                return

            log_info(f"Collection created successfully: {self.collection_name}")

            # Step 2: Populate with sample data if requested
            if self.add_sample and self.sample_config:
                log_info(f"Adding sample data: {self.sample_config}")
                self.progress_update.emit("Generating sample data...", 2, 3)

                success, message = self.collection_service.populate_with_sample_data(
                    connection=self.connection,
                    collection_name=self.collection_name,
                    count=self.sample_config.get("count", 10),
                    data_type=SampleDataType(self.sample_config.get("data_type", "text")),
                    embedder_name=self.sample_config["embedder_name"],
                    embedder_type=self.sample_config.get("embedder_type", "sentence-transformer"),
                )

                duration_ms = int((time.time() - start_time) * 1000)
                rows_created = self.sample_config.get("count", 0) if success else 0

                # Send telemetry
                try:
                    telemetry = TelemetryService()
                    event_name = (
                        "sample_db.create_completed" if success else "sample_db.create_failed"
                    )
                    metadata = {
                        "db_type": provider_type,
                        "sample_db_id": self.collection_name,
                        "duration_ms": duration_ms,
                        "correlation_id": correlation_id,
                        "success": success,
                    }
                    if success:
                        metadata["rows_created"] = rows_created
                    else:
                        metadata["error_code"] = "SAMPLE_CREATION_FAILED"
                        metadata["retriable"] = True
                    telemetry.queue_event({"event_name": event_name, "metadata": metadata})
                    telemetry.send_batch()
                except Exception:
                    pass  # Best effort telemetry

                if not success:
                    error_msg = f"Collection created but sample data failed: {message}"
                    log_error(error_msg)
                    self.creation_complete.emit(False, error_msg)
                    return

                log_info(f"Sample data added successfully: {message}")
                self.creation_complete.emit(True, message)
            else:
                success_msg = f"Collection '{self.collection_name}' created successfully"
                log_info(success_msg)
                self.creation_complete.emit(True, success_msg)

        except Exception as e:
            import traceback

            error_msg = f"{e!s}\n{traceback.format_exc()}"
            log_error(f"Collection creation exception: {error_msg}")
            self.error_occurred.emit(str(e) if str(e) else "Unknown error occurred")
