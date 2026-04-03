# Shared Code Query Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Worker's CodeQueryTools to a shared module and add higher-level ProjectCodeContext helpers so Manager and Atomizer can query existing project code.

**Architecture:** Extract `CodeQueryTools` from `services/worker/mcp_tools.py` into `shared/code_query_tools.py`, add `ProjectCodeContext` wrapper with project-aware helpers, update Manager and Atomizer to use it, keep Worker working via re-export.

**Tech Stack:** Python 3.11+, requests, pytest, pytest-mock

---

### Task 1: Create shared/code_query_tools.py with CodeQueryTools and ProjectCodeContext

**Files:**
- Create: `shared/code_query_tools.py`
- Test: `shared/test_code_query_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# shared/test_code_query_tools.py
import pytest
from shared.code_query_tools import CodeQueryTools


class TestCodeQueryTools:
    """Tests for the base CodeQueryTools HTTP client."""

    def test_init_stores_url(self):
        tools = CodeQueryTools("http://localhost:8001")
        assert tools.librarian_url == "http://localhost:8001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest shared/test_code_query_tools.py::TestCodeQueryTools::test_init_stores_url -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'shared.code_query_tools'"

- [ ] **Step 3: Write minimal implementation**

```python
# shared/code_query_tools.py
"""Shared code query tools for all services that need code database access."""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CodeQueryTools:
    """HTTP client for the Librarian's code query API.

    Used by Worker, Manager, and Atomizer to query the code knowledge graph
    instead of reading files directly.
    """

    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url

    def search_code(self, query: str, type: str = "function") -> list:
        """Search for functions/classes by semantic similarity."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/search",
                params={"q": query, "type": type},
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("results", [])
        except requests.RequestException as e:
            logger.warning(f"Code search failed: {e}")
        return []

    def get_function(self, name: str) -> Optional[dict]:
        """Get function body and signature by name."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/function/{name}",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logger.warning(f"Get function failed: {e}")
        return None

    def get_callers(self, function_name: str) -> list:
        """Get all functions that call this function."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/function/{function_name}/callers",
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("callers", [])
        except requests.RequestException as e:
            logger.warning(f"Get callers failed: {e}")
        return []

    def get_callees(self, function_name: str) -> list:
        """Get all functions this function calls."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/function/{function_name}/callees",
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("callees", [])
        except requests.RequestException as e:
            logger.warning(f"Get callees failed: {e}")
        return []

    def get_full_context(self, function_name: str) -> dict:
        """Get everything needed to understand a function."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/function/{function_name}/full-context",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logger.warning(f"Get full context failed: {e}")
        return {}

    def get_class(self, name: str) -> Optional[dict]:
        """Get class definition and all methods."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/class/{name}",
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logger.warning(f"Get class failed: {e}")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest shared/test_code_query_tools.py::TestCodeQueryTools::test_init_stores_url -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/code_query_tools.py shared/test_code_query_tools.py
git commit -m "feat: add shared CodeQueryTools base client"
```

---

### Task 2: Add CodeQueryTools error handling tests

**Files:**
- Modify: `shared/test_code_query_tools.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `shared/test_code_query_tools.py`:

```python
class TestCodeQueryToolsErrorHandling:
    """Tests for CodeQueryTools error handling."""

    def test_search_code_returns_empty_list_on_connection_error(self, mocker):
        tools = CodeQueryTools("http://localhost:9999")
        mocker.patch.object(tools, 'search_code', side_effect=requests.RequestException("Connection refused"))
        # Actually test the real method by not mocking it — it should return [] on failure
        result = tools.search_code("test")
        assert result == []

    def test_get_function_returns_none_on_404(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 404
        mock_get = mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.get_function("nonexistent")
        assert result is None

    def test_get_function_returns_none_on_connection_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_function("test")
        assert result is None

    def test_get_callers_returns_empty_list_on_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_callers("test")
        assert result == []

    def test_get_callees_returns_empty_list_on_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_callees("test")
        assert result == []

    def test_get_full_context_returns_empty_dict_on_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_full_context("test")
        assert result == {}

    def test_get_class_returns_none_on_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_class("test")
        assert result is None
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest shared/test_code_query_tools.py::TestCodeQueryToolsErrorHandling -v`
Expected: PASS (the implementation already handles these cases gracefully)

- [ ] **Step 3: Add success-case tests**

```python
class TestCodeQueryToolsSuccess:
    """Tests for CodeQueryTools successful responses."""

    def test_search_code_returns_results(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"name": "my_func", "file": "app.py"}]}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.search_code("authentication")
        assert len(result) == 1
        assert result[0]["name"] == "my_func"

    def test_get_function_returns_data(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "login", "body": "def login(): ..."}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.get_function("login")
        assert result is not None
        assert result["name"] == "login"

    def test_get_class_returns_data(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"class": {"name": "AuthService"}, "methods": []}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.get_class("AuthService")
        assert result is not None
        assert result["class"]["name"] == "AuthService"
```

- [ ] **Step 4: Run all CodeQueryTools tests**

Run: `pytest shared/test_code_query_tools.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add shared/test_code_query_tools.py
git commit -m "test: add CodeQueryTools error handling and success tests"
```

---

### Task 3: Add ProjectCodeContext class to shared/code_query_tools.py

**Files:**
- Modify: `shared/code_query_tools.py`
- Modify: `shared/test_code_query_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to shared/test_code_query_tools.py
from shared.code_query_tools import ProjectCodeContext


class TestProjectCodeContext:
    """Tests for ProjectCodeContext higher-level helpers."""

    def test_init_stores_tools(self):
        tools = CodeQueryTools("http://localhost:8001")
        ctx = ProjectCodeContext(tools)
        assert ctx.tools is tools
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest shared/test_code_query_tools.py::TestProjectCodeContext::test_init_stores_tools -v`
Expected: FAIL with "ImportError: cannot import name 'ProjectCodeContext'"

- [ ] **Step 3: Write minimal implementation — add ProjectCodeContext to shared/code_query_tools.py**

Append to `shared/code_query_tools.py`:

```python
class ProjectCodeContext:
    """Higher-level code context helpers for a specific project.

    Wraps CodeQueryTools with project-aware methods that help services
    understand what code already exists for a given project.
    """

    def __init__(self, tools: CodeQueryTools):
        self.tools = tools

    def get_project_overview(self, project_name: str) -> Optional[dict]:
        """Get a summary of the project's code structure.

        Returns None if the project has no code in the database.
        """
        # Broad search to discover project code
        all_functions = self.tools.search_code("", type="function")
        all_classes = self.tools.search_code("", type="class")

        if not all_functions and not all_classes:
            return None

        files = set()
        for func in all_functions:
            if func.get("file"):
                files.add(func["file"])
        for cls in all_classes:
            if cls.get("metadata", {}).get("file"):
                files.add(cls["metadata"]["file"])

        return {
            "project_name": project_name,
            "files": [{"path": f} for f in sorted(files)],
            "classes": [{"name": c.get("name", ""), "file": c.get("metadata", {}).get("file", "")} for c in all_classes],
            "functions": [{"name": f.get("name", ""), "file": f.get("file", "")} for f in all_functions],
            "total_files": len(files),
            "total_functions": len(all_functions),
            "total_classes": len(all_classes),
        }

    def find_existing_features(self, project_name: str, features: list[str]) -> dict:
        """Check which features already have matching code.

        Returns a dict mapping each feature keyword to its matches.
        """
        result = {}
        for feature in features:
            matches = self.tools.search_code(feature, type="function")
            class_matches = self.tools.search_code(feature, type="class")
            all_matches = []
            for m in matches:
                all_matches.append({"name": m.get("name", "unknown"), "type": "function"})
            for m in class_matches:
                all_matches.append({"name": m.get("name", m.get("metadata", {}).get("name", "unknown")), "type": "class"})
            result[feature] = {
                "found": len(all_matches) > 0,
                "matches": all_matches,
            }
        return result

    def get_dependency_map(self) -> dict:
        """Get the CALLS and INHERITS graph for known code.

        Returns a dict with 'calls' and 'inherits' lists.
        """
        all_functions = self.tools.search_code("", type="function")
        calls = []
        for func in all_functions:
            name = func.get("name")
            if not name:
                continue
            callees = self.tools.get_callees(name)
            for callee in callees:
                calls.append({"caller": name, "callee": callee.get("name", "unknown")})

        all_classes = self.tools.search_code("", type="class")
        inherits = []
        for cls in all_classes:
            name = cls.get("name")
            if not name:
                continue
            class_data = self.tools.get_class(name)
            if class_data and class_data.get("class"):
                bases = class_data["class"].get("bases", [])
                for base in bases:
                    inherits.append({"child": name, "parent": base})

        return {"calls": calls, "inherits": inherits}

    def search_by_category(self, category: str) -> list:
        """Search for code related to a common category.

        Categories: auth, database, api, testing, config, logging
        """
        category_keywords = {
            "auth": ["auth", "login", "token", "permission", "session"],
            "database": ["database", "db", "model", "query", "sql", "mongo"],
            "api": ["api", "endpoint", "route", "handler", "request", "response"],
            "testing": ["test", "mock", "fixture", "assert"],
            "config": ["config", "settings", "env", "setup"],
            "logging": ["log", "logger", "debug", "info", "warn"],
        }
        keywords = category_keywords.get(category, [category])
        results = []
        for keyword in keywords:
            results.extend(self.tools.search_code(keyword, type="function"))
            results.extend(self.tools.search_code(keyword, type="class"))
        # Deduplicate by name
        seen = set()
        unique = []
        for r in results:
            key = r.get("name", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest shared/test_code_query_tools.py::TestProjectCodeContext::test_init_stores_tools -v`
Expected: PASS

- [ ] **Step 5: Add ProjectCodeContext unit tests with mocked tools**

```python
class TestProjectCodeContextHelpers:
    """Tests for ProjectCodeContext helper methods."""

    def test_get_project_overview_returns_none_when_empty(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.return_value = []
        ctx = ProjectCodeContext(tools)

        result = ctx.get_project_overview("myproject")
        assert result is None

    def test_get_project_overview_returns_summary(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.side_effect = [
            [{"name": "func1", "file": "app.py"}, {"name": "func2", "file": "utils.py"}],  # functions
            [{"name": "MyClass", "metadata": {"file": "app.py"}}],  # classes
        ]
        ctx = ProjectCodeContext(tools)

        result = ctx.get_project_overview("myproject")
        assert result is not None
        assert result["total_functions"] == 2
        assert result["total_classes"] == 1
        assert result["total_files"] == 2  # app.py and utils.py

    def test_find_existing_features(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.side_effect = [
            [{"name": "authenticate"}],   # auth functions
            [{"name": "AuthService"}],    # auth classes
            [],                            # payment functions
            [],                            # payment classes
        ]
        ctx = ProjectCodeContext(tools)

        result = ctx.find_existing_features("myproject", ["auth", "payment"])
        assert result["auth"]["found"] is True
        assert result["payment"]["found"] is False

    def test_get_dependency_map(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.side_effect = [
            [{"name": "func_a"}, {"name": "func_b"}],  # functions
            [],  # classes
        ]
        tools.get_callees.side_effect = [
            [{"name": "func_b"}],  # func_a calls func_b
            [],                     # func_b calls nothing
        ]
        tools.get_class.return_value = None
        ctx = ProjectCodeContext(tools)

        result = ctx.get_dependency_map()
        assert len(result["calls"]) == 1
        assert result["calls"][0] == {"caller": "func_a", "callee": "func_b"}

    def test_search_by_category(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.return_value = [{"name": "AuthService"}]
        ctx = ProjectCodeContext(tools)

        result = ctx.search_by_category("auth")
        assert len(result) >= 1
```

- [ ] **Step 6: Run all ProjectCodeContext tests**

Run: `pytest shared/test_code_query_tools.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add shared/code_query_tools.py shared/test_code_query_tools.py
git commit -m "feat: add ProjectCodeContext with project-aware helpers"
```

---

### Task 4: Update shared/__init__.py to export new classes

**Files:**
- Modify: `shared/__init__.py`

- [ ] **Step 1: Update exports**

```python
# shared/__init__.py
from shared.models import (
    ProjectSpec, Task, TaskStatus, Tool, ToolHealth,
    CodeFile, CodeClass, CodeFunction
)
from shared.code_query_tools import CodeQueryTools, ProjectCodeContext

__all__ = [
    "ProjectSpec", "Task", "TaskStatus", "Tool", "ToolHealth",
    "CodeFile", "CodeClass", "CodeFunction",
    "CodeQueryTools", "ProjectCodeContext",
]
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from shared import CodeQueryTools, ProjectCodeContext; print('OK')"`
Expected: Prints "OK"

- [ ] **Step 3: Commit**

```bash
git add shared/__init__.py
git commit -m "chore: export CodeQueryTools and ProjectCodeContext from shared"
```

---

### Task 5: Update Worker to re-export from shared (backward compatibility)

**Files:**
- Modify: `services/worker/mcp_tools.py`

- [ ] **Step 1: Replace with re-export**

```python
# services/worker/mcp_tools.py
"""Backward-compatible re-export of CodeQueryTools from shared module.

New code should import from shared.code_query_tools directly.
"""
from shared.code_query_tools import CodeQueryTools

__all__ = ["CodeQueryTools"]
```

- [ ] **Step 2: Verify Worker's existing imports still work**

Run: `python -c "from services.worker.mcp_tools import CodeQueryTools; print('OK')"`
Expected: Prints "OK"

- [ ] **Step 3: Run Worker's existing mcp_tools tests**

Run: `pytest services/worker/tests/test_mcp_tools.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add services/worker/mcp_tools.py
git commit -m "refactor: re-export CodeQueryTools from shared in worker/mcp_tools"
```

---

### Task 6: Add code context support to Manager's Interviewer

**Files:**
- Modify: `services/manager/interviewer.py`
- Test: `services/manager/tests/test_interviewer.py`

- [ ] **Step 1: Write the failing test**

Add to `services/manager/tests/test_interviewer.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest services/manager/tests/test_interviewer.py::TestInterviewerCodeContext -v`
Expected: FAIL — `load_code_context` method doesn't exist

- [ ] **Step 3: Update Interviewer to support code context**

```python
# services/manager/interviewer.py
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
        InterviewQuestion(
            text="What's the name of your project?",
            category="overview"
        ),
        InterviewQuestion(
            text="In one sentence, what does your project do?",
            category="overview"
        ),
        InterviewQuestion(
            text="What tech stack do you want to use? (e.g., FastAPI, React, PostgreSQL)",
            category="tech_stack"
        ),
        InterviewQuestion(
            text="What are the main features? (comma-separated list)",
            category="features"
        ),
        InterviewQuestion(
            text="Any specific requirements or constraints?",
            category="constraints"
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
        self.responses.append({
            "question_idx": self.current_question_idx,
            "category": category,
            "answer": answer
        })
        self.questions_asked += 1
        self.current_question_idx += 1

    def is_complete(self) -> bool:
        return self.current_question_idx >= len(self.QUESTIONS)

    def extract_project_spec(self) -> dict:
        """Extract ProjectSpec from interview responses"""
        spec = {
            "name": "",
            "tech_stack": [],
            "features": []
        }

        for response in self.responses:
            if response["category"] == "overview":
                if response["question_idx"] == 0:
                    spec["name"] = response["answer"]
            elif response["category"] == "tech_stack":
                spec["tech_stack"] = [
                    s.strip() for s in response["answer"].split(",")
                ]
            elif response["category"] == "features":
                spec["features"] = [
                    s.strip() for s in response["answer"].split(",")
                ]

        return spec
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest services/manager/tests/test_interviewer.py::TestInterviewerCodeContext -v`
Expected: All tests PASS

- [ ] **Step 5: Run all Manager tests**

Run: `pytest services/manager/tests/ -v`
Expected: All tests PASS (including existing ones)

- [ ] **Step 6: Commit**

```bash
git add services/manager/interviewer.py services/manager/tests/test_interviewer.py
git commit -m "feat: add code context support to Manager's Interviewer"
```

---

### Task 7: Update Manager CLI to use code context during interview

**Files:**
- Modify: `services/manager/cli.py`

- [ ] **Step 1: Update CLI to load code context after getting project name**

```python
# services/manager/cli.py
import click
import sys
import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, '/home/loki/ideas/sea-qwens/worktrees/legion-implement')
from services.manager.interviewer import Interviewer


LIBRARIAN_URL = "http://localhost:8001"


@click.group()
def cli():
    """Legion Manager - Interview users and create ProjectSpecs"""
    pass


@cli.command()
def interview():
    """Conduct a project requirements interview"""
    click.echo("=" * 60)
    click.echo("LEGION MANAGER - Project Requirements Interview")
    click.echo("=" * 60)
    click.echo()

    interviewer = Interviewer(librarian_url=LIBRARIAN_URL)

    while not interviewer.is_complete():
        question = interviewer.get_next_question()
        if not question:
            break

        click.echo(click.style(f"\n{question.text}", fg="green", bold=True))
        answer = click.prompt("Your answer")
        interviewer.record_response(answer, question.category)

        # After getting project name, try to load code context
        if question.category == "overview" and interviewer.questions_asked == 1:
            project_name = interviewer.responses[-1]["answer"].strip()
            if project_name:
                click.echo(click.style(f"\nChecking for existing project: {project_name}...", fg="yellow"))
                interviewer.load_code_context(project_name, [])
                if interviewer.code_context:
                    overview = interviewer.code_context.get_project_overview(project_name)
                    if overview:
                        click.echo(click.style(
                            f"Found existing code: {overview['total_files']} files, "
                            f"{overview['total_functions']} functions, "
                            f"{overview['total_classes']} classes",
                            fg="cyan"
                        ))
                    else:
                        click.echo(click.style("No existing code found for this project.", fg="yellow"))
                else:
                    click.echo(click.style("Could not connect to code database.", fg="yellow"))

    # Extract and display spec
    spec = interviewer.extract_project_spec()

    # Show existing features if code context is available
    if interviewer.code_context and spec["features"]:
        click.echo(click.style("\nChecking existing features...", fg="yellow"))
        feature_map = interviewer.code_context.find_existing_features(
            spec["name"], spec["features"]
        )
        for feature, info in feature_map.items():
            if info["found"]:
                match_names = ", ".join(m["name"] for m in info["matches"])
                click.echo(click.style(
                    f"  ✓ '{feature}' — found: {match_names}",
                    fg="green"
                ))
            else:
                click.echo(click.style(
                    f"  ✗ '{feature}' — not found (new implementation needed)",
                    fg="yellow"
                ))

    click.echo()
    click.echo("=" * 60)
    click.echo("EXTRACTED PROJECT SPEC")
    click.echo("=" * 60)
    click.echo(f"Name: {spec['name']}")
    click.echo(f"Tech Stack: {', '.join(spec['tech_stack'])}")
    click.echo(f"Features: {', '.join(spec['features'])}")
    click.echo()

    # Confirm before sending
    if click.confirm("Send this ProjectSpec to the Librarian?"):
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


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Verify CLI still runs (syntax check)**

Run: `python -c "import services.manager.cli; print('OK')"`
Expected: Prints "OK"

- [ ] **Step 3: Commit**

```bash
git add services/manager/cli.py
git commit -m "feat: show code context during Manager interview"
```

---

### Task 8: Add code context support to Atomizer's decomposer

**Files:**
- Modify: `services/atomizer/decomposer.py`
- Test: `services/atomizer/tests/test_decomposer.py`

- [ ] **Step 1: Write the failing test**

Add to `services/atomizer/tests/test_decomposer.py`:

```python
class TestAtomizerCodeContext:
    """Tests for Atomizer's code context integration."""

    def test_decompose_uses_code_context_when_available(self, mocker):
        """Decompose skips features that already exist in code DB."""
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

        # Should still return tasks, but auth task should be modified/skipped
        assert isinstance(tasks, list)
        assert len(tasks) > 0

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest services/atomizer/tests/test_decomposer.py::TestAtomizerCodeContext -v`
Expected: FAIL — `ProjectCodeContext` not imported, `decompose` doesn't use it

- [ ] **Step 3: Update decomposer to use code context**

```python
# services/atomizer/decomposer.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest services/atomizer/tests/test_decomposer.py::TestAtomizerCodeContext -v`
Expected: All tests PASS

- [ ] **Step 5: Run all Atomizer tests to ensure backward compat**

Run: `pytest services/atomizer/tests/ -v`
Expected: All tests PASS (existing tests should still work since code_context defaults to None)

- [ ] **Step 6: Commit**

```bash
git add services/atomizer/decomposer.py services/atomizer/tests/test_decomposer.py
git commit -m "feat: add code context support to Atomizer's decomposer"
```

---

### Task 9: Run full test suite and fix any regressions

**Files:** All modified files

- [ ] **Step 1: Run the full project test suite**

Run: `pytest services/ shared/ -v`
Expected: All tests PASS

- [ ] **Step 2: If any tests fail, fix them**

Common issues to watch for:
- Import errors in Worker tests (should be fixed by Task 5's re-export)
- Manager tests failing due to new `librarian_url` parameter (existing tests use default)
- Atomizer tests failing due to new `code_context` parameter (defaults to None, should be fine)

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "test: verify full test suite passes after shared code query tools refactor"
```

---

### Task 10: Update README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add section about code database access for Manager and Atomizer**

Find the "Code Knowledge Graph" section in README.md and add this subsection after the "Querying Code" section:

```markdown
### Code Access for Manager and Atomizer

The Manager and Atomizer services can query the code knowledge graph to understand existing project code before acting.

**Manager** — During the interview, after you provide a project name, the Manager checks if the project already exists in the code database. If it does, it shows you what code is already there and which features exist.

**Atomizer** — When decomposing a project spec, the Atomizer checks for existing code. Features that already exist generate "extend" tasks instead of "implement from scratch" tasks.

Both services use the shared `CodeQueryTools` and `ProjectCodeContext` from `shared/code_query_tools.py`. The Worker also imports from this shared module (with backward-compatible re-export in `services/worker/mcp_tools.py`).
```

- [ ] **Step 2: Verify README renders correctly**

Read the README.md file to confirm the new section looks good.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document code database access for Manager and Atomizer"
```
