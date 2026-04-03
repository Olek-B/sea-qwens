import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')


class TestPostIndexer:

    @pytest.fixture
    def client(self):
        with patch('services.librarian.app.get_neo4j_store') as mock_get_neo4j, \
             patch('services.librarian.app.get_chroma_store') as mock_get_chroma:
            mock_neo4j = MagicMock()
            mock_chroma = MagicMock()
            mock_get_neo4j.return_value = mock_neo4j
            mock_get_chroma.return_value = mock_chroma
            mock_neo4j.driver = MagicMock()
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value.single.return_value = None
            mock_neo4j.driver.session.return_value = mock_session
            mock_chroma.search_code.return_value = []
            from services.librarian.app import app
            yield TestClient(app)

    def test_index_updated_endpoint(self, client):
        response = client.post("/index/updated", json={
            "files": [
                {"path": "services/librarian/app.py", "content": "from fastapi import FastAPI\napp = FastAPI()"}
            ]
        })
        assert response.status_code == 200
        assert "indexed" in response.json()

    def test_index_updated_empty_files(self, client):
        response = client.post("/index/updated", json={"files": []})
        assert response.status_code == 200
