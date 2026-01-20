"""Service for applying client-side filters to data."""

from typing import Dict, Any, List


def apply_client_side_filters(data: Dict[str, Any], filters: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Apply client-side filters to fetched data.
    
    Args:
        data: Data dictionary with ids, documents, metadatas, etc.
        filters: List of client-side filter dictionaries
        
    Returns:
        Filtered data dictionary
    """
    if not filters:
        return data
    
    ids = data.get("ids", [])
    documents = data.get("documents", [])
    metadatas = data.get("metadatas", [])
    embeddings = data.get("embeddings", [])
    
    # Track which indices to keep
    keep_indices = []
    
    for i in range(len(ids)):
        # Check if this item passes all client-side filters
        passes = True
        
        for filt in filters:
            field = filt.get("field", "")
            op = filt.get("op", "")
            value = filt.get("value", "")
            
            # Special handling for document field
            if field.lower() == "document":
                item_value = documents[i] if i < len(documents) else ""
            else:
                # Get from metadata
                metadata = metadatas[i] if i < len(metadatas) else {}
                item_value = metadata.get(field, "")
            
            # Convert to string for text operations
            item_value_str = str(item_value).lower()
            search_value = str(value).lower()
            
            # Apply operator
            if op == "contains":
                if search_value not in item_value_str:
                    passes = False
                    break
            elif op == "not_contains":
                if search_value in item_value_str:
                    passes = False
                    break
        
        if passes:
            keep_indices.append(i)
    
    # Filter the data
    filtered_data = {
        "ids": [ids[i] for i in keep_indices],
        "documents": [documents[i] for i in keep_indices if i < len(documents)],
        "metadatas": [metadatas[i] for i in keep_indices if i < len(metadatas)],
    }
    
    if embeddings:
        filtered_data["embeddings"] = [embeddings[i] for i in keep_indices if i < len(embeddings)]
    
    return filtered_data
