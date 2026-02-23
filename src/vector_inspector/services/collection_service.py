"""Service for managing collections and sample data."""

import uuid

from PySide6.QtCore import QObject, Signal

from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.embedding_providers import ProviderFactory
from vector_inspector.core.logging import log_error, log_info
from vector_inspector.core.sample_data import SampleDataType, generate_sample_data


class CollectionService(QObject):
    """Service for collection operations including sample data population."""

    # Signals
    operation_started = Signal(str)  # operation_name
    operation_progress = Signal(str, int, int)  # message, current, total
    operation_completed = Signal(str, bool, str)  # operation_name, success, message

    def __init__(self, parent=None):
        super().__init__(parent)

    def create_collection(
        self, connection: VectorDBConnection, collection_name: str, dimension: int | None = None
    ) -> bool:
        """Create a new collection.

        Args:
            connection: Active database connection
            collection_name: Name for the new collection
            dimension: Vector dimension (required for some providers)

        Returns:
            True if successful, False otherwise
        """
        try:
            log_info(f"Creating collection: {collection_name}")

            # Use the unified create_collection method
            # Some providers require dimension, others will determine it on first insert
            if dimension is not None:
                success = connection.create_collection(name=collection_name, vector_size=dimension, distance="cosine")
            else:
                # Try without dimension (works for ChromaDB)
                success = connection.create_collection(
                    name=collection_name,
                    vector_size=384,  # Default dimension if not specified
                    distance="cosine",
                )

            if success:
                log_info(f"Collection '{collection_name}' created successfully")
            else:
                log_error(f"Failed to create collection '{collection_name}'")

            return success

        except Exception as e:
            log_error(f"Error creating collection: {e}")
            return False

    def populate_with_sample_data(
        self,
        connection: VectorDBConnection,
        collection_name: str,
        count: int,
        data_type: SampleDataType,
        embedder_name: str,
        embedder_type: str = "sentence-transformer",
        randomize: bool = True,
    ) -> tuple[bool, str]:
        """Populate collection with sample data.

        Args:
            connection: Active database connection
            collection_name: Target collection name
            count: Number of samples to generate
            data_type: Type of sample data
            embedder_name: Embedding model name
            embedder_type: Embedding model type

        Returns:
            Tuple of (success, message)
        """
        try:
            self.operation_started.emit("Generating sample data")
            log_info(f"Generating {count} sample items of type {data_type}")

            # Generate sample data (allow deterministic generation when requested)
            # sample_config may include 'random_data' (bool) to control randomness
            samples = generate_sample_data(count, data_type, randomize=randomize)
            self.operation_progress.emit("Sample data generated", 1, 3)

            # Load embedding model
            self.operation_progress.emit(f"Loading embedding model: {embedder_name}", 2, 3)
            log_info(f"Loading embedding model: {embedder_name} ({embedder_type})")

            try:
                provider = ProviderFactory.create(embedder_name, embedder_type)
                metadata = provider.get_metadata()
                dimension = metadata.dimension
                log_info(f"Model loaded, dimension: {dimension}")
            except Exception as e:
                error_msg = f"Failed to load embedding model: {e}"
                log_error(error_msg)
                self.operation_completed.emit("populate_sample_data", False, error_msg)
                return False, error_msg

            # Generate embeddings
            self.operation_progress.emit("Generating embeddings...", 2, 3)
            texts = [sample["text"] for sample in samples]
            metadatas = [sample["metadata"] for sample in samples]

            try:
                embeddings = provider.encode(texts, normalize=True, show_progress=False)
                log_info(f"Generated {len(embeddings)} embeddings")
            except Exception as e:
                error_msg = f"Failed to generate embeddings: {e}"
                log_error(error_msg)
                self.operation_completed.emit("populate_sample_data", False, error_msg)
                return False, error_msg

            # Upsert into collection
            self.operation_progress.emit("Inserting data into collection...", 3, 3)
            log_info(f"Upserting {count} items to collection '{collection_name}'")

            try:
                # Use the unified add_items method
                # Generate proper UUIDs for Weaviate compatibility, otherwise use sample_{i}
                if connection.__class__.__name__.lower().startswith("weaviate"):
                    ids = [str(uuid.uuid4()) for _ in range(len(texts))]
                else:
                    ids = [f"sample_{i}" for i in range(len(texts))]
                success = connection.add_items(
                    collection_name=collection_name,
                    documents=texts,
                    metadatas=metadatas,
                    ids=ids,
                    embeddings=embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings,
                )

                if not success:
                    error_msg = "Failed to insert data into collection"
                    log_error(error_msg)
                    self.operation_completed.emit("populate_sample_data", False, error_msg)
                    return False, error_msg

                # Save embedding model info to settings for future reference
                try:
                    from vector_inspector.services.settings_service import SettingsService

                    profile_name = getattr(connection, "profile_name", None)
                    if profile_name:
                        settings = SettingsService()
                        settings.save_embedding_model(
                            profile_name=profile_name,
                            collection_name=collection_name,
                            model_name=embedder_name,
                            model_type=embedder_type,
                        )
                        log_info(f"Saved embedding model '{embedder_name}' for collection '{collection_name}'")
                except Exception as e:
                    # Don't fail the operation if saving settings fails
                    log_error(f"Failed to save embedding model to settings: {e}")

                success_msg = f"Successfully added {count} sample items to '{collection_name}'"
                log_info(success_msg)
                self.operation_completed.emit("populate_sample_data", True, success_msg)
                return True, success_msg

            except Exception as e:
                error_msg = f"Failed to insert data: {e}"
                log_error(error_msg)
                self.operation_completed.emit("populate_sample_data", False, error_msg)
                return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error during sample data population: {e}"
            log_error(error_msg)
            self.operation_completed.emit("populate_sample_data", False, error_msg)
            return False, error_msg
