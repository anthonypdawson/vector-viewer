"""Service for backing up and restoring collections."""

import json
import zipfile
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import shutil


class BackupRestoreService:
    """Handles backup and restore operations for vector database collections."""
    
    @staticmethod
    def backup_collection(
        connection,
        collection_name: str,
        backup_dir: str,
        include_embeddings: bool = True
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
            # Create backup directory if it doesn't exist
            Path(backup_dir).mkdir(parents=True, exist_ok=True)
            
            # Get collection info
            collection_info = connection.get_collection_info(collection_name)
            if not collection_info:
                print(f"Failed to get collection info for {collection_name}")
                return None
            
            # Get all items from collection
            all_data = connection.get_all_items(collection_name)
            if not all_data or not all_data.get("ids"):
                print(f"No data to backup from collection {collection_name}")
                return None
            
            # Convert numpy arrays to lists for JSON serialization
            if "embeddings" in all_data:
                try:
                    import numpy as np
                    if isinstance(all_data["embeddings"], np.ndarray):
                        all_data["embeddings"] = all_data["embeddings"].tolist()
                    elif isinstance(all_data["embeddings"], list):
                        # Convert any numpy arrays in the list
                        all_data["embeddings"] = [
                            emb.tolist() if isinstance(emb, np.ndarray) else emb
                            for emb in all_data["embeddings"]
                        ]
                except ImportError:
                    pass  # numpy not available, assume already lists
            
            # Remove embeddings if not needed (to save space)
            if not include_embeddings and "embeddings" in all_data:
                del all_data["embeddings"]
            
            # Create backup metadata
            backup_metadata = {
                "collection_name": collection_name,
                "backup_timestamp": datetime.now().isoformat(),
                "item_count": len(all_data["ids"]),
                "collection_info": collection_info,
                "include_embeddings": include_embeddings
            }
            
            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{collection_name}_backup_{timestamp}.zip"
            backup_path = Path(backup_dir) / backup_filename
            
            # Create zip file with data and metadata
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Write metadata
                zipf.writestr('metadata.json', json.dumps(backup_metadata, indent=2))
                
                # Write collection data
                zipf.writestr('data.json', json.dumps(all_data, indent=2))
            
            print(f"Backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            print(f"Backup failed: {e}")
            return None
    
    @staticmethod
    def restore_collection(
        connection,
        backup_file: str,
        collection_name: Optional[str] = None,
        overwrite: bool = False
    ) -> bool:
        """
        Restore a collection from a backup file.
        
        Args:
            connection: Vector database connection
            backup_file: Path to backup zip file
            collection_name: Optional new name for restored collection
            overwrite: Whether to overwrite existing collection
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract backup
            with zipfile.ZipFile(backup_file, 'r') as zipf:
                # Read metadata
                metadata_str = zipf.read('metadata.json').decode('utf-8')
                metadata = json.loads(metadata_str)
                
                # Read data
                data_str = zipf.read('data.json').decode('utf-8')
                data = json.loads(data_str)
            
            # Determine collection name
            restore_collection_name = collection_name or metadata["collection_name"]
            
            # Check if collection exists
            existing_collections = connection.list_collections()
            if restore_collection_name in existing_collections:
                if not overwrite:
                    print(f"Collection {restore_collection_name} already exists. Use overwrite=True to replace it.")
                    return False
                else:
                    # Delete existing collection
                    connection.delete_collection(restore_collection_name)
            
            # Check if this is Qdrant - need to create collection first
            from vector_inspector.core.connections.qdrant_connection import QdrantConnection
            if isinstance(connection, QdrantConnection):
                # Get vector size from collection info or embeddings
                vector_size = None
                if metadata.get("collection_info") and "vector_size" in metadata["collection_info"]:
                    vector_size = metadata["collection_info"]["vector_size"]
                elif data.get("embeddings") and len(data["embeddings"]) > 0:
                    vector_size = len(data["embeddings"][0])
                
                if not vector_size:
                    print("Cannot determine vector size for Qdrant collection")
                    return False
                
                # Create collection
                distance = metadata.get("collection_info", {}).get("distance", "Cosine")
                if not connection.create_collection(restore_collection_name, vector_size, distance):
                    print(f"Failed to create collection {restore_collection_name}")
                    return False
                
                # Check if embeddings are missing and need to be generated
                if not data.get("embeddings"):
                    print("Embeddings missing in backup. Generating embeddings...")
                    try:
                        from sentence_transformers import SentenceTransformer
                        model = SentenceTransformer("all-MiniLM-L6-v2")
                        documents = data.get("documents", [])
                        data["embeddings"] = model.encode(documents, show_progress_bar=True).tolist()
                    except Exception as e:
                        print(f"Failed to generate embeddings: {e}")
                        return False
                
                # Keep IDs as strings - Qdrant's _to_uuid method handles conversion
                # Just ensure all IDs are strings
                original_ids = data.get("ids", [])
                data["ids"] = [str(id_val) for id_val in original_ids]
            
            # Add items to collection
            success = connection.add_items(
                restore_collection_name,
                documents=data.get("documents", []),
                metadatas=data.get("metadatas"),
                ids=data.get("ids"),
                embeddings=data.get("embeddings")
            )
            
            if success:
                print(f"Collection '{restore_collection_name}' restored from backup")
                print(f"Restored {len(data.get('ids', []))} items")
                return True
            else:
                print("Failed to restore collection")
                # Clean up partially created collection
                try:
                    if restore_collection_name in connection.list_collections():
                        print(f"Cleaning up failed restore: deleting collection '{restore_collection_name}'")
                        connection.delete_collection(restore_collection_name)
                except Exception as cleanup_error:
                    print(f"Warning: Failed to clean up collection: {cleanup_error}")
                return False
                
        except Exception as e:
            print(f"Restore failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Clean up partially created collection
            try:
                if restore_collection_name in connection.list_collections():
                    print(f"Cleaning up failed restore: deleting collection '{restore_collection_name}'")
                    connection.delete_collection(restore_collection_name)
            except Exception as cleanup_error:
                print(f"Warning: Failed to clean up collection: {cleanup_error}")
            
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
        try:
            backup_path = Path(backup_dir)
            if not backup_path.exists():
                return []
            
            backups = []
            for backup_file in backup_path.glob("*_backup_*.zip"):
                try:
                    # Read metadata from backup
                    with zipfile.ZipFile(backup_file, 'r') as zipf:
                        metadata_str = zipf.read('metadata.json').decode('utf-8')
                        metadata = json.loads(metadata_str)
                    
                    backups.append({
                        "file_path": str(backup_file),
                        "file_name": backup_file.name,
                        "collection_name": metadata.get("collection_name", "Unknown"),
                        "timestamp": metadata.get("backup_timestamp", "Unknown"),
                        "item_count": metadata.get("item_count", 0),
                        "file_size": backup_file.stat().st_size
                    })
                except Exception:
                    # Skip invalid backup files
                    continue
            
            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x["timestamp"], reverse=True)
            return backups
            
        except Exception as e:
            print(f"Failed to list backups: {e}")
            return []
    
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
            print(f"Failed to delete backup: {e}")
            return False
