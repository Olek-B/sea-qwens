import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens/worktrees/legion-implement')
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
