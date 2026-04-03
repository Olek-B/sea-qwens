import pytest
import sys
import os
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from services.tester.validator import ValidationResult, ContractValidator


# ─── ValidationResult Tests ──────────────────────────────────────────────────

def test_validation_result_pass():
    """ValidationResult should represent a fully passing validation."""
    result = ValidationResult(
        passed=True,
        contract_valid=True,
        tests_passed=True,
        semantic_valid=True,
        errors=[],
    )

    assert result.passed is True
    assert result.contract_valid is True
    assert result.tests_passed is True
    assert result.semantic_valid is True
    assert result.errors == []


def test_validation_result_contract_fail():
    """ValidationResult should capture contract validation failures."""
    result = ValidationResult(
        passed=False,
        contract_valid=False,
        tests_passed=True,
        semantic_valid=True,
        errors=["Missing required field: 'output' in contract"],
    )

    assert result.passed is False
    assert result.contract_valid is False
    assert result.tests_passed is True
    assert result.semantic_valid is True
    assert len(result.errors) == 1
    assert "Missing required field" in result.errors[0]


def test_validation_result_tests_fail():
    """ValidationResult should capture test failures."""
    result = ValidationResult(
        passed=False,
        contract_valid=True,
        tests_passed=False,
        semantic_valid=True,
        errors=["test_create_user failed: AssertionError"],
    )

    assert result.passed is False
    assert result.contract_valid is True
    assert result.tests_passed is False
    assert result.semantic_valid is True
    assert "test_create_user failed" in result.errors[0]


def test_validation_result_semantic_fail():
    """ValidationResult should capture semantic validation failures."""
    result = ValidationResult(
        passed=False,
        contract_valid=True,
        tests_passed=True,
        semantic_valid=False,
        errors=["Semantic check: endpoint does not match contract spec"],
    )

    assert result.passed is False
    assert result.contract_valid is True
    assert result.tests_passed is True
    assert result.semantic_valid is False


def test_validation_result_multiple_errors():
    """ValidationResult should accumulate multiple errors."""
    errors = [
        "Contract missing 'output' field",
        "test_login failed",
        "Semantic mismatch on /auth endpoint",
    ]
    result = ValidationResult(
        passed=False,
        contract_valid=False,
        tests_passed=False,
        semantic_valid=False,
        errors=errors,
    )

    assert result.passed is False
    assert len(result.errors) == 3
    assert result.contract_valid is False
    assert result.tests_passed is False
    assert result.semantic_valid is False


# ─── ContractValidator Tests ─────────────────────────────────────────────────

class TestContractValidator:
    """Tests for the ContractValidator class."""

    def setup_method(self):
        self.validator = ContractValidator()

    def _create_temp_worktree(self, files=None):
        """Create a temporary directory simulating a worktree with optional files."""
        tmpdir = tempfile.mkdtemp()
        if files:
            for filename, content in files.items():
                filepath = os.path.join(tmpdir, filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'w') as f:
                    f.write(content)
        return tmpdir

    # ─── _validate_contract tests ────────────────────────────────────────────

    def test_validate_contract_valid(self):
        """_validate_contract should pass for a well-formed contract."""
        contract = {
            "input": {"fields": ["username", "password"]},
            "output": {"type": "JWT", "fields": ["token", "expiry"]},
            "constraints": ["password must be hashed", "token expires in 24h"],
        }
        errors = self.validator._validate_contract(contract)
        assert errors == []

    def test_validate_contract_missing_required(self):
        """_validate_contract should flag missing required fields."""
        contract = {"input": {"fields": ["username"]}}
        errors = self.validator._validate_contract(contract)
        assert len(errors) > 0
        assert any("output" in e for e in errors)

    def test_validate_contract_empty(self):
        """_validate_contract should flag an empty contract."""
        errors = self.validator._validate_contract({})
        assert len(errors) > 0

    def test_validate_contract_invalid_type(self):
        """_validate_contract should handle non-dict input gracefully."""
        errors = self.validator._validate_contract("not a dict")
        assert len(errors) > 0

    # ─── _extract_metadata tests ─────────────────────────────────────────────

    def test_extract_metadata_with_main(self):
        """_extract_metadata should detect files_created and has_main."""
        tmpdir = self._create_temp_worktree({
            "src/app.py": "def main(): pass",
            "src/utils.py": "def helper(): pass",
            "tests/test_app.py": "def test_app(): pass",
        })

        metadata = self.validator._extract_metadata(tmpdir)

        assert metadata["has_main"] is True
        assert "src/app.py" in metadata["files_created"]
        assert "src/utils.py" in metadata["files_created"]
        assert "tests/test_app.py" in metadata["files_created"]

    def test_extract_metadata_no_main(self):
        """_extract_metadata should detect absence of main function."""
        tmpdir = self._create_temp_worktree({
            "src/utils.py": "def helper(): pass",
        })

        metadata = self.validator._extract_metadata(tmpdir)

        assert metadata["has_main"] is False
        assert "src/utils.py" in metadata["files_created"]

    def test_extract_metadata_empty_worktree(self):
        """_extract_metadata should handle an empty worktree."""
        tmpdir = self._create_temp_worktree()
        metadata = self.validator._extract_metadata(tmpdir)

        assert metadata["has_main"] is False
        assert metadata["files_created"] == []

    # ─── _run_tests tests ────────────────────────────────────────────────────

    def test_run_tests_passing(self):
        """_run_tests should return True when pytest passes."""
        tmpdir = self._create_temp_worktree({
            "tests/test_dummy.py": "def test_always_passes():\n    assert True\n",
        })

        passed, output = self.validator._run_tests(tmpdir)

        assert passed is True
        assert "passed" in output.lower() or "1 passed" in output

    def test_run_tests_failing(self):
        """_run_tests should return False when pytest fails."""
        tmpdir = self._create_temp_worktree({
            "tests/test_dummy.py": "def test_always_fails():\n    assert False\n",
        })

        passed, output = self.validator._run_tests(tmpdir)

        assert passed is False

    def test_run_tests_no_tests(self):
        """_run_tests should handle a worktree with no test files."""
        tmpdir = self._create_temp_worktree({
            "src/app.py": "def main(): pass",
        })

        passed, output = self.validator._run_tests(tmpdir)

        # No tests found is not a failure, just no test results
        assert isinstance(passed, bool)

    def test_run_tests_invalid_worktree(self):
        """_run_tests should handle a non-existent worktree path."""
        passed, output = self.validator._run_tests("/nonexistent/path")

        assert passed is False
        assert "error" in output.lower() or "not found" in output.lower()

    # ─── _validate_semantic tests ────────────────────────────────────────────

    def test_validate_semantic_placeholder(self):
        """_validate_semantic should return a placeholder result for now."""
        tmpdir = self._create_temp_worktree({
            "src/app.py": "def main(): pass",
        })
        contract = {"input": {}, "output": {}}

        valid, errors = self.validator._validate_semantic("task-001", tmpdir, contract)

        # Placeholder: should return True with a note that it's not implemented
        assert isinstance(valid, bool)
        assert isinstance(errors, list)

    # ─── validate (full pipeline) tests ──────────────────────────────────────

    def test_validate_full_pass(self):
        """validate should return a passing ValidationResult for good work."""
        tmpdir = self._create_temp_worktree({
            "src/app.py": "def main(): pass\n",
            "tests/test_app.py": "def test_main():\n    assert True\n",
        })
        contract = {"input": {}, "output": {}}

        result = self.validator.validate("task-001", tmpdir, contract)

        assert isinstance(result, ValidationResult)
        assert result.contract_valid is True
        assert result.tests_passed is True

    def test_validate_contract_fail(self):
        """validate should flag contract validation failures."""
        tmpdir = self._create_temp_worktree({
            "src/app.py": "def main(): pass\n",
        })
        contract = {}  # Empty contract should fail

        result = self.validator.validate("task-002", tmpdir, contract)

        assert isinstance(result, ValidationResult)
        assert result.contract_valid is False
        assert result.passed is False

    def test_validate_invalid_worktree_path(self):
        """validate should handle a non-existent worktree path."""
        result = self.validator.validate("task-003", "/nonexistent", {})

        assert isinstance(result, ValidationResult)
        assert result.passed is False
        assert len(result.errors) > 0
