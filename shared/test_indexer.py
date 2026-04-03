# shared/test_indexer.py

import pytest
from shared.indexer import CodeIndexer, IndexResult, CallRelation


@pytest.fixture
def sample_python_file():
    return '''
"""Sample module for testing."""

class AuthService:
    """Handles authentication."""
    
    def __init__(self, db):
        self.db = db
    
    def login(self, username, password):
        """Authenticate a user."""
        user = self.db.find_user(username)
        if user and verify_password(password, user.hash):
            return create_token(user.id)
        return None

def verify_password(password, hash):
    """Verify password against hash."""
    return password == hash

def create_token(user_id):
    """Create auth token."""
    return f"token-{user_id}"

def get_user(db, user_id):
    """Fetch user from database."""
    return db.find_by_id(user_id)
'''


def test_indexer_extracts_functions(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    func_names = [f.name for f in result.functions]
    assert "login" in func_names
    assert "verify_password" in func_names
    assert "create_token" in func_names
    assert "get_user" in func_names


def test_indexer_extracts_class(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    assert len(result.classes) == 1
    assert result.classes[0].name == "AuthService"


def test_indexer_extracts_methods(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    methods = [f for f in result.functions if f.is_method]
    method_names = [m.name for m in methods]
    assert "login" in method_names
    assert "__init__" in method_names


def test_indexer_detects_calls(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    login_calls = [c.callee for c in result.calls if c.caller == "login"]
    assert "verify_password" in login_calls
    assert "create_token" in login_calls


def test_index_result_has_file_info(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    assert result.file.path == "auth.py"
    assert result.file.language == "python"
