# services/worker/app.py
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
    title="Sea Qwens Worker",
    description="Worker executor service for Sea Qwens",
    version="0.1.0",
)

executor = TaskExecutor()

_execution_store: dict[str, ExecutionResult] = {}


class ExecuteRequest(BaseModel):
    task: Task
    tool_id: Optional[str] = None
    tool_command: str = "qwen --non-interactive"
    worktree_path: Optional[str] = None


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
            status_code=404,
            detail=f"Task {task_id} not found",
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
        service="sea-qwens-worker",
        timestamp=datetime.utcnow().isoformat(),
    )


async def _run_execution(
    task: Task,
    tool_id: Optional[str],
    tool_command: str,
    worktree_path: Optional[str],
):
    """Run task execution in the background."""
    logger.info(f"Starting execution of task: {task.task_id} with tool: {tool_id}")

    # Create worktree if not provided
    if not worktree_path:
        from services.worker.worktree_manager import WorktreeManager
        wt_manager = WorktreeManager()
        worktree_path = wt_manager.create_worktree(task.task_id)

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
