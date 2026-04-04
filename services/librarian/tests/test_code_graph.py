# services/librarian/tests/test_code_graph.py

import pytest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from shared.models import CodeFile, CodeFunction, CodeClass


class TestCodeGraphOperations:
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.run.return_value = MagicMock()
        return session

    @pytest.fixture
    def mock_driver(self, mock_session):
        driver = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        return driver

    @pytest.fixture
    def store(self, mock_driver):
        with patch("services.librarian.neo4j_store.GraphDatabase") as mock_gd:
            mock_gd.driver.return_value = mock_driver
            from services.librarian.neo4j_store import Neo4jStore

            store = Neo4jStore()
            store.driver = mock_driver
            return store

    def test_upsert_file(self, store, mock_session):
        code_file = CodeFile(path="test.py", language="python", content="x = 1")
        store.upsert_file(code_file)
        mock_session.run.assert_called()

    def test_upsert_function(self, store, mock_session):
        func = CodeFunction(
            name="test_func",
            file_path="test.py",
            line_start=1,
            line_end=5,
            body="def test_func(): pass",
        )
        store.upsert_function(func)
        mock_session.run.assert_called()

    def test_upsert_class(self, store, mock_session):
        cls = CodeClass(
            name="TestClass",
            file_path="test.py",
            line_start=1,
            line_end=10,
            body="class TestClass: pass",
        )
        store.upsert_class(cls)
        mock_session.run.assert_called()

    def test_create_call_relationship(self, store, mock_session):
        store.create_call_relationship("func_a", "func_b")
        mock_session.run.assert_called()

    def test_get_function_by_name(self, store, mock_session):
        mock_session.run.return_value.single.return_value = {
            "f": {
                "name": "test_func",
                "body": "def test_func(): pass",
                "file_path": "test.py",
                "signature": "def test_func(): pass",
                "docstring": "",
                "is_method": False,
            }
        }
        result = store.get_function_by_name("test_func")
        assert result is not None
        assert result["name"] == "test_func"

    def test_get_callers(self, store, mock_session):
        mock_session.run.return_value = [
            {"caller": {"name": "func_a"}},
            {"caller": {"name": "func_b"}},
        ]
        result = store.get_callers("target_func")
        assert len(result) == 2

    def test_get_callees(self, store, mock_session):
        mock_session.run.return_value = [{"callee": {"name": "helper_func"}}]
        result = store.get_callees("main_func")
        assert len(result) == 1
        assert result[0]["name"] == "helper_func"

    def test_search_functions_semantic(self, store, mock_session):
        mock_session.run.return_value = [
            {"f": {"name": "login", "body": "def login(): ..."}}
        ]
        result = store.search_functions("authentication")
        assert len(result) == 1
