"""Controller for managing connection lifecycle and threading."""

import hashlib
import time
import uuid
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog, QWidget

from vector_inspector import get_version
from vector_inspector.core.connection_manager import ConnectionManager, ConnectionState
from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.provider_factory import ProviderFactory
from vector_inspector.services.collection_service import CollectionService
from vector_inspector.services.profile_service import ProfileService
from vector_inspector.services.telemetry_service import TelemetryService
from vector_inspector.ui.components.create_collection_dialog import CreateCollectionDialog
from vector_inspector.ui.components.loading_dialog import LoadingDialog
from vector_inspector.ui.workers.collection_worker import CollectionCreationWorker


class ConnectionThread(QThread):
    """Background thread for connecting to database."""

    finished = Signal(
        bool, list, str, float, str
    )  # success, collections, error_message, duration_ms, correlation_id

    def __init__(self, connection: VectorDBConnection, correlation_id: str, provider: str):
        super().__init__()
        self.connection = connection
        self.correlation_id = correlation_id
        self.provider = provider

    def run(self):
        """Connect to database and get collections."""
        start_time = time.time()
        try:
            success = self.connection.connect()
            duration_ms = int((time.time() - start_time) * 1000)
            if success:
                collections = self.connection.list_collections()
                self.finished.emit(True, collections, "", duration_ms, self.correlation_id)
            else:
                self.finished.emit(False, [], "Connection failed", duration_ms, self.correlation_id)
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.finished.emit(False, [], str(e), duration_ms, self.correlation_id)


class ConnectionController(QObject):
    """Controller for managing connection operations and lifecycle.

    This handles:
    - Creating connections from profiles
    - Starting connection threads
    - Handling connection results
    - Managing loading dialogs
    - Emitting signals for UI updates
    """

    connection_completed = Signal(
        str, bool, list, str
    )  # connection_id, success, collections, error

    def __init__(
        self,
        connection_manager: ConnectionManager,
        profile_service: ProfileService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.connection_manager = connection_manager
        self.profile_service = profile_service
        self.parent_widget = parent

        # State
        self._connection_threads: dict[str, ConnectionThread] = {}
        self._active_worker = None
        self.loading_dialog = LoadingDialog("Loading...", parent)
        self.collection_service = CollectionService(parent)

    def connect_to_profile(self, profile_id: str) -> bool:
        """Connect to a profile.

        Args:
            profile_id: ID of the profile to connect to

        Returns:
            True if connection initiated successfully, False otherwise
        """
        profile_data = self.profile_service.get_profile_with_credentials(profile_id)
        if not profile_data:
            QMessageBox.warning(self.parent_widget, "Error", "Profile not found.")
            return False

        # Check connection limit
        if self.connection_manager.get_connection_count() >= ConnectionManager.MAX_CONNECTIONS:
            QMessageBox.warning(
                self.parent_widget,
                "Connection Limit",
                f"Maximum number of connections ({ConnectionManager.MAX_CONNECTIONS}) reached. "
                "Please close a connection first.",
            )
            return False

        # Create connection
        provider = profile_data["provider"]
        config = profile_data["config"]
        credentials = profile_data.get("credentials", {})

        try:
            # Create connection object using factory
            connection = ProviderFactory.create(provider, config, credentials)

            # Register with connection manager, using profile_id as connection_id for persistence
            connection_id = self.connection_manager.create_connection(
                name=profile_data["name"],
                provider=provider,
                connection=connection,
                config=config,
                connection_id=profile_data["id"],
            )

            # Update state to connecting
            self.connection_manager.update_connection_state(
                connection_id, ConnectionState.CONNECTING
            )

            # Generate correlation ID for telemetry
            correlation_id = str(uuid.uuid4())

            # Send connection attempt telemetry
            try:
                telemetry = TelemetryService()
                # Hash host/path for privacy
                host_value = config.get("host") or config.get("path") or "unknown"
                host_hash = hashlib.sha256(host_value.encode()).hexdigest()[:16]
                telemetry.queue_event(
                    {
                        "event_name": "db.connection_attempt",
                        "app_version": get_version(),
                        "metadata": {
                            "db_type": provider,
                            "host_hash": host_hash,
                            "connection_id": connection_id,
                            "correlation_id": correlation_id,
                        },
                    }
                )
            except Exception:
                pass  # Best effort telemetry

            # Connect in background thread
            thread = ConnectionThread(connection, correlation_id, provider)
            thread.finished.connect(
                lambda success, collections, error, duration_ms, corr_id: (
                    self._on_connection_finished(
                        connection_id, provider, success, collections, error, duration_ms, corr_id
                    )
                )
            )
            self._connection_threads[connection_id] = thread
            thread.start()

            # Show loading dialog
            self.loading_dialog.show_loading(f"Connecting to {profile_data['name']}...")
            return True

        except Exception as e:
            QMessageBox.critical(
                self.parent_widget, "Connection Error", f"Failed to create connection: {e}"
            )
            return False

    def _on_connection_finished(
        self,
        connection_id: str,
        provider: str,
        success: bool,
        collections: list,
        error: str,
        duration_ms: float,
        correlation_id: str,
    ):
        """Handle connection thread completion."""
        self.loading_dialog.hide_loading()

        # Send connection result telemetry
        try:
            telemetry = TelemetryService()
            metadata = {
                "success": success,
                "db_type": provider,
                "duration_ms": duration_ms,
                "correlation_id": correlation_id,
            }
            if not success:
                metadata["error_code"] = "CONNECTION_FAILED"
                metadata["error_class"] = type(error).__name__ if error else "Unknown"
            telemetry.queue_event({"event_name": "db.connection_result", "metadata": metadata})
            telemetry.send_batch()
        except Exception:
            pass  # Best effort telemetry

        # Clean up thread
        thread = self._connection_threads.pop(connection_id, None)
        if thread:
            thread.wait()  # Wait for thread to fully finish
            thread.deleteLater()

        if success:
            # Update state to connected
            self.connection_manager.update_connection_state(
                connection_id, ConnectionState.CONNECTED
            )

            # Mark connection as opened first (will show in UI)
            self.connection_manager.mark_connection_opened(connection_id)

            # Then update collections (UI item now exists to receive them)
            self.connection_manager.update_collections(connection_id, collections)
        else:
            # Update state to error
            self.connection_manager.update_connection_state(
                connection_id, ConnectionState.ERROR, error
            )

            QMessageBox.warning(
                self.parent_widget, "Connection Failed", f"Failed to connect: {error}"
            )

            # Remove the failed connection
            self.connection_manager.close_connection(connection_id)

        # Emit signal for UI updates
        self.connection_completed.emit(connection_id, success, collections, error)

    def create_collection_with_dialog(self, connection_id: str = None) -> bool:
        """Show dialog to create a new collection with optional sample data.

        Args:
            connection_id: ID of the active connection

        Returns:
            True if collection was created, False otherwise
        """
        # Get active connection
        if connection_id is None:
            connection_id = self.connection_manager.get_active_connection_id()

        if not connection_id:
            QMessageBox.warning(
                self.parent_widget, "No Connection", "Please connect to a database first."
            )
            return False

        connection = self.connection_manager.get_connection(connection_id)
        if not connection:
            QMessageBox.warning(self.parent_widget, "Error", "Connection not found.")
            return False

        # Show dialog
        dialog = CreateCollectionDialog(self.parent_widget)
        if dialog.exec() != CreateCollectionDialog.DialogCode.Accepted:
            return False

        config = dialog.get_configuration()
        collection_name = config["name"]

        # Check if collection already exists
        try:
            existing_collections = connection.list_collections()
            if collection_name in existing_collections:
                QMessageBox.warning(
                    self.parent_widget,
                    "Collection Exists",
                    f"A collection named '{collection_name}' already exists.",
                )
                return False
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget, "Error", f"Could not check existing collections: {e}"
            )
            return False

        # Create progress dialog immediately
        progress_dialog = QProgressDialog(
            "Preparing...",
            None,  # No cancel button label
            0,
            0,  # Indefinite progress initially
            self.parent_widget,
        )
        progress_dialog.setWindowTitle("Creating Collection")
        progress_dialog.setModal(True)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setCancelButton(None)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        progress_dialog.setValue(0)
        progress_dialog.show()
        QApplication.processEvents()

        # Get dimension from model if sample data is requested
        # Show loading progress while we do this
        dimension = None
        if config["add_sample"]:
            progress_dialog.setLabelText("Loading embedding model...")
            QApplication.processEvents()

            try:
                from vector_inspector.core.embedding_providers import ProviderFactory

                provider = ProviderFactory.create(config["embedder_name"], config["embedder_type"])
                metadata = provider.get_metadata()
                dimension = metadata.dimension
            except Exception as e:
                progress_dialog.close()
                QMessageBox.critical(
                    self.parent_widget, "Error", f"Failed to get model dimension: {e}"
                )
                return False

        # Now set up for collection creation
        progress_dialog.setMaximum(3)
        progress_dialog.setLabelText("Creating collection...")
        progress_dialog.setValue(0)
        QApplication.processEvents()

        # Create worker thread
        sample_config = None
        if config["add_sample"]:
            sample_config = {
                "count": config["count"],
                "data_type": config["data_type"],
                "embedder_name": config["embedder_name"],
                "embedder_type": config["embedder_type"],
            }

        worker = CollectionCreationWorker(
            connection=connection,
            collection_name=collection_name,
            dimension=dimension,
            add_sample=config["add_sample"],
            sample_config=sample_config,
            parent=self,
        )

        def on_progress(message: str, current: int, total: int):
            """Update progress dialog."""
            from vector_inspector.core.logging import log_info

            log_info(f"Collection creation progress: {message} ({current}/{total})")
            progress_dialog.setLabelText(message)
            progress_dialog.setMaximum(total)
            progress_dialog.setValue(current)
            QApplication.processEvents()

        def on_complete(success: bool, message: str):
            """Handle completion."""
            from vector_inspector.core.logging import log_error, log_info

            progress_dialog.setValue(3)
            progress_dialog.close()

            # Save embedding model information if collection was created successfully with sample data
            if success and config["add_sample"]:
                try:
                    from vector_inspector.services.settings_service import SettingsService

                    settings = SettingsService()

                    # Get profile name from connection
                    profile_name = (
                        connection.name if hasattr(connection, "name") else str(connection_id)
                    )

                    # Save the embedding model configuration
                    settings.save_embedding_model(
                        profile_name=profile_name,
                        collection_name=collection_name,
                        model_name=config["embedder_name"],
                        model_type=config["embedder_type"],
                    )
                    log_info(
                        f"Saved embedding model config: {config['embedder_name']} for {collection_name}"
                    )
                except Exception as e:
                    # Log but don't fail - collection is created successfully
                    log_error(f"Failed to save embedding model configuration: {e}")

            # Show result
            if success:
                log_info(f"Collection creation successful: {message}")
                QMessageBox.information(self.parent_widget, "Success", message)
            else:
                log_error(f"Collection creation failed: {message}")
                QMessageBox.warning(self.parent_widget, "Error", message)

            # Refresh collections
            if success:
                try:
                    collections = connection.list_collections()
                    self.connection_manager.update_collections(connection_id, collections)
                    log_info("Refreshed collection list")
                except Exception as e:
                    log_error(f"Failed to refresh collections: {e}")

            # Clean up worker reference
            if hasattr(self, "_active_worker"):
                self._active_worker = None

        def on_error(error: str):
            """Handle error."""
            from vector_inspector.core.logging import log_error

            log_error(f"Collection creation error: {error}")
            progress_dialog.close()

            error_message = f"Error: {error}" if error else "An unknown error occurred"
            QMessageBox.critical(self.parent_widget, "Error", error_message)

            # Clean up worker reference
            if hasattr(self, "_active_worker"):
                self._active_worker = None

        # Connect signals
        worker.progress_update.connect(on_progress)
        worker.creation_complete.connect(on_complete)
        worker.error_occurred.connect(on_error)

        # Store worker reference to prevent garbage collection
        self._active_worker = worker

        # Start worker (non-blocking)
        worker.start()

        return True  # Successfully started the operation

    def cleanup(self):
        """Clean up connection threads on shutdown."""
        for thread in list(self._connection_threads.values()):
            if thread.isRunning():
                thread.quit()
                thread.wait(1000)  # Wait up to 1 second
