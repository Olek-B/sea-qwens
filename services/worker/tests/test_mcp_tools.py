import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from services.worker.mcp_tools import CodeQueryTools


class TestMCPTools:

    @pytest.fixture
    def tools(self):
        return CodeQueryTools(librarian_url="http://localhost:8001")

    def test_search_code(self, tools):
        with patch('services.worker.mcp_tools.requests.get') as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"results": [{"name": "auth"}]})
            result = tools.search_code("authentication")
            assert isinstance(result, list)
            mock_get.assert_called_once()

    def test_get_function(self, tools):
        with patch('services.worker.mcp_tools.requests.get') as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"name": "login", "body": "def login(): ..."})
            result = tools.get_function("login")
            assert result is not None
            mock_get.assert_called_once()

    def test_get_callers(self, tools):
        with patch('services.worker.mcp_tools.requests.get') as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"callers": ["main", "cli"]})
            result = tools.get_callers("login")
            assert isinstance(result, list)
            mock_get.assert_called_once()

    def test_get_callees(self, tools):
        with patch('services.worker.mcp_tools.requests.get') as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"callees": ["db_connect", "validate"]})
            result = tools.get_callees("main")
            assert isinstance(result, list)
            mock_get.assert_called_once()

    def test_get_full_context(self, tools):
        with patch('services.worker.mcp_tools.requests.get') as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"function": {}, "callers": [], "callees": []})
            result = tools.get_full_context("login")
            assert isinstance(result, dict)
            mock_get.assert_called_once()

    def test_get_class(self, tools):
        with patch('services.worker.mcp_tools.requests.get') as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"name": "AuthService", "methods": []})
            result = tools.get_class("AuthService")
            assert result is not None
            mock_get.assert_called_once()
