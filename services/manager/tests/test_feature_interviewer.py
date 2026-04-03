import pytest
import sys
import os
import json
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from services.manager.feature_interviewer import FeatureInterviewer


class TestFeatureInterviewerInit:
    def test_initializes_with_default_url(self):
        interviewer = FeatureInterviewer()
        assert interviewer.librarian_url == "http://localhost:8001"
        assert interviewer.responses == []
        assert interviewer.code_context is None
        assert interviewer.selected_project is None

    def test_accepts_custom_librarian_url(self):
        interviewer = FeatureInterviewer(librarian_url="http://custom:9001")
        assert interviewer.librarian_url == "http://custom:9001"


class TestFeatureInterviewerListProjects:
    def test_list_projects_returns_projects(self, mocker):
        """list_projects fetches from Librarian and returns list."""
        mock_response = mocker.Mock(status_code=200)
        mock_response.json.return_value = [
            {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI"], "features": ["auth"]},
        ]
        mocker.patch("requests.get", return_value=mock_response)

        interviewer = FeatureInterviewer()
        projects = interviewer.list_projects()

        assert len(projects) == 1
        assert projects[0]["name"] == "MyApp"

    def test_list_projects_handles_connection_error(self, mocker):
        """list_projects returns empty list when Librarian is unreachable."""
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        interviewer = FeatureInterviewer()
        projects = interviewer.list_projects()

        assert projects == []

    def test_list_projects_handles_empty_response(self, mocker):
        """list_projects returns empty list when no projects exist."""
        mock_response = mocker.Mock(status_code=200)
        mock_response.json.return_value = []
        mocker.patch("requests.get", return_value=mock_response)

        interviewer = FeatureInterviewer()
        projects = interviewer.list_projects()

        assert projects == []


class TestFeatureInterviewerLoadContext:
    def test_load_project_context_when_available(self, mocker):
        """load_project_context loads code overview for the selected project."""
        mock_ctx = mocker.Mock()
        mock_ctx.get_project_overview.return_value = {
            "project_name": "MyApp",
            "total_files": 5,
            "total_functions": 12,
            "total_classes": 3,
            "files": [],
            "functions": [],
            "classes": [],
        }
        mocker.patch("services.manager.feature_interviewer.ProjectCodeContext", return_value=mock_ctx)

        interviewer = FeatureInterviewer()
        interviewer.load_project_context("MyApp")

        assert interviewer.code_context is not None
        mock_ctx.get_project_overview.assert_called_once_with("MyApp")

    def test_load_project_context_handles_connection_error(self, mocker):
        """load_project_context handles gracefully when Librarian is unreachable."""
        mocker.patch("services.manager.feature_interviewer.ProjectCodeContext", side_effect=Exception("Connection refused"))

        interviewer = FeatureInterviewer()
        interviewer.load_project_context("MyApp")

        assert interviewer.code_context is None

    def test_load_project_context_handles_missing_project(self, mocker):
        """load_project_context handles when project has no code in DB."""
        mock_ctx = mocker.Mock()
        mock_ctx.get_project_overview.return_value = None
        mocker.patch("services.manager.feature_interviewer.ProjectCodeContext", return_value=mock_ctx)

        interviewer = FeatureInterviewer()
        interviewer.load_project_context("MyApp")

        # code_context is set but overview is None
        assert interviewer.code_context is not None
        mock_ctx.get_project_overview.assert_called_once_with("MyApp")


class TestFeatureInterviewerGenerateQuestions:
    def test_generate_questions_returns_ready_when_clear(self, mocker):
        """generate_questions returns None when LLM says READY."""
        mock_llm = mocker.Mock()
        mock_llm.invoke.return_value = "READY"

        interviewer = FeatureInterviewer(llm_client=mock_llm)
        result = interviewer.generate_questions("Add user auth", "5 files, 12 functions")

        assert result is None

    def test_generate_questions_returns_questions_when_needed(self, mocker):
        """generate_questions returns list of questions when LLM asks for clarification."""
        mock_llm = mocker.Mock()
        mock_llm.invoke.return_value = json.dumps([
            "What authentication method do you want? (JWT, session, OAuth)",
            "Should it integrate with the existing UserService class?"
        ])

        interviewer = FeatureInterviewer(llm_client=mock_llm)
        result = interviewer.generate_questions("Add user auth", "5 files, 12 functions")

        assert isinstance(result, list)
        assert len(result) == 2
        assert "authentication method" in result[0].lower()

    def test_generate_questions_includes_previous_qa(self, mocker):
        """generate_questions includes previous Q&A in the prompt."""
        mock_llm = mocker.Mock()
        mock_llm.invoke.return_value = json.dumps(["What about rate limiting?"])

        interviewer = FeatureInterviewer(llm_client=mock_llm)
        interviewer.responses = [
            {"question": "What auth method?", "answer": "JWT"},
        ]
        result = interviewer.generate_questions("Add user auth", "5 files")

        assert isinstance(result, list)
        # Verify the prompt actually contains the previous Q&A
        call_args = mock_llm.invoke.call_args[0][0]
        assert "Q: What auth method?" in call_args
        assert "A: JWT" in call_args

    def test_generate_questions_handles_llm_error(self, mocker):
        """generate_questions returns None when LLM call fails."""
        mock_llm = mocker.Mock()
        mock_llm.invoke.side_effect = Exception("LLM API timeout")

        interviewer = FeatureInterviewer(llm_client=mock_llm)
        result = interviewer.generate_questions("Add user auth", "5 files")

        assert result is None

    def test_generate_questions_without_llm(self):
        """generate_questions works without LLM (returns None = ready)."""
        interviewer = FeatureInterviewer()
        result = interviewer.generate_questions("Add user auth", "5 files")
        # Without LLM, should return None (ready to build spec)
        assert result is None


class TestFeatureInterviewerRecordResponse:
    def test_record_response(self):
        """record_response stores question and answer."""
        interviewer = FeatureInterviewer()
        interviewer.record_response("What auth method?", "JWT")

        assert len(interviewer.responses) == 1
        assert interviewer.responses[0]["question"] == "What auth method?"
        assert interviewer.responses[0]["answer"] == "JWT"


class TestFeatureInterviewerBuildSpec:
    def test_build_spec_creates_spec_with_parent_project(self):
        """build_spec creates a ProjectSpec dict with parent_project reference."""
        interviewer = FeatureInterviewer()
        interviewer.selected_project = {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI", "React"], "features": ["auth"]}

        spec = interviewer.build_spec("Add user registration")

        assert "myapp" in spec["name"].lower()
        assert spec["parent_project"] == "spec-1"
        assert "user registration" in spec["features"][0].lower()
        assert "FastAPI" in spec["tech_stack"]
        assert "React" in spec["tech_stack"]

    def test_build_spec_includes_interview_responses(self):
        """build_spec includes interview responses as constraints."""
        interviewer = FeatureInterviewer()
        interviewer.selected_project = {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI"], "features": []}
        interviewer.responses = [
            {"question": "What about rate limiting?", "answer": "Use Redis"},
        ]

        spec = interviewer.build_spec("Add API endpoint")

        assert len(spec["constraints"]) > 0
        assert any("Redis" in c for c in spec["constraints"])

    def test_build_spec_handles_missing_project(self):
        """build_spec works even if selected_project is None."""
        interviewer = FeatureInterviewer()
        interviewer.selected_project = None

        spec = interviewer.build_spec("Standalone feature")

        assert spec["name"] == "standalone-feature"
        assert spec["parent_project"] is None
        assert spec["tech_stack"] == []
