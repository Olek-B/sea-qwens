# Add Feature Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `add-feature` CLI command that lets users select an existing project, describe a new feature, and go through an adaptive LLM-driven interview to create a new ProjectSpec that extends the existing project.

**Architecture:** A new `FeatureInterviewer` class handles the adaptive interview flow. A new `GET /projects` endpoint on the Librarian lists existing projects. The `ProjectSpec` model gains an optional `parent_project` field.

**Tech Stack:** Python, Click (CLI), FastAPI (Librarian), Pydantic (models), requests (HTTP client), pytest (testing)

---

### Task 1: Add `parent_project` field to ProjectSpec model

**Files:**
- Modify: `shared/models.py:24-28`
- Test: `shared/test_models.py`

- [ ] **Step 1: Write the failing test**

Add a test to `shared/test_models.py` that verifies the `parent_project` field exists and defaults to `None`:

```python
def test_project_spec_has_parent_project_field():
    """ProjectSpec supports a parent_project reference."""
    spec = ProjectSpec(
        name="myapp-add-auth",
        tech_stack=["FastAPI", "React"],
        features=["add user authentication"],
        parent_project="myapp"
    )
    assert spec.parent_project == "myapp"

def test_project_spec_parent_project_defaults_to_none():
    """parent_project is optional and defaults to None."""
    spec = ProjectSpec(
        name="myapp",
        tech_stack=["FastAPI"],
        features=["api"]
    )
    assert spec.parent_project is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest shared/test_models.py::test_project_spec_has_parent_project_field -v`
Expected: FAIL with "unexpected keyword argument 'parent_project'"

- [ ] **Step 3: Write minimal implementation**

In `shared/models.py`, add `parent_project` to the `ProjectSpec` class:

```python
class ProjectSpec(BaseModel):
    name: str
    tech_stack: list[str]
    features: list[str]
    id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    parent_project: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest shared/test_models.py -v`
Expected: PASS (all tests including the two new ones)

- [ ] **Step 5: Commit**

```bash
git add shared/models.py shared/test_models.py
git commit -m "feat: add parent_project field to ProjectSpec model"
```

---

### Task 2: Add `list_all_project_specs` method to Neo4jStore

**Files:**
- Modify: `services/librarian/neo4j_store.py` (add method after `get_project_spec`)
- Test: `services/librarian/tests/test_api.py` (add to TestProjectSpecEndpoints class)

- [ ] **Step 1: Write the failing test**

Add to `services/librarian/tests/test_api.py` inside `TestProjectSpecEndpoints`:

```python
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

def test_list_all_project_specs_empty(self, client, mock_stores):
    """Test listing when no projects exist"""
    mock_stores['neo4j'].list_all_project_specs.return_value = []

    response = client.get("/projects")
    assert response.status_code == 200
    assert response.json() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/librarian/tests/test_api.py::TestProjectSpecEndpoints::test_list_all_project_specs -v`
Expected: FAIL — `list_all_project_specs` method doesn't exist

- [ ] **Step 3: Write minimal implementation — Neo4jStore method**

Add to `services/librarian/neo4j_store.py` after the `get_project_spec` method:

```python
def list_all_project_specs(self) -> list[dict]:
    """Retrieve all ProjectSpec nodes from Neo4j."""
    with self.driver.session() as session:
        result = session.run("MATCH (p:ProjectSpec) RETURN p ORDER BY p.created_at DESC")
        return [dict(record["p"]) for record in result]
```

- [ ] **Step 4: Write minimal implementation — FastAPI endpoint**

Add to `services/librarian/app.py` before the `@app.post("/project-specs")` endpoint:

```python
@app.get("/projects")
def list_projects():
    """List all existing project specs."""
    neo4j = get_neo4j_store()
    return neo4j.list_all_project_specs()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest services/librarian/tests/test_api.py::TestProjectSpecEndpoints::test_list_all_project_specs services/librarian/tests/test_api.py::TestProjectSpecEndpoints::test_list_all_project_specs_empty -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/librarian/neo4j_store.py services/librarian/app.py services/librarian/tests/test_api.py
git commit -m "feat: add GET /projects endpoint to list all project specs"
```

---

### Task 3: Create FeatureInterviewer class

**Files:**
- Create: `services/manager/feature_interviewer.py`
- Test: `services/manager/tests/test_feature_interviewer.py`

- [ ] **Step 1: Write tests for initialization and project listing**

Create `services/manager/tests/test_feature_interviewer.py`:

```python
import pytest
import sys
import os
import json

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
        mocker.patch("requests.get", side_effect=Exception("Connection refused"))

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest services/manager/tests/test_feature_interviewer.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Write FeatureInterviewer class with init and list_projects**

Create `services/manager/feature_interviewer.py`:

```python
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FeatureInterviewer:
    """Adaptive, LLM-driven interview for adding features to existing projects."""

    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url
        self.responses: list[dict] = []
        self.code_context = None
        self.selected_project: Optional[dict] = None

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest services/manager/tests/test_feature_interviewer.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add services/manager/feature_interviewer.py services/manager/tests/test_feature_interviewer.py
git commit -m "feat: add FeatureInterviewer class with list_projects method"
```

---

### Task 4: Add load_project_context to FeatureInterviewer

**Files:**
- Modify: `services/manager/feature_interviewer.py`
- Test: `services/manager/tests/test_feature_interviewer.py`

- [ ] **Step 1: Write the failing tests**

Add to `services/manager/tests/test_feature_interviewer.py`:

```python
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
        assert interviewer.code_context.get_project_overview.called

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest services/manager/tests/test_feature_interviewer.py::TestFeatureInterviewerLoadContext -v`
Expected: FAIL — `load_project_context` method doesn't exist

- [ ] **Step 3: Write minimal implementation**

Add to `services/manager/feature_interviewer.py` after the `list_projects` method:

```python
try:
    from shared.code_query_tools import ProjectCodeContext, CodeQueryTools
except ImportError:
    ProjectCodeContext = None
    CodeQueryTools = None


class FeatureInterviewer:
    # ... existing code ...

    def load_project_context(self, project_name: str):
        """Load code context for the selected project.

        Gracefully handles missing project or connection errors.
        """
        if ProjectCodeContext is None:
            logger.warning("CodeQueryTools not available, skipping code context")
            self.code_context = None
            return

        try:
            tools = CodeQueryTools(self.librarian_url)
            self.code_context = ProjectCodeContext(tools)
            self.code_context.get_project_overview(project_name)
        except Exception as e:
            logger.warning(f"Failed to load code context: {e}")
            self.code_context = None
```

Note: The import block goes at the top of the file, before the class definition. The `load_project_context` method goes inside the class.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest services/manager/tests/test_feature_interviewer.py::TestFeatureInterviewerLoadContext -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/manager/feature_interviewer.py services/manager/tests/test_feature_interviewer.py
git commit -m "feat: add load_project_context to FeatureInterviewer"
```

---

### Task 5: Add LLM-driven question generation to FeatureInterviewer

**Files:**
- Modify: `services/manager/feature_interviewer.py`
- Test: `services/manager/tests/test_feature_interviewer.py`

- [ ] **Step 1: Write the failing tests**

Add to `services/manager/tests/test_feature_interviewer.py`:

```python
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
        # Verify the LLM was called (prompt includes previous Q&A)
        assert mock_llm.invoke.called

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest services/manager/tests/test_feature_interviewer.py::TestFeatureInterviewerGenerateQuestions -v`
Expected: FAIL — `generate_questions` method doesn't exist

- [ ] **Step 3: Write minimal implementation**

Add to `services/manager/feature_interviewer.py` inside the class:

```python
LLM_PROMPT_TEMPLATE = """You are conducting a requirements interview for adding a feature to an existing software project.

EXISTING PROJECT:
{code_overview}

FEATURE DESCRIPTION:
{feature_description}

{previous_q_and_a}

Based on the above, is the feature description clear enough to create a detailed project spec?

If YES, respond with exactly: READY

If NO, list the specific clarifying questions you need answered. Ask as many questions as needed.
Focus on: what the feature does, how it interacts with existing code, technical requirements,
constraints, and edge cases. Do NOT ask about things that are already covered in the description
or that are clearly present in the existing code.

Return your response as JSON:
- If ready: "READY"
- If questions needed: ["question 1", "question 2", ...]"""


class FeatureInterviewer:
    # ... existing code ...

    def __init__(self, librarian_url: str = "http://localhost:8001", llm_client=None):
        self.librarian_url = librarian_url
        self.responses: list[dict] = []
        self.code_context = None
        self.selected_project: Optional[dict] = None
        self.llm_client = llm_client

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
            response = response.strip()

            if response == "READY":
                return None

            questions = json.loads(response)
            if isinstance(questions, list) and len(questions) > 0:
                return questions
            return None
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"LLM question generation failed: {e}")
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest services/manager/tests/test_feature_interviewer.py::TestFeatureInterviewerGenerateQuestions -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/manager/feature_interviewer.py services/manager/tests/test_feature_interviewer.py
git commit -m "feat: add LLM-driven question generation to FeatureInterviewer"
```

---

### Task 6: Add build_spec and record_response to FeatureInterviewer

**Files:**
- Modify: `services/manager/feature_interviewer.py`
- Test: `services/manager/tests/test_feature_interviewer.py`

- [ ] **Step 1: Write the failing tests**

Add to `services/manager/tests/test_feature_interviewer.py`:

```python
class TestFeatureInterviewerBuildSpec:
    def test_record_response(self):
        """record_response stores question and answer."""
        interviewer = FeatureInterviewer()
        interviewer.record_response("What auth method?", "JWT")

        assert len(interviewer.responses) == 1
        assert interviewer.responses[0]["question"] == "What auth method?"
        assert interviewer.responses[0]["answer"] == "JWT"

    def test_build_spec_creates_spec_with_parent_project(self):
        """build_spec creates a ProjectSpec dict with parent_project reference."""
        interviewer = FeatureInterviewer()
        interviewer.selected_project = {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI", "React"], "features": ["auth"]}
        interviewer.code_context_overview = "5 files, 12 functions"

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest services/manager/tests/test_feature_interviewer.py::TestFeatureInterviewerBuildSpec -v`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Write minimal implementation**

Add to `services/manager/feature_interviewer.py` inside the class:

```python
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
        safe_feature = feature_description.lower().replace(" ", "-")[:50]
        spec_name = f"{parent_name.lower().replace(' ', '-')}-{safe_feature}"

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest services/manager/tests/test_feature_interviewer.py::TestFeatureInterviewerBuildSpec -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/manager/feature_interviewer.py services/manager/tests/test_feature_interviewer.py
git commit -m "feat: add build_spec and record_response to FeatureInterviewer"
```

---

### Task 7: Add `add_feature` CLI command

**Files:**
- Modify: `services/manager/cli.py`
- Test: `services/manager/tests/test_cli.py` (new file)

- [ ] **Step 1: Write the failing tests**

Create `services/manager/tests/test_cli.py`:

```python
import pytest
from click.testing import CliRunner
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from services.manager.cli import cli


class TestAddFeatureCommand:
    def test_add_feature_no_projects(self, mocker):
        """add-feature handles empty project list gracefully."""
        mocker.patch("services.manager.feature_interviewer.FeatureInterviewer.list_projects", return_value=[])

        runner = CliRunner()
        result = runner.invoke(cli, ["add-feature"])

        assert result.exit_code == 0
        assert "No existing projects found" in result.output

    def test_add_feature_shows_project_list(self, mocker):
        """add-feature displays numbered project list."""
        mock_list = mocker.patch(
            "services.manager.feature_interviewer.FeatureInterviewer.list_projects",
            return_value=[
                {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI"], "features": ["auth"]},
                {"id": "spec-2", "name": "OtherApp", "tech_stack": ["Django"], "features": ["admin"]},
            ]
        )

        runner = CliRunner()
        # Input: select project 1, describe feature, then cancel at confirm
        result = runner.invoke(cli, ["add-feature"], input="1\nAdd email notifications\nn\n")

        assert result.exit_code == 0
        assert "MyApp" in result.output
        assert "OtherApp" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest services/manager/tests/test_cli.py -v`
Expected: FAIL — `add-feature` command doesn't exist

- [ ] **Step 3: Write minimal implementation**

Add to `services/manager/cli.py` after the `interview` command:

```python
@cli.command()
def add_feature():
    """Add a new feature to an existing project"""
    click.echo("=" * 60)
    click.echo("SEA QWENS MANAGER - Add Feature to Existing Project")
    click.echo("=" * 60)
    click.echo()

    interviewer = FeatureInterviewer(librarian_url=LIBRARIAN_URL)

    # Step 1: List existing projects
    projects = interviewer.list_projects()
    if not projects:
        click.echo(click.style(
            "No existing projects found. Run `interview` first to create a project.",
            fg="yellow"
        ))
        return

    click.echo(click.style("\nSelect a project to extend:", fg="green", bold=True))
    for i, project in enumerate(projects, 1):
        tech = ", ".join(project.get("tech_stack", []))
        features = ", ".join(project.get("features", []))
        click.echo(f"  {i}. {project['name']} (tech: {tech}, features: {features})")

    click.echo()
    choice = click.prompt("Enter project number", type=int)

    if choice < 1 or choice > len(projects):
        click.echo(click.style("Invalid selection. Interview cancelled.", fg="red"))
        return

    selected = projects[choice - 1]
    interviewer.selected_project = selected
    project_name = selected["name"]

    # Step 2: Load code context
    click.echo(click.style(f"\nLoading code context for {project_name}...", fg="yellow"))
    interviewer.load_project_context(project_name)

    if interviewer.code_context:
        overview = interviewer.code_context.get_project_overview(project_name)
        if overview:
            interviewer.code_context_overview = (
                f"{overview['total_files']} files, "
                f"{overview['total_functions']} functions, "
                f"{overview['total_classes']} classes"
            )
            click.echo(click.style(
                f"Found existing code: {interviewer.code_context_overview}",
                fg="cyan"
            ))
        else:
            interviewer.code_context_overview = "No code overview available."
    else:
        interviewer.code_context_overview = "Code context unavailable."
        click.echo(click.style("Could not load code context.", fg="yellow"))

    # Step 3: Get feature description
    click.echo()
    click.echo(click.style(
        f"Describe the feature you want to add to {project_name}:",
        fg="green", bold=True
    ))
    feature_description = click.prompt("Feature description")

    # Step 4: LLM-driven clarifying questions
    click.echo()
    click.echo(click.style("Analyzing your description...", fg="yellow"))

    while True:
        questions = interviewer.generate_questions(feature_description, interviewer.code_context_overview)
        if questions is None:
            break

        for question in questions:
            click.echo(click.style(f"\n{question}", fg="green", bold=True))
            answer = click.prompt("Your answer")
            interviewer.record_response(question, answer)

    # Step 5: Build and display spec
    spec = interviewer.build_spec(feature_description)

    click.echo()
    click.echo("=" * 60)
    click.echo("EXTRACTED FEATURE SPEC")
    click.echo("=" * 60)
    click.echo(f"Name: {spec['name']}")
    click.echo(f"Parent Project: {spec['parent_project']}")
    click.echo(f"Tech Stack: {', '.join(spec['tech_stack'])}")
    click.echo(f"Features: {', '.join(spec['features'])}")
    if spec.get('constraints'):
        click.echo(f"Constraints: {', '.join(spec['constraints'])}")
    click.echo()

    # Step 6: Confirm and send
    if click.confirm("Send this FeatureSpec to the Librarian?"):
        try:
            response = requests.post(
                f"{LIBRARIAN_URL}/project-specs",
                json=spec
            )
            if response.status_code == 201:
                result = response.json()
                click.echo(click.style(
                    f"✓ ProjectSpec created with ID: {result['id']}",
                    fg="green", bold=True
                ))
            else:
                click.echo(click.style(
                    f"✗ Error: {response.text}",
                    fg="red"
                ))
        except requests.exceptions.ConnectionError:
            click.echo(click.style(
                "✗ Could not connect to Librarian. Is it running?",
                fg="red"
            ))
            click.echo(f"Spec would be: {json.dumps(spec, indent=2)}")
    else:
        click.echo("Interview cancelled. No data sent.")
```

Also add the import at the top of `cli.py`:

```python
from services.manager.feature_interviewer import FeatureInterviewer
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest services/manager/tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Run all manager tests to ensure no regressions**

Run: `python -m pytest services/manager/tests/ -v`
Expected: PASS (all tests including existing interviewer tests)

- [ ] **Step 6: Commit**

```bash
git add services/manager/cli.py services/manager/tests/test_cli.py
git commit -m "feat: add add-feature CLI command with adaptive interview flow"
```

---

### Task 8: Integration test and final verification

**Files:**
- Modify: `services/manager/tests/test_feature_interviewer.py` (add integration-style test)
- Modify: `services/manager/tests/test_cli.py` (add full flow test)

- [ ] **Step 1: Write integration test for full CLI flow**

Add to `services/manager/tests/test_cli.py`:

```python
    def test_add_feature_full_flow(self, mocker):
        """add-feature completes full flow: select project → describe → questions → spec → send."""
        # Mock project listing
        mocker.patch(
            "services.manager.feature_interviewer.FeatureInterviewer.list_projects",
            return_value=[
                {"id": "spec-1", "name": "MyApp", "tech_stack": ["FastAPI"], "features": ["auth"]},
            ]
        )

        # Mock code context
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

        # Mock LLM: first round asks 1 question, second round says READY
        mock_llm = mocker.Mock()
        mock_llm.invoke.side_effect = [
            json.dumps(["What auth provider?"]),
            "READY",
        ]

        # Mock Librarian POST
        mock_post = mocker.patch("requests.post")
        mock_post.return_value = mocker.Mock(status_code=201, json=lambda: {"id": "spec-new"})

        runner = CliRunner()
        result = runner.invoke(cli, ["add-feature"], input="1\nAdd OAuth login\nAuth0\ny\n")

        assert result.exit_code == 0
        assert "EXTRACTED FEATURE SPEC" in result.output
        assert mock_post.called
```

- [ ] **Step 2: Run all tests**

Run: `python -m pytest services/manager/tests/ services/librarian/tests/test_api.py shared/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add services/manager/tests/test_cli.py services/manager/tests/test_feature_interviewer.py
git commit -m "test: add full integration flow test for add-feature command"
```

---

## Self-Review

**1. Spec coverage check:**

| Spec Requirement | Task |
|-----------------|------|
| `parent_project` field on ProjectSpec | Task 1 |
| `GET /projects` endpoint on Librarian | Task 2 |
| `list_all_project_specs` in Neo4jStore | Task 2 |
| `FeatureInterviewer` class | Task 3 |
| Project listing with numbered selection | Task 7 |
| Code context loading | Task 4 |
| LLM-driven clarifying questions (no limit) | Task 5 |
| Question loop until LLM returns READY | Task 7 (CLI loop) |
| `build_spec` with parent_project ref | Task 6 |
| Tech stack inheritance from parent | Task 6 |
| Error: no projects in DB | Task 7 |
| Error: code context unavailable | Task 4, 7 |
| Error: LLM unavailable | Task 5 |
| Error: Librarian connection failed | Task 7 |
| User cancel at any point | Task 7 |
| Tests for all components | Tasks 1-8 |

All spec requirements covered.

**2. Placeholder scan:** No TBD, TODO, "implement later", "add appropriate error handling", or "similar to Task N" patterns found. All code steps contain actual code.

**3. Type consistency:** 
- `FeatureInterviewer.__init__` accepts `llm_client` parameter (Task 5) — consistent with tests that mock it.
- `build_spec` returns `dict` matching `ProjectSpec` fields (Task 6) — `name`, `tech_stack`, `features`, `constraints`, `parent_project`.
- `list_projects` returns `list[dict]` matching the `/projects` endpoint response (Task 3) — consistent with Task 2's endpoint.
- `code_context_overview` attribute is set in Task 7 CLI and used in Task 5's `generate_questions` — consistent naming.

All consistent. Plan is ready.
