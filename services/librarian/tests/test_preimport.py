import pytest
import tempfile
import os
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')


class TestPreimporter:

    @pytest.fixture
    def sample_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "auth"))
            with open(os.path.join(tmpdir, "auth", "__init__.py"), "w") as f:
                f.write("")
            with open(os.path.join(tmpdir, "auth", "service.py"), "w") as f:
                f.write('''
class AuthService:
    def login(self, username, password):
        return True
    def logout(self, user_id):
        return True

def verify_token(token):
    return True
''')
            with open(os.path.join(tmpdir, "main.py"), "w") as f:
                f.write('''
from auth.service import AuthService

def main():
    auth = AuthService()
    auth.login("user", "pass")

if __name__ == "__main__":
    main()
''')
            yield tmpdir

    def test_scan_project(self, sample_project):
        from services.librarian.preimport import scan_project
        files = scan_project(sample_project)
        py_files = [f for f in files if f.endswith(".py")]
        assert len(py_files) >= 3

    def test_import_file(self, sample_project):
        from unittest.mock import MagicMock
        from services.librarian.preimport import import_file
        filepath = os.path.join(sample_project, "auth", "service.py")
        mock_neo4j = MagicMock()
        mock_chroma = MagicMock()
        result = import_file(filepath, sample_project, mock_neo4j, mock_chroma)
        assert result is not None
        assert "functions" in result
