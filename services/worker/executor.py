# services/worker/executor.py
import subprocess
import os
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from shared.models import Task


@dataclass
class ExecutionResult:
    """Result of a task execution by a worker agent."""
    success: bool
    task_id: str
    output: str = ""
    test_passed: bool = False
    error: Optional[str] = None
    rate_limited: bool = False


class TaskExecutor:
    """Execute coding tasks using CLI tools in isolated worktrees."""

    def execute_task(
        self,
        task: Task,
        tool_id: Optional[str] = None,
        tool_command: str = "qwen --non-interactive",
        worktree_path: str = "",
    ) -> ExecutionResult:
        """
        Execute a task in the given worktree.

        1. Build prompt from task title + contract
        2. Run the given CLI tool in the worktree directory
        3. Run self-tests (pytest) in the worktree
        4. Return ExecutionResult
        """
        wt_path = Path(worktree_path)
        if not wt_path.exists() or not wt_path.is_dir():
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=f"Worktree path does not exist: {worktree_path}",
            )

        prompt = self._build_prompt(task.title, task.contract)

        try:
            env = os.environ.copy()
            if tool_id:
                env["LEGION_TOOL_ID"] = tool_id

            cmd = [
                *tool_command.split(),
                "--prompt", prompt,
                "--cwd", str(wt_path),
            ]

            result = subprocess.run(
                cmd,
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
            )

            tool_output = result.stdout
            tool_error = result.stderr

            rate_limited = self._is_rate_limited(tool_output, tool_error)

            if result.returncode != 0 or rate_limited:
                return ExecutionResult(
                    success=False,
                    task_id=task.task_id,
                    output=tool_output,
                    error=tool_error or "Tool returned non-zero exit code",
                    rate_limited=rate_limited,
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error="Task execution timed out (600s)",
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=f"Command not found: {tool_command.split()[0]}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=str(e),
            )

        test_result = self._run_self_tests(str(wt_path), task)

        return ExecutionResult(
            success=test_result.success,
            task_id=task.task_id,
            output=tool_output + "\n--- Tests ---\n" + test_result.output,
            test_passed=test_result.test_passed,
            error=test_result.error,
            rate_limited=test_result.rate_limited,
        )

    def _build_prompt(self, title: str, contract: dict) -> str:
        """Build prompt for the CLI tool with code graph tool instructions."""
        prompt = f"""Implement the following task:

{title}

Requirements (contract):
{json.dumps(contract, indent=2)}

## Code Knowledge Graph Tools

You have access to a code knowledge graph. Instead of reading files, use these tools to understand the codebase:

- `search_code(query)` - Find functions/classes by semantic search
- `get_function(name)` - Get a function's body and signature
- `get_callers(name)` - Find who calls this function
- `get_callees(name)` - Find what this function calls
- `get_full_context(name)` - Get complete context for understanding a function
- `get_class(name)` - Get a class definition and all methods

## Workflow

1. Before implementing, search for existing related code
2. Use `get_full_context` to understand call chains
3. Implement your changes following existing patterns
4. Ensure your code integrates with existing functions

## Guidelines

- Write clean, tested code
- Follow best practices
- Ensure all tests pass
- Do not modify files outside the task scope
"""
        return prompt

    def _run_self_tests(
        self,
        worktree_path: str,
        task: Task,
    ) -> ExecutionResult:
        """Run pytest in the worktree to verify the implementation."""
        wt_path = Path(worktree_path)

        if not wt_path.exists():
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=f"Worktree path does not exist: {worktree_path}",
            )

        try:
            result = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=120,
            )

            output = result.stdout + result.stderr
            passed = result.returncode == 0

            return ExecutionResult(
                success=passed,
                task_id=task.task_id,
                output=output,
                test_passed=passed,
                error=None if passed else "Some tests failed",
            )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error="Self-tests timed out (120s)",
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error="pytest not found in worktree environment",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=str(e),
            )

    @staticmethod
    def _is_rate_limited(stdout: str, stderr: str) -> bool:
        """Detect rate limiting signals in output."""
        rate_limit_signals = [
            "rate limit",
            "quota exceeded",
            "too many requests",
            "429",
            "resource exhausted",
            "rate_limited",
        ]
        combined = (stdout + stderr).lower()
        return any(signal in combined for signal in rate_limit_signals)
