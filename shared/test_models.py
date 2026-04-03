from shared.models import ProjectSpec, TaskStatus, Task, Profile

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
        profile_id="qwen-agent-01"
    )
    assert task.task_id == "task-001"
    assert task.status == TaskStatus.PENDING


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
