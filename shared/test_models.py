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
