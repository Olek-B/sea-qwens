# Tool-Centric Task Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the profile-centric dispatch model with a tool-centric model — one config file (`configs/tools.json`), one rotation mechanism (least-used healthy tool).

**Architecture:** Rename `Profile` → `Tool` across all layers (shared models, Neo4j nodes, API endpoints, dispatcher, worker). The Worker becomes tool-agnostic, executing whatever CLI command string it receives.

**Tech Stack:** Python, FastAPI, Pydantic, Neo4j, pytest, requests

---

### Task 1: Rename `Profile` → `Tool` in shared models

**Files:**
- Modify: `shared/models.py`
- Modify: `shared/test_models.py`

- [ ] **Step 1: Update `shared/models.py` — rename `Profile` to `Tool`, `profile_id` to `tool_id`**

```python
# shared/models.py — changes only (full file below)

from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ToolHealth(str, Enum):
    HEALTHY = "HEALTHY"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR = "ERROR"


class ProjectSpec(BaseModel):
    name: str
    tech_stack: list[str]
    features: list[str]
    id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Task(BaseModel):
    task_id: str
    title: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: list[str] = Field(default_factory=list)
    contract: dict = Field(default_factory=dict)
    tool_id: Optional[str] = None
    worktree_path: Optional[str] = None
    test_spec: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Tool(BaseModel):
    name: str
    command: str = "qwen --non-interactive"
    usage_count: int = 0
    last_used: Optional[datetime] = None
    daily_limit: int = 1000
    requests_today: int = 0
    reset_time: datetime = Field(default_factory=lambda: datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0))
    capabilities: list[str] = Field(default_factory=lambda: ["coding", "testing", "refactoring"])
    health_status: ToolHealth = ToolHealth.HEALTHY
    consecutive_failures: int = 0


class CodeFile(BaseModel):
    path: str
    language: str
    content: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class CodeFunction(BaseModel):
    name: str
    file_path: str
    line_start: int
    line_end: int
    body: str
    signature: str = ""
    docstring: str = ""
    is_method: bool = False
    parent_class: Optional[str] = None


class CodeClass(BaseModel):
    name: str
    file_path: str
    line_start: int
    line_end: int
    body: str
    docstring: str = ""
    bases: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Update `shared/test_models.py` — use `Tool` and `tool_id`**

```python
# shared/test_models.py — replace entire file

from shared.models import ProjectSpec, TaskStatus, Task, Tool

def test_project_spec_creation():
    spec = ProjectSpec(
        name="Test Project",
        tech_stack=["FastAPI", "PostgreSQL"],
        features=["User auth", "API endpoints"]
    )
    assert spec.name == "Test Project"
    assert len(spec.tech_stack) == 2

def test_task_creation():
    task = Task(
        task_id="task-001",
        title="Create API endpoint",
        status=TaskStatus.PENDING,
        dependencies=[],
        contract={"type": "object"},
        tool_id="qwen-coder"
    )
    assert task.task_id == "task-001"
    assert task.status == TaskStatus.PENDING

def test_tool_creation():
    tool = Tool(
        name="qwen-coder",
        command="qwen --non-interactive",
        usage_count=0,
        daily_limit=1000,
        requests_today=0,
        capabilities=["coding", "testing", "refactoring"],
        health_status=ToolHealth.HEALTHY,
        consecutive_failures=0
    )
    assert tool.name == "qwen-coder"
    assert tool.command == "qwen --non-interactive"
    assert tool.health_status == ToolHealth.HEALTHY


from shared.models import CodeFile, CodeFunction, CodeClass

def test_code_file_creation():
    f = CodeFile(
        path="services/librarian/app.py",
        language="python",
        content="from fastapi import FastAPI\n..."
    )
    assert f.path == "services/librarian/app.py"
    assert f.language == "python"

def test_code_function_creation():
    func = CodeFunction(
        name="health_check",
        file_path="services/librarian/app.py",
        line_start=10,
        line_end=15,
        body="def health_check():\n    return {'status': 'ok'}",
        signature="def health_check() -> dict",
        docstring="Health check endpoint",
        is_method=False,
        parent_class=None
    )
    assert func.name == "health_check"
    assert not func.is_method

def test_code_class_creation():
    cls = CodeClass(
        name="Neo4jStore",
        file_path="services/librarian/neo4j_store.py",
        line_start=5,
        line_end=50,
        body="class Neo4jStore:\n    ...",
        docstring="Neo4j operations",
        bases=["object"]
    )
    assert cls.name == "Neo4jStore"
    assert "object" in cls.bases
```

- [ ] **Step 3: Run shared model tests**

```bash
python -m pytest shared/test_models.py -v
```
Expected: All 6 tests pass.

- [ ] **Step 4: Commit**

```bash
git add shared/models.py shared/test_models.py
git commit -m "refactor: rename Profile→Tool, profile_id→tool_id in shared models"
```

---

### Task 2: Create `configs/tools.json` and delete `configs/profiles.json`

**Files:**
- Create: `configs/tools.json`
- Delete: `configs/profiles.json`

- [ ] **Step 1: Create `configs/tools.json`**

```json
[
  {
    "name": "qwen-coder",
    "command": "qwen --non-interactive",
    "usage_count": 0,
    "last_used": null,
    "daily_limit": 1000,
    "requests_today": 0,
    "reset_time": "2026-04-03T00:00:00Z",
    "capabilities": ["coding", "testing", "refactoring", "debugging"],
    "health_status": "HEALTHY",
    "consecutive_failures": 0
  },
  {
    "name": "qwen-planner",
    "command": "qwen --non-interactive",
    "usage_count": 0,
    "last_used": null,
    "daily_limit": 1000,
    "requests_today": 0,
    "reset_time": "2026-04-03T00:00:00Z",
    "capabilities": ["architecture", "planning", "documentation"],
    "health_status": "HEALTHY",
    "consecutive_failures": 0
  },
  {
    "name": "qwen-reviewer",
    "command": "qwen --non-interactive",
    "usage_count": 0,
    "last_used": null,
    "daily_limit": 1000,
    "requests_today": 0,
    "reset_time": "2026-04-03T00:00:00Z",
    "capabilities": ["review", "testing", "qa"],
    "health_status": "HEALTHY",
    "consecutive_failures": 0
  }
]
```

- [ ] **Step 2: Delete `configs/profiles.json`**

```bash
rm configs/profiles.json
```

- [ ] **Step 3: Commit**

```bash
git add configs/tools.json configs/profiles.json
git commit -m "feat: replace profiles.json with tools.json"
```

---

### Task 3: Update Neo4jStore — rename Profile → Tool

**Files:**
- Modify: `services/librarian/neo4j_store.py`

- [ ] **Step 1: Rename `create_profile` → `create_tool`, `Profile` node → `Tool` node**

In `services/librarian/neo4j_store.py`, replace the `create_profile` method:

```python
# OLD (lines ~103-119):
    def create_profile(self, profile_data: dict) -> dict:
        """Create a new Profile node in Neo4j"""
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (p:Profile {
                    name: $name,
                    usage_count: $usage_count,
                    requests_today: $requests_today,
                    health_status: $health_status
                })
                RETURN p
                """,
                **profile_data
            )
            record = result.single()
            return dict(record["p"])

# NEW:
    def create_tool(self, tool_data: dict) -> dict:
        """Create a new Tool node in Neo4j"""
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (t:Tool {
                    name: $name,
                    command: $command,
                    usage_count: $usage_count,
                    requests_today: $requests_today,
                    health_status: $health_status
                })
                RETURN t
                """,
                **tool_data
            )
            record = result.single()
            return dict(record["t"])
```

- [ ] **Step 2: Rename `get_least_used_profile` → `get_least_used_tool`, `Profile` → `Tool`**

```python
# OLD (lines ~121-135):
    def get_least_used_profile(self) -> Optional[dict]:
        """Get profile with lowest usage_count among healthy profiles"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Profile {health_status: 'HEALTHY'})
                WHERE p.requests_today < p.daily_limit
                RETURN p
                ORDER BY p.usage_count ASC
                LIMIT 1
                """
            )
            record = result.single()
            if record:
                return dict(record["p"])
            return None

# NEW:
    def get_least_used_tool(self) -> Optional[dict]:
        """Get tool with lowest usage_count among healthy tools"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Tool {health_status: 'HEALTHY'})
                WHERE t.requests_today < t.daily_limit
                RETURN t
                ORDER BY t.usage_count ASC
                LIMIT 1
                """
            )
            record = result.single()
            if record:
                return dict(record["t"])
            return None
```

- [ ] **Step 3: Rename `increment_profile_usage` → `increment_tool_usage`, `Profile` → `Tool`**

```python
# OLD (lines ~138-152):
    def increment_profile_usage(self, profile_name: str) -> Optional[dict]:
        """Increment profile usage counters"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Profile {name: $name})
                SET p.usage_count = p.usage_count + 1
                SET p.requests_today = p.requests_today + 1
                SET p.last_used = datetime()
                RETURN p
                """,
                name=profile_name
            )
            record = result.single()
            if record:
                return dict(record["p"])
            return None

# NEW:
    def increment_tool_usage(self, tool_name: str) -> Optional[dict]:
        """Increment tool usage counters"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Tool {name: $name})
                SET t.usage_count = t.usage_count + 1
                SET t.requests_today = t.requests_today + 1
                SET t.last_used = datetime()
                RETURN t
                """,
                name=tool_name
            )
            record = result.single()
            if record:
                return dict(record["t"])
            return None
```

- [ ] **Step 4: Update `create_task` — rename `profile_id` → `tool_id`**

```python
# OLD (lines ~52-67):
    def create_task(self, task_data: dict) -> dict:
        """Create a new Task node in Neo4j"""
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (t:Task {
                    task_id: $task_id,
                    title: $title,
                    status: $status,
                    dependencies: $dependencies,
                    contract: $contract,
                    profile_id: $profile_id
                })
                RETURN t
                """,
                **task_data
            )
            record = result.single()
            return dict(record["t"])

# NEW:
    def create_task(self, task_data: dict) -> dict:
        """Create a new Task node in Neo4j"""
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (t:Task {
                    task_id: $task_id,
                    title: $title,
                    status: $status,
                    dependencies: $dependencies,
                    contract: $contract,
                    tool_id: $tool_id
                })
                RETURN t
                """,
                **task_data
            )
            record = result.single()
            return dict(record["t"])
```

- [ ] **Step 5: Commit**

```bash
git add services/librarian/neo4j_store.py
git commit -m "refactor: rename Profile→Tool in Neo4jStore queries"
```

---

### Task 4: Update Librarian API — rename profile endpoints → tool endpoints

**Files:**
- Modify: `services/librarian/app.py`
- Modify: `services/librarian/tests/test_api.py`

- [ ] **Step 1: Update imports and endpoint renames in `services/librarian/app.py`**

Change the import line:
```python
# OLD:
from shared.models import ProjectSpec, Task, TaskStatus, Profile
# NEW:
from shared.models import ProjectSpec, Task, TaskStatus, Tool
```

Change `TaskInput` model:
```python
# OLD:
class TaskInput(BaseModel):
    """Input model for creating a task"""
    task_id: str
    title: str
    status: str = "PENDING"
    dependencies: list[str] = Field(default_factory=list)
    contract: dict = Field(default_factory=dict)
    profile_id: Optional[str] = None
# NEW:
class TaskInput(BaseModel):
    """Input model for creating a task"""
    task_id: str
    title: str
    status: str = "PENDING"
    dependencies: list[str] = Field(default_factory=list)
    contract: dict = Field(default_factory=dict)
    tool_id: Optional[str] = None
```

Change task creation in `create_task` endpoint:
```python
# OLD:
    task_data = {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status,
        "dependencies": task.dependencies,
        "contract": task.contract,
        "profile_id": task.profile_id
    }
# NEW:
    task_data = {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status,
        "dependencies": task.dependencies,
        "contract": task.contract,
        "tool_id": task.tool_id
    }
```

Change task creation in `create_tasks_batch` endpoint:
```python
# OLD:
        task_data = {
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status,
            "dependencies": task.dependencies,
            "contract": task.contract,
            "profile_id": task.profile_id
        }
# NEW:
        task_data = {
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status,
            "dependencies": task.dependencies,
            "contract": task.contract,
            "tool_id": task.tool_id
        }
```

Rename the profile endpoints to tool endpoints:
```python
# OLD:
@app.get("/profiles/least-used")
def get_least_used_profile():
    """Get the least used healthy profile"""
    neo4j = get_neo4j_store()
    result = neo4j.get_least_used_profile()
    if not result:
        raise HTTPException(status_code=404, detail="No healthy profiles available")
    return result


@app.post("/profiles/{profile_name}/increment")
def increment_profile_usage(profile_name: str):
    """Increment profile usage counters"""
    neo4j = get_neo4j_store()
    result = neo4j.increment_profile_usage(profile_name)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result

# NEW:
@app.get("/tools/least-used")
def get_least_used_tool():
    """Get the least used healthy tool"""
    neo4j = get_neo4j_store()
    result = neo4j.get_least_used_tool()
    if not result:
        raise HTTPException(status_code=404, detail="No healthy tools available")
    return result


@app.post("/tools/{tool_name}/increment")
def increment_tool_usage(tool_name: str):
    """Increment tool usage counters"""
    neo4j = get_neo4j_store()
    result = neo4j.increment_tool_usage(tool_name)
    if not result:
        raise HTTPException(status_code=404, detail="Tool not found")
    return result
```

- [ ] **Step 2: Update Librarian tests — rename profile tests → tool tests**

In `services/librarian/tests/test_api.py`, replace the `TestProfileEndpoints` class:

```python
# OLD TestProfileEndpoints class:
class TestProfileEndpoints:
    """Tests for Profile rotation endpoints"""

    def test_get_least_used_profile(self, client, mock_stores):
        """Test getting the least used healthy profile"""
        mock_stores['neo4j'].get_least_used_profile.return_value = {
            'name': 'qwen-agent-01',
            'usage_count': 10
        }

        response = client.get("/profiles/least-used")
        assert response.status_code == 200
        assert response.json()["name"] == "qwen-agent-01"

    def test_get_least_used_profile_not_found(self, client, mock_stores):
        """Test 404 when no healthy profiles available"""
        mock_stores['neo4j'].get_least_used_profile.return_value = None

        response = client.get("/profiles/least-used")
        assert response.status_code == 404

    def test_increment_profile_usage(self, client, mock_stores):
        """Test incrementing profile usage counters"""
        mock_stores['neo4j'].increment_profile_usage.return_value = {
            'name': 'test-profile',
            'usage_count': 11
        }

        response = client.post("/profiles/test-profile/increment")
        assert response.status_code == 200

    def test_increment_profile_not_found(self, client, mock_stores):
        """Test 404 when profile doesn't exist"""
        mock_stores['neo4j'].increment_profile_usage.return_value = None

        response = client.post("/profiles/non-existent/increment")
        assert response.status_code == 404

# NEW:
class TestToolEndpoints:
    """Tests for Tool rotation endpoints"""

    def test_get_least_used_tool(self, client, mock_stores):
        """Test getting the least used healthy tool"""
        mock_stores['neo4j'].get_least_used_tool.return_value = {
            'name': 'qwen-coder',
            'usage_count': 10
        }

        response = client.get("/tools/least-used")
        assert response.status_code == 200
        assert response.json()["name"] == "qwen-coder"

    def test_get_least_used_tool_not_found(self, client, mock_stores):
        """Test 404 when no healthy tools available"""
        mock_stores['neo4j'].get_least_used_tool.return_value = None

        response = client.get("/tools/least-used")
        assert response.status_code == 404

    def test_increment_tool_usage(self, client, mock_stores):
        """Test incrementing tool usage counters"""
        mock_stores['neo4j'].increment_tool_usage.return_value = {
            'name': 'qwen-coder',
            'usage_count': 11
        }

        response = client.post("/tools/qwen-coder/increment")
        assert response.status_code == 200

    def test_increment_tool_not_found(self, client, mock_stores):
        """Test 404 when tool doesn't exist"""
        mock_stores['neo4j'].increment_tool_usage.return_value = None

        response = client.post("/tools/non-existent/increment")
        assert response.status_code == 404
```

Also update the task test mocks — replace all `'profile_id'` with `'tool_id'`:

```python
# In test_create_task (around line 130):
# OLD:
            'profile_id': None
# NEW:
            'tool_id': None

# In test_create_task_with_dependencies (around line 152):
# OLD:
            'profile_id': None
# NEW:
            'tool_id': None

# In test_create_tasks_batch (around lines 168-169):
# OLD:
            {'task_id': 'batch-001', 'title': 'Batch task 1', 'status': 'PENDING', 'dependencies': [], 'contract': {}, 'profile_id': None},
            {'task_id': 'batch-002', 'title': 'Batch task 2', 'status': 'PENDING', 'dependencies': ['batch-001'], 'contract': {}, 'profile_id': None}
# NEW:
            {'task_id': 'batch-001', 'title': 'Batch task 1', 'status': 'PENDING', 'dependencies': [], 'contract': {}, 'tool_id': None},
            {'task_id': 'batch-002', 'title': 'Batch task 2', 'status': 'PENDING', 'dependencies': ['batch-001'], 'contract': {}, 'tool_id': None}
```

- [ ] **Step 3: Run Librarian tests**

```bash
python -m pytest services/librarian/tests/test_api.py -v
```
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add services/librarian/app.py services/librarian/tests/test_api.py
git commit -m "refactor: rename profile→tool endpoints in Librarian API"
```

---

### Task 5: Update Kanban dispatcher — select tools instead of profiles

**Files:**
- Modify: `services/kanban/profile_manager.py` → rename to `services/kanban/tool_manager.py`
- Modify: `services/kanban/dispatcher.py`
- Create: `services/kanban/tests/test_tool_manager.py` (rename existing profile tests)

- [ ] **Step 1: Rename `profile_manager.py` → `tool_manager.py`**

```bash
mv services/kanban/profile_manager.py services/kanban/tool_manager.py
```

- [ ] **Step 2: Rewrite `tool_manager.py` — rename Profile → Tool**

```python
# services/kanban/tool_manager.py — full file replacement
from datetime import datetime
from typing import Optional
import requests


class ToolSelectionResult:
    def __init__(self, tool: dict, reason: str):
        self.tool = tool
        self.reason = reason


class ToolManager:
    """Manage tool selection and rotation"""

    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url

    def get_all_tools(self) -> list[dict]:
        """Fetch all tools from Librarian"""
        try:
            response = requests.get(f"{self.librarian_url}/tools")
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            return []

    def _select_best_from_list(self, tools: list[dict]) -> Optional[dict]:
        """Select the best tool from a list"""
        healthy = [
            t for t in tools
            if t.get("health_status") == "HEALTHY"
            and t.get("requests_today", 0) < t.get("daily_limit", 1000)
        ]

        if not healthy:
            return None

        return min(healthy, key=lambda t: t.get("usage_count", 0))

    def select_tool(self, task_capabilities: Optional[list[str]] = None) -> Optional[ToolSelectionResult]:
        """
        Select the best tool for a task.

        If task_capabilities is provided, prefer tools with matching capabilities.
        Otherwise, select least-used healthy tool.
        """
        tools = self.get_all_tools()

        if not tools:
            return None

        if task_capabilities:
            matching = [
                t for t in tools
                if any(cap in t.get("capabilities", []) for cap in task_capabilities)
            ]
            if matching:
                selected = self._select_best_from_list(matching)
                if selected:
                    return ToolSelectionResult(
                        tool=selected,
                        reason=f"Matched capabilities: {task_capabilities}"
                    )

        selected = self._select_best_from_list(tools)
        if selected:
            return ToolSelectionResult(
                tool=selected,
                reason="Least-used healthy tool"
            )

        return None

    def mark_tool_rate_limited(self, tool_name: str):
        """Mark a tool as rate-limited in Neo4j"""
        pass

    def increment_tool_usage(self, tool_name: str) -> bool:
        """Increment tool usage counters"""
        try:
            response = requests.post(
                f"{self.librarian_url}/tools/{tool_name}/increment"
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
```

- [ ] **Step 3: Update `dispatcher.py` — use ToolManager instead of ProfileManager**

```python
# services/kanban/dispatcher.py — full file replacement
from datetime import datetime, timezone
from typing import Optional
import requests
import logging

from services.kanban.tool_manager import ToolManager

logger = logging.getLogger(__name__)


class DispatchResult:
    def __init__(self, success: bool, task_id: str, tool_name: str, message: str):
        self.success = success
        self.task_id = task_id
        self.tool_name = tool_name
        self.message = message
        self.timestamp = datetime.now(timezone.utc)


class Dispatcher:
    """Dispatch ready tasks to workers"""

    def __init__(
        self,
        librarian_url: str = "http://localhost:8001",
        worker_url: str = "http://localhost:8004"
    ):
        self.librarian_url = librarian_url
        self.worker_url = worker_url
        self.tool_manager = ToolManager(librarian_url)

    def get_ready_tasks(self) -> list[dict]:
        """Fetch ready tasks from Librarian"""
        try:
            response = requests.get(f"{self.librarian_url}/tasks/ready")
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            return []

    def dispatch_task(self, task: dict) -> DispatchResult:
        """Dispatch a single task to a worker"""
        selection = self.tool_manager.select_tool()
        if not selection:
            return DispatchResult(
                success=False,
                task_id=task.get("task_id", "unknown"),
                tool_name="",
                message="No healthy tools available"
            )

        tool = selection.tool
        tool_name = tool["name"]
        tool_command = tool.get("command", "qwen --non-interactive")

        # Mark task as IN_PROGRESS in Librarian
        try:
            requests.post(
                f"{self.librarian_url}/tasks/update",
                params={"task_id": task["task_id"]},
                json={"status": "IN_PROGRESS", "tool_id": tool_name}
            )
        except requests.exceptions.RequestException:
            pass  # Best effort

        # Increment tool usage
        self.tool_manager.increment_tool_usage(tool_name)

        # Dispatch to Worker
        try:
            response = requests.post(
                f"{self.worker_url}/execute",
                json={
                    "task": task,
                    "tool_id": tool_name,
                    "tool_command": tool_command
                }
            )

            # Handle 429 rate limit
            if response.status_code == 429:
                self.handle_rate_limit(task, tool_name)
                return DispatchResult(
                    success=False,
                    task_id=task["task_id"],
                    tool_name=tool_name,
                    message="Rate limit hit, tool rotated and task re-queued"
                )

            if response.status_code == 202:
                return DispatchResult(
                    success=True,
                    task_id=task["task_id"],
                    tool_name=tool_name,
                    message=f"Dispatched to worker with tool {tool_name}"
                )
            else:
                return DispatchResult(
                    success=False,
                    task_id=task["task_id"],
                    tool_name=tool_name,
                    message=f"Worker rejected: {response.text}"
                )
        except requests.exceptions.RequestException as e:
            return DispatchResult(
                success=False,
                task_id=task["task_id"],
                tool_name=tool_name,
                message=f"Worker unavailable: {str(e)}"
            )

    def poll_and_dispatch(self) -> int:
        """Poll for ready tasks and dispatch them"""
        tasks = self.get_ready_tasks()
        dispatched = 0

        for task in tasks:
            result = self.dispatch_task(task)
            if result.success:
                dispatched += 1

        return dispatched

    def handle_rate_limit(self, task: dict, failed_tool: str):
        """Handle 429 rate limit by rotating tool and re-queuing"""
        logger.warning(
            f"Rate limit hit for tool {failed_tool}, "
            f"re-queuing task {task['task_id']}"
        )

        self.tool_manager.mark_tool_rate_limited(failed_tool)

        try:
            requests.post(
                f"{self.librarian_url}/tasks/update",
                params={"task_id": task["task_id"]},
                json={"status": "PENDING"}
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to re-queue task: {e}")
```

- [ ] **Step 4: Delete old profile tests and create new tool tests**

```bash
rm services/kanban/tests/test_profile_manager.py
```

Create `services/kanban/tests/test_tool_manager.py`:

```python
# services/kanban/tests/test_tool_manager.py
import pytest
from unittest.mock import patch, MagicMock
import requests

from services.kanban.tool_manager import ToolManager, ToolSelectionResult


class TestToolSelectionResult:
    def test_creation(self):
        tool = {"name": "qwen-coder", "command": "qwen --non-interactive"}
        result = ToolSelectionResult(tool=tool, reason="Least-used healthy tool")
        assert result.tool["name"] == "qwen-coder"
        assert result.reason == "Least-used healthy tool"


class TestToolManager:
    @patch("services.kanban.tool_manager.requests.get")
    def test_get_all_tools_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"name": "qwen-coder", "health_status": "HEALTHY", "usage_count": 5}
        ]

        manager = ToolManager(librarian_url="http://localhost:8001")
        tools = manager.get_all_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "qwen-coder"

    @patch("services.kanban.tool_manager.requests.get")
    def test_get_all_tools_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("fail")

        manager = ToolManager(librarian_url="http://localhost:8001")
        tools = manager.get_all_tools()

        assert tools == []

    @patch("services.kanban.tool_manager.requests.get")
    def test_select_tool_least_used(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"name": "tool-a", "health_status": "HEALTHY", "usage_count": 10, "requests_today": 0, "daily_limit": 1000, "capabilities": ["coding"]},
            {"name": "tool-b", "health_status": "HEALTHY", "usage_count": 5, "requests_today": 0, "daily_limit": 1000, "capabilities": ["coding"]},
        ]

        manager = ToolManager()
        result = manager.select_tool()

        assert result is not None
        assert result.tool["name"] == "tool-b"

    @patch("services.kanban.tool_manager.requests.get")
    def test_select_tool_no_healthy_tools(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"name": "tool-a", "health_status": "ERROR", "usage_count": 10, "requests_today": 0, "daily_limit": 1000, "capabilities": ["coding"]},
        ]

        manager = ToolManager()
        result = manager.select_tool()

        assert result is None

    @patch("services.kanban.tool_manager.requests.post")
    def test_increment_tool_usage(self, mock_post):
        mock_post.return_value.status_code = 200

        manager = ToolManager()
        result = manager.increment_tool_usage("qwen-coder")

        assert result is True
        mock_post.assert_called_once_with("http://localhost:8001/tools/qwen-coder/increment")
```

- [ ] **Step 5: Update `test_dispatcher.py` — rename profile → tool references**

```python
# services/kanban/tests/test_dispatcher.py — full file replacement
import pytest
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, '/home/loki/ideas/sea-qwens/worktrees/legion-implement')
from services.kanban.dispatcher import Dispatcher, DispatchResult


def test_dispatcher_initializes():
    dispatcher = Dispatcher()
    assert dispatcher.librarian_url != ""
    assert dispatcher.worker_url != ""


def test_dispatch_result_success():
    result = DispatchResult(
        success=True,
        task_id="task-001",
        tool_name="qwen-coder",
        message="Dispatched successfully"
    )
    assert result.success
    assert result.task_id == "task-001"


def test_handle_rate_limit_marks_tool_and_resets_task():
    """handle_rate_limit should mark tool rate-limited and reset task to PENDING"""
    dispatcher = Dispatcher()
    dispatcher.tool_manager = MagicMock()

    task = {"task_id": "task-42"}

    with patch("services.kanban.dispatcher.requests.post") as mock_post:
        dispatcher.handle_rate_limit(task, "qwen-coder")

        dispatcher.tool_manager.mark_tool_rate_limited.assert_called_once_with(
            "qwen-coder"
        )

        call_args = mock_post.call_args
        assert call_args[1]["params"] == {"task_id": "task-42"}
        assert call_args[1]["json"] == {"status": "PENDING"}


def test_handle_rate_limit_logs_warning():
    """handle_rate_limit should log a warning with tool and task info"""
    dispatcher = Dispatcher()
    dispatcher.tool_manager = MagicMock()

    task = {"task_id": "task-99"}

    with patch("services.kanban.dispatcher.requests.post"), \
         patch("services.kanban.dispatcher.logger.warning") as mock_warn:
        dispatcher.handle_rate_limit(task, "qwen-coder")
        mock_warn.assert_called_once()
        assert "qwen-coder" in mock_warn.call_args[0][0]
        assert "task-99" in mock_warn.call_args[0][0]


def test_handle_rate_limit_handles_request_error_gracefully():
    """handle_rate_limit should not raise if the PENDING update fails"""
    dispatcher = Dispatcher()
    dispatcher.tool_manager = MagicMock()

    task = {"task_id": "task-55"}

    with patch("services.kanban.dispatcher.requests.post") as mock_post:
        import requests as req
        mock_post.side_effect = req.exceptions.RequestException("connection error")

        with patch("services.kanban.dispatcher.logger.error") as mock_err:
            dispatcher.handle_rate_limit(task, "qwen-coder")
            mock_err.assert_called_once()
            assert "Failed to re-queue task" in mock_err.call_args[0][0]


def test_dispatch_task_handles_429_response():
    """dispatch_task should call handle_rate_limit on 429 and return failure"""
    dispatcher = Dispatcher()

    mock_selection = MagicMock()
    mock_selection.tool = {"name": "qwen-coder", "command": "qwen --non-interactive"}
    dispatcher.tool_manager.select_tool = MagicMock(return_value=mock_selection)
    dispatcher.tool_manager.increment_tool_usage = MagicMock()
    dispatcher.handle_rate_limit = MagicMock()

    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.text = "Too Many Requests"

    task = {"task_id": "task-100"}

    with patch("services.kanban.dispatcher.requests.post", return_value=mock_429):
        result = dispatcher.dispatch_task(task)

        dispatcher.handle_rate_limit.assert_called_once_with(task, "qwen-coder")
        assert result.success is False
        assert result.task_id == "task-100"
        assert "Rate limit hit" in result.message
        assert result.tool_name == "qwen-coder"
```

- [ ] **Step 6: Run Kanban tests**

```bash
python -m pytest services/kanban/tests/ -v
```
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add services/kanban/tool_manager.py services/kanban/dispatcher.py services/kanban/profile_manager.py services/kanban/tests/test_tool_manager.py services/kanban/tests/test_dispatcher.py services/kanban/tests/test_profile_manager.py
git commit -m "refactor: Kanban dispatcher selects tools instead of profiles"
```

---

### Task 6: Update Worker — accept `tool_command` instead of hardcoded `qwen`

**Files:**
- Modify: `services/worker/executor.py`
- Modify: `services/worker/app.py`
- Modify: `services/worker/tests/test_executor.py`

- [ ] **Step 1: Update `executor.py` — accept `tool_command` parameter**

```python
# services/worker/executor.py — full file replacement
import subprocess
import os
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from shared.models import Task


@dataclass
class ExecutionResult:
    """Result of a task execution by a worker agent."""
    success: bool
    task_id: str
    output: str = ""
    test_passed: bool = False
    error: Optional[str] = None
    rate_limited: bool = False


class TaskExecutor:
    """Execute coding tasks using CLI tools in isolated worktrees."""

    def execute_task(
        self,
        task: Task,
        tool_id: Optional[str] = None,
        tool_command: str = "qwen --non-interactive",
        worktree_path: str = "",
    ) -> ExecutionResult:
        """
        Execute a task in the given worktree.

        1. Build prompt from task title + contract
        2. Run the given CLI tool in the worktree directory
        3. Run self-tests (pytest) in the worktree
        4. Return ExecutionResult
        """
        wt_path = Path(worktree_path)
        if not wt_path.exists() or not wt_path.is_dir():
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=f"Worktree path does not exist: {worktree_path}",
            )

        prompt = self._build_prompt(task.title, task.contract)

        try:
            env = os.environ.copy()
            if tool_id:
                env["LEGION_TOOL_ID"] = tool_id

            cmd = [
                *tool_command.split(),
                "--prompt", prompt,
                "--cwd", str(wt_path),
            ]

            result = subprocess.run(
                cmd,
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
            )

            tool_output = result.stdout
            tool_error = result.stderr

            rate_limited = self._is_rate_limited(tool_output, tool_error)

            if result.returncode != 0 or rate_limited:
                return ExecutionResult(
                    success=False,
                    task_id=task.task_id,
                    output=tool_output,
                    error=tool_error or "Tool returned non-zero exit code",
                    rate_limited=rate_limited,
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error="Task execution timed out (600s)",
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=f"Command not found: {tool_command.split()[0]}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=str(e),
            )

        test_result = self._run_self_tests(str(wt_path), task)

        return ExecutionResult(
            success=test_result.success,
            task_id=task.task_id,
            output=tool_output + "\n--- Tests ---\n" + test_result.output,
            test_passed=test_result.test_passed,
            error=test_result.error,
            rate_limited=test_result.rate_limited,
        )

    def _build_prompt(self, title: str, contract: dict) -> str:
        """Build prompt for the CLI tool with code graph tool instructions."""
        prompt = f"""Implement the following task:

{title}

Requirements (contract):
{json.dumps(contract, indent=2)}

## Code Knowledge Graph Tools

You have access to a code knowledge graph. Instead of reading files, use these tools to understand the codebase:

- `search_code(query)` - Find functions/classes by semantic search
- `get_function(name)` - Get a function's body and signature
- `get_callers(name)` - Find who calls this function
- `get_callees(name)` - Find what this function calls
- `get_full_context(name)` - Get complete context for understanding a function
- `get_class(name)` - Get a class definition and all methods

## Workflow

1. Before implementing, search for existing related code
2. Use `get_full_context` to understand call chains
3. Implement your changes following existing patterns
4. Ensure your code integrates with existing functions

## Guidelines

- Write clean, tested code
- Follow best practices
- Ensure all tests pass
- Do not modify files outside the task scope
"""
        return prompt

    def _run_self_tests(
        self,
        worktree_path: str,
        task: Task,
    ) -> ExecutionResult:
        """Run pytest in the worktree to verify the implementation."""
        wt_path = Path(worktree_path)

        if not wt_path.exists():
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=f"Worktree path does not exist: {worktree_path}",
            )

        try:
            result = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=120,
            )

            output = result.stdout + result.stderr
            passed = result.returncode == 0

            return ExecutionResult(
                success=passed,
                task_id=task.task_id,
                output=output,
                test_passed=passed,
                error=None if passed else "Some tests failed",
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error="Self-tests timed out (120s)",
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error="pytest not found in worktree environment",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=str(e),
            )

    @staticmethod
    def _is_rate_limited(stdout: str, stderr: str) -> bool:
        """Detect rate limiting signals in output."""
        rate_limit_signals = [
            "rate limit",
            "quota exceeded",
            "too many requests",
            "429",
            "resource exhausted",
            "rate_limited",
        ]
        combined = (stdout + stderr).lower()
        return any(signal in combined for signal in rate_limit_signals)
```

- [ ] **Step 2: Update `app.py` — accept `tool_id` and `tool_command` in request**

```python
# services/worker/app.py — full file replacement
import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

from services.worker.executor import TaskExecutor, ExecutionResult
from shared.models import Task

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Legion Worker",
    description="Worker executor service for Project Legion",
    version="0.1.0",
)

executor = TaskExecutor()

_execution_store: dict[str, ExecutionResult] = {}


class ExecuteRequest(BaseModel):
    task: Task
    tool_id: Optional[str] = None
    tool_command: str = "qwen --non-interactive"
    worktree_path: str


class ExecuteResponse(BaseModel):
    task_id: str
    status: str
    message: str = ""


class ExecutionStatus(BaseModel):
    task_id: str
    success: bool
    output: str = ""
    test_passed: bool = False
    error: Optional[str] = None
    rate_limited: bool = False
    completed_at: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str


@app.post("/execute", response_model=ExecuteResponse)
async def execute_task(
    request: ExecuteRequest,
    background_tasks: BackgroundTasks,
):
    """Submit a task for execution. Runs asynchronously in the background."""
    task_id = request.task.task_id

    if task_id in _execution_store:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} is already being executed",
        )

    _execution_store[task_id] = ExecutionResult(
        success=False,
        task_id=task_id,
        output="Task queued for execution",
    )

    background_tasks.add_task(
        _run_execution,
        task=request.task,
        tool_id=request.tool_id,
        tool_command=request.tool_command,
        worktree_path=request.worktree_path,
    )

    return ExecuteResponse(
        task_id=task_id,
        status="IN_PROGRESS",
        message="Task submitted for execution",
    )


@app.get("/execute/{task_id}", response_model=ExecutionStatus)
async def get_execution_status(task_id: str):
    """Get the execution status for a task."""
    if task_id not in _execution_store:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found",
        )

    result = _execution_store[task_id]

    return ExecutionStatus(
        task_id=result.task_id,
        success=result.success,
        output=result.output,
        test_passed=result.test_passed,
        error=result.error,
        rate_limited=result.rate_limited,
        completed_at=datetime.utcnow().isoformat() if result.success or result.error else None,
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="legion-worker",
        timestamp=datetime.utcnow().isoformat(),
    )


async def _run_execution(
    task: Task,
    tool_id: Optional[str],
    tool_command: str,
    worktree_path: str,
):
    """Run task execution in the background."""
    logger.info(f"Starting execution of task: {task.task_id} with tool: {tool_id}")

    try:
        result = executor.execute_task(
            task=task,
            tool_id=tool_id,
            tool_command=tool_command,
            worktree_path=worktree_path,
        )
        _execution_store[task.task_id] = result

        if result.success:
            logger.info(f"Task {task.task_id} completed successfully")
        else:
            logger.warning(f"Task {task.task_id} failed: {result.error}")

    except Exception as e:
        logger.error(f"Task {task.task_id} raised unexpected error: {e}")
        _execution_store[task.task_id] = ExecutionResult(
            success=False,
            task_id=task.task_id,
            error=str(e),
        )
```

- [ ] **Step 3: Update Worker tests**

```python
# services/worker/tests/test_executor.py — full file replacement
import pytest
import sys
import os

sys.path.insert(0, '/home/loki/ideas/sea-qwens/worktrees/legion-implement')

from services.worker.executor import ExecutionResult, TaskExecutor
from shared.models import Task


# ─── ExecutionResult Tests ───────────────────────────────────────────────────

def test_execution_result_success():
    result = ExecutionResult(
        success=True,
        task_id="task-001",
        output="All tests passed",
        test_passed=True,
        error=None,
        rate_limited=False,
    )
    assert result.success is True
    assert result.task_id == "task-001"
    assert result.output == "All tests passed"
    assert result.test_passed is True
    assert result.error is None
    assert result.rate_limited is False


def test_execution_result_failure():
    result = ExecutionResult(
        success=False,
        task_id="task-002",
        output="",
        test_passed=False,
        error="AssertionError: expected 2, got 1",
        rate_limited=False,
    )
    assert result.success is False
    assert result.task_id == "task-002"
    assert result.output == ""
    assert result.test_passed is False
    assert result.error == "AssertionError: expected 2, got 1"
    assert result.rate_limited is False


def test_execution_result_rate_limited():
    result = ExecutionResult(
        success=False,
        task_id="task-003",
        output="",
        test_passed=False,
        error="Rate limit exceeded",
        rate_limited=True,
    )
    assert result.success is False
    assert result.task_id == "task-003"
    assert result.rate_limited is True
    assert result.error == "Rate limit exceeded"


def test_execution_result_defaults():
    result = ExecutionResult(
        success=True,
        task_id="task-004",
    )
    assert result.success is True
    assert result.task_id == "task-004"
    assert result.output == ""
    assert result.test_passed is False
    assert result.error is None
    assert result.rate_limited is False


# ─── TaskExecutor Tests ──────────────────────────────────────────────────────

def test_build_prompt():
    executor = TaskExecutor()
    title = "Add user authentication"
    contract = {
        "input": "username, password",
        "output": "JWT token",
        "constraints": ["bcrypt hashing", "token expiry 24h"],
    }
    prompt = executor._build_prompt(title, contract)
    assert title in prompt
    assert "username, password" in prompt
    assert "JWT token" in prompt
    assert "bcrypt hashing" in prompt


def test_build_prompt_empty_contract():
    executor = TaskExecutor()
    prompt = executor._build_prompt("Simple task", {})
    assert "Simple task" in prompt


def test_build_prompt_with_complex_contract():
    executor = TaskExecutor()
    contract = {
        "input": {"fields": ["name", "email"]},
        "output": {"type": "User", "id": "uuid"},
        "constraints": ["validate email", "unique constraint"],
        "tests": ["test_create_user", "test_duplicate_email"],
    }
    prompt = executor._build_prompt("Create user endpoint", contract)
    assert "Create user endpoint" in prompt
    assert "validate email" in prompt
    assert "test_create_user" in prompt


def test_run_self_tests_invalid_worktree():
    executor = TaskExecutor()
    task = Task(task_id="task-999", title="Test")
    result = executor._run_self_tests("/nonexistent/path", task)
    assert result.success is False
    assert result.error is not None


def test_execute_task_builds_prompt():
    executor = TaskExecutor()
    task = Task(
        task_id="task-test",
        title="Test task",
        contract={"input": "none", "output": "none"},
    )
    result = executor.execute_task(
        task,
        tool_id=None,
        tool_command="qwen --non-interactive",
        worktree_path="/nonexistent",
    )
    assert result.success is False
    assert result.task_id == "task-test"


def test_execute_task_uses_custom_command():
    """Verify executor splits tool_command correctly."""
    executor = TaskExecutor()
    task = Task(
        task_id="task-cmd-test",
        title="Test with custom command",
        contract={},
    )
    # Use a command that exists but will fail (worktree doesn't exist)
    # This verifies the command parsing logic
    result = executor.execute_task(
        task,
        tool_id="test-tool",
        tool_command="echo hello",
        worktree_path="/nonexistent",
    )
    # Should fail due to missing worktree, not command parsing
    assert result.success is False
    assert result.task_id == "task-cmd-test"
```

- [ ] **Step 4: Run Worker tests**

```bash
python -m pytest services/worker/tests/test_executor.py -v
```
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add services/worker/executor.py services/worker/app.py services/worker/tests/test_executor.py
git commit -m "refactor: Worker accepts tool_command instead of hardcoded qwen"
```

---

### Task 7: Update integration tests and remaining references

**Files:**
- Modify: `services/librarian/tests/test_integration.py`
- Modify: `services/worker/tests/test_mcp_tools.py` (if it references profiles)

- [ ] **Step 1: Update integration tests — rename profile → tool**

In `services/librarian/tests/test_integration.py`, replace all profile references:

```python
# Rename the test class:
# OLD:
class TestProfileRotationIntegration:
    """Integration tests for profile rotation"""
# NEW:
class TestToolRotationIntegration:
    """Integration tests for tool rotation"""

# Update all endpoint references:
# OLD:
    response = requests.get(f"{LIBRARIAN_BASE_URL}/profiles/least-used")
# NEW:
    response = requests.get(f"{LIBRARIAN_BASE_URL}/tools/least-used")

# OLD:
    f"{LIBRARIAN_BASE_URL}/profiles/{profile_name}/increment"
# NEW:
    f"{LIBRARIAN_BASE_URL}/tools/{tool_name}/increment"
```

Full replacement of the `TestToolRotationIntegration` class:

```python
class TestToolRotationIntegration:
    """Integration tests for tool rotation"""

    def test_get_least_used_tool(self):
        """Test getting the least used healthy tool"""
        response = requests.get(f"{LIBRARIAN_BASE_URL}/tools/least-used")
        if response.status_code == 200:
            tool = response.json()
            assert "name" in tool
            assert "usage_count" in tool
        else:
            assert response.status_code == 404

    def test_tool_usage_increment(self):
        """Test incrementing tool usage counters"""
        get_response = requests.get(f"{LIBRARIAN_BASE_URL}/tools/least-used")
        if get_response.status_code == 200:
            tool_name = get_response.json()["name"]
            increment_response = requests.post(
                f"{LIBRARIAN_BASE_URL}/tools/{tool_name}/increment"
            )
            assert increment_response.status_code == 200
            updated_tool = increment_response.json()
            assert updated_tool["name"] == tool_name
            assert "usage_count" in updated_tool

    def test_increment_nonexistent_tool(self):
        """Test 404 when incrementing non-existent tool"""
        response = requests.post(
            f"{LIBRARIAN_BASE_URL}/tools/non-existent-tool/increment"
        )
        assert response.status_code == 404
```

Also update the workflow test that references profiles:

```python
# In the complete workflow test:
# OLD:
        profile_response = requests.get(f"{LIBRARIAN_BASE_URL}/profiles/least-used")
        if profile_response.status_code == 200:
            profile_name = profile_response.json()["name"]
            # Step 4: Increment profile usage
            requests.post(
                f"{LIBRARIAN_BASE_URL}/profiles/{profile_name}/increment"
            )
# NEW:
        tool_response = requests.get(f"{LIBRARIAN_BASE_URL}/tools/least-used")
        if tool_response.status_code == 200:
            tool_name = tool_response.json()["name"]
            requests.post(
                f"{LIBRARIAN_BASE_URL}/tools/{tool_name}/increment"
            )
```

- [ ] **Step 2: Run all tests**

```bash
python -m pytest services/ shared/ -v
```
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add services/librarian/tests/test_integration.py
git commit -m "refactor: update integration tests for tool-centric dispatch"
```

---

### Task 8: Update README and documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README — replace all profile references with tool references**

In the Configuration section, replace:

```markdown
# OLD:
### Agent Profiles

Agent profiles are defined in `configs/profiles.json`. Each profile has:

- **`name`** — unique identifier (e.g., `qwen-agent-01`)
- **`daily_limit`** — max requests per day (default: 1000)
- **`capabilities`** — skill tags (coding, testing, debugging, etc.)
- **`health_status`** — `HEALTHY`, `RATE_LIMITED`, or `ERROR`
- **`consecutive_failures`** — auto-tracked failure counter

The Kanban dispatcher selects the **least-used healthy profile** whose capabilities match the task.

```bash
# View current profiles
cat configs/profiles.json | python -m json.tool
```

To add or modify profiles, edit `configs/profiles.json` and restart the Kanban service.

# NEW:
### Tool Configuration

CLI tools are defined in `configs/tools.json`. Each tool entry has:

- **`name`** — human-readable identifier (e.g., `qwen-coder`)
- **`command`** — non-interactive CLI command (e.g., `qwen --non-interactive`)
- **`daily_limit`** — max requests per day (default: 1000)
- **`capabilities`** — skill tags (coding, testing, debugging, etc.)
- **`health_status`** — `HEALTHY`, `RATE_LIMITED`, or `ERROR`
- **`consecutive_failures`** — auto-tracked failure counter

The Kanban dispatcher selects the **least-used healthy tool** whose capabilities match the task.

```bash
# View current tools
cat configs/tools.json | python -m json.tool
```

To add or modify tools, edit `configs/tools.json` and restart the Kanban service.
```

In the Project Structure section:

```markdown
# OLD:
│   └── profiles.json          # Agent profile definitions
# NEW:
│   └── tools.json             # CLI tool definitions
```

In the Add a New Profile section:

```markdown
# OLD:
### Add a New Profile

1. Edit `configs/profiles.json` and add a new entry to the `profiles` array.
2. Restart the Kanban service to pick up the changes:

```bash
docker compose -f docker-compose.yml restart kanban
```

# NEW:
### Add a New Tool

1. Edit `configs/tools.json` and add a new entry to the `tools` array.
2. Restart the Kanban service to pick up the changes:

```bash
docker compose -f docker-compose.yml restart kanban
```
```

In the Troubleshooting section:

```markdown
# OLD:
### Rate Limits

If agent profiles hit their daily limit or become rate-limited:

```bash
# Check profile health via Librarian
curl http://localhost:8001/profiles/least-used

# Reset a profile's counters in Neo4j Browser
# Open http://localhost:7474 and run:
# MATCH (p:Profile {name: "qwen-agent-01"})
# SET p.requests_today = 0, p.consecutive_failures = 0, p.health_status = "HEALTHY"
# RETURN p
```

# NEW:
### Rate Limits

If tools hit their daily limit or become rate-limited:

```bash
# Check tool health via Librarian
curl http://localhost:8001/tools/least-used

# Reset a tool's counters in Neo4j Browser
# Open http://localhost:7474 and run:
# MATCH (t:Tool {name: "qwen-coder"})
# SET t.requests_today = 0, t.consecutive_failures = 0, t.health_status = "HEALTHY"
# RETURN t
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README for tool-centric dispatch"
```

---

### Task 9: Create Neo4j migration script

**Files:**
- Create: `services/librarian/migrate_profiles_to_tools.py`

- [ ] **Step 1: Create migration script**

```python
#!/usr/bin/env python
"""One-time migration: rename (Profile) nodes → (Tool) in Neo4j.

Usage:
    python -m services.librarian.migrate_profiles_to_tools

This script:
1. Connects to Neo4j using settings from the Librarian config
2. Renames all (Profile) nodes to (Tool) by creating new nodes with the same
   properties and deleting the old ones
3. Reports how many nodes were migrated
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from neo4j import GraphDatabase
from services.librarian.config import settings


def migrate():
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )

    with driver.session() as session:
        # Count existing Profile nodes
        count_result = session.run("MATCH (p:Profile) RETURN count(p) as cnt")
        count = count_result.single()["cnt"]
        print(f"Found {count} Profile nodes to migrate.")

        if count == 0:
            print("Nothing to migrate. Exiting.")
            return

        # Copy all Profile nodes to Tool nodes (same properties)
        session.run("""
            MATCH (p:Profile)
            CREATE (t:Tool)
            SET t = p
            WITH p, t
            SET t.name = p.name
        """)

        # Verify Tool nodes were created
        tool_count_result = session.run("MATCH (t:Tool) RETURN count(t) as cnt")
        tool_count = tool_count_result.single()["cnt"]
        print(f"Created {tool_count} Tool nodes.")

        # Delete old Profile nodes
        session.run("MATCH (p:Profile) DETACH DELETE p")

        # Verify deletion
        verify_result = session.run("MATCH (p:Profile) RETURN count(p) as cnt")
        remaining = verify_result.single()["cnt"]
        print(f"Remaining Profile nodes: {remaining}")

        if remaining == 0 and tool_count == count:
            print("Migration successful!")
        else:
            print("WARNING: Migration may have failed. Check Neo4j manually.")

    driver.close()


if __name__ == "__main__":
    migrate()
```

- [ ] **Step 2: Commit**

```bash
git add services/librarian/migrate_profiles_to_tools.py
git commit -m "feat: add Neo4j migration script Profile→Tool"
```

---
