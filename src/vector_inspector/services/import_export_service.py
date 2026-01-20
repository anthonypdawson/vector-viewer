"""Service for importing and exporting collection data."""

import json
import csv
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd


class ImportExportService:
    """Handles import/export operations for vector database collections."""
    
    @staticmethod
    def export_to_json(data: Dict[str, Any], file_path: str) -> bool:
        """
        Export collection data to JSON format.
        
        Args:
            data: Collection data dictionary with ids, documents, metadatas, embeddings
            file_path: Path to save JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Structure data for export
            export_data = []
            ids = data.get("ids", [])
            documents = data.get("documents", [])
            metadatas = data.get("metadatas", [])
            embeddings = data.get("embeddings", [])
            
            for i, item_id in enumerate(ids):
                item = {
                    "id": item_id,
                    "document": documents[i] if i < len(documents) else None,
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                }
                # Optionally include embeddings
                if embeddings and i < len(embeddings):
                    item["embedding"] = embeddings[i]
                export_data.append(item)
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
                
            return True
        except Exception as e:
            print(f"Export to JSON failed: {e}")
            return False
    
    @staticmethod
    def export_to_csv(data: Dict[str, Any], file_path: str, include_embeddings: bool = False) -> bool:
        """
        Export collection data to CSV format.
        
        Args:
            data: Collection data dictionary
            file_path: Path to save CSV file
            include_embeddings: Whether to include embedding vectors
            
        Returns:
            True if successful, False otherwise
        """
        try:
            ids = data.get("ids", [])
            documents = data.get("documents", [])
            metadatas = data.get("metadatas", [])
            embeddings = data.get("embeddings", [])
            
            # Prepare rows
            rows = []
            for i, item_id in enumerate(ids):
                row = {
                    "id": item_id,
                    "document": documents[i] if i < len(documents) else "",
                }
                
                # Add metadata fields
                if i < len(metadatas) and metadatas[i]:
                    for key, value in metadatas[i].items():
                        row[f"metadata_{key}"] = value
                
                # Optionally add embeddings
                if include_embeddings and embeddings and i < len(embeddings):
                    row["embedding"] = json.dumps(embeddings[i])
                    
                rows.append(row)
            
            # Convert to DataFrame and save
            df = pd.DataFrame(rows)
            df.to_csv(file_path, index=False, encoding='utf-8')
            
            return True
        except Exception as e:
            print(f"Export to CSV failed: {e}")
            return False
    
    @staticmethod
    def export_to_parquet(data: Dict[str, Any], file_path: str) -> bool:
        """
        Export collection data to Parquet format.
        
        Args:
            data: Collection data dictionary
            file_path: Path to save Parquet file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            ids = data.get("ids", [])
            documents = data.get("documents", [])
            metadatas = data.get("metadatas", [])
            embeddings = data.get("embeddings", [])
            
            # Prepare data for DataFrame
            df_data = {
                "id": ids,
                "document": documents if documents else [None] * len(ids),
            }
            
            # Add metadata fields as separate columns
            if metadatas and metadatas[0]:
                for key in metadatas[0].keys():
                    df_data[f"metadata_{key}"] = [m.get(key) if m else None for m in metadatas]
            
            # Add embeddings as a column
            if embeddings:
                df_data["embedding"] = embeddings
            
            # Create DataFrame and save
            df = pd.DataFrame(df_data)
            df.to_parquet(file_path, index=False, engine='pyarrow')
            
            return True
        except Exception as e:
            print(f"Export to Parquet failed: {e}")
            return False
    
    @staticmethod
    def import_from_json(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Import collection data from JSON format.
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Dictionary with ids, documents, metadatas, embeddings or None if failed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Parse data
            ids = []
            documents = []
            metadatas = []
            embeddings = []
            
            for item in data:
                ids.append(item.get("id", ""))
                documents.append(item.get("document", ""))
                metadatas.append(item.get("metadata", {}))
                if "embedding" in item:
                    embeddings.append(item["embedding"])
            
            result = {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }
            
            if embeddings:
                result["embeddings"] = embeddings
                
            return result
            
        except Exception as e:
            print(f"Import from JSON failed: {e}")
            return None
    
    @staticmethod
    def import_from_csv(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Import collection data from CSV format.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Dictionary with ids, documents, metadatas, embeddings or None if failed
        """
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            
            ids = df["id"].tolist()
            documents = df["document"].tolist() if "document" in df.columns else [""] * len(ids)
            
            # Extract metadata columns
            metadata_cols = [col for col in df.columns if col.startswith("metadata_")]
            metadatas = []
            
            for idx in range(len(ids)):
                metadata = {}
                for col in metadata_cols:
                    key = col.replace("metadata_", "")
                    value = df.loc[idx, col]
                    if pd.notna(value):
                        metadata[key] = value
                metadatas.append(metadata)
            
            # Extract embeddings if present
            embeddings = []
            if "embedding" in df.columns:
                for emb_str in df["embedding"]:
                    if pd.notna(emb_str):
                        embeddings.append(json.loads(emb_str))
                    else:
                        embeddings.append([])
            
            result = {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }
            
            if embeddings:
                result["embeddings"] = embeddings
                
            return result
            
        except Exception as e:
            print(f"Import from CSV failed: {e}")
            return None
    
    @staticmethod
    def import_from_parquet(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Import collection data from Parquet format.
        
        Args:
            file_path: Path to Parquet file
            
        Returns:
            Dictionary with ids, documents, metadatas, embeddings or None if failed
        """
        try:
            df = pd.read_parquet(file_path, engine='pyarrow')
            
            ids = df["id"].tolist()
            documents = df["document"].tolist() if "document" in df.columns else [""] * len(ids)
            
            # Extract metadata columns
            metadata_cols = [col for col in df.columns if col.startswith("metadata_")]
            metadatas = []
            
            for idx in range(len(ids)):
                metadata = {}
                for col in metadata_cols:
                    key = col.replace("metadata_", "")
                    value = df.loc[idx, col]
                    if pd.notna(value):
                        metadata[key] = value
                metadatas.append(metadata)
            
            # Extract embeddings if present
            embeddings = []
            if "embedding" in df.columns:
                embeddings = df["embedding"].tolist()
            
            result = {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }
            
            if embeddings:
                result["embeddings"] = embeddings
                
            return result
            
        except Exception as e:
            print(f"Import from Parquet failed: {e}")
            return None
