import subprocess
import os
import json
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from shared.models import Task, Tool


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
    """Execute coding tasks using qwen-code CLI in isolated worktrees."""

    QWEN_CODE_CMD = "qwen"  # qwen-code CLI command

    def execute_task(
        self,
        task: Task,
        profile_id: Optional[str] = None,
        worktree_path: str = "",
    ) -> ExecutionResult:
        """
        Execute a task in the given worktree.

        1. Build prompt from task title + contract
        2. Run qwen-code CLI in the worktree directory
        3. Run self-tests (pytest) in the worktree
        4. Return ExecutionResult
        """
        # Validate worktree path
        wt_path = Path(worktree_path)
        if not wt_path.exists() or not wt_path.is_dir():
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=f"Worktree path does not exist: {worktree_path}",
            )

        # Build the prompt
        prompt = self._build_prompt(task.title, task.contract)

        # Run qwen-code CLI in the worktree
        try:
            env = os.environ.copy()
            if profile_id:
                env["LEGION_PROFILE_ID"] = profile_id

            cmd = [
                self.QWEN_CODE_CMD,
                "--prompt", prompt,
                "--cwd", str(wt_path),
                "--non-interactive",
            ]

            result = subprocess.run(
                cmd,
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                env=env,
            )

            qwen_output = result.stdout
            qwen_error = result.stderr

            # Detect rate limiting in output
            rate_limited = self._is_rate_limited(qwen_output, qwen_error)

            if result.returncode != 0 or rate_limited:
                return ExecutionResult(
                    success=False,
                    task_id=task.task_id,
                    output=qwen_output,
                    error=qwen_error or "qwen-code returned non-zero exit code",
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
                error=f"Command not found: {self.QWEN_CODE_CMD}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=str(e),
            )

        # Run self-tests after qwen-code execution
        test_result = self._run_self_tests(str(wt_path), task)

        return ExecutionResult(
            success=test_result.success,
            task_id=task.task_id,
            output=qwen_output + "\n--- Tests ---\n" + test_result.output,
            test_passed=test_result.test_passed,
            error=test_result.error,
            rate_limited=test_result.rate_limited,
        )

    def _build_prompt(self, title: str, contract: dict) -> str:
        """Build prompt for qwen-code with code graph tool instructions."""
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
        """
        Run pytest in the worktree to verify the implementation.
        """
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
