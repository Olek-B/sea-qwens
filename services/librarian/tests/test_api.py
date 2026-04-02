import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))


@pytest.fixture
def mock_stores():
    """Mock Neo4j and Chroma stores for unit testing"""
    with patch('services.librarian.app.get_neo4j_store') as mock_neo4j_getter, \
         patch('services.librarian.app.get_chroma_store') as mock_chroma_getter:
        
        # Create mock instances
        mock_neo4j = MagicMock()
        mock_chroma = MagicMock()
        
        mock_neo4j_getter.return_value = mock_neo4j
        mock_chroma_getter.return_value = mock_chroma
        
        # Import app after mocking
        from services.librarian.app import app
        
        yield {
            'neo4j': mock_neo4j,
            'chroma': mock_chroma,
            'app': app
        }


@pytest.fixture
def client(mock_stores):
    """Create test client with mocked stores"""
    return TestClient(mock_stores['app'])


class TestProjectSpecEndpoints:
    """Tests for ProjectSpec CRUD endpoints"""

    def test_create_project_spec(self, client, mock_stores):
        """Test creating a new project spec"""
        # Setup mock
        mock_stores['neo4j'].create_project_spec.return_value = {
            'id': 'test-id-123',
            'name': 'Test API',
            'tech_stack': ['FastAPI', 'Neo4j'],
            'features': ['REST API']
        }
        
        response = client.post("/project-specs", json={
            "name": "Test API",
            "tech_stack": ["FastAPI", "Neo4j"],
            "features": ["REST API"]
        })
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test API"
        assert "id" in data
        assert data["id"] == 'test-id-123'

    def test_get_project_spec(self, client, mock_stores):
        """Test retrieving a project spec by ID"""
        # Setup mock
        mock_stores['neo4j'].get_project_spec.return_value = {
            'id': 'test-id-456',
            'name': 'Get Test',
            'tech_stack': ['FastAPI'],
            'features': ['Test']
        }
        
        response = client.get("/project-specs/test-id-456")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test"

    def test_get_project_spec_not_found(self, client, mock_stores):
        """Test 404 when retrieving non-existent project spec"""
        mock_stores['neo4j'].get_project_spec.return_value = None
        
        response = client.get("/project-specs/non-existent-id")
        assert response.status_code == 404


class TestTaskEndpoints:
    """Tests for Task management endpoints"""

    def test_update_task_status(self, client, mock_stores):
        """Test updating a task status"""
        mock_stores['neo4j'].update_task_status.return_value = {
            'task_id': 'task-001',
            'status': 'IN_PROGRESS'
        }
        
        response = client.post("/tasks/update?task_id=task-001", json={
            "status": "IN_PROGRESS",
            "metadata": {"started_at": "2026-04-03T10:00:00Z"}
        })
        assert response.status_code == 200

    def test_update_task_not_found(self, client, mock_stores):
        """Test 404 when updating non-existent task"""
        mock_stores['neo4j'].update_task_status.return_value = None
        
        response = client.post("/tasks/update?task_id=non-existent", json={
            "status": "IN_PROGRESS"
        })
        assert response.status_code == 404

    def test_get_ready_tasks(self, client, mock_stores):
        """Test getting tasks ready for execution"""
        mock_stores['neo4j'].get_ready_tasks.return_value = [
            {'task_id': 'task-001', 'title': 'Test task'}
        ]
        
        response = client.get("/tasks/ready")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 1


class TestProfileEndpoints:
    """Tests for Profile rotation endpoints"""

    def test_get_least_used_profile(self, client, mock_stores):
        """Test getting the least used healthy profile"""
        mock_stores['neo4j'].get_least_used_profile.return_value = {
            'name': 'qwen-agent-01',
            'usage_count': 10
        }
        
        response = client.get("/profiles/least-used")
        assert response.status_code == 200
        assert response.json()["name"] == "qwen-agent-01"

    def test_get_least_used_profile_not_found(self, client, mock_stores):
        """Test 404 when no healthy profiles available"""
        mock_stores['neo4j'].get_least_used_profile.return_value = None
        
        response = client.get("/profiles/least-used")
        assert response.status_code == 404

    def test_increment_profile_usage(self, client, mock_stores):
        """Test incrementing profile usage counters"""
        mock_stores['neo4j'].increment_profile_usage.return_value = {
            'name': 'test-profile',
            'usage_count': 11
        }
        
        response = client.post("/profiles/test-profile/increment")
        assert response.status_code == 200

    def test_increment_profile_not_found(self, client, mock_stores):
        """Test 404 when profile doesn't exist"""
        mock_stores['neo4j'].increment_profile_usage.return_value = None
        
        response = client.post("/profiles/non-existent/increment")
        assert response.status_code == 404


class TestIngestEndpoint:
    """Tests for document ingestion endpoint"""

    def test_ingest_document(self, client, mock_stores):
        """Test ingesting a document into ChromaDB"""
        mock_stores['chroma'].add_document.return_value = None
        
        response = client.post("/ingest", json={
            "uid": "test-doc-001",
            "content": "This is test content for vector embedding",
            "metadata": {"type": "code", "language": "python"}
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["uid"] == "test-doc-001"
