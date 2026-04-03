import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens-dev')
from services.manager.interviewer import Interviewer, InterviewQuestion


def test_interviewer_initializes():
    interviewer = Interviewer()
    assert interviewer.questions_asked == 0
    assert interviewer.responses == []


def test_interviewer_first_question():
    interviewer = Interviewer()
    question = interviewer.get_next_question()
    assert "project" in question.text.lower()
    assert question.category == "overview"


def test_interviewer_records_response():
    interviewer = Interviewer()
    interviewer.record_response("My project is a REST API", "overview")
    assert len(interviewer.responses) == 1
    assert interviewer.questions_asked == 1


def test_interviewer_is_complete():
    interviewer = Interviewer()
    # Not complete at start
    assert not interviewer.is_complete()
    
    # Simulate going through all questions
    for _ in range(len(interviewer.QUESTIONS)):
        interviewer.get_next_question()
        interviewer.record_response("test", "test")
    
    # Should be complete after all questions
    assert interviewer.is_complete()


def test_interviewer_extract_project_spec():
    interviewer = Interviewer()
    
    # Record responses for each category
    interviewer.record_response("TestAPI", "overview")
    interviewer.record_response("A REST API for testing", "overview")
    interviewer.record_response("FastAPI, PostgreSQL", "tech_stack")
    interviewer.record_response("User auth, Health endpoint", "features")
    interviewer.record_response("Must be async", "constraints")
    
    spec = interviewer.extract_project_spec()
    
    assert spec["name"] == "TestAPI"
    assert "FastAPI" in spec["tech_stack"]
    assert "PostgreSQL" in spec["tech_stack"]
    assert "User auth" in spec["features"]
    assert "Health endpoint" in spec["features"]


def test_interviewer_get_next_question_returns_none_when_complete():
    interviewer = Interviewer()
    
    # Exhaust all questions
    for _ in range(len(interviewer.QUESTIONS) + 1):
        question = interviewer.get_next_question()
        if question:
            interviewer.record_response("test", "test")
    
    # Should return None when complete
    assert interviewer.get_next_question() is None


class TestInterviewerCodeContext:
    """Tests for Interviewer's code context integration."""

    def test_load_code_context_when_available(self, mocker):
        """Interviewer loads code context if project exists in code DB."""
        mock_ctx = mocker.Mock()
        mock_ctx.get_project_overview.return_value = {
            "project_name": "TestAPI",
            "total_files": 5,
            "total_functions": 12,
            "total_classes": 3,
            "files": [],
            "functions": [],
            "classes": [],
        }
        mock_ctx.find_existing_features.return_value = {
            "auth": {"found": True, "matches": [{"name": "AuthService", "type": "class"}]}
        }

        mocker.patch("services.manager.interviewer.ProjectCodeContext", return_value=mock_ctx)

        interviewer = Interviewer()
        interviewer.load_code_context("TestAPI", ["auth", "database"])

        assert interviewer.code_context is not None
        assert interviewer.code_context.get_project_overview.called

    def test_load_code_context_handles_missing_project(self, mocker):
        """Interviewer handles gracefully when project not in code DB."""
        mock_ctx = mocker.Mock()
        mock_ctx.get_project_overview.return_value = None

        mocker.patch("services.manager.interviewer.ProjectCodeContext", return_value=mock_ctx)

        interviewer = Interviewer()
        interviewer.load_code_context("NewProject", ["auth"])

        # Should not raise, code_context should be set but empty
        assert interviewer.code_context is not None

    def test_load_code_context_handles_connection_error(self, mocker):
        """Interviewer handles gracefully when Librarian is unreachable."""
        mocker.patch("services.manager.interviewer.ProjectCodeContext", side_effect=Exception("Connection refused"))

        interviewer = Interviewer()
        interviewer.load_code_context("TestAPI", ["auth"])

        # Should not raise
        assert interviewer.code_context is None

    def test_interviewer_has_code_context_attribute(self):
        """Interviewer initializes with code_context as None."""
        interviewer = Interviewer()
        assert interviewer.code_context is None
        assert interviewer.librarian_url == "http://localhost:8001"

    def test_interviewer_accepts_custom_librarian_url(self):
        """Interviewer accepts custom librarian URL."""
        interviewer = Interviewer(librarian_url="http://custom:9001")
        assert interviewer.librarian_url == "http://custom:9001"
