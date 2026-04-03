import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


class TestCodeQueryEndpoints:

    @pytest.fixture
    def client(self):
        with patch('services.librarian.app.get_neo4j_store') as mock_get_neo4j, \
             patch('services.librarian.app.get_chroma_store') as mock_get_chroma:
            mock_neo4j = MagicMock()
            mock_chroma = MagicMock()
            mock_get_neo4j.return_value = mock_neo4j
            mock_get_chroma.return_value = mock_chroma
            mock_neo4j.search_code.return_value = []
            mock_neo4j.search_functions.return_value = []
            mock_neo4j.get_function_by_name.return_value = None
            mock_neo4j.get_callers.return_value = []
            mock_neo4j.get_callees.return_value = []
            mock_neo4j.get_full_context.return_value = {}
            mock_neo4j.driver = MagicMock()
            mock_session = MagicMock()
            mock_session.__enter__ = MagicMock(return_value=mock_session)
            mock_session.__exit__ = MagicMock(return_value=False)
            mock_session.run.return_value.single.return_value = None
            mock_neo4j.driver.session.return_value = mock_session
            mock_chroma.search_code.return_value = []
            from services.librarian.app import app
            yield TestClient(app)

    def test_search_code_endpoint(self, client):
        response = client.get("/code/search?q=login&type=function")
        assert response.status_code == 200
        assert "results" in response.json()

    def test_get_function_by_name(self, client):
        response = client.get("/code/function/login")
        assert response.status_code in [200, 404]

    def test_get_function_callers(self, client):
        response = client.get("/code/function/login/callers")
        assert response.status_code == 200

    def test_get_function_callees(self, client):
        response = client.get("/code/function/login/callees")
        assert response.status_code == 200

    def test_get_full_context(self, client):
        response = client.get("/code/function/login/full-context")
        assert response.status_code in [200, 404]

    def test_get_class_by_name(self, client):
        response = client.get("/code/class/AuthService")
        assert response.status_code in [200, 404]

    def test_get_file_content(self, client):
        response = client.get("/code/file/services/librarian/app.py")
        assert response.status_code in [200, 404]
