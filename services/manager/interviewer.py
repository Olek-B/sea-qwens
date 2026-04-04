from pydantic import BaseModel
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)

try:
    from shared.code_query_tools import ProjectCodeContext, CodeQueryTools
except ImportError:
    ProjectCodeContext = None
    CodeQueryTools = None


class InterviewQuestion(BaseModel):
    text: str
    category: str
    follow_up: bool = False


class Interviewer:
    """LLM-assisted project requirements interviewer"""

    QUESTIONS = [
        InterviewQuestion(text="What's the name of your project?", category="overview"),
        InterviewQuestion(
            text="In one sentence, what does your project do?", category="overview"
        ),
        InterviewQuestion(
            text="What tech stack do you want to use? (e.g., FastAPI, React, PostgreSQL)",
            category="tech_stack",
        ),
        InterviewQuestion(
            text="What are the main features? (comma-separated list)",
            category="features",
        ),
        InterviewQuestion(
            text="Any specific requirements or constraints?", category="constraints"
        ),
    ]

    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.questions_asked = 0
        self.responses: list[dict] = []
        self.current_question_idx = 0
        self.code_context = None
        self.librarian_url = librarian_url

    def load_code_context(self, project_name: str, features: list[str]):
        """Load code context for an existing project.

        Gracefully handles missing project or connection errors.
        """
        if ProjectCodeContext is None:
            logger.warning("CodeQueryTools not available, skipping code context")
            self.code_context = None
            return

        try:
            tools = CodeQueryTools(self.librarian_url)
            self.code_context = ProjectCodeContext(tools)
            overview = self.code_context.get_project_overview(project_name)
            if overview:
                self.code_context.find_existing_features(project_name, features)
        except Exception as e:
            logger.warning(f"Failed to load code context: {e}")
            self.code_context = None

    def get_next_question(self) -> Optional[InterviewQuestion]:
        if self.current_question_idx >= len(self.QUESTIONS):
            return None
        return self.QUESTIONS[self.current_question_idx]

    def record_response(self, answer: str, category: str):
        self.responses.append(
            {
                "question_idx": self.current_question_idx,
                "category": category,
                "answer": answer,
            }
        )
        self.questions_asked += 1
        self.current_question_idx += 1

    def is_complete(self) -> bool:
        return self.current_question_idx >= len(self.QUESTIONS)

    def extract_project_spec(self) -> dict:
        """Extract ProjectSpec from interview responses"""
        spec = {
            "name": "",
            "tech_stack": [],
            "features": [],
            "constraints": [],
        }

        for response in self.responses:
            if response["category"] == "overview":
                if response["question_idx"] == 0:
                    spec["name"] = response["answer"]
            elif response["category"] == "tech_stack":
                spec["tech_stack"] = [s.strip() for s in response["answer"].split(",")]
            elif response["category"] == "features":
                spec["features"] = [s.strip() for s in response["answer"].split(",")]
            elif response["category"] == "constraints":
                spec["constraints"] = [
                    s.strip() for s in response["answer"].split(",") if s.strip()
                ]

        return spec
