import pytest
import sys
import os

sys.path.insert(0, '/home/loki/ideas/sea-qwens/worktrees/legion-implement')

from services.worker.executor import ExecutionResult, TaskExecutor
from shared.models import Task


# ─── ExecutionResult Tests ───────────────────────────────────────────────────

def test_execution_result_success():
    """ExecutionResult should capture a successful task execution"""
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
    """ExecutionResult should capture a failed task execution"""
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
    """ExecutionResult should capture a rate-limited execution"""
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
    """ExecutionResult should have sensible defaults"""
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
    """_build_prompt should format title and contract into a prompt string"""
    executor = TaskExecutor()
    title = "Add user authentication"
    contract = {
        "input": "username, password",
        "output": "JWT token",
        "constraints": ["bcrypt hashing", "token expiry 24h"],
    }

    prompt = executor._build_prompt(title, contract)

    assert title in prompt
    assert "Add user authentication" in prompt
    assert "username, password" in prompt
    assert "JWT token" in prompt
    assert "bcrypt hashing" in prompt


def test_build_prompt_empty_contract():
    """_build_prompt should handle an empty contract gracefully"""
    executor = TaskExecutor()
    prompt = executor._build_prompt("Simple task", {})

    assert "Simple task" in prompt


def test_build_prompt_with_complex_contract():
    """_build_prompt should handle nested contract structures"""
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
    """_run_self_tests should handle a non-existent worktree path"""
    executor = TaskExecutor()
    task = Task(task_id="task-999", title="Test")
    result = executor._run_self_tests("/nonexistent/path", task)

    assert result.success is False
    assert result.error is not None


def test_execute_task_builds_prompt():
    """execute_task should build a prompt from task title and contract"""
    executor = TaskExecutor()

    # We can't actually run qwen-code in tests, but we can verify
    # that the method handles a missing worktree gracefully
    from shared.models import Task, TaskStatus

    task = Task(
        task_id="task-test",
        title="Test task",
        status=TaskStatus.PENDING,
        contract={"input": "none", "output": "none"},
    )

    # Should fail gracefully since worktree doesn't exist
    result = executor.execute_task(task, profile_id=None, worktree_path="/nonexistent")
    assert result.success is False
    assert result.task_id == "task-test"
