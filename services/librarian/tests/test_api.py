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

    def test_list_all_project_specs(self, client, mock_stores):
        """Test listing all project specs"""
        mock_stores['neo4j'].list_all_project_specs.return_value = [
            {'id': 'spec-1', 'name': 'MyApp', 'tech_stack': ['FastAPI'], 'features': ['auth']},
            {'id': 'spec-2', 'name': 'OtherApp', 'tech_stack': ['Django'], 'features': ['admin']},
        ]

        response = client.get("/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["name"] == "MyApp"
        assert data[1]["name"] == "OtherApp"
        mock_stores['neo4j'].list_all_project_specs.assert_called_once()

    def test_list_all_project_specs_empty(self, client, mock_stores):
        """Test listing when no projects exist"""
        mock_stores['neo4j'].list_all_project_specs.return_value = []

        response = client.get("/projects")
        assert response.status_code == 200
        assert response.json() == []
        mock_stores['neo4j'].list_all_project_specs.assert_called_once()


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

    def test_create_task(self, client, mock_stores):
        """Test creating a new task"""
        mock_stores['neo4j'].create_task.return_value = {
            'task_id': 'task-002',
            'title': 'New task',
            'status': 'PENDING',
            'dependencies': [],
            'contract': {},
            'tool_id': None
        }
        mock_stores['neo4j'].create_dependency_relationship.return_value = True

        response = client.post("/tasks", json={
            "task_id": "task-002",
            "title": "New task",
            "status": "PENDING"
        })
        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "task-002"
        assert data["title"] == "New task"

    def test_create_task_with_dependencies(self, client, mock_stores):
        """Test creating a task with dependencies"""
        mock_stores['neo4j'].create_task.return_value = {
            'task_id': 'task-003',
            'title': 'Dependent task',
            'status': 'PENDING',
            'dependencies': ['task-001', 'task-002'],
            'contract': {},
            'tool_id': None
        }
        mock_stores['neo4j'].create_dependency_relationship.return_value = True

        response = client.post("/tasks", json={
            "task_id": "task-003",
            "title": "Dependent task",
            "dependencies": ["task-001", "task-002"]
        })
        assert response.status_code == 201
        # Verify dependency relationship was called
        assert mock_stores['neo4j'].create_dependency_relationship.call_count == 2

    def test_create_tasks_batch(self, client, mock_stores):
        """Test creating multiple tasks in batch"""
        mock_stores['neo4j'].create_task.side_effect = [
            {'task_id': 'batch-001', 'title': 'Batch task 1', 'status': 'PENDING', 'dependencies': [], 'contract': {}, 'tool_id': None},
            {'task_id': 'batch-002', 'title': 'Batch task 2', 'status': 'PENDING', 'dependencies': ['batch-001'], 'contract': {}, 'tool_id': None}
        ]
        mock_stores['neo4j'].create_dependency_relationship.return_value = True

        response = client.post("/tasks/batch", json=[
            {"task_id": "batch-001", "title": "Batch task 1"},
            {"task_id": "batch-002", "title": "Batch task 2", "dependencies": ["batch-001"]}
        ])
        assert response.status_code == 201
        data = response.json()
        assert data["count"] == 2
        assert len(data["tasks"]) == 2


class TestToolEndpoints:
    """Tests for Tool rotation endpoints"""

    def test_get_least_used_tool(self, client, mock_stores):
        """Test getting the least used healthy tool"""
        mock_stores['neo4j'].get_least_used_tool.return_value = {
            'name': 'qwen-coder',
            'usage_count': 10
        }

        response = client.get("/tools/least-used")
        assert response.status_code == 200
        assert response.json()["name"] == "qwen-coder"

    def test_get_least_used_tool_not_found(self, client, mock_stores):
        """Test 404 when no healthy tools available"""
        mock_stores['neo4j'].get_least_used_tool.return_value = None

        response = client.get("/tools/least-used")
        assert response.status_code == 404

    def test_increment_tool_usage(self, client, mock_stores):
        """Test incrementing tool usage counters"""
        mock_stores['neo4j'].increment_tool_usage.return_value = {
            'name': 'qwen-coder',
            'usage_count': 11
        }

        response = client.post("/tools/qwen-coder/increment")
        assert response.status_code == 200

    def test_increment_tool_not_found(self, client, mock_stores):
        """Test 404 when tool doesn't exist"""
        mock_stores['neo4j'].increment_tool_usage.return_value = None

        response = client.post("/tools/non-existent/increment")
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
