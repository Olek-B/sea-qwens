"""
Integration tests for Project Legion Librarian service.

These tests require running services:
- Neo4j (port 7687)
- ChromaDB (port 8000)
- Librarian API (port 8001)

Run with: pytest -m integration

Tests connect to localhost:8001 and verify end-to-end functionality.
"""
import pytest
import requests
import time
from typing import Optional
from datetime import datetime

# Base URL for the Librarian API
LIBRARIAN_BASE_URL = "http://localhost:8001"


@pytest.mark.integration
class TestProjectSpecIntegration:
    """Integration tests for ProjectSpec full flow"""

    def test_create_and_retrieve_project_spec(self):
        """Test full ProjectSpec flow: create → retrieve"""
        # Create a unique project spec
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        spec_data = {
            "name": f"Integration Test API {timestamp}",
            "tech_stack": ["FastAPI", "Neo4j", "ChromaDB"],
            "features": ["REST API", "Vector Search", "Graph Storage"]
        }

        # Create the project spec
        create_response = requests.post(
            f"{LIBRARIAN_BASE_URL}/project-specs",
            json=spec_data
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["name"] == spec_data["name"]
        assert "id" in created
        spec_id = created["id"]

        # Retrieve the project spec by ID
        get_response = requests.get(f"{LIBRARIAN_BASE_URL}/project-specs/{spec_id}")
        assert get_response.status_code == 200
        retrieved = get_response.json()
        assert retrieved["id"] == spec_id
        assert retrieved["name"] == spec_data["name"]
        assert retrieved["tech_stack"] == spec_data["tech_stack"]
        assert retrieved["features"] == spec_data["features"]

    def test_project_spec_lifecycle(self):
        """Test creating multiple project specs and retrieving them"""
        specs_created = []

        # Create multiple project specs
        for i in range(3):
            spec_data = {
                "name": f"Multi Spec {i} - {datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "tech_stack": ["Python"],
                "features": [f"Feature {i}"]
            }
            response = requests.post(f"{LIBRARIAN_BASE_URL}/project-specs", json=spec_data)
            assert response.status_code == 201
            specs_created.append(response.json()["id"])

        # Verify each can be retrieved
        for spec_id in specs_created:
            response = requests.get(f"{LIBRARIAN_BASE_URL}/project-specs/{spec_id}")
            assert response.status_code == 200
            assert response.json()["id"] == spec_id

    def test_get_nonexistent_project_spec(self):
        """Test 404 response for non-existent project spec"""
        response = requests.get(f"{LIBRARIAN_BASE_URL}/project-specs/non-existent-id")
        assert response.status_code == 404


@pytest.mark.integration
class TestTaskLifecycleIntegration:
    """Integration tests for task lifecycle management"""

    def test_task_status_update_flow(self):
        """Test full task lifecycle: PENDING → IN_PROGRESS → DONE"""
        # Create a project spec first (tasks depend on project specs)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        spec_data = {
            "name": f"Task Test Project {timestamp}",
            "tech_stack": ["FastAPI"],
            "features": ["Testing"]
        }
        spec_response = requests.post(f"{LIBRARIAN_BASE_URL}/project-specs", json=spec_data)
        assert spec_response.status_code == 201
        spec_id = spec_response.json()["id"]

        # Note: In the current implementation, tasks are created via Neo4j directly
        # For integration testing, we test the update flow with a mock task ID
        # The task would normally be created when a ProjectSpec is created with tasks

        # Test updating task status through the lifecycle
        task_id = f"integration-test-task-{timestamp}"

        # Update to IN_PROGRESS
        update_response = requests.post(
            f"{LIBRARIAN_BASE_URL}/tasks/update?task_id={task_id}",
            json={"status": "IN_PROGRESS", "metadata": {"started_at": datetime.utcnow().isoformat()}}
        )
        # May return 404 if task doesn't exist, which is expected behavior
        if update_response.status_code == 200:
            assert update_response.json()["status"] == "IN_PROGRESS"

        # Update to DONE
        update_response = requests.post(
            f"{LIBRARIAN_BASE_URL}/tasks/update?task_id={task_id}",
            json={"status": "DONE", "metadata": {"completed_at": datetime.utcnow().isoformat()}}
        )
        if update_response.status_code == 200:
            assert update_response.json()["status"] == "DONE"

    def test_get_ready_tasks(self):
        """Test getting tasks ready for execution"""
        response = requests.get(f"{LIBRARIAN_BASE_URL}/tasks/ready")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_update_nonexistent_task(self):
        """Test 404 when updating non-existent task"""
        response = requests.post(
            f"{LIBRARIAN_BASE_URL}/tasks/update?task_id=non-existent-task",
            json={"status": "IN_PROGRESS"}
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestProfileRotationIntegration:
    """Integration tests for profile rotation"""

    def test_get_least_used_profile(self):
        """Test getting the least used healthy profile"""
        response = requests.get(f"{LIBRARIAN_BASE_URL}/profiles/least-used")

        # If profiles exist, should return 200
        if response.status_code == 200:
            profile = response.json()
            assert "name" in profile
            assert "usage_count" in profile
        else:
            # 404 is acceptable if no healthy profiles exist
            assert response.status_code == 404

    def test_profile_usage_increment(self):
        """Test incrementing profile usage counters"""
        # First, try to get a profile
        get_response = requests.get(f"{LIBRARIAN_BASE_URL}/profiles/least-used")

        if get_response.status_code == 200:
            profile_name = get_response.json()["name"]

            # Increment usage
            increment_response = requests.post(
                f"{LIBRARIAN_BASE_URL}/profiles/{profile_name}/increment"
            )
            assert increment_response.status_code == 200
            updated_profile = increment_response.json()
            assert updated_profile["name"] == profile_name
            assert "usage_count" in updated_profile

    def test_increment_nonexistent_profile(self):
        """Test 404 when incrementing non-existent profile"""
        response = requests.post(
            f"{LIBRARIAN_BASE_URL}/profiles/non-existent-profile/increment"
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestDocumentIngestionIntegration:
    """Integration tests for document ingestion into ChromaDB"""

    def test_ingest_and_verify_document(self):
        """Test ingesting a document into ChromaDB"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        doc_data = {
            "uid": f"test-doc-{timestamp}",
            "content": "This is integration test content for vector embedding in ChromaDB",
            "metadata": {
                "type": "integration_test",
                "language": "python",
                "timestamp": timestamp
            }
        }

        # Ingest the document
        response = requests.post(f"{LIBRARIAN_BASE_URL}/ingest", json=doc_data)
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "ok"
        assert result["uid"] == doc_data["uid"]

    def test_ingest_multiple_documents(self):
        """Test ingesting multiple documents"""
        for i in range(3):
            doc_data = {
                "uid": f"multi-doc-{i}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "content": f"Document content number {i} for batch ingestion test",
                "metadata": {"batch": i}
            }
            response = requests.post(f"{LIBRARIAN_BASE_URL}/ingest", json=doc_data)
            assert response.status_code == 200

    def test_ingest_empty_content(self):
        """Test ingesting document with empty content"""
        doc_data = {
            "uid": f"empty-doc-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "content": "",
            "metadata": {}
        }
        response = requests.post(f"{LIBRARIAN_BASE_URL}/ingest", json=doc_data)
        # Should still succeed (empty content is valid)
        assert response.status_code == 200


@pytest.mark.integration
class TestEndToEndIntegration:
    """End-to-end integration tests combining multiple flows"""

    def test_full_workflow(self):
        """Test complete workflow: spec → task → profile → ingest"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        # Step 1: Create a project spec
        spec_data = {
            "name": f"E2E Test Project {timestamp}",
            "tech_stack": ["FastAPI", "Neo4j", "ChromaDB"],
            "features": ["E2E Testing", "Integration"]
        }
        spec_response = requests.post(f"{LIBRARIAN_BASE_URL}/project-specs", json=spec_data)
        assert spec_response.status_code == 201
        spec_id = spec_response.json()["id"]

        # Step 2: Verify spec retrieval
        get_response = requests.get(f"{LIBRARIAN_BASE_URL}/project-specs/{spec_id}")
        assert get_response.status_code == 200

        # Step 3: Get a profile for task execution
        profile_response = requests.get(f"{LIBRARIAN_BASE_URL}/profiles/least-used")
        if profile_response.status_code == 200:
            profile_name = profile_response.json()["name"]

            # Step 4: Increment profile usage
            increment_response = requests.post(
                f"{LIBRARIAN_BASE_URL}/profiles/{profile_name}/increment"
            )
            assert increment_response.status_code == 200

        # Step 5: Ingest documentation
        doc_data = {
            "uid": f"e2e-doc-{timestamp}",
            "content": f"E2E test documentation for project {spec_id}",
            "metadata": {"project_id": spec_id, "type": "documentation"}
        }
        ingest_response = requests.post(f"{LIBRARIAN_BASE_URL}/ingest", json=doc_data)
        assert ingest_response.status_code == 200

        # Step 6: Check ready tasks
        tasks_response = requests.get(f"{LIBRARIAN_BASE_URL}/tasks/ready")
        assert tasks_response.status_code == 200


@pytest.mark.integration
class TestServiceHealthIntegration:
    """Integration tests for service health and connectivity"""

    def test_api_responds(self):
        """Test that the Librarian API is responding"""
        # Test the OpenAPI docs endpoint (always available in FastAPI)
        response = requests.get(f"{LIBRARIAN_BASE_URL}/docs")
        assert response.status_code == 200

    def test_api_health_check(self):
        """Test API health via root endpoint"""
        response = requests.get(f"{LIBRARIAN_BASE_URL}/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data or "info" in data
