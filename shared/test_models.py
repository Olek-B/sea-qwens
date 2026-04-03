# shared/test_models.py

from shared.models import ProjectSpec, TaskStatus, Task, Tool, ToolHealth

def test_project_spec_creation():
    spec = ProjectSpec(
        name="Test Project",
        tech_stack=["FastAPI", "PostgreSQL"],
        features=["User auth", "API endpoints"]
    )
    assert spec.name == "Test Project"
    assert len(spec.tech_stack) == 2

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


def test_tool_model_has_adapter_field():
    """Tool model should have an optional adapter field defaulting to empty string."""
    from shared.models import Tool
    tool = Tool(name="qwen-code", command="qwen --non-interactive")
    assert hasattr(tool, "adapter"), "Tool model missing adapter field"
    assert tool.adapter == "", "adapter should default to empty string"


def test_tool_model_with_adapter():
    """Tool model should accept an adapter value."""
    from shared.models import Tool
    tool = Tool(name="qwen-code", command="qwen --non-interactive", adapter="qwen.sh")
    assert tool.adapter == "qwen.sh"


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
