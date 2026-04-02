from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from services.librarian.config import settings
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.models import ProjectSpec, Task, TaskStatus, Profile

app = FastAPI(title="Legion Librarian")

# Store instances - initialized lazily for testability
_neo4j_store = None
_chroma_store = None


def get_neo4j_store():
    """Get or create Neo4jStore instance"""
    global _neo4j_store
    if _neo4j_store is None:
        from services.librarian.neo4j_store import Neo4jStore
        _neo4j_store = Neo4jStore()
    return _neo4j_store


def get_chroma_store():
    """Get or create ChromaStore instance"""
    global _chroma_store
    if _chroma_store is None:
        from services.librarian.chroma_store import ChromaStore
        _chroma_store = ChromaStore()
    return _chroma_store


class ProjectSpecInput(BaseModel):
    """Input model for creating a ProjectSpec"""
    name: str
    tech_stack: list[str]
    features: list[str]


class TaskUpdateInput(BaseModel):
    """Input model for updating a task"""
    status: str
    metadata: Optional[dict] = None


class IngestInput(BaseModel):
    """Input model for ingesting documents"""
    uid: str
    content: str
    metadata: Optional[dict] = None


class TaskInput(BaseModel):
    """Input model for creating a task"""
    task_id: str
    title: str
    status: str = "PENDING"
    dependencies: list[str] = Field(default_factory=list)
    contract: dict = Field(default_factory=dict)
    profile_id: Optional[str] = None


@app.post("/project-specs", status_code=201)
def create_project_spec(spec: ProjectSpecInput):
    """Create a new ProjectSpec"""
    neo4j = get_neo4j_store()
    result = neo4j.create_project_spec(
        name=spec.name,
        tech_stack=spec.tech_stack,
        features=spec.features
    )
    return result


@app.get("/project-specs/{spec_id}")
def get_project_spec(spec_id: str):
    """Retrieve a ProjectSpec by ID"""
    neo4j = get_neo4j_store()
    result = neo4j.get_project_spec(spec_id)
    if not result:
        raise HTTPException(status_code=404, detail="ProjectSpec not found")
    return result


@app.post("/tasks/update")
def update_task(task_id: str, update: TaskUpdateInput):
    """Update a task's status"""
    neo4j = get_neo4j_store()
    result = neo4j.update_task_status(task_id, update.status, update.metadata)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return result


@app.get("/tasks/ready")
def get_ready_tasks():
    """Get tasks where all dependencies are DONE"""
    neo4j = get_neo4j_store()
    return neo4j.get_ready_tasks()


@app.post("/tasks", status_code=201)
def create_task(task: TaskInput):
    """Create a new task"""
    neo4j = get_neo4j_store()
    task_data = {
        "task_id": task.task_id,
        "title": task.title,
        "status": task.status,
        "dependencies": task.dependencies,
        "contract": task.contract,
        "profile_id": task.profile_id
    }
    created_task = neo4j.create_task(task_data)
    
    # Create dependency relationships
    for dep_id in task.dependencies:
        neo4j.create_dependency_relationship(task.task_id, dep_id)
    
    return created_task


@app.post("/tasks/batch", status_code=201)
def create_tasks_batch(tasks: list[TaskInput]):
    """Create multiple tasks with their dependencies (for Atomizer)"""
    neo4j = get_neo4j_store()
    created_tasks = []
    
    for task in tasks:
        task_data = {
            "task_id": task.task_id,
            "title": task.title,
            "status": task.status,
            "dependencies": task.dependencies,
            "contract": task.contract,
            "profile_id": task.profile_id
        }
        created_task = neo4j.create_task(task_data)
        created_tasks.append(created_task)
        
        # Create dependency relationships
        for dep_id in task.dependencies:
            neo4j.create_dependency_relationship(task.task_id, dep_id)
    
    return {
        "count": len(created_tasks),
        "tasks": created_tasks
    }


@app.post("/ingest")
def ingest_document(data: IngestInput):
    """Ingest a document into ChromaDB vector store"""
    chroma = get_chroma_store()
    chroma.add_document(data.uid, data.content, data.metadata)
    return {"status": "ok", "uid": data.uid}


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
