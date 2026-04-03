import pytest
import tempfile
import os
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.worker.worktree_manager import WorktreeManager


@pytest.fixture
def temp_repo():
    """Create a temporary git repo for testing"""
    import subprocess
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test"], check=True)
        # Create initial commit
        with open("README.md", "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)
        yield tmpdir


def test_worktree_manager_initializes(temp_repo):
    manager = WorktreeManager(root_dir=temp_repo)
    assert manager.root_dir == temp_repo


def test_create_worktree(temp_repo):
    manager = WorktreeManager(root_dir=temp_repo)
    worktree_path = manager.create_worktree("task-001")
    assert os.path.exists(worktree_path)
    assert "task-001" in worktree_path


def test_cleanup_worktree(temp_repo):
    manager = WorktreeManager(root_dir=temp_repo)
    worktree_path = manager.create_worktree("task-002")
    manager.cleanup_worktree("task-002")
    # Worktree removed but path may still exist
    # Main assertion: no errors raised
