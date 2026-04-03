# services/kanban/tests/test_dispatcher.py
import pytest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from services.kanban.dispatcher import Dispatcher, DispatchResult


def test_dispatcher_initializes():
    dispatcher = Dispatcher()
    assert dispatcher.librarian_url != ""
    assert dispatcher.worker_url != ""


def test_dispatch_result_success():
    result = DispatchResult(
        success=True,
        task_id="task-001",
        tool_name="qwen-coder",
        message="Dispatched successfully"
    )
    assert result.success
    assert result.task_id == "task-001"


def test_handle_rate_limit_marks_tool_and_resets_task():
    """handle_rate_limit should mark tool rate-limited and reset task to PENDING"""
    dispatcher = Dispatcher()
    dispatcher.tool_manager = MagicMock()

    task = {"task_id": "task-42"}

    with patch("services.kanban.dispatcher.requests.post") as mock_post:
        dispatcher.handle_rate_limit(task, "qwen-coder")

        dispatcher.tool_manager.mark_tool_rate_limited.assert_called_once_with(
            "qwen-coder"
        )

        call_args = mock_post.call_args
        assert call_args[1]["params"] == {"task_id": "task-42"}
        assert call_args[1]["json"] == {"status": "PENDING"}


def test_handle_rate_limit_logs_warning():
    """handle_rate_limit should log a warning with tool and task info"""
    dispatcher = Dispatcher()
    dispatcher.tool_manager = MagicMock()

    task = {"task_id": "task-99"}

    with patch("services.kanban.dispatcher.requests.post"), \
         patch("services.kanban.dispatcher.logger.warning") as mock_warn:
        dispatcher.handle_rate_limit(task, "qwen-coder")
        mock_warn.assert_called_once()
        assert "qwen-coder" in mock_warn.call_args[0][0]
        assert "task-99" in mock_warn.call_args[0][0]


def test_handle_rate_limit_handles_request_error_gracefully():
    """handle_rate_limit should not raise if the PENDING update fails"""
    dispatcher = Dispatcher()
    dispatcher.tool_manager = MagicMock()

    task = {"task_id": "task-55"}

    with patch("services.kanban.dispatcher.requests.post") as mock_post:
        import requests as req
        mock_post.side_effect = req.exceptions.RequestException("connection error")

        with patch("services.kanban.dispatcher.logger.error") as mock_err:
            dispatcher.handle_rate_limit(task, "qwen-coder")
            mock_err.assert_called_once()
            assert "Failed to re-queue task" in mock_err.call_args[0][0]


def test_dispatch_task_handles_429_response():
    """dispatch_task should call handle_rate_limit on 429 and return failure"""
    dispatcher = Dispatcher()

    mock_selection = MagicMock()
    mock_selection.tool = {"name": "qwen-coder", "command": "qwen --non-interactive"}
    dispatcher.tool_manager.select_tool = MagicMock(return_value=mock_selection)
    dispatcher.tool_manager.increment_tool_usage = MagicMock()
    dispatcher.handle_rate_limit = MagicMock()

    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.text = "Too Many Requests"

    task = {"task_id": "task-100"}

    with patch("services.kanban.dispatcher.requests.post", return_value=mock_429):
        result = dispatcher.dispatch_task(task)

        dispatcher.handle_rate_limit.assert_called_once_with(task, "qwen-coder")
        assert result.success is False
        assert result.task_id == "task-100"
        assert "Rate limit hit" in result.message
        assert result.tool_name == "qwen-coder"


def test_dispatch_task_passes_adapter_to_worker():
    """dispatch_task should include the adapter field when calling Worker."""
    dispatcher = Dispatcher()

    mock_selection = MagicMock()
    mock_selection.tool = {
        "name": "qwen-code",
        "command": "qwen --non-interactive",
        "adapter": "qwen.sh",
    }
    dispatcher.tool_manager.select_tool = MagicMock(return_value=mock_selection)
    dispatcher.tool_manager.increment_tool_usage = MagicMock()

    mock_response = MagicMock()
    mock_response.status_code = 200
    task = {"task_id": "task-adapter-test"}

    with patch("services.kanban.dispatcher.requests.post", return_value=mock_response) as mock_post:
        result = dispatcher.dispatch_task(task)

        assert result.success is True
        # Verify the adapter field was included in the Worker request
        call_json = mock_post.call_args[1]["json"]
        assert "adapter" in call_json
        assert call_json["adapter"] == "qwen.sh"
