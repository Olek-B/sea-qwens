"""
Tests for GitMerger – branch merge & cleanup logic.
"""

import pytest
import subprocess
import tempfile
import os
import shutil

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from services.tester.merger import GitMerger, MergeResult


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _init_test_repo(tmpdir: str, branch: str = "main") -> None:
    """Create a minimal git repo in *tmpdir* on *branch*."""
    subprocess.run(
        ["git", "init", "-b", branch],
        cwd=tmpdir, capture_output=True, text=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmpdir, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmpdir, capture_output=True, check=True,
    )
    # Initial commit
    readme = os.path.join(tmpdir, "README.md")
    with open(readme, "w") as f:
        f.write("# Project\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=tmpdir, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmpdir, capture_output=True, check=True,
    )


def _create_task_branch(tmpdir: str, task_id: str, file_name: str = "feature.py") -> str:
    """Create a task branch with a new file and commit."""
    branch_name = f"task/{task_id}"
    subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=tmpdir, capture_output=True, check=True,
    )
    feature_path = os.path.join(tmpdir, file_name)
    with open(feature_path, "w") as f:
        f.write(f"# Task {task_id}\ndef hello():\n    return 'hello'\n")
    subprocess.run(
        ["git", "add", "."],
        cwd=tmpdir, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"feat: implement {task_id}"],
        cwd=tmpdir, capture_output=True, check=True,
    )
    return branch_name


# ─── GitMerger Tests ─────────────────────────────────────────────────────────

class TestGitMerger:
    """Tests for the GitMerger class."""

    def test_merger_initializes(self):
        """GitMerger should store the root_dir and derive the repo path."""
        merger = GitMerger("/some/path")
        assert merger.root_dir == "/some/path"

    def test_merge_task_branch_success(self, tmp_path):
        """merge_task_branch should merge a task branch into main."""
        tmpdir = str(tmp_path)
        _init_test_repo(tmpdir)
        task_id = "task-001"
        _create_task_branch(tmpdir, task_id)

        merger = GitMerger(tmpdir)
        result = merger.merge_task_branch(task_id)

        assert result.success is True
        assert result.task_id == task_id
        assert result.conflicts is False
        assert result.error is None

        # Verify the feature file is now on main
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=tmpdir, capture_output=True, check=True,
        )
        feature_path = os.path.join(tmpdir, "feature.py")
        assert os.path.exists(feature_path)

    def test_merge_task_branch_no_branch(self, tmp_path):
        """merge_task_branch should fail gracefully when branch doesn't exist."""
        tmpdir = str(tmp_path)
        _init_test_repo(tmpdir)

        merger = GitMerger(tmpdir)
        result = merger.merge_task_branch("nonexistent")

        assert result.success is False
        assert result.task_id == "nonexistent"
        assert result.error is not None

    def test_merge_task_branch_already_merged(self, tmp_path):
        """merge_task_branch should handle an already-merged branch."""
        tmpdir = str(tmp_path)
        _init_test_repo(tmpdir)
        task_id = "task-002"
        _create_task_branch(tmpdir, task_id)

        merger = GitMerger(tmpdir)
        # First merge should succeed
        result1 = merger.merge_task_branch(task_id)
        assert result1.success is True

        # Second merge: branch may already be merged or deleted
        # The implementation should handle this gracefully
        result2 = merger.merge_task_branch(task_id)
        # Either success (if branch still exists and is fast-forward) or
        # a graceful error is acceptable
        assert isinstance(result2, MergeResult)

    def test_cleanup_task_branch_success(self, tmp_path):
        """cleanup_task_branch should delete the task branch."""
        tmpdir = str(tmp_path)
        _init_test_repo(tmpdir)
        task_id = "task-003"
        _create_task_branch(tmpdir, task_id)

        # Merge first so cleanup is clean
        merger = GitMerger(tmpdir)
        merger.merge_task_branch(task_id)

        result = merger.cleanup_task_branch(task_id)
        assert result is True

        # Verify branch is gone
        result = subprocess.run(
            ["git", "branch", "--list", f"task/{task_id}"],
            cwd=tmpdir, capture_output=True, text=True,
        )
        assert f"task/{task_id}" not in result.stdout

    def test_cleanup_task_branch_nonexistent(self, tmp_path):
        """cleanup_task_branch should handle a non-existent branch gracefully."""
        tmpdir = str(tmp_path)
        _init_test_repo(tmpdir)

        merger = GitMerger(tmpdir)
        result = merger.cleanup_task_branch("nonexistent")
        # Should not raise – return False or True (idempotent)
        assert isinstance(result, bool)

    def test_merge_and_cleanup_full_flow(self, tmp_path):
        """Full flow: create branch, merge, cleanup – should leave main clean."""
        tmpdir = str(tmp_path)
        _init_test_repo(tmpdir)
        task_id = "task-004"
        _create_task_branch(tmpdir, task_id)

        merger = GitMerger(tmpdir)

        # Merge
        merge_result = merger.merge_task_branch(task_id)
        assert merge_result.success is True

        # Cleanup
        cleanup_result = merger.cleanup_task_branch(task_id)
        assert cleanup_result is True

        # Verify we're on main and the feature file exists
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=tmpdir, capture_output=True, text=True,
        )
        assert result.stdout.strip() == "main"

        feature_path = os.path.join(tmpdir, "feature.py")
        assert os.path.exists(feature_path)
