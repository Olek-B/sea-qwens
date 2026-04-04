import chromadb
from chromadb.config import Settings as ChromaSettings
from services.librarian.config import settings
from typing import Optional


class ChromaStore:
    """ChromaDB vector store operations for code/document embeddings"""

    def __init__(self):
        self.client = chromadb.HttpClient(
            host=settings.CHROMA_DB_HOST, port=settings.CHROMA_DB_PORT
        )
        self.collection = self.client.get_or_create_collection(
            name="code_embeddings", metadata={"hnsw:space": "cosine"}
        )

    def add_document(self, uid: str, content: str, metadata: Optional[dict] = None):
        """Add a document to the vector store"""
        kwargs: dict = {"documents": [content], "ids": [uid]}
        if metadata:
            kwargs["metadatas"] = [metadata]
        self.collection.add(**kwargs)

    def search_similar(self, query: str, n_results: int = 5) -> list:
        """Search for similar documents by query text"""
        results = self.collection.query(query_texts=[query], n_results=n_results)
        return results

    def get_document(self, uid: str) -> Optional[dict]:
        """Get a document by ID"""
        results = self.collection.get(ids=[uid])
        if results.get("documents") and results["documents"]:
            return {
                "uid": uid,
                "content": results["documents"][0],
                "metadata": results.get("metadatas", [None])[0]
                if results.get("metadatas")
                else None,
            }
        return None

    def add_function_embedding(self, uid: str, body: str, metadata: dict):
        """Embed a function definition with type metadata"""
        self.collection.add(
            documents=[body], ids=[uid], metadatas=[{**metadata, "type": "function"}]
        )

    def add_class_embedding(self, uid: str, body: str, metadata: dict):
        """Embed a class definition with type metadata"""
        self.collection.add(
            documents=[body], ids=[uid], metadatas=[{**metadata, "type": "class"}]
        )

    def search_code(self, query: str, n_results: int = 10) -> list[dict]:
        """Search for code by semantic query, returning structured results"""
        results = self.collection.query(query_texts=[query], n_results=n_results)
        items = []
        if results.get("ids") and results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                items.append(
                    {
                        "id": doc_id,
                        "document": results["documents"][0][i]
                        if results.get("documents")
                        else None,
                        "metadata": results["metadatas"][0][i]
                        if results.get("metadatas") and results["metadatas"][0]
                        else None,
                        "distance": results["distances"][0][i]
                        if results.get("distances") and results["distances"][0]
                        else None,
                    }
                )
        return items

    def delete_by_id(self, uid: str):
        """Delete a document by its ID"""
        self.collection.delete(ids=[uid])
