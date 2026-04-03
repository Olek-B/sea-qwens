import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens/worktrees/legion-implement')
from services.kanban.dispatcher import Dispatcher, DispatchResult


def test_dispatcher_initializes():
    dispatcher = Dispatcher()
    assert dispatcher.librarian_url != ""
    assert dispatcher.worker_url != ""


def test_dispatch_result_success():
    result = DispatchResult(
        success=True,
        task_id="task-001",
        profile_name="qwen-agent-01",
        message="Dispatched successfully"
    )
    assert result.success
    assert result.task_id == "task-001"
