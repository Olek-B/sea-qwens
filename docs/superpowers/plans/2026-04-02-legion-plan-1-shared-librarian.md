# Project Legion Plan 1: Shared Models + Librarian Service

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational data models and central knowledge service (Librarian) with Neo4j and ChromaDB integration.

**Architecture:** FastAPI service exposing REST endpoints for task management, project specs, and profile rotation. Neo4j stores graph relationships (tasks, dependencies, profiles), ChromaDB stores vector embeddings for semantic search.

**Tech Stack:** Python 3.11+, FastAPI, Neo4j (graph), ChromaDB (vector), Pydantic, pytest

---

## File Structure

```
/legion-root/
├── shared/
│   └── models.py           # Pydantic models: ProjectSpec, Task, Profile
├── services/
│   └── librarian/
│       ├── app.py          # FastAPI application
│       ├── main.py         # Entry point
│       ├── requirements.txt
│       ├── config.py       # Settings (Neo4j/ChromaDB URLs)
│       ├── neo4j_store.py  # Neo4j operations
│       ├── chroma_store.py # ChromaDB operations
│       └── tests/
│           ├── test_api.py
│           ├── test_neo4j.py
│           └── test_chroma.py
└── docker-compose.yml      # Neo4j + ChromaDB infrastructure
```

---

### Task 1: Shared Models

**Files:**
- Create: `shared/models.py`
- Test: `shared/test_models.py`

- [ ] **Step 1: Write tests for ProjectSpec model**

```python
# shared/test_models.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest shared/test_models.py -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'shared.models'"

- [ ] **Step 3: Implement shared models**

```python
# shared/models.py
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


class ProfileHealth(str, Enum):
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
    profile_id: Optional[str] = None
    worktree_path: Optional[str] = None
    test_spec: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Profile(BaseModel):
    name: str
    usage_count: int = 0
    last_used: Optional[datetime] = None
    daily_limit: int = 1000
    requests_today: int = 0
    reset_time: datetime = Field(default_factory=lambda: datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0))
    capabilities: list[str] = Field(default_factory=lambda: ["coding", "testing", "refactoring"])
    health_status: ProfileHealth = ProfileHealth.HEALTHY
    consecutive_failures: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest shared/test_models.py -v
```
Expected: PASS

- [ ] **Step 5: Create shared/__init__.py**

```python
# shared/__init__.py
from shared.models import ProjectSpec, Task, TaskStatus, Profile, ProfileHealth

__all__ = ["ProjectSpec", "Task", "TaskStatus", "Profile", "ProfileHealth"]
```

- [ ] **Step 6: Commit**

```bash
git add shared/models.py shared/__init__.py shared/test_models.py
git commit -m "feat: add shared Pydantic models for ProjectSpec, Task, Profile"
```

---

### Task 2: Librarian Project Spec API

**Files:**
- Create: `services/librarian/app.py`, `services/librarian/main.py`, `services/librarian/requirements.txt`, `services/librarian/config.py`, `services/librarian/neo4j_store.py`
- Test: `services/librarian/tests/test_api.py`

- [ ] **Step 1: Write tests for ProjectSpec endpoints**

```python
# services/librarian/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.librarian.app import app

client = TestClient(app)

def test_create_project_spec():
    response = client.post("/project-specs", json={
        "name": "Test API",
        "tech_stack": ["FastAPI", "Neo4j"],
        "features": ["REST API"]
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test API"
    assert "id" in data

def test_get_project_spec():
    # First create one
    create_resp = client.post("/project-specs", json={
        "name": "Get Test",
        "tech_stack": ["FastAPI"],
        "features": ["Test"]
    })
    spec_id = create_resp.json()["id"]
    
    response = client.get(f"/project-specs/{spec_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Get Test"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_api.py::test_create_project_spec -v
```
Expected: FAIL (app not implemented yet)

- [ ] **Step 3: Create Librarian requirements and config**

```txt
# services/librarian/requirements.txt
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
neo4j==5.17.0
chromadb==0.4.22
pytest==8.0.0
httpx==0.26.0
```

```python
# services/librarian/config.py
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # ChromaDB
    CHROMA_DB_HOST: str = "localhost"
    CHROMA_DB_PORT: int = 8000
    
    # App
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 4: Implement Neo4j store**

```python
# services/librarian/neo4j_store.py
from neo4j import GraphDatabase
from services.librarian.config import settings
from typing import Optional, Any
import uuid


class Neo4jStore:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
    
    def close(self):
        self.driver.close()
    
    def create_project_spec(self, name: str, tech_stack: list[str], features: list[str]) -> dict:
        spec_id = str(uuid.uuid4())
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (p:ProjectSpec {
                    id: $id,
                    name: $name,
                    tech_stack: $tech_stack,
                    features: $features
                })
                RETURN p
                """,
                id=spec_id, name=name, tech_stack=tech_stack, features=features
            )
            record = result.single()
            return dict(record["p"])
    
    def get_project_spec(self, spec_id: str) -> Optional[dict]:
        with self.driver.session() as session:
            result = session.run(
                "MATCH (p:ProjectSpec {id: $id}) RETURN p",
                id=spec_id
            )
            record = result.single()
            if record:
                return dict(record["p"])
            return None
    
    def create_task(self, task_data: dict) -> dict:
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
    
    def get_ready_tasks(self) -> list[dict]:
        """Get tasks where all dependencies are DONE"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Task {status: 'PENDING'})
                WHERE ALL(dep_id IN t.dependencies WHERE 
                    EXISTS((:Task {task_id: dep_id, status: 'DONE'}))
                )
                RETURN t
                """
            )
            return [dict(record["t"]) for record in result]
    
    def update_task_status(self, task_id: str, status: str, metadata: Optional[dict] = None) -> Optional[dict]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Task {task_id: $task_id})
                SET t.status = $status
                RETURN t
                """,
                task_id=task_id, status=status
            )
            record = result.single()
            if record:
                return dict(record["t"])
            return None
    
    def create_profile(self, profile_data: dict) -> dict:
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
    
    def get_least_used_profile(self) -> Optional[dict]:
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
    
    def increment_profile_usage(self, profile_name: str) -> Optional[dict]:
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
```

- [ ] **Step 5: Implement ChromaDB store**

```python
# services/librarian/chroma_store.py
import chromadb
from chromadb.config import Settings as ChromaSettings
from services.librarian.config import settings
from typing import Optional


class ChromaStore:
    def __init__(self):
        self.client = chromadb.HttpClient(
            host=settings.CHROMA_DB_HOST,
            port=settings.CHROMA_DB_PORT
        )
        self.collection = self.client.get_or_create_collection(
            name="code_embeddings",
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_document(self, uid: str, content: str, metadata: Optional[dict] = None):
        """Add a document to the vector store"""
        self.collection.add(
            documents=[content],
            ids=[uid],
            metadatas=[metadata or {}]
        )
    
    def search_similar(self, query: str, n_results: int = 5) -> list:
        """Search for similar documents"""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        return results
    
    def get_document(self, uid: str) -> Optional[dict]:
        """Get a document by ID"""
        results = self.collection.get(ids=[uid])
        if results["documents"]:
            return {
                "uid": uid,
                "content": results["documents"][0],
                "metadata": results["metadatas"][0]
            }
        return None
```

- [ ] **Step 6: Implement FastAPI app**

```python
# services/librarian/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.librarian.neo4j_store import Neo4jStore
from services.librarian.chroma_store import ChromaStore
from services.librarian.config import settings
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from shared.models import ProjectSpec, Task, TaskStatus, Profile

app = FastAPI(title="Legion Librarian")

neo4j = Neo4jStore()
chroma = ChromaStore()


class ProjectSpecInput(BaseModel):
    name: str
    tech_stack: list[str]
    features: list[str]


class TaskUpdateInput(BaseModel):
    status: str
    metadata: Optional[dict] = None


class IngestInput(BaseModel):
    uid: str
    content: str
    metadata: Optional[dict] = None


@app.post("/project-specs", status_code=201)
def create_project_spec(spec: ProjectSpecInput):
    result = neo4j.create_project_spec(
        name=spec.name,
        tech_stack=spec.tech_stack,
        features=spec.features
    )
    return result


@app.get("/project-specs/{spec_id}")
def get_project_spec(spec_id: str):
    result = neo4j.get_project_spec(spec_id)
    if not result:
        raise HTTPException(status_code=404, detail="ProjectSpec not found")
    return result


@app.post("/tasks/update")
def update_task(task_id: str, update: TaskUpdateInput):
    result = neo4j.update_task_status(task_id, update.status, update.metadata)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@app.get("/tasks/ready")
def get_ready_tasks():
    return neo4j.get_ready_tasks()


@app.post("/ingest")
def ingest_document(data: IngestInput):
    chroma.add_document(data.uid, data.content, data.metadata)
    return {"status": "ok", "uid": data.uid}


@app.get("/profiles/least-used")
def get_least_used_profile():
    result = neo4j.get_least_used_profile()
    if not result:
        raise HTTPException(status_code=404, detail="No healthy profiles available")
    return result


@app.post("/profiles/{profile_name}/increment")
def increment_profile_usage(profile_name: str):
    result = neo4j.increment_profile_usage(profile_name)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result
```

- [ ] **Step 7: Create main entry point**

```python
# services/librarian/main.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=True)
```

- [ ] **Step 8: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_api.py -v
```
Expected: PASS (requires Neo4j running - may need to mock for unit tests)

- [ ] **Step 9: Commit**

```bash
git add services/librarian/
git commit -m "feat: implement Librarian FastAPI service with Neo4j and ChromaDB"
```

---

### Task 3: Docker Compose Infrastructure

**Files:**
- Create: `docker-compose.yml`

- [ ] **Step 1: Create docker-compose.yml**

```yaml
# docker-compose.yml
version: '3.8'

services:
  neo4j:
    image: neo4j:5
    container_name: legion-neo4j
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
    networks:
      - legion-network

  chromadb:
    image: chromadb/chroma
    container_name: legion-chromadb
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma
    networks:
      - legion-network

  librarian:
    build:
      context: .
      dockerfile: services/librarian/Dockerfile
    container_name: legion-librarian
    ports:
      - "8001:8001"
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: password
      CHROMA_DB_HOST: chromadb
      CHROMA_DB_PORT: 8000
    depends_on:
      - neo4j
      - chromadb
    networks:
      - legion-network
    volumes:
      - .:/app

volumes:
  neo4j_data:
  chroma_data:

networks:
  legion-network:
    driver: bridge
```

- [ ] **Step 2: Create Librarian Dockerfile**

```dockerfile
# services/librarian/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY services/librarian/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["python", "services/librarian/main.py"]
```

- [ ] **Step 3: Create .env file for local development**

```bash
# .env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
CHROMA_DB_HOST=localhost
CHROMA_DB_PORT=8000
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml services/librarian/Dockerfile .env
git commit -m "feat: add docker-compose for Neo4j, ChromaDB, and Librarian"
```

---

### Task 4: Integration Tests

**Files:**
- Modify: `services/librarian/tests/test_api.py` (add integration tests)

- [ ] **Step 1: Add integration test with docker-compose**

```python
# services/librarian/tests/test_integration.py
import pytest
import requests
import time

LIBRARIAN_URL = "http://localhost:8001"


@pytest.mark.integration
class TestLibrarianIntegration:
    
    def test_full_project_spec_flow(self):
        # Create ProjectSpec
        response = requests.post(f"{LIBRARIAN_URL}/project-specs", json={
            "name": "Integration Test Project",
            "tech_stack": ["FastAPI", "Neo4j", "ChromaDB"],
            "features": ["Full integration test"]
        })
        assert response.status_code == 201
        spec_id = response.json()["id"]
        
        # Retrieve ProjectSpec
        response = requests.get(f"{LIBRARIAN_URL}/project-specs/{spec_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Integration Test Project"
    
    def test_task_lifecycle(self):
        # Create a task via direct Neo4j (for testing)
        # Then test status update
        pass  # Requires task creation endpoint
    
    def test_profile_rotation(self):
        # Test getting least-used profile
        response = requests.get(f"{LIBRARIAN_URL}/profiles/least-used")
        if response.status_code == 200:
            profile = response.json()
            assert "name" in profile
            assert "usage_count" in profile
```

- [ ] **Step 2: Commit**

```bash
git add services/librarian/tests/test_integration.py
git commit -m "test: add integration tests for Librarian service"
```

---

## Verification

After completing all tasks, run:

```bash
# Start infrastructure
docker-compose up -d neo4j chromadb

# Wait for services
sleep 10

# Run unit tests
pytest shared/ services/librarian/tests/ -v

# Run integration tests (requires running services)
pytest services/librarian/tests/test_integration.py -v -m integration
```

Expected: All tests pass
