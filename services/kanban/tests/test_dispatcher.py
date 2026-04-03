import pytest
import sys
from unittest.mock import MagicMock, patch

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


def test_handle_rate_limit_marks_profile_and_resets_task():
    """handle_rate_limit should mark profile rate-limited and reset task to PENDING"""
    dispatcher = Dispatcher()
    dispatcher.profile_manager = MagicMock()

    task = {"task_id": "task-42"}

    with patch("services.kanban.dispatcher.requests.post") as mock_post:
        dispatcher.handle_rate_limit(task, "qwen-agent-03")

        # Profile marked as rate-limited
        dispatcher.profile_manager.mark_profile_rate_limited.assert_called_once_with(
            "qwen-agent-03"
        )

        # Task reset to PENDING
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["params"] == {"task_id": "task-42"}
        assert call_args[1]["json"] == {"status": "PENDING"}


def test_handle_rate_limit_logs_warning():
    """handle_rate_limit should log a warning with profile and task info"""
    dispatcher = Dispatcher()
    dispatcher.profile_manager = MagicMock()

    task = {"task_id": "task-99"}

    with patch("services.kanban.dispatcher.requests.post"), \
         patch("services.kanban.dispatcher.logger.warning") as mock_warn:
        dispatcher.handle_rate_limit(task, "qwen-agent-07")
        mock_warn.assert_called_once()
        assert "qwen-agent-07" in mock_warn.call_args[0][0]
        assert "task-99" in mock_warn.call_args[0][0]


def test_handle_rate_limit_handles_request_error_gracefully():
    """handle_rate_limit should not raise if the PENDING update fails"""
    dispatcher = Dispatcher()
    dispatcher.profile_manager = MagicMock()

    task = {"task_id": "task-55"}

    with patch("services.kanban.dispatcher.requests.post") as mock_post:
        import requests as req
        mock_post.side_effect = req.exceptions.RequestException("connection error")

        with patch("services.kanban.dispatcher.logger.error") as mock_err:
            dispatcher.handle_rate_limit(task, "qwen-agent-10")
            # Should log error but not raise
            mock_err.assert_called_once()
            assert "Failed to re-queue task" in mock_err.call_args[0][0]


def test_dispatch_task_handles_429_response():
    """dispatch_task should call handle_rate_limit on 429 and return failure"""
    dispatcher = Dispatcher()

    mock_selection = MagicMock()
    mock_selection.profile = {"name": "qwen-agent-05"}
    dispatcher.profile_manager.select_profile = MagicMock(return_value=mock_selection)
    dispatcher.profile_manager.increment_profile_usage = MagicMock()
    dispatcher.handle_rate_limit = MagicMock()

    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.text = "Too Many Requests"

    task = {"task_id": "task-100"}

    with patch("services.kanban.dispatcher.requests.post", return_value=mock_429):
        result = dispatcher.dispatch_task(task)

        dispatcher.handle_rate_limit.assert_called_once_with(task, "qwen-agent-05")
        assert result.success is False
        assert result.task_id == "task-100"
        assert "Rate limit hit" in result.message
        assert result.profile_name == "qwen-agent-05"
