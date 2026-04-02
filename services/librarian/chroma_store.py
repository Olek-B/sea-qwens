import chromadb
from chromadb.config import Settings as ChromaSettings
from services.librarian.config import settings
from typing import Optional


class ChromaStore:
    """ChromaDB vector store operations for code/document embeddings"""

    def __init__(self):
        self.client = chromadb.HttpClient(
            host=settings.CHROMA_DB_HOST,
            port=settings.CHROMA_DB_PORT
        )
        self.collection = self.client.get_or_create_collection(
            name="code_embeddings",
            metadata={"hnsw:space": "cosine"}
        )

    def add_document(self, uid: str, content: str, metadata: Optional[dict] = None):
        """Add a document to the vector store"""
        self.collection.add(
            documents=[content],
            ids=[uid],
            metadatas=[metadata or {}]
        )

    def search_similar(self, query: str, n_results: int = 5) -> list:
        """Search for similar documents by query text"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results

    def get_document(self, uid: str) -> Optional[dict]:
        """Get a document by ID"""
        results = self.collection.get(ids=[uid])
        if results["documents"]:
            return {
                "uid": uid,
                "content": results["documents"][0],
                "metadata": results["metadatas"][0]
            }
        return None
