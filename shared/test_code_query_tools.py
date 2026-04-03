import pytest
import requests
from shared.code_query_tools import CodeQueryTools, ProjectCodeContext


class TestCodeQueryTools:
    """Tests for the base CodeQueryTools HTTP client."""

    def test_init_stores_url(self):
        tools = CodeQueryTools("http://localhost:8001")
        assert tools.librarian_url == "http://localhost:8001"

    def test_init_default_url(self):
        tools = CodeQueryTools()
        assert tools.librarian_url == "http://localhost:8001"


class TestCodeQueryToolsErrorHandling:
    """Tests for CodeQueryTools error handling."""

    def test_search_code_returns_empty_list_on_connection_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))
        tools = CodeQueryTools("http://localhost:9999")
        result = tools.search_code("test")
        assert result == []

    def test_get_function_returns_none_on_404(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 404
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.get_function("nonexistent")
        assert result is None

    def test_get_function_returns_none_on_connection_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_function("test")
        assert result is None

    def test_get_callers_returns_empty_list_on_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_callers("test")
        assert result == []

    def test_get_callees_returns_empty_list_on_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_callees("test")
        assert result == []

    def test_get_full_context_returns_empty_dict_on_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_full_context("test")
        assert result == {}

    def test_get_class_returns_none_on_error(self, mocker):
        mocker.patch("requests.get", side_effect=requests.RequestException("Connection refused"))

        tools = CodeQueryTools("http://localhost:9999")
        result = tools.get_class("test")
        assert result is None


class TestCodeQueryToolsSuccess:
    """Tests for CodeQueryTools successful responses."""

    def test_search_code_returns_results(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"name": "my_func", "file": "app.py"}]}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.search_code("authentication")
        assert len(result) == 1
        assert result[0]["name"] == "my_func"

    def test_search_code_returns_empty_on_no_results_key(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"other": "data"}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.search_code("test")
        assert result == []

    def test_get_function_returns_data(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "login", "body": "def login(): ..."}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.get_function("login")
        assert result is not None
        assert result["name"] == "login"

    def test_get_callers_returns_list(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"callers": [{"name": "caller1"}]}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.get_callers("target")
        assert len(result) == 1
        assert result[0]["name"] == "caller1"

    def test_get_callees_returns_list(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"callees": [{"name": "callee1"}]}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.get_callees("source")
        assert len(result) == 1
        assert result[0]["name"] == "callee1"

    def test_get_full_context_returns_dict(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"function": {}, "callers": [], "callees": []}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.get_full_context("my_func")
        assert "function" in result

    def test_get_class_returns_data(self, mocker):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"class": {"name": "AuthService"}, "methods": []}
        mocker.patch("requests.get", return_value=mock_response)

        tools = CodeQueryTools("http://localhost:8001")
        result = tools.get_class("AuthService")
        assert result is not None
        assert result["class"]["name"] == "AuthService"


class TestProjectCodeContext:
    """Tests for ProjectCodeContext higher-level helpers."""

    def test_init_stores_tools(self):
        tools = CodeQueryTools("http://localhost:8001")
        ctx = ProjectCodeContext(tools)
        assert ctx.tools is tools


class TestProjectCodeContextHelpers:
    """Tests for ProjectCodeContext helper methods."""

    def test_get_project_overview_returns_none_when_empty(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.return_value = []
        ctx = ProjectCodeContext(tools)

        result = ctx.get_project_overview("myproject")
        assert result is None

    def test_get_project_overview_returns_summary(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.side_effect = [
            [{"name": "func1", "file": "app.py"}, {"name": "func2", "file": "utils.py"}],
            [{"name": "MyClass", "metadata": {"file": "app.py"}}],
        ]
        ctx = ProjectCodeContext(tools)

        result = ctx.get_project_overview("myproject")
        assert result is not None
        assert result["total_functions"] == 2
        assert result["total_classes"] == 1
        assert result["total_files"] == 2
        assert result["project_name"] == "myproject"

    def test_find_existing_features(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.side_effect = [
            [{"name": "authenticate"}],
            [{"name": "AuthService"}],
            [],
            [],
        ]
        ctx = ProjectCodeContext(tools)

        result = ctx.find_existing_features("myproject", ["auth", "payment"])
        assert result["auth"]["found"] is True
        assert result["payment"]["found"] is False
        assert len(result["auth"]["matches"]) == 2

    def test_find_existing_features_all_missing(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.return_value = []
        ctx = ProjectCodeContext(tools)

        result = ctx.find_existing_features("myproject", ["auth", "payment"])
        assert result["auth"]["found"] is False
        assert result["payment"]["found"] is False

    def test_get_dependency_map(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.side_effect = [
            [{"name": "func_a"}, {"name": "func_b"}],
            [],
        ]
        tools.get_callees.side_effect = [
            [{"name": "func_b"}],
            [],
        ]
        tools.get_class.return_value = None
        ctx = ProjectCodeContext(tools)

        result = ctx.get_dependency_map()
        assert len(result["calls"]) == 1
        assert result["calls"][0] == {"caller": "func_a", "callee": "func_b"}
        assert result["inherits"] == []

    def test_get_dependency_map_with_inherits(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.side_effect = [
            [],
            [{"name": "AdminService"}],
        ]
        tools.get_class.return_value = {"class": {"name": "AdminService", "bases": ["AuthService"]}}
        ctx = ProjectCodeContext(tools)

        result = ctx.get_dependency_map()
        assert len(result["inherits"]) == 1
        assert result["inherits"][0] == {"child": "AdminService", "parent": "AuthService"}

    def test_search_by_category(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        tools.search_code.return_value = [{"name": "AuthService"}]
        ctx = ProjectCodeContext(tools)

        result = ctx.search_by_category("auth")
        assert len(result) >= 1

    def test_search_by_category_deduplicates(self, mocker):
        tools = mocker.Mock(spec=CodeQueryTools)
        # Same result returned for multiple keywords
        tools.search_code.return_value = [{"name": "AuthService"}]
        ctx = ProjectCodeContext(tools)

        result = ctx.search_by_category("auth")
        names = [r["name"] for r in result]
        assert names.count("AuthService") == 1
