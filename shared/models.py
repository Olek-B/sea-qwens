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
    parent_project: Optional[str] = None
    constraints: list[str] = Field(default_factory=list)


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
    adapter: str = ""  # Optional: adapter script name (defaults to <name>.sh)
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
