import uuid
import json
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from shared.code_query_tools import ProjectCodeContext, CodeQueryTools
except ImportError:
    ProjectCodeContext = None
    CodeQueryTools = None


def generate_task_id() -> str:
    """Generate a unique task identifier using UUID4"""
    return str(uuid.uuid4())


class Atomizer:
    """
    Atomizer service for decomposing project specifications into atomic tasks.

    The Atomizer takes a high-level ProjectSpec and breaks it down into
    discrete, executable tasks that can be assigned to worker agents.
    """

    def __init__(self, librarian_url: str = "http://localhost:8001"):
        """
        Initialize the Atomizer.

        Args:
            librarian_url: URL of the Librarian service for fetching project specs
        """
        self.librarian_url = librarian_url

    def decompose(self, project_spec: dict) -> list[dict]:
        """
        Decompose a project specification into atomic tasks.

        Args:
            project_spec: Dictionary containing name, tech_stack, and features

        Returns:
            List of task dictionaries with task_id, title, status, dependencies
        """
        # Try to load code context for existing projects
        code_context = self._load_code_context(project_spec)

        # Use mock decompose for now - can be replaced with AI-powered decomposition
        return self._mock_decompose(project_spec, code_context)

    def _load_code_context(self, project_spec: dict):
        """Load code context for the project if available.

        Returns ProjectCodeContext instance or None.
        """
        if ProjectCodeContext is None:
            return None

        try:
            tools = CodeQueryTools(self.librarian_url)
            ctx = ProjectCodeContext(tools)
            overview = ctx.get_project_overview(project_spec.get("name", ""))
            if overview:
                return ctx
        except Exception as e:
            logger.warning(f"Failed to load code context: {e}")
        return None

    def _mock_decompose(self, project_spec: dict, code_context=None) -> list[dict]:
        """
        Generate a mock decomposition of the project spec into tasks.

        This creates a basic task structure for the project including:
        - Project setup task
        - Feature implementation tasks
        - Integration task

        Args:
            project_spec: Dictionary containing name, tech_stack, and features
            code_context: Optional ProjectCodeContext for existing projects

        Returns:
            List of task dictionaries
        """
        tasks = []
        project_name = project_spec.get("name", "Unknown Project")
        tech_stack = project_spec.get("tech_stack", [])
        features = project_spec.get("features", [])

        # Check which features already exist
        existing_features = {}
        if code_context:
            existing_features = code_context.find_existing_features(project_name, features)

        # Task 1: Project Setup
        setup_task = {
            "task_id": generate_task_id(),
            "title": f"Setup project structure for {project_name}",
            "status": "PENDING",
            "dependencies": [],
            "contract": {
                "type": "setup",
                "tech_stack": tech_stack,
                "project_name": project_name
            }
        }
        tasks.append(setup_task)
        setup_task_id = setup_task["task_id"]

        # Task 2+: Feature implementation tasks
        feature_task_ids = []
        for i, feature in enumerate(features):
            # Check if this feature already exists
            feature_info = existing_features.get(feature, {})
            if feature_info.get("found"):
                # Feature exists — create a task to extend it
                match_names = ", ".join(m["name"] for m in feature_info.get("matches", []))
                feature_task = {
                    "task_id": generate_task_id(),
                    "title": f"Extend existing {feature} ({match_names})",
                    "status": "PENDING",
                    "dependencies": [setup_task_id],
                    "contract": {
                        "type": "extend_feature",
                        "feature": feature,
                        "existing_code": feature_info.get("matches", []),
                        "tech_stack": tech_stack
                    }
                }
            else:
                # New feature — implement from scratch
                feature_task = {
                    "task_id": generate_task_id(),
                    "title": f"Implement feature: {feature}",
                    "status": "PENDING",
                    "dependencies": [setup_task_id],
                    "contract": {
                        "type": "feature",
                        "feature": feature,
                        "tech_stack": tech_stack
                    }
                }
            tasks.append(feature_task)
            feature_task_ids.append(feature_task["task_id"])

        # Final task: Integration and testing
        if len(features) > 1:
            integration_task = {
                "task_id": generate_task_id(),
                "title": f"Integration testing for {project_name}",
                "status": "PENDING",
                "dependencies": feature_task_ids,
                "contract": {
                    "type": "integration",
                    "project_name": project_name
                }
            }
            tasks.append(integration_task)

        return tasks

    def fetch_project_spec(self, spec_id: str) -> dict:
        """
        Fetch a project specification from the Librarian service.

        Args:
            spec_id: The ID of the project spec to fetch

        Returns:
            Project spec dictionary

        Raises:
            requests.exceptions.HTTPError: If the spec is not found (404)
            requests.exceptions.RequestException: If connection fails
        """
        url = f"{self.librarian_url}/project-specs/{spec_id}"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()

    def save_tasks(self, tasks: list[dict], output_path: str) -> None:
        """
        Save decomposed tasks to a JSON file.

        Args:
            tasks: List of task dictionaries
            output_path: Path to the output JSON file
        """
        with open(output_path, 'w') as f:
            json.dump(tasks, f, indent=2)
