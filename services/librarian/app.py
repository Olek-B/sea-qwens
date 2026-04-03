from fastapi import FastAPI, HTTPException, Query
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import Optional, List
from services.librarian.config import settings
import json
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.models import ProjectSpec, Task, TaskStatus, Tool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed tools from configs/tools.json on startup."""
    _seed_tools()
    yield


def _seed_tools():
    """Load tools from config file and create them in Neo4j if they don't exist."""
    config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'configs', 'tools.json')
    if not os.path.exists(config_path):
        logger.warning(f"Tools config not found: {config_path}")
        return

    try:
        with open(config_path) as f:
            tools_config = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to read tools config: {e}")
        return

    neo4j = get_neo4j_store()
    existing_tools = neo4j.get_all_tools()
    existing_names = {t["name"] for t in existing_tools}

    for tool_data in tools_config:
        if tool_data["name"] not in existing_names:
            neo4j.create_tool(tool_data)
            logger.info(f"Seeded tool: {tool_data['name']}")


app = FastAPI(title="Legion Librarian", lifespan=lifespan)

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
    tool_id: Optional[str] = None


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
        "tool_id": task.tool_id
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
            "tool_id": task.tool_id
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


@app.get("/tools")
def get_all_tools():
    """Get all tools."""
    neo4j = get_neo4j_store()
    return neo4j.get_all_tools()


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


class ToolStatusUpdate(BaseModel):
    health_status: str


@app.put("/tools/{tool_name}/status")
def update_tool_status(tool_name: str, update: ToolStatusUpdate):
    """Update a tool's health status"""
    neo4j = get_neo4j_store()
    with neo4j.driver.session() as session:
        result = session.run(
            """
            MATCH (t:Tool {name: $name})
            SET t.health_status = $health_status
            RETURN t
            """,
            name=tool_name,
            health_status=update.health_status
        )
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="Tool not found")
        return dict(record["t"])


# ==================== Code Knowledge Graph Endpoints ====================

@app.get("/code/search")
def search_code(q: str = Query(..., description="Search query"), type: str = Query("function")):
    """Search code semantically via ChromaDB and by name via Neo4j."""
    store = get_chroma_store()
    vector_results = store.search_code(q)
    neo4j_store = get_neo4j_store()
    graph_results = neo4j_store.search_functions(q)
    return {"query": q, "results": vector_results, "graph_results": graph_results}


@app.get("/code/function/{name}")
def get_function(name: str):
    """Get function details by name."""
    neo4j_store = get_neo4j_store()
    func = neo4j_store.get_function_by_name(name)
    if not func:
        raise HTTPException(status_code=404, detail=f"Function '{name}' not found")
    return func


@app.get("/code/function/{name}/callers")
def get_function_callers(name: str):
    """Get all functions that call this function."""
    neo4j_store = get_neo4j_store()
    callers = neo4j_store.get_callers(name)
    return {"function": name, "callers": callers}


@app.get("/code/function/{name}/callees")
def get_function_callees(name: str):
    """Get all functions this function calls."""
    neo4j_store = get_neo4j_store()
    callees = neo4j_store.get_callees(name)
    return {"function": name, "callees": callees}


@app.get("/code/function/{name}/full-context")
def get_function_full_context(name: str, depth: int = Query(2, ge=0, le=5)):
    """Get function + callers + callees recursively."""
    neo4j_store = get_neo4j_store()
    context = neo4j_store.get_full_context(name, depth)
    if not context:
        raise HTTPException(status_code=404, detail=f"Function '{name}' not found")
    return context


@app.get("/code/class/{name}")
def get_class(name: str):
    """Get class details and methods."""
    neo4j_store = get_neo4j_store()
    with neo4j_store.driver.session() as session:
        result = session.run(
            "MATCH (c:Class {name: $name}) OPTIONAL MATCH (c)-[:CONTAINS]->(m:Function) RETURN c, collect(m) as methods",
            name=name
        )
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail=f"Class '{name}' not found")
        return {"class": dict(record["c"]), "methods": [dict(m) for m in record["methods"] if m]}


@app.get("/code/file/{path:path}")
def get_file_content(path: str):
    """Get file content by path."""
    neo4j_store = get_neo4j_store()
    with neo4j_store.driver.session() as session:
        result = session.run("MATCH (f:File {path: $path}) RETURN f", path=path)
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail=f"File '{path}' not found")
        return dict(record["f"])


# ==================== Post-Execution Indexer ====================

class FileContent(BaseModel):
    path: str
    content: Optional[str] = None
    language: str = "python"


class IndexUpdatedInput(BaseModel):
    files: List[FileContent]


@app.post("/index/updated")
def index_updated(body: IndexUpdatedInput):
    """Index changed files after a merge.

    The Tester sends file content directly — the Librarian never reads
    the filesystem.
    """
    from services.librarian.post_indexer import PostIndexer
    indexer = PostIndexer(get_neo4j_store(), get_chroma_store())
    file_dicts = [f.model_dump() for f in body.files]
    result = indexer.index_files(file_dicts)
    return {"indexed": result}
