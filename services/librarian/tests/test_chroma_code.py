# services/librarian/tests/test_chroma_code.py

import pytest
from unittest.mock import MagicMock, patch


class TestChromaCodeOperations:

    @pytest.fixture
    def chroma_store(self):
        with patch('services.librarian.chroma_store.chromadb') as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.HttpClient.return_value = mock_client
            from services.librarian.chroma_store import ChromaStore
            store = ChromaStore()
            store.client = mock_client
            store.collection = mock_collection
            return store

    def test_add_function_embedding(self, chroma_store):
        chroma_store.add_function_embedding(
            uid="test_func", body="def test_func(): pass",
            metadata={"name": "test_func", "file": "test.py"}
        )
        chroma_store.collection.add.assert_called()

    def test_add_class_embedding(self, chroma_store):
        chroma_store.add_class_embedding(
            uid="TestClass", body="class TestClass: pass",
            metadata={"name": "TestClass", "file": "test.py"}
        )
        chroma_store.collection.add.assert_called()

    def test_search_code(self, chroma_store):
        chroma_store.collection.query.return_value = {
            "ids": [["func1"]], "documents": [["def func1(): pass"]],
            "metadatas": [[{"name": "func1"}]], "distances": [[0.1]]
        }
        results = chroma_store.search_code("authentication")
        assert len(results) == 1
        assert results[0]["id"] == "func1"
        assert results[0]["metadata"]["name"] == "func1"

    def test_delete_by_id(self, chroma_store):
        chroma_store.delete_by_id("test_func")
        chroma_store.collection.delete.assert_called_with(ids=["test_func"])
