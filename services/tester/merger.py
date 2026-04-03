"""
GitMerger – merge task branches into main and clean up.

Used by the Tester service after validation passes:
1. Merge the worker's task branch into main
2. Handle merge conflicts gracefully
3. Delete the task branch after a successful merge
"""

import subprocess
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ─── MergeResult ─────────────────────────────────────────────────────────────

@dataclass
class MergeResult:
    """Result of a merge operation."""
    success: bool
    task_id: str
    conflicts: bool = False
    error: Optional[str] = None
    output: str = ""


# ─── GitMerger ───────────────────────────────────────────────────────────────

class GitMerger:
    """Merge task branches into main and clean up."""

    MAIN_BRANCH = "main"

    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        """Run a git command in the root directory."""
        return subprocess.run(
            ["git", *args],
            cwd=self.root_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _branch_exists(self, branch: str) -> bool:
        """Check if a branch exists."""
        result = self._run_git("branch", "--list", branch)
        return branch in result.stdout

    def merge_task_branch(self, task_id: str) -> MergeResult:
        """
        Merge a task branch (task/<task_id>) into main.

        Steps:
        1. Ensure we're on main
        2. Check the task branch exists
        3. Attempt merge (no-ff for auditability)
        4. Handle conflicts by aborting the merge

        Returns a MergeResult with success status and any error details.
        """
        branch = f"task/{task_id}"

        # Check branch exists
        if not self._branch_exists(branch):
            return MergeResult(
                success=False,
                task_id=task_id,
                error=f"Branch '{branch}' does not exist",
            )

        # Ensure we're on main
        checkout = self._run_git("checkout", self.MAIN_BRANCH)
        if checkout.returncode != 0:
            return MergeResult(
                success=False,
                task_id=task_id,
                error=f"Failed to checkout {self.MAIN_BRANCH}: {checkout.stderr}",
            )

        # Pull latest main (best-effort, ignore if no remote)
        self._run_git("pull", "origin", self.MAIN_BRANCH)

        # Attempt merge
        merge = self._run_git("merge", "--no-ff", branch, "-m",
                              f"Merge {branch} into {self.MAIN_BRANCH}")

        if merge.returncode != 0:
            # Check if it's a conflict
            conflict_detected = "CONFLICT" in merge.stdout or "CONFLICT" in merge.stderr

            # Abort the merge to leave repo in clean state
            self._run_git("merge", "--abort")

            return MergeResult(
                success=False,
                task_id=task_id,
                conflicts=conflict_detected,
                error=f"Merge failed: {merge.stderr or merge.stdout}",
            )

        logger.info(f"Successfully merged {branch} into {self.MAIN_BRANCH}")
        return MergeResult(
            success=True,
            task_id=task_id,
            conflicts=False,
            output=merge.stdout,
        )

    def cleanup_task_branch(self, task_id: str) -> bool:
        """
        Delete the task branch after a successful merge.

        Returns True if the branch was deleted or didn't exist (idempotent).
        Returns False if deletion failed for an unexpected reason.
        """
        branch = f"task/{task_id}"

        if not self._branch_exists(branch):
            logger.info(f"Branch '{branch}' already removed – nothing to do")
            return True

        # Ensure we're on main (can't delete branch we're on)
        checkout = self._run_git("checkout", self.MAIN_BRANCH)
        if checkout.returncode != 0:
            logger.error(f"Failed to checkout {self.MAIN_BRANCH}: {checkout.stderr}")
            return False

        # Force delete the branch
        delete = self._run_git("branch", "-D", branch)
        if delete.returncode != 0:
            logger.error(f"Failed to delete branch '{branch}': {delete.stderr}")
            return False

        logger.info(f"Deleted branch '{branch}'")
        return True
