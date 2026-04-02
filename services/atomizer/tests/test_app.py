import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


@pytest.fixture
def mock_atomizer_instance():
    """Create a mock Atomizer instance"""
    mock_instance = MagicMock()
    return mock_instance


@pytest.fixture
def app_with_mock_atomizer(mock_atomizer_instance):
    """Create app with mocked atomizer"""
    with patch('services.atomizer.app.Atomizer') as MockAtomizer:
        MockAtomizer.return_value = mock_atomizer_instance
        
        # Import app after mocking - this ensures the module-level atomizer uses our mock
        from services.atomizer.app import app
        
        # Also patch the module-level atomizer instance
        with patch('services.atomizer.app.atomizer', mock_atomizer_instance):
            yield app


@pytest.fixture
def client(app_with_mock_atomizer):
    """Create test client with mocked atomizer"""
    return TestClient(app_with_mock_atomizer)


class TestDecomposeEndpoint:
    """Tests for /decompose POST endpoint"""

    def test_decompose_with_project_spec(self, client, mock_atomizer_instance):
        """Test decomposing a project using direct project_spec"""
        # Setup mock
        mock_atomizer_instance.decompose.return_value = [
            {"task_id": "task-1", "title": "Setup project", "status": "PENDING"},
            {"task_id": "task-2", "title": "Implement feature", "status": "PENDING"}
        ]

        response = client.post("/decompose", json={
            "project_spec": {
                "name": "Test API",
                "tech_stack": ["FastAPI"],
                "features": ["Test feature"]
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "count" in data
        assert data["count"] == 2
        assert len(data["tasks"]) == 2

    def test_decompose_with_spec_id(self, client, mock_atomizer_instance):
        """Test decomposing using spec_id fetched from Librarian"""
        # Setup mocks
        mock_atomizer_instance.fetch_project_spec.return_value = {
            "id": "spec-123",
            "name": "Fetched API",
            "tech_stack": ["FastAPI"],
            "features": ["Feature 1"]
        }
        mock_atomizer_instance.decompose.return_value = [
            {"task_id": "task-1", "title": "Setup", "status": "PENDING"}
        ]

        response = client.post("/decompose", json={
            "spec_id": "spec-123"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        mock_atomizer_instance.fetch_project_spec.assert_called_once_with("spec-123")

    def test_decompose_no_input(self, client, mock_atomizer_instance):
        """Test 400 when neither spec_id nor project_spec provided"""
        response = client.post("/decompose", json={})
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_decompose_fetch_error(self, client, mock_atomizer_instance):
        """Test 500 when fetching project spec fails"""
        mock_atomizer_instance.fetch_project_spec.side_effect = Exception("Connection failed")

        response = client.post("/decompose", json={
            "spec_id": "non-existent"
        })
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data

    def test_decompose_empty_features(self, client, mock_atomizer_instance):
        """Test decomposing project with empty features"""
        mock_atomizer_instance.decompose.return_value = [
            {"task_id": "task-1", "title": "Setup project", "status": "PENDING"}
        ]

        response = client.post("/decompose", json={
            "project_spec": {
                "name": "Empty Project",
                "tech_stack": [],
                "features": []
            }
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 0


class TestHealthEndpoint:
    """Tests for /health GET endpoint"""

    def test_health_check(self, client, mock_atomizer_instance):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "atomizer"
