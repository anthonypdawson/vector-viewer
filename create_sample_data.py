"""Sample script to populate ChromaDB with test data."""

import chromadb
from chromadb.utils import embedding_functions


def create_sample_data():
    """Create sample data for testing Vector Viewer."""
    print("Creating sample ChromaDB data...")
    
    # Create client
    client = chromadb.PersistentClient(path="./chroma_data")
    
    # Create or get collection
    collection = client.get_or_create_collection(
        name="sample_documents",
        metadata={"description": "Sample documents for testing"}
    )
    
    # Sample documents
    documents = [
        "The quick brown fox jumps over the lazy dog.",
        "Python is a high-level programming language.",
        "Machine learning is a subset of artificial intelligence.",
        "Neural networks are inspired by the human brain.",
        "Data science involves extracting insights from data.",
        "Vector databases store high-dimensional embeddings.",
        "Natural language processing enables computers to understand text.",
        "Deep learning uses multiple layers of neural networks.",
        "Embeddings represent data in continuous vector spaces.",
        "Similarity search finds vectors close to a query vector.",
    ]
    
    metadatas = [
        {"category": "animals", "length": "short"},
        {"category": "programming", "length": "short"},
        {"category": "ai", "length": "short"},
        {"category": "ai", "length": "short"},
        {"category": "data", "length": "short"},
        {"category": "databases", "length": "short"},
        {"category": "ai", "length": "medium"},
        {"category": "ai", "length": "short"},
        {"category": "vectors", "length": "short"},
        {"category": "vectors", "length": "short"},
    ]
    
    ids = [f"doc_{i}" for i in range(len(documents))]
    
    # Add documents
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    
    print(f"Added {len(documents)} documents to collection '{collection.name}'")
    print(f"Collection now contains {collection.count()} items")
    print("\nYou can now:")
    print("1. Run the Vector Viewer application")
    print("2. Connect to Persistent storage with path: ./chroma_data")
    print("3. Select the 'sample_documents' collection")
    print("4. Browse, search, and visualize the data!")


if __name__ == "__main__":
    create_sample_data()
