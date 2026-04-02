# Project Legion Plan 2: Manager + Atomizer Services

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the user interview service (Manager) that extracts requirements via LLM, and the Atomizer service that decomposes projects into atomic tasks with contracts and dependencies.

**Architecture:** Manager is a CLI tool that conducts conversational interviews using LLM. Atomizer is a FastAPI service that pulls ProjectSpecs and uses LLM to generate task graphs with JSON Schema contracts and test specifications.

**Tech Stack:** Python 3.11+, FastAPI, Click (CLI), OpenAI-compatible API (for Qwen), Pydantic, pytest

---

## File Structure

```
/legion-root/
├── services/
│   ├── manager/
│   │   ├── cli.py            # Click CLI entry point
│   │   ├── interviewer.py    # LLM-based interview logic
│   │   ├── requirements.txt
│   │   └── tests/
│   │       └── test_interviewer.py
│   └── atomizer/
│       ├── app.py            # FastAPI application
│       ├── decomposer.py     # Task decomposition logic
│       ├── contract_gen.py   # JSON Schema generator
│       ├── requirements.txt
│       └── tests/
│           ├── test_decomposer.py
│           └── test_contract_gen.py
└── configs/
    └── profiles.json         # Profile templates (created in Plan 3)
```

---

### Task 1: Manager CLI Foundation

**Files:**
- Create: `services/manager/cli.py`, `services/manager/interviewer.py`, `services/manager/requirements.txt`
- Test: `services/manager/tests/test_interviewer.py`

- [ ] **Step 1: Write tests for interviewer**

```python
# services/manager/tests/test_interviewer.py
import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/manager/tests/test_interviewer.py -v
```
Expected: FAIL (module not implemented)

- [ ] **Step 3: Create Manager requirements**

```txt
# services/manager/requirements.txt
click==8.1.7
pydantic==2.5.3
requests==2.31.0
python-dotenv==1.0.0
```

- [ ] **Step 4: Implement Interviewer**

```python
# services/manager/interviewer.py
from pydantic import BaseModel
from typing import Optional
import json


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
    
    def __init__(self):
        self.questions_asked = 0
        self.responses: list[dict] = []
        self.current_question_idx = 0
    
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

- [ ] **Step 5: Implement CLI**

```python
# services/manager/cli.py
import click
import sys
import requests
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
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
    
    interviewer = Interviewer()
    
    while not interviewer.is_complete():
        question = interviewer.get_next_question()
        if not question:
            break
        
        click.echo(click.style(f"\n{question.text}", fg="green", bold=True))
        answer = click.prompt("Your answer")
        interviewer.record_response(answer, question.category)
    
    # Extract and display spec
    spec = interviewer.extract_project_spec()
    
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

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/manager/tests/test_interviewer.py -v
```
Expected: PASS

- [ ] **Step 7: Test CLI manually**

```bash
cd /home/loki/ideas/sea-qwens
python -m services.manager.cli interview
```
Expected: Interactive interview runs

- [ ] **Step 8: Commit**

```bash
git add services/manager/
git commit -m "feat: implement Manager CLI with interview workflow"
```

---

### Task 2: Atomizer Task Decomposition

**Files:**
- Create: `services/atomizer/app.py`, `services/atomizer/decomposer.py`, `services/atomizer/requirements.txt`
- Test: `services/atomizer/tests/test_decomposer.py`

- [ ] **Step 1: Write tests for decomposer**

```python
# services/atomizer/tests/test_decomposer.py
import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.atomizer.decomposer import Atomizer, generate_task_id


def test_generate_task_id():
    task_id = generate_task_id("Create API")
    assert task_id.startswith("task-")
    assert len(task_id) > 10


def test_atomizer_initializes():
    atomizer = Atomizer()
    assert atomizer.librarian_url != ""


def test_atomizer_decompose_mock():
    """Test decomposition with mocked LLM"""
    atomizer = Atomizer()
    spec = {
        "name": "Test API",
        "tech_stack": ["FastAPI"],
        "features": ["Health endpoint"]
    }
    # This would normally call LLM, we'll mock it
    tasks = atomizer._mock_decompose(spec)
    assert len(tasks) > 0
    assert "task_id" in tasks[0]
    assert "title" in tasks[0]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/atomizer/tests/test_decomposer.py -v
```
Expected: FAIL

- [ ] **Step 3: Create Atomizer requirements**

```txt
# services/atomizer/requirements.txt
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
requests==2.31.0
python-dotenv==1.0.0
pytest==8.0.0
```

- [ ] **Step 4: Implement Decomposer**

```python
# services/atomizer/decomposer.py
import uuid
import json
from datetime import datetime
from typing import Optional
import requests


def generate_task_id(title: str) -> str:
    """Generate a unique task ID from title"""
    slug = title.lower().replace(" ", "-")[:20]
    return f"task-{slug}-{uuid.uuid4().hex[:6]}"


class Atomizer:
    """Decompose ProjectSpec into atomic tasks using LLM"""
    
    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url
    
    def fetch_project_spec(self, spec_id: str) -> Optional[dict]:
        """Fetch ProjectSpec from Librarian"""
        try:
            response = requests.get(
                f"{self.librarian_url}/project-specs/{spec_id}"
            )
            if response.status_code == 200:
                return response.json()
            return None
        except requests.exceptions.RequestException:
            return None
    
    def decompose(self, spec: dict) -> list[dict]:
        """
        Decompose ProjectSpec into atomic tasks.
        
        In production, this calls an LLM service. For now,
        we use rule-based decomposition as a placeholder.
        """
        # TODO: Replace with actual LLM call
        # For now, use mock decomposition
        return self._mock_decompose(spec)
    
    def _mock_decompose(self, spec: dict) -> list[dict]:
        """Mock decomposition for testing"""
        tasks = []
        tech_stack = spec.get("tech_stack", [])
        features = spec.get("features", [])
        
        # Infrastructure tasks
        if any("fastapi" in t.lower() for t in tech_stack):
            tasks.append({
                "task_id": generate_task_id("Setup FastAPI"),
                "title": "Setup FastAPI application skeleton",
                "dependencies": [],
                "contract": {
                    "type": "object",
                    "properties": {
                        "files_created": {"type": "array", "items": {"type": "string"}},
                        "has_main": {"type": "boolean"}
                    },
                    "required": ["files_created", "has_main"]
                },
                "test_spec": {
                    "test_file": "tests/test_app.py",
                    "assertions": ["app starts", "health endpoint returns 200"]
                }
            })
        
        # Feature tasks
        for i, feature in enumerate(features):
            dep_task_id = tasks[0]["task_id"] if tasks else None
            task = {
                "task_id": generate_task_id(feature[:20]),
                "title": f"Implement: {feature}",
                "dependencies": [dep_task_id] if dep_task_id else [],
                "contract": {
                    "type": "object",
                    "properties": {
                        "feature_name": {"type": "string"},
                        "implemented": {"type": "boolean"}
                    },
                    "required": ["feature_name", "implemented"]
                },
                "test_spec": {
                    "test_file": "tests/test_feature.py",
                    "assertions": [f"{feature} works correctly"]
                }
            }
            tasks.append(task)
        
        return tasks
    
    def save_tasks(self, tasks: list[dict], project_spec_id: str):
        """Save tasks to Librarian"""
        # Note: This would need a POST /tasks endpoint in Librarian
        # For now, we'll note this as a dependency
        pass
```

- [ ] **Step 5: Implement Atomizer FastAPI app**

```python
# services/atomizer/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.atomizer.decomposer import Atomizer


app = FastAPI(title="Legion Atomizer")

atomizer = Atomizer()


class DecomposeRequest(BaseModel):
    project_spec_id: str


class DecomposeResponse(BaseModel):
    project_spec_id: str
    tasks_created: int
    tasks: list[dict]


@app.post("/decompose")
def decompose_project(request: DecomposeRequest):
    """Decompose a ProjectSpec into atomic tasks"""
    # Fetch spec from Librarian
    spec = atomizer.fetch_project_spec(request.project_spec_id)
    if not spec:
        raise HTTPException(status_code=404, detail="ProjectSpec not found")
    
    # Decompose into tasks
    tasks = atomizer.decompose(spec)
    
    # TODO: Save tasks to Librarian (requires POST /tasks endpoint)
    # For now, return them
    return DecomposeResponse(
        project_spec_id=request.project_spec_id,
        tasks_created=len(tasks),
        tasks=tasks
    )


@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

- [ ] **Step 6: Create Atomizer main entry point**

```python
# services/atomizer/main.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8002, reload=True)
```

- [ ] **Step 7: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/atomizer/tests/test_decomposer.py -v
```
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add services/atomizer/
git commit -m "feat: implement Atomizer service for task decomposition"
```

---

### Task 3: Contract Generator

**Files:**
- Create: `services/atomizer/contract_gen.py`
- Test: `services/atomizer/tests/test_contract_gen.py`

- [ ] **Step 1: Write tests for contract generator**

```python
# services/atomizer/tests/test_contract_gen.py
import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.atomizer.contract_gen import (
    generate_api_contract,
    generate_function_contract,
    validate_contract
)


def test_generate_api_contract():
    contract = generate_api_contract(
        endpoint="/api/users",
        method="GET",
        response_schema={"type": "array"}
    )
    assert "endpoint" in contract
    assert contract["method"] == "GET"


def test_generate_function_contract():
    contract = generate_function_contract(
        name="calculate_total",
        params=["items"],
        return_type="number"
    )
    assert contract["function_name"] == "calculate_total"
    assert "items" in contract["parameters"]


def test_validate_contract_valid():
    contract = {"type": "object", "required": ["name"]}
    data = {"name": "test"}
    is_valid, errors = validate_contract(contract, data)
    assert is_valid
    assert errors == []


def test_validate_contract_invalid():
    contract = {"type": "object", "required": ["name"]}
    data = {}
    is_valid, errors = validate_contract(contract, data)
    assert not is_valid
    assert len(errors) > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/atomizer/tests/test_contract_gen.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement contract generator**

```python
# services/atomizer/contract_gen.py
from typing import Any, Optional
import json


def generate_api_contract(
    endpoint: str,
    method: str = "GET",
    request_schema: Optional[dict] = None,
    response_schema: Optional[dict] = None
) -> dict:
    """Generate a JSON Schema contract for an API endpoint"""
    return {
        "type": "api",
        "endpoint": endpoint,
        "method": method,
        "request": request_schema or {"type": "object"},
        "response": response_schema or {"type": "object"},
        "validation_rules": {
            "status_codes": [200, 201, 400, 404, 500],
            "content_type": "application/json"
        }
    }


def generate_function_contract(
    name: str,
    params: list[str],
    return_type: str,
    description: str = ""
) -> dict:
    """Generate a contract for a function signature"""
    return {
        "type": "function",
        "function_name": name,
        "parameters": params,
        "return_type": return_type,
        "description": description,
        "validation_rules": {
            "param_count": len(params),
            "pure_function": True
        }
    }


def generate_file_contract(
    filepath: str,
    expected_content: Optional[str] = None,
    must_exist: bool = True
) -> dict:
    """Generate a contract for file existence/content"""
    return {
        "type": "file",
        "filepath": filepath,
        "must_exist": must_exist,
        "expected_content_pattern": expected_content
    }


def validate_contract(contract: dict, data: Any) -> tuple[bool, list[str]]:
    """
    Validate data against a contract.
    Returns (is_valid, list_of_errors)
    """
    errors = []
    
    if contract.get("type") == "object":
        required = contract.get("required", [])
        for field in required:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        properties = contract.get("properties", {})
        for key, value in data.items():
            if key in properties:
                prop_schema = properties[key]
                expected_type = prop_schema.get("type")
                if expected_type and not isinstance(value, eval(expected_type)):
                    errors.append(f"Field '{key}' has wrong type")
    
    return len(errors) == 0, errors
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/atomizer/tests/test_contract_gen.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/atomizer/contract_gen.py services/atomizer/tests/test_contract_gen.py
git commit -m "feat: add contract generator with validation"
```

---

### Task 4: Librarian Task Endpoints

**Files:**
- Modify: `services/librarian/app.py`, `services/librarian/neo4j_store.py`

- [ ] **Step 1: Add task creation to Neo4j store**

```python
# services/librarian/neo4j_store.py - ADD this method

    def create_task(self, task_data: dict) -> dict:
        """Create a task node in Neo4j"""
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (t:Task {
                    task_id: $task_id,
                    title: $title,
                    status: $status,
                    dependencies: $dependencies,
                    contract: $contract,
                    profile_id: $profile_id,
                    test_spec: $test_spec
                })
                RETURN t
                """,
                task_id=task_data.get("task_id"),
                title=task_data.get("title"),
                status=task_data.get("status", "PENDING"),
                dependencies=task_data.get("dependencies", []),
                contract=task_data.get("contract", {}),
                profile_id=task_data.get("profile_id"),
                test_spec=task_data.get("test_spec")
            )
            record = result.single()
            if record:
                return dict(record["t"])
            return None
    
    def create_dependency_relationship(self, from_task_id: str, to_task_id: str):
        """Create a DEPENDS_ON relationship between tasks"""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (from:Task {task_id: $from_id})
                MATCH (to:Task {task_id: $to_id})
                MERGE (from)-[:DEPENDS_ON]->(to)
                """,
                from_id=from_task_id,
                to_id=to_task_id
            )
```

- [ ] **Step 2: Add task endpoints to FastAPI app**

```python
# services/librarian/app.py - ADD these imports and endpoints

from pydantic import BaseModel
from typing import Optional

# Add this class
class TaskInput(BaseModel):
    task_id: str
    title: str
    status: str = "PENDING"
    dependencies: list[str] = []
    contract: dict = {}
    profile_id: Optional[str] = None
    test_spec: Optional[dict] = None


# Add these endpoints before the existing ones

@app.post("/tasks", status_code=201)
def create_task(task: TaskInput):
    """Create a new task"""
    task_data = task.model_dump()
    result = neo4j.create_task(task_data)
    
    # Create dependency relationships
    for dep_id in task.dependencies:
        neo4j.create_dependency_relationship(task.task_id, dep_id)
    
    return result


@app.post("/tasks/batch", status_code=201)
def create_tasks_batch(tasks: list[TaskInput]):
    """Create multiple tasks (for Atomizer)"""
    results = []
    for task in tasks:
        task_data = task.model_dump()
        result = neo4j.create_task(task_data)
        if result:
            results.append(result)
            # Create dependency relationships
            for dep_id in task.dependencies:
                neo4j.create_dependency_relationship(task.task_id, dep_id)
    return {"tasks_created": len(results), "tasks": results}
```

- [ ] **Step 3: Update existing TaskUpdateInput to use metadata properly**

```python
# services/librarian/app.py - Modify the update_task endpoint

@app.post("/tasks/update")
def update_task(task_id: str, update: TaskUpdateInput):
    result = neo4j.update_task_status(task_id, update.status, update.metadata)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result
```

- [ ] **Step 4: Commit**

```bash
git add services/librarian/app.py services/librarian/neo4j_store.py
git commit -m "feat: add task creation endpoints to Librarian"
```

---

## Verification

After completing all tasks, run:

```bash
# Test Manager
python -m services.manager.cli interview

# Test Atomizer decomposition
curl -X POST http://localhost:8002/decompose \
  -H "Content-Type: application/json" \
  -d '{"project_spec_id": "<spec-id>"}'

# Run all tests
pytest services/manager/ services/atomizer/ -v
```

Expected: All tests pass, services run independently
