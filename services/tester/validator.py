"""
Contract Validator for Sea Qwens Tester Service.

Validates worker output against contracts through:
1. JSON Schema contract validation
2. Test suite execution (pytest)
3. Semantic validation (LLM-based, placeholder)
"""

import subprocess
import os
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import jsonschema


# ─── JSON Schema for Contract Validation ─────────────────────────────────────

CONTRACT_SCHEMA = {
    "type": "object",
    "required": ["input", "output"],
    "properties": {
        "input": {
            "type": "object",
            "properties": {
                "fields": {"type": "array", "items": {"type": "string"}},
                "format": {"type": "string"},
            },
        },
        "output": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "fields": {"type": "array", "items": {"type": "string"}},
            },
        },
        "constraints": {
            "type": "array",
            "items": {"type": "string"},
        },
        "tests": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


# ─── ValidationResult ────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Result of a full contract validation pipeline."""
    passed: bool
    contract_valid: bool
    tests_passed: bool
    semantic_valid: bool
    errors: list[str] = field(default_factory=list)


# ─── ContractValidator ───────────────────────────────────────────────────────

class ContractValidator:
    """Validate worker output against task contracts."""

    def validate(
        self,
        task_id: str,
        worktree_path: str,
        contract: dict,
    ) -> ValidationResult:
        """
        Run the full validation pipeline for a task.

        1. Validate contract structure (JSON Schema)
        2. Extract metadata from worktree
        3. Run pytest in worktree
        4. Run semantic validation (LLM-based, placeholder)
        5. Return aggregated ValidationResult
        """
        errors: list[str] = []

        # Validate worktree path exists
        wt_path = Path(worktree_path)
        if not wt_path.exists() or not wt_path.is_dir():
            return ValidationResult(
                passed=False,
                contract_valid=False,
                tests_passed=False,
                semantic_valid=False,
                errors=[f"Worktree path does not exist: {worktree_path}"],
            )

        # Step 1: Contract validation
        contract_errors = self._validate_contract(contract)
        contract_valid = len(contract_errors) == 0
        errors.extend(contract_errors)

        # Step 2: Extract metadata (informational, doesn't affect pass/fail)
        metadata = self._extract_metadata(worktree_path)

        # Step 3: Run tests
        tests_passed, test_output = self._run_tests(worktree_path)
        if not tests_passed:
            errors.append(f"Tests failed: {test_output[:500]}")

        # Step 4: Semantic validation
        semantic_valid, semantic_errors = self._validate_semantic(
            task_id, worktree_path, contract
        )
        errors.extend(semantic_errors)

        # Aggregate result
        passed = contract_valid and tests_passed and semantic_valid

        return ValidationResult(
            passed=passed,
            contract_valid=contract_valid,
            tests_passed=tests_passed,
            semantic_valid=semantic_valid,
            errors=errors,
        )

    def _validate_contract(self, contract: dict) -> list[str]:
        """
        Validate contract structure against JSON Schema.

        Returns a list of validation errors (empty if valid).
        """
        errors: list[str] = []

        # Check that contract is a dict
        if not isinstance(contract, dict):
            return [f"Contract must be a dict, got {type(contract).__name__}"]

        # Validate against schema
        try:
            jsonschema.validate(instance=contract, schema=CONTRACT_SCHEMA)
        except jsonschema.ValidationError as e:
            errors.append(f"Contract schema validation failed: {e.message}")
        except jsonschema.SchemaError as e:
            errors.append(f"Schema error: {e.message}")

        return errors

    def _extract_metadata(self, worktree_path: str) -> dict:
        """
        Extract metadata from the worktree.

        Returns dict with:
        - files_created: list of file paths
        - has_main: whether any file contains a main() function
        """
        wt_path = Path(worktree_path)
        files_created: list[str] = []
        has_main = False

        if not wt_path.exists():
            return {"files_created": [], "has_main": False}

        # Walk the worktree and collect Python files
        for root, dirs, files in os.walk(wt_path):
            # Skip hidden directories and common non-source dirs
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and d not in (
                    "__pycache__", "node_modules", ".git", ".venv", "venv"
                )
            ]

            for filename in files:
                if filename.endswith(".py"):
                    filepath = Path(root) / filename
                    rel_path = str(filepath.relative_to(wt_path))
                    files_created.append(rel_path)

                    # Check for main function
                    if not has_main:
                        try:
                            content = filepath.read_text()
                            if re.search(r"def\s+main\s*\(", content):
                                has_main = True
                        except (OSError, UnicodeDecodeError):
                            pass

        return {
            "files_created": sorted(files_created),
            "has_main": has_main,
        }

    def _run_tests(self, worktree_path: str) -> tuple[bool, str]:
        """
        Run pytest in the worktree directory.

        Returns (passed, output) tuple.
        """
        wt_path = Path(worktree_path)

        if not wt_path.exists():
            return False, f"Error: worktree path not found: {worktree_path}"

        try:
            result = subprocess.run(
                ["pytest", "-v", "--tb=short"],
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=120,
            )

            output = result.stdout + result.stderr
            passed = result.returncode == 0

            return passed, output

        except subprocess.TimeoutExpired:
            return False, "Error: tests timed out (120s)"
        except FileNotFoundError:
            return False, "Error: pytest not found in environment"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def _validate_semantic(
        self,
        task_id: str,
        worktree_path: str,
        contract: dict,
    ) -> tuple[bool, list[str]]:
        """
        Semantic validation via LLM analysis (placeholder).

        In production, this would send the contract + generated code to an
        LLM to verify the implementation matches the specification.

        Returns (valid, errors) tuple.
        """
        # Placeholder: return True with a note
        return True, [
            "Semantic validation not yet implemented (LLM-based check)"
        ]
