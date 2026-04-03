# services/kanban/tests/test_tool_manager.py
import pytest
from unittest.mock import patch, MagicMock
import requests

from services.kanban.tool_manager import ToolManager, ToolSelectionResult


class TestToolSelectionResult:
    def test_creation(self):
        tool = {"name": "qwen-coder", "command": "qwen --non-interactive"}
        result = ToolSelectionResult(tool=tool, reason="Least-used healthy tool")
        assert result.tool["name"] == "qwen-coder"
        assert result.reason == "Least-used healthy tool"


class TestToolManager:
    @patch("services.kanban.tool_manager.requests.get")
    def test_get_all_tools_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"name": "qwen-coder", "health_status": "HEALTHY", "usage_count": 5}
        ]

        manager = ToolManager(librarian_url="http://localhost:8001")
        tools = manager.get_all_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "qwen-coder"

    @patch("services.kanban.tool_manager.requests.get")
    def test_get_all_tools_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("fail")

        manager = ToolManager(librarian_url="http://localhost:8001")
        tools = manager.get_all_tools()

        assert tools == []

    @patch("services.kanban.tool_manager.requests.get")
    def test_select_tool_least_used(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"name": "tool-a", "health_status": "HEALTHY", "usage_count": 10, "requests_today": 0, "daily_limit": 1000, "capabilities": ["coding"]},
            {"name": "tool-b", "health_status": "HEALTHY", "usage_count": 5, "requests_today": 0, "daily_limit": 1000, "capabilities": ["coding"]},
        ]

        manager = ToolManager()
        result = manager.select_tool()

        assert result is not None
        assert result.tool["name"] == "tool-b"

    @patch("services.kanban.tool_manager.requests.get")
    def test_select_tool_no_healthy_tools(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {"name": "tool-a", "health_status": "ERROR", "usage_count": 10, "requests_today": 0, "daily_limit": 1000, "capabilities": ["coding"]},
        ]

        manager = ToolManager()
        result = manager.select_tool()

        assert result is None

    @patch("services.kanban.tool_manager.requests.post")
    def test_increment_tool_usage(self, mock_post):
        mock_post.return_value.status_code = 200

        manager = ToolManager()
        result = manager.increment_tool_usage("qwen-coder")

        assert result is True
        mock_post.assert_called_once_with("http://localhost:8001/tools/qwen-coder/increment")
