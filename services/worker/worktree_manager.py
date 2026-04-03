import subprocess
import os
from pathlib import Path
from typing import Optional


class WorktreeManager:
    """Manage git worktrees for isolated task execution"""

    def __init__(self, root_dir: str = "/home/loki/ideas/sea-qwens"):
        self.root_dir = root_dir
        self._root_path = Path(root_dir)
        self.worktrees_dir = self._root_path / "worktrees"
        self.worktrees_dir.mkdir(exist_ok=True)

    def _get_default_branch(self) -> str:
        """Detect the default branch of the repo"""
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(self.root_dir),
            capture_output=True,
            text=True
        )
        return result.stdout.strip() if result.returncode == 0 else "main"

    def create_worktree(self, task_id: str, branch: str = None) -> str:
        """Create a new worktree for a task"""
        worktree_path = self.worktrees_dir / task_id

        # Remove if exists
        if worktree_path.exists():
            self.cleanup_worktree(task_id)

        # Use provided branch or detect default
        actual_branch = branch if branch is not None else self._get_default_branch()

        # Create worktree
        cmd = ["git", "worktree", "add", "-b", f"task/{task_id}", str(worktree_path), actual_branch]
        result = subprocess.run(
            cmd,
            cwd=str(self.root_dir),
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {result.stderr}")

        return str(worktree_path)

    def cleanup_worktree(self, task_id: str):
        """Remove a worktree after task completion"""
        worktree_path = self.worktrees_dir / task_id

        # Remove worktree
        cmd = ["git", "worktree", "remove", str(worktree_path), "--force"]
        subprocess.run(
            cmd,
            cwd=str(self.root_dir),
            capture_output=True,
            text=True
        )

        # Also remove directory if it still exists
        if worktree_path.exists():
            import shutil
            shutil.rmtree(worktree_path, ignore_errors=True)

    def get_worktree_path(self, task_id: str) -> str:
        """Get the path to a worktree"""
        return str(self.worktrees_dir / task_id)
