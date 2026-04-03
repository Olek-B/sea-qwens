import pytest
import sys
import os
import uuid

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from services.atomizer.decomposer import Atomizer, generate_task_id


class TestGenerateTaskId:
    """Tests for generate_task_id function"""

    def test_generates_unique_id(self):
        """Test that generate_task_id creates a unique identifier"""
        task_id = generate_task_id()
        assert task_id is not None
        assert len(task_id) > 0

    def test_generates_different_ids(self):
        """Test that multiple calls generate different IDs"""
        id1 = generate_task_id()
        id2 = generate_task_id()
        assert id1 != id2

    def test_id_format(self):
        """Test that generated ID has expected format"""
        task_id = generate_task_id()
        # Should be a valid UUID format
        uuid.UUID(task_id)  # Should not raise


class TestAtomizerDecompose:
    """Tests for Atomizer.decompose method"""

    def test_decompose_returns_tasks_list(self):
        """Test that decompose returns a list of tasks"""
        atomizer = Atomizer()
        project_spec = {
            "name": "Test API",
            "tech_stack": ["FastAPI", "PostgreSQL"],
            "features": ["User auth", "Health endpoint"]
        }
        tasks = atomizer.decompose(project_spec)
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_decompose_tasks_have_required_fields(self):
        """Test that decomposed tasks have required fields"""
        atomizer = Atomizer()
        project_spec = {
            "name": "Test API",
            "tech_stack": ["FastAPI"],
            "features": ["REST API"]
        }
        tasks = atomizer.decompose(project_spec)
        
        for task in tasks:
            assert "task_id" in task
            assert "title" in task
            assert "status" in task
            assert "dependencies" in task

    def test_decompose_tasks_have_unique_ids(self):
        """Test that each task has a unique ID"""
        atomizer = Atomizer()
        project_spec = {
            "name": "Test API",
            "tech_stack": ["FastAPI"],
            "features": ["Feature 1", "Feature 2", "Feature 3"]
        }
        tasks = atomizer.decompose(project_spec)
        task_ids = [task["task_id"] for task in tasks]
        assert len(task_ids) == len(set(task_ids))

    def test_decompose_empty_spec(self):
        """Test decompose with empty project spec"""
        atomizer = Atomizer()
        project_spec = {"name": "", "tech_stack": [], "features": []}
        tasks = atomizer.decompose(project_spec)
        assert isinstance(tasks, list)


class TestAtomizerMockDecompose:
    """Tests for Atomizer._mock_decompose method"""

    def test_mock_decompose_returns_tasks(self):
        """Test that _mock_decompose returns task list"""
        atomizer = Atomizer()
        project_spec = {
            "name": "Mock Test",
            "tech_stack": ["FastAPI"],
            "features": ["Test feature"]
        }
        tasks = atomizer._mock_decompose(project_spec)
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_mock_decompose_includes_setup_task(self):
        """Test that mock decompose includes project setup task"""
        atomizer = Atomizer()
        project_spec = {
            "name": "Mock Test",
            "tech_stack": ["FastAPI", "PostgreSQL"],
            "features": ["Test feature"]
        }
        tasks = atomizer._mock_decompose(project_spec)
        task_titles = [task["title"].lower() for task in tasks]
        # Should have a setup/initialization task
        assert any("setup" in title or "project" in title for title in task_titles)

    def test_mock_decompose_includes_feature_tasks(self):
        """Test that mock decompose creates tasks for features"""
        atomizer = Atomizer()
        project_spec = {
            "name": "Mock Test",
            "tech_stack": ["FastAPI"],
            "features": ["User authentication", "Health endpoint"]
        }
        tasks = atomizer._mock_decompose(project_spec)
        task_titles = [task["title"].lower() for task in tasks]
        # Should have tasks related to features
        assert len(tasks) >= len(project_spec["features"])


class TestAtomizerFetchProjectSpec:
    """Tests for Atomizer.fetch_project_spec method"""

    def test_fetch_project_spec_success(self, requests_mock):
        """Test fetching project spec from Librarian"""
        atomizer = Atomizer(librarian_url="http://localhost:8001")
        
        mock_spec = {
            "id": "spec-123",
            "name": "Fetched API",
            "tech_stack": ["FastAPI"],
            "features": ["Test feature"]
        }
        requests_mock.get("http://localhost:8001/project-specs/spec-123", json=mock_spec)
        
        result = atomizer.fetch_project_spec("spec-123")
        assert result == mock_spec

    def test_fetch_project_spec_not_found(self, requests_mock):
        """Test fetching non-existent project spec"""
        atomizer = Atomizer(librarian_url="http://localhost:8001")
        requests_mock.get("http://localhost:8001/project-specs/non-existent", status_code=404)
        
        with pytest.raises(Exception) as exc_info:
            atomizer.fetch_project_spec("non-existent")
        assert "404" in str(exc_info.value)

    def test_fetch_project_spec_connection_error(self):
        """Test fetching project spec with connection error"""
        atomizer = Atomizer(librarian_url="http://localhost:9999")
        
        with pytest.raises(Exception):
            atomizer.fetch_project_spec("spec-123")


class TestAtomizerSaveTasks:
    """Tests for Atomizer.save_tasks method"""

    def test_save_tasks_to_file(self, tmp_path):
        """Test saving tasks to a JSON file"""
        atomizer = Atomizer()
        tasks = [
            {"task_id": "task-1", "title": "Task 1", "status": "PENDING"},
            {"task_id": "task-2", "title": "Task 2", "status": "PENDING"}
        ]
        
        output_file = tmp_path / "tasks.json"
        atomizer.save_tasks(tasks, str(output_file))
        
        assert output_file.exists()
        import json
        with open(output_file) as f:
            saved_tasks = json.load(f)
        assert saved_tasks == tasks

    def test_save_tasks_empty_list(self, tmp_path):
        """Test saving empty task list"""
        atomizer = Atomizer()
        output_file = tmp_path / "empty_tasks.json"
        atomizer.save_tasks([], str(output_file))

        assert output_file.exists()
        import json
        with open(output_file) as f:
            saved_tasks = json.load(f)
        assert saved_tasks == []


class TestAtomizerCodeContext:
    """Tests for Atomizer's code context integration."""

    def test_decompose_uses_code_context_when_available(self, mocker):
        """Decompose creates extend tasks for features that already exist."""
        mock_ctx = mocker.Mock()
        mock_ctx.get_project_overview.return_value = {
            "project_name": "TestAPI",
            "total_files": 3,
            "total_functions": 8,
            "total_classes": 2,
            "files": [],
            "functions": [],
            "classes": [],
        }
        mock_ctx.find_existing_features.return_value = {
            "User auth": {"found": True, "matches": [{"name": "AuthService", "type": "class"}]},
            "Health endpoint": {"found": False, "matches": []},
        }
        mocker.patch("services.atomizer.decomposer.ProjectCodeContext", return_value=mock_ctx)

        atomizer = Atomizer(librarian_url="http://localhost:8001")
        project_spec = {
            "name": "TestAPI",
            "tech_stack": ["FastAPI"],
            "features": ["User auth", "Health endpoint"]
        }
        tasks = atomizer.decompose(project_spec)

        # Should still return tasks
        assert isinstance(tasks, list)
        assert len(tasks) > 0

        # Find the User auth task - should be an extend task
        auth_tasks = [t for t in tasks if "User auth" in t["title"]]
        assert len(auth_tasks) > 0
        assert "Extend existing" in auth_tasks[0]["title"]
        assert auth_tasks[0]["contract"]["type"] == "extend_feature"

    def test_decompose_handles_missing_code_context_gracefully(self, mocker):
        """Decompose works when code context is unavailable."""
        mocker.patch("services.atomizer.decomposer.ProjectCodeContext", side_effect=Exception("Connection refused"))

        atomizer = Atomizer(librarian_url="http://localhost:8001")
        project_spec = {
            "name": "NewAPI",
            "tech_stack": ["FastAPI"],
            "features": ["User auth"]
        }
        tasks = atomizer.decompose(project_spec)

        # Should still work normally
        assert isinstance(tasks, list)
        assert len(tasks) > 0

    def test_decompose_creates_extend_feature_contract(self, mocker):
        """When feature exists, task contract includes existing_code reference."""
        mock_ctx = mocker.Mock()
        mock_ctx.get_project_overview.return_value = {"project_name": "X", "total_files": 1, "total_functions": 1, "total_classes": 0, "files": [], "functions": [], "classes": []}
        mock_ctx.find_existing_features.return_value = {
            "auth": {"found": True, "matches": [{"name": "AuthService", "type": "class"}]}
        }
        mocker.patch("services.atomizer.decomposer.ProjectCodeContext", return_value=mock_ctx)

        atomizer = Atomizer()
        tasks = atomizer.decompose({"name": "X", "tech_stack": [], "features": ["auth"]})

        feature_tasks = [t for t in tasks if t["contract"].get("type") == "extend_feature"]
        assert len(feature_tasks) == 1
        assert feature_tasks[0]["contract"]["existing_code"] == [{"name": "AuthService", "type": "class"}]
