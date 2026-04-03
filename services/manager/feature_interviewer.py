import requests
import json
import logging
import re
from typing import Optional

try:
    from shared.code_query_tools import ProjectCodeContext, CodeQueryTools
except ImportError:
    ProjectCodeContext = None
    CodeQueryTools = None

logger = logging.getLogger(__name__)


LLM_PROMPT_TEMPLATE = """You are conducting a requirements interview for adding a feature to an existing software project.

EXISTING PROJECT:
{code_overview}

FEATURE DESCRIPTION:
{feature_description}

{previous_q_and_a}

Based on the above, is the feature description clear enough to create a detailed project spec?

If YES, respond with exactly: READY

If NO, list the specific clarifying questions you need answered. Ask at most 5 questions per round.
Focus on: what the feature does, how it interacts with existing code, technical requirements,
constraints, and edge cases. Do NOT ask about things that are already covered in the description
or that are clearly present in the existing code.

Return your response as JSON:
- If ready: "READY"
- If questions needed: ["question 1", "question 2", ...]"""


class FeatureInterviewer:
    """Adaptive, LLM-driven interview for adding features to existing projects.

    Handles project selection, code context loading, and LLM-driven
    clarifying questions. Does not persist specs — that is handled by
    the CLI command.
    """

    def __init__(self, librarian_url: str = "http://localhost:8001", llm_client=None):
        self.librarian_url = librarian_url
        self.responses: list[dict] = []
        self.code_context = None
        self.code_context_overview: Optional[str] = None
        self.selected_project: Optional[dict] = None
        self.llm_client = llm_client

    def list_projects(self) -> list[dict]:
        """Fetch all existing projects from the Librarian."""
        try:
            response = requests.get(
                f"{self.librarian_url}/projects",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logger.warning(f"Failed to list projects: {e}")
        return []

    def load_project_context(self, project_name: str):
        """Load code context for the selected project.

        Gracefully handles missing project or connection errors.
        """
        if ProjectCodeContext is None:
            logger.warning("ProjectCodeContext not available, skipping code context")
            self.code_context = None
            self.code_context_overview = None
            return

        try:
            tools = CodeQueryTools(self.librarian_url)
            self.code_context = ProjectCodeContext(tools)
            overview = self.code_context.get_project_overview(project_name)
            if overview:
                self.code_context_overview = (
                    f"{overview['total_files']} files, "
                    f"{overview['total_functions']} functions, "
                    f"{overview['total_classes']} classes"
                )
            else:
                self.code_context_overview = "No code overview available."
            # NOTE: find_existing_features is intentionally NOT called here.
            # Unlike Interviewer.load_code_context, we don't have feature keywords
            # at this stage — features come later during the interview.
        except Exception as e:
            logger.warning(f"Failed to load code context: {e}")
            self.code_context = None
            self.code_context_overview = None

    def generate_questions(self, feature_description: str, code_overview: str) -> Optional[list[str]]:
        """Use LLM to generate clarifying questions or determine readiness.

        Returns:
            None if the spec is clear (LLM returned READY),
            list of question strings if more clarification is needed.
        """
        if self.llm_client is None:
            logger.info("No LLM client available, proceeding with spec construction")
            return None

        previous_qa = ""
        if self.responses:
            qa_lines = [f"Q: {r['question']}\nA: {r['answer']}" for r in self.responses]
            previous_qa = "PREVIOUS Q&A:\n" + "\n".join(qa_lines)

        prompt = LLM_PROMPT_TEMPLATE.format(
            code_overview=code_overview,
            feature_description=feature_description,
            previous_q_and_a=previous_qa,
        )

        try:
            response = self.llm_client.invoke(prompt)
            if not isinstance(response, str):
                logger.warning("LLM returned non-string response")
                return None
            response = response.strip()

            if response == "READY":
                return None

            questions = json.loads(response)
            if isinstance(questions, list) and len(questions) > 0:
                return questions
            return None
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            logger.warning(f"LLM question generation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in LLM question generation: {e}")
            return None

    def record_response(self, question: str, answer: str):
        """Record a question-answer pair from the interview."""
        self.responses.append({
            "question": question,
            "answer": answer,
        })

    def build_spec(self, feature_description: str) -> dict:
        """Construct a ProjectSpec dict from the interview data."""
        project = self.selected_project or {}
        parent_id = project.get("id")
        parent_name = project.get("name", "standalone")
        parent_tech_stack = project.get("tech_stack", [])

        # Derive spec name from parent project and feature
        safe_feature = re.sub(r'[^a-z0-9-]', '', feature_description.lower().replace(' ', '-'))[:50]
        if self.selected_project is None:
            spec_name = safe_feature
        else:
            safe_parent = re.sub(r'[^a-z0-9-]', '', parent_name.lower().replace(' ', '-'))
            spec_name = f"{safe_parent}-{safe_feature}"

        # Collect constraints from interview responses
        constraints = []
        for r in self.responses:
            if r["answer"].strip():
                constraints.append(f"{r['question']}: {r['answer']}")

        # Features list contains the new feature description
        features = [feature_description]

        return {
            "name": spec_name,
            "tech_stack": parent_tech_stack,
            "features": features,
            "constraints": constraints,
            "parent_project": parent_id,
        }
