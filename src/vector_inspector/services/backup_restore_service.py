"""Service for backing up and restoring collections."""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone
import shutil

from vector_inspector.core.logging import log_info, log_error, log_debug
from .backup_helpers import write_backup_zip, read_backup_zip, normalize_embeddings


class BackupRestoreService:
    """Handles backup and restore operations for vector database collections."""

    @staticmethod
    def backup_collection(
        connection, collection_name: str, backup_dir: str, include_embeddings: bool = True
    ) -> Optional[str]:
        """
        Backup a collection to a directory.

        Args:
            connection: Vector database connection
            collection_name: Name of collection to backup
            backup_dir: Directory to store backups
            include_embeddings: Whether to include embedding vectors

        Returns:
            Path to backup file or None if failed
        """
        try:
            Path(backup_dir).mkdir(parents=True, exist_ok=True)

            collection_info = connection.get_collection_info(collection_name)
            if not collection_info:
                log_error("Failed to get collection info for %s", collection_name)
                return None

            all_data = connection.get_all_items(collection_name)
            if not all_data or not all_data.get("ids"):
                log_info("No data to backup from collection %s", collection_name)
                return None

            # Normalize embeddings to plain lists
            all_data = normalize_embeddings(all_data)

            if not include_embeddings and "embeddings" in all_data:
                del all_data["embeddings"]

            backup_metadata = {
                "collection_name": collection_name,
                "backup_timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "item_count": len(all_data["ids"]),
                "collection_info": collection_info,
                "include_embeddings": include_embeddings,
            }
            # Include embedding model info when available to assist accurate restores
            try:
                embed_model = None
                embed_model_type = None
                # Prefer explicit collection_info entries
                if collection_info and collection_info.get("embedding_model"):
                    embed_model = collection_info.get("embedding_model")
                    embed_model_type = collection_info.get("embedding_model_type")
                else:
                    # Ask connection for a model hint (may consult settings/service)
                    try:
                        embed_model = connection.get_embedding_model(collection_name)
                    except Exception:
                        embed_model = None

                if embed_model:
                    backup_metadata["embedding_model"] = embed_model
                if embed_model_type:
                    backup_metadata["embedding_model_type"] = embed_model_type
            except Exception as e:
                # Embedding metadata is optional; log failure but do not abort backup.
                log_debug("Failed to populate embedding metadata for %s: %s", collection_name, e)

            timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{collection_name}_backup_{timestamp}.zip"
            backup_path = Path(backup_dir) / backup_filename

            write_backup_zip(backup_path, backup_metadata, all_data)
            log_info("Backup created: %s", backup_path)
            return str(backup_path)
        except Exception as e:
            log_error("Backup failed: %s", e)
            return None

    @staticmethod
    def restore_collection(
        connection,
        backup_file: str,
        collection_name: Optional[str] = None,
        overwrite: bool = False,
        recompute_embeddings: Optional[bool] = None,
    ) -> bool:
        """
        Restore a collection from a backup file.

        Args:
            connection: Vector database connection
            backup_file: Path to backup zip file
            collection_name: Optional new name for restored collection
            overwrite: Whether to overwrite existing collection
            recompute_embeddings: Whether to recompute embeddings during restore.
                - True: Always recompute embeddings from documents if model metadata is available
                - False: Never recompute, use embeddings from backup as-is
                - None (default): Auto mode - only recompute if backup contains embeddings
                  and model metadata is available

        Returns:
            True if successful, False otherwise
        """
        restore_collection_name = None
        try:
            metadata, data = read_backup_zip(backup_file)
            restore_collection_name = collection_name or metadata.get("collection_name")

            existing_collections = connection.list_collections()
            if restore_collection_name in existing_collections:
                if not overwrite:
                    log_info(
                        "Collection %s already exists. Use overwrite=True to replace it.",
                        restore_collection_name,
                    )
                    return False
                else:
                    connection.delete_collection(restore_collection_name)
            else:
                # Collection does not exist on target; attempt to create it.
                # Try to infer vector size from metadata or embedded vectors in backup.
                try:
                    inferred_size = None
                    col_info = metadata.get("collection_info") if metadata else None
                    if (
                        col_info
                        and col_info.get("vector_dimension")
                        and isinstance(col_info.get("vector_dimension"), int)
                    ):
                        inferred_size = int(col_info.get("vector_dimension"))

                    # Fallback: inspect embeddings in backup data
                    if inferred_size is None and data and data.get("embeddings"):
                        first_emb = data.get("embeddings")[0]
                        if first_emb is not None:
                            inferred_size = len(first_emb)

                    # Final fallback: common default
                    if inferred_size is None:
                        log_error(
                            "Unable to infer vector dimension for collection %s from metadata or backup data; restore aborted.",
                            restore_collection_name,
                        )
                        return False

                    created = True
                    if hasattr(connection, "create_collection"):
                        created = connection.create_collection(
                            restore_collection_name, inferred_size
                        )

                    if not created:
                        log_error(
                            "Failed to create collection %s before restore", restore_collection_name
                        )
                        return False
                except Exception as e:
                    log_error("Error while creating collection %s: %s", restore_collection_name, e)
                    return False

            # Provider-specific preparation hook
            if hasattr(connection, "prepare_restore"):
                ok = connection.prepare_restore(metadata, data)
                if not ok:
                    log_error("Provider prepare_restore failed for %s", restore_collection_name)
                    return False

            # Ensure embeddings normalized
            data = normalize_embeddings(data)

            # Decide whether to use embeddings from backup, recompute, or omit.
            embeddings_to_use = data.get("embeddings")
            if recompute_embeddings is False:
                # User explicitly requested restore without embeddings: ignore any stored embeddings
                embeddings_to_use = None

            # Determine if we should recompute embeddings based on:
            # 1. Explicit request (recompute_embeddings=True), OR
            # 2. Auto mode (None) with embedding_model in metadata and embeddings in backup
            try:
                should_recompute = False
                if recompute_embeddings is True:
                    # Explicit recompute request - allow regardless of backup having embeddings
                    should_recompute = True
                elif (
                    recompute_embeddings is None
                    and metadata
                    and metadata.get("embedding_model")
                    and data.get("embeddings")
                ):
                    # Auto mode: only recompute if embeddings exist in backup
                    should_recompute = True

                if should_recompute:
                    try:
                        from vector_inspector.core.embedding_utils import (
                            load_embedding_model,
                            encode_text,
                        )

                        model_name = metadata.get("embedding_model") if metadata else None
                        docs = data.get("documents", [])

                        # Check if we have the necessary data to recompute
                        if not model_name:
                            log_info(
                                "No embedding model available in metadata to recompute embeddings"
                            )
                            embeddings_to_use = None
                        elif not docs:
                            log_info(
                                "No documents available in backup to recompute embeddings"
                            )
                            embeddings_to_use = None
                        else:
                            # We have both model metadata and documents, proceed with recomputation
                            model_type = metadata.get("embedding_model_type", "sentence-transformer")
                            model = load_embedding_model(model_name, model_type)
                            new_embeddings = []
                            if model_type == "clip":
                                # CLIP: encode per-document
                                for d in docs:
                                    new_embeddings.append(encode_text(d, model, model_type))
                            else:
                                # sentence-transformer supports batch encode
                                new_embeddings = model.encode(
                                    docs, show_progress_bar=False
                                ).tolist()

                            embeddings_to_use = new_embeddings
                    except Exception as e:
                        log_error("Failed to recompute embeddings during restore: %s", e)
                        embeddings_to_use = None

                # If target provider (e.g., Chroma) cannot accept mismatched embeddings, and embeddings_to_use
                # exists but likely mismatched, it is safer to omit them. We already attempted recompute when possible.
            except Exception:
                embeddings_to_use = data.get("embeddings")

            success = connection.add_items(
                restore_collection_name,
                documents=data.get("documents", []),
                metadatas=data.get("metadatas"),
                ids=data.get("ids"),
                embeddings=embeddings_to_use,
            )

            if success:
                log_info("Collection '%s' restored from backup", restore_collection_name)
                log_info("Restored %d items", len(data.get("ids", [])))
                return True

            # Failure: attempt cleanup
            log_error("Failed to restore collection %s", restore_collection_name)
            try:
                if restore_collection_name in connection.list_collections():
                    log_info(
                        "Cleaning up failed restore: deleting collection '%s'",
                        restore_collection_name,
                    )
                    connection.delete_collection(restore_collection_name)
            except Exception as cleanup_error:
                log_error("Warning: Failed to clean up collection: %s", cleanup_error)
            return False

        except Exception as e:
            log_error("Restore failed: %s", e)
            try:
                if (
                    restore_collection_name
                    and restore_collection_name in connection.list_collections()
                ):
                    log_info(
                        "Cleaning up failed restore: deleting collection '%s'",
                        restore_collection_name,
                    )
                    connection.delete_collection(restore_collection_name)
            except Exception as cleanup_error:
                log_error("Warning: Failed to clean up collection: %s", cleanup_error)
            return False

    @staticmethod
    def list_backups(backup_dir: str) -> list:
        """
        List all backup files in a directory.

        Args:
            backup_dir: Directory containing backups

        Returns:
            List of backup file information dictionaries
        """
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            return []

        backups = []
        for backup_file in backup_path.glob("*_backup_*.zip"):
            try:
                metadata, _ = read_backup_zip(backup_file)
                backups.append(
                    {
                        "file_path": str(backup_file),
                        "file_name": backup_file.name,
                        "collection_name": metadata.get("collection_name", "Unknown"),
                        "timestamp": metadata.get("backup_timestamp", "Unknown"),
                        "item_count": metadata.get("item_count", 0),
                        "file_size": backup_file.stat().st_size,
                    }
                )
            except Exception:
                continue

        backups.sort(key=lambda x: x["timestamp"], reverse=True)
        return backups

    @staticmethod
    def delete_backup(backup_file: str) -> bool:
        """
        Delete a backup file.

        Args:
            backup_file: Path to backup file to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            Path(backup_file).unlink()
            return True
        except Exception as e:
            log_error("Failed to delete backup: %s", e)
            return False
