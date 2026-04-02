# Project Legion Plan 4: Worker + Tester Services

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Worker execution agent that runs tasks in isolated git worktrees using qwen-code CLI, and the Supreme Tester that validates contracts and manages merges.

**Architecture:** Worker receives tasks from Kanban, creates git worktrees, executes `qwen-code --profile [name]`, and runs self-tests. Tester validates code against contracts (JSON Schema + generated tests + LLM semantic check), then merges or requests retry.

**Tech Stack:** Python 3.11+, FastAPI, subprocess (git worktree, qwen-code CLI), pytest, JSON Schema validation, requests

---

## File Structure

```
/legion-root/
├── worktrees/              # Isolated git worktrees (gitignored)
├── services/
│   ├── worker/
│   │   ├── app.py          # FastAPI application
│   │   ├── executor.py     # Task execution logic
│   │   ├── worktree_manager.py # Git worktree operations
│   │   ├── requirements.txt
│   │   └── tests/
│   │       ├── test_executor.py
│   │       └── test_worktree.py
│   └── tester/
│       ├── app.py          # FastAPI application
│       ├── validator.py    # Contract validation
│       ├── merger.py       # Git merge operations
│       ├── requirements.txt
│       └── tests/
│           ├── test_validator.py
│           └── test_merger.py
```

---

### Task 1: Worker Worktree Manager

**Files:**
- Create: `services/worker/worktree_manager.py`, `services/worker/requirements.txt`
- Test: `services/worker/tests/test_worktree.py`

- [ ] **Step 1: Write tests for worktree manager**

```python
# services/worker/tests/test_worktree.py
import pytest
import tempfile
import os
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.worker.worktree_manager import WorktreeManager


@pytest.fixture
def temp_repo():
    """Create a temporary git repo for testing"""
    import subprocess
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "config", "user.email", "test@test.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test"], check=True)
        # Create initial commit
        with open("README.md", "w") as f:
            f.write("# Test Repo")
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)
        yield tmpdir


def test_worktree_manager_initializes(temp_repo):
    manager = WorktreeManager(root_dir=temp_repo)
    assert manager.root_dir == temp_repo


def test_create_worktree(temp_repo):
    manager = WorktreeManager(root_dir=temp_repo)
    worktree_path = manager.create_worktree("task-001")
    assert os.path.exists(worktree_path)
    assert "task-001" in worktree_path


def test_cleanup_worktree(temp_repo):
    manager = WorktreeManager(root_dir=temp_repo)
    worktree_path = manager.create_worktree("task-002")
    manager.cleanup_worktree("task-002")
    # Worktree removed but path may still exist
    # Main assertion: no errors raised
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/worker/tests/test_worktree.py -v
```
Expected: FAIL

- [ ] **Step 3: Create Worker requirements**

```txt
# services/worker/requirements.txt
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
requests==2.31.0
pytest==8.0.0
```

- [ ] **Step 4: Implement Worktree Manager**

```python
# services/worker/worktree_manager.py
import subprocess
import os
from pathlib import Path
from typing import Optional


class WorktreeManager:
    """Manage git worktrees for isolated task execution"""
    
    def __init__(self, root_dir: str = "/home/loki/ideas/sea-qwens"):
        self.root_dir = Path(root_dir)
        self.worktrees_dir = self.root_dir / "worktrees"
        self.worktrees_dir.mkdir(exist_ok=True)
    
    def create_worktree(self, task_id: str, branch: str = "main") -> str:
        """Create a new worktree for a task"""
        worktree_path = self.worktrees_dir / task_id
        
        # Remove if exists
        if worktree_path.exists():
            self.cleanup_worktree(task_id)
        
        # Create worktree
        cmd = ["git", "worktree", "add", "-b", f"task/{task_id}", str(worktree_path), branch]
        result = subprocess.run(
            cmd,
            cwd=str(self.root_dir),
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Failed to create worktree: {result.stderr}")
        
        return str(worktree_path)
    
    def cleanup_worktree(self, task_id: str):
        """Remove a worktree after task completion"""
        worktree_path = self.worktrees_dir / task_id
        
        # Remove worktree
        cmd = ["git", "worktree", "remove", str(worktree_path), "--force"]
        subprocess.run(
            cmd,
            cwd=str(self.root_dir),
            capture_output=True,
            text=True
        )
        
        # Also remove directory if it still exists
        if worktree_path.exists():
            import shutil
            shutil.rmtree(worktree_path, ignore_errors=True)
    
    def get_worktree_path(self, task_id: str) -> str:
        """Get the path to a worktree"""
        return str(self.worktrees_dir / task_id)
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/worker/tests/test_worktree.py -v
```
Expected: PASS (requires git)

- [ ] **Step 6: Commit**

```bash
git add services/worker/worktree_manager.py services/worker/tests/test_worktree.py
git commit -m "feat: implement WorktreeManager for isolated task execution"
```

---

### Task 2: Worker Executor

**Files:**
- Create: `services/worker/executor.py`, `services/worker/app.py`, `services/worker/main.py`
- Test: `services/worker/tests/test_executor.py`

- [ ] **Step 1: Write tests for executor**

```python
# services/worker/tests/test_executor.py
import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.worker.executor import TaskExecutor, ExecutionResult


def test_execution_result_success():
    result = ExecutionResult(
        success=True,
        task_id="task-001",
        output="Task completed",
        test_passed=True
    )
    assert result.success
    assert result.test_passed


def test_execution_result_failure():
    result = ExecutionResult(
        success=False,
        task_id="task-002",
        output="Error occurred",
        test_passed=False,
        error="Rate limit exceeded"
    )
    assert not result.success
    assert result.error == "Rate limit exceeded"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/worker/tests/test_executor.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement Task Executor**

```python
# services/worker/executor.py
import subprocess
import os
from pathlib import Path
from typing import Optional
import json

from services.worker.worktree_manager import WorktreeManager


class ExecutionResult:
    def __init__(
        self,
        success: bool,
        task_id: str,
        output: str,
        test_passed: bool = False,
        error: Optional[str] = None,
        rate_limited: bool = False
    ):
        self.success = success
        self.task_id = task_id
        self.output = output
        self.test_passed = test_passed
        self.error = error
        self.rate_limited = rate_limited


class TaskExecutor:
    """Execute tasks using qwen-code CLI"""
    
    def __init__(self, worktree_manager: Optional[WorktreeManager] = None):
        self.worktree_manager = worktree_manager or WorktreeManager()
    
    def execute_task(
        self,
        task: dict,
        profile: dict,
        worktree_path: Optional[str] = None
    ) -> ExecutionResult:
        """Execute a task in an isolated worktree"""
        task_id = task.get("task_id", "unknown")
        profile_name = profile.get("name", "")
        
        try:
            # Create worktree if not provided
            if not worktree_path:
                worktree_path = self.worktree_manager.create_worktree(task_id)
            
            # Build qwen-code command
            title = task.get("title", "")
            contract = task.get("contract", {})
            
            prompt = self._build_prompt(title, contract)
            
            # Execute qwen-code CLI
            cmd = [
                "qwen-code",
                "--profile", profile_name,
                "-p", prompt
            ]
            
            result = subprocess.run(
                cmd,
                cwd=worktree_path,
                capture_output=True,
                text=True,
                timeout=900  # 15 minute timeout
            )
            
            # Check for rate limit in output
            if "429" in result.stderr or "rate limit" in result.stderr.lower():
                return ExecutionResult(
                    success=False,
                    task_id=task_id,
                    output=result.stderr,
                    rate_limited=True,
                    error="Rate limit exceeded"
                )
            
            if result.returncode != 0:
                return ExecutionResult(
                    success=False,
                    task_id=task_id,
                    output=result.stderr,
                    error=f"qwen-code failed with code {result.returncode}"
                )
            
            # Run self-tests
            test_passed = self._run_self_tests(worktree_path, task)
            
            return ExecutionResult(
                success=test_passed,
                task_id=task_id,
                output=result.stdout,
                test_passed=test_passed
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                task_id=task_id,
                output="",
                error="Task execution timed out (15 min)"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                task_id=task_id,
                output="",
                error=str(e)
            )
    
    def _build_prompt(self, title: str, contract: dict) -> str:
        """Build prompt for qwen-code"""
        prompt = f"""Implement the following task:

{title}

Requirements (contract):
{json.dumps(contract, indent=2)}

Instructions:
1. Write clean, tested code
2. Follow best practices
3. Ensure all tests pass
4. Do not modify files outside the task scope
"""
        return prompt
    
    def _run_self_tests(self, worktree_path: str, task: dict) -> bool:
        """Run self-tests in the worktree"""
        test_spec = task.get("test_spec", {})
        
        if not test_spec:
            # No test spec, assume pass
            return True
        
        test_file = test_spec.get("test_file", "")
        if not test_file:
            return True
        
        # Run pytest
        cmd = ["python", "-m", "pytest", test_file, "-v"]
        result = subprocess.run(
            cmd,
            cwd=worktree_path,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return result.returncode == 0
```

- [ ] **Step 4: Implement FastAPI app**

```python
# services/worker/app.py
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

from services.worker.executor import TaskExecutor, ExecutionResult
from services.worker.worktree_manager import WorktreeManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Legion Worker")

executor = TaskExecutor()
worktree_manager = WorktreeManager()

# Store results for retrieval
execution_results: Dict[str, ExecutionResult] = {}


class TaskRequest(BaseModel):
    task: Dict[str, Any]
    profile: Dict[str, Any]


class ExecutionStatus(BaseModel):
    task_id: str
    status: str  # "pending", "running", "completed", "failed"
    result: Optional[dict] = None


@app.post("/execute", status_code=202)
async def execute_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Execute a task asynchronously"""
    task_id = request.task.get("task_id", "unknown")
    
    # Store as pending
    execution_results[task_id] = ExecutionResult(
        success=False,
        task_id=task_id,
        output="Task queued"
    )
    
    # Execute in background
    background_tasks.add_task(
        _execute_background,
        request.task,
        request.profile,
        task_id
    )
    
    return {"status": "accepted", "task_id": task_id}


async def _execute_background(task: dict, profile: dict, task_id: str):
    """Execute task in background"""
    logger.info(f"Executing task {task_id} with profile {profile.get('name')}")
    
    result = executor.execute_task(task, profile)
    execution_results[task_id] = result
    
    # Notify Tester if successful
    if result.success:
        try:
            import requests
            requests.post(
                "http://localhost:8005/validate",
                json={
                    "task_id": task_id,
                    "worktree_path": worktree_manager.get_worktree_path(task_id)
                }
            )
        except Exception as e:
            logger.error(f"Failed to notify Tester: {e}")


@app.get("/execute/{task_id}")
def get_execution_status(task_id: str):
    """Get execution status for a task"""
    if task_id not in execution_results:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = execution_results[task_id]
    return {
        "task_id": task_id,
        "status": "completed" if result.success else "failed",
        "output": result.output,
        "test_passed": result.test_passed,
        "error": result.error
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

- [ ] **Step 5: Create main entry point**

```python
# services/worker/main.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8004, reload=True)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/worker/tests/test_executor.py -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add services/worker/executor.py services/worker/app.py services/worker/main.py services/worker/tests/test_executor.py
git commit -m "feat: implement Worker executor with qwen-code CLI integration"
```

---

### Task 3: Tester Contract Validator

**Files:**
- Create: `services/tester/validator.py`, `services/tester/requirements.txt`
- Test: `services/tester/tests/test_validator.py`

- [ ] **Step 1: Write tests for validator**

```python
# services/tester/tests/test_validator.py
import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.tester.validator import ContractValidator, ValidationResult


def test_validation_result_pass():
    result = ValidationResult(
        passed=True,
        contract_valid=True,
        tests_passed=True,
        semantic_valid=True
    )
    assert result.passed


def test_validation_result_contract_fail():
    result = ValidationResult(
        passed=False,
        contract_valid=False,
        tests_passed=True,
        semantic_valid=True,
        errors=["Contract validation failed"]
    )
    assert not result.passed
    assert len(result.errors) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/tester/tests/test_validator.py -v
```
Expected: FAIL

- [ ] **Step 3: Create Tester requirements**

```txt
# services/tester/requirements.txt
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
requests==2.31.0
pytest==8.0.0
jsonschema==4.20.0
```

- [ ] **Step 4: Implement Contract Validator**

```python
# services/tester/validator.py
import json
import subprocess
from pathlib import Path
from typing import Optional, Any
from jsonschema import validate, ValidationError


class ValidationResult:
    def __init__(
        self,
        passed: bool,
        contract_valid: bool = True,
        tests_passed: bool = True,
        semantic_valid: bool = True,
        errors: Optional[list[str]] = None
    ):
        self.passed = passed
        self.contract_valid = contract_valid
        self.tests_passed = tests_passed
        self.semantic_valid = semantic_valid
        self.errors = errors or []


class ContractValidator:
    """Validate code against contracts"""
    
    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url
    
    def validate(
        self,
        task_id: str,
        worktree_path: str,
        contract: dict
    ) -> ValidationResult:
        """Run full validation: contract + tests + semantic"""
        errors = []
        
        # 1. Contract validation (JSON Schema)
        contract_valid, contract_errors = self._validate_contract(
            worktree_path, contract
        )
        if not contract_valid:
            errors.extend(contract_errors)
        
        # 2. Test execution
        tests_passed, test_errors = self._run_tests(worktree_path)
        if not tests_passed:
            errors.extend(test_errors)
        
        # 3. Semantic validation (LLM-based)
        semantic_valid, semantic_errors = self._validate_semantic(
            task_id, worktree_path, contract
        )
        if not semantic_valid:
            errors.extend(semantic_errors)
        
        return ValidationResult(
            passed=len(errors) == 0,
            contract_valid=contract_valid,
            tests_passed=tests_passed,
            semantic_valid=semantic_valid,
            errors=errors
        )
    
    def _validate_contract(
        self,
        worktree_path: str,
        contract: dict
    ) -> tuple[bool, list[str]]:
        """Validate code structure against JSON Schema contract"""
        errors = []
        
        # Extract metadata from worktree
        metadata = self._extract_metadata(worktree_path)
        
        try:
            validate(instance=metadata, schema=contract)
            return True, []
        except ValidationError as e:
            errors.append(f"Contract violation: {e.message}")
            return False, errors
    
    def _extract_metadata(self, worktree_path: str) -> dict:
        """Extract metadata from code files for validation"""
        path = Path(worktree_path)
        
        # Simple metadata extraction
        files = [str(f.relative_to(path)) for f in path.rglob("*.py")]
        
        return {
            "files_created": files,
            "has_main": (path / "main.py").exists()
        }
    
    def _run_tests(self, worktree_path: str) -> tuple[bool, list[str]]:
        """Run pytest in worktree"""
        errors = []
        
        cmd = ["python", "-m", "pytest", worktree_path, "-v", "--tb=short"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            errors.append(f"Tests failed: {result.stdout}")
            return False, errors
        
        return True, []
    
    def _validate_semantic(
        self,
        task_id: str,
        worktree_path: str,
        contract: dict
    ) -> tuple[bool, list[str]]:
        """
        LLM-based semantic validation.
        
        In production, this would call an LLM to verify the code
        semantically matches the task intent.
        """
        # TODO: Implement LLM semantic check
        # For now, pass through
        return True, []
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/tester/tests/test_validator.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/tester/validator.py services/tester/tests/test_validator.py
git commit -m "feat: implement ContractValidator for task validation"
```

---

### Task 4: Tester Merger + FastAPI App

**Files:**
- Create: `services/tester/merger.py`, `services/tester/app.py`, `services/tester/main.py`
- Test: `services/tester/tests/test_merger.py`

- [ ] **Step 1: Write tests for merger**

```python
# services/tester/tests/test_merger.py
import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.tester.merger import GitMerger


def test_merger_initializes():
    merger = GitMerger()
    assert merger.root_dir is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/tester/tests/test_merger.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement Git Merger**

```python
# services/tester/merger.py
import subprocess
from pathlib import Path
from typing import Optional


class GitMerger:
    """Handle git merge operations"""
    
    def __init__(self, root_dir: str = "/home/loki/ideas/sea-qwens"):
        self.root_dir = Path(root_dir)
    
    def merge_task_branch(self, task_id: str) -> tuple[bool, Optional[str]]:
        """
        Merge a task branch into main.
        Returns (success, error_message)
        """
        branch_name = f"task/{task_id}"
        
        try:
            # Fetch latest
            subprocess.run(
                ["git", "fetch"],
                cwd=str(self.root_dir),
                check=True,
                capture_output=True
            )
            
            # Checkout main
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=str(self.root_dir),
                check=True,
                capture_output=True
            )
            
            # Merge task branch
            result = subprocess.run(
                ["git", "merge", "--no-ff", "-m", f"Merge {branch_name}", branch_name],
                cwd=str(self.root_dir),
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                if "conflict" in result.stdout.lower():
                    # Abort merge on conflict
                    subprocess.run(
                        ["git", "merge", "--abort"],
                        cwd=str(self.root_dir),
                        capture_output=True
                    )
                    return False, "Merge conflict detected"
                return False, f"Merge failed: {result.stderr}"
            
            return True, None
            
        except subprocess.CalledProcessError as e:
            return False, f"Git error: {str(e)}"
    
    def cleanup_task_branch(self, task_id: str):
        """Delete task branch after merge"""
        branch_name = f"task/{task_id}"
        subprocess.run(
            ["git", "branch", "-D", branch_name],
            cwd=str(self.root_dir),
            capture_output=True
        )
```

- [ ] **Step 4: Implement Tester FastAPI app**

```python
# services/tester/app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import requests

from services.tester.validator import ContractValidator, ValidationResult
from services.tester.merger import GitMerger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Legion Supreme Tester")

validator = ContractValidator()
merger = GitMerger()

LIBRARIAN_URL = "http://localhost:8001"


class ValidateRequest(BaseModel):
    task_id: str
    worktree_path: str
    contract: Optional[dict] = None


class ValidateResponse(BaseModel):
    task_id: str
    passed: bool
    action: str  # "merged", "retry", "manual_review"
    errors: Optional[list[str]] = None


@app.post("/validate")
def validate_task(request: ValidateRequest):
    """Validate completed task work"""
    logger.info(f"Validating task {request.task_id}")
    
    # Fetch task from Librarian to get contract
    contract = request.contract or {}
    
    # Run validation
    result = validator.validate(
        request.task_id,
        request.worktree_path,
        contract
    )
    
    if result.passed:
        # Merge to main
        success, error = merger.merge_task_branch(request.task_id)
        if success:
            # Update task status to DONE
            try:
                requests.post(
                    f"{LIBRARIAN_URL}/tasks/update",
                    params={"task_id": request.task_id},
                    json={"status": "DONE"}
                )
            except Exception as e:
                logger.error(f"Failed to update task status: {e}")
            
            # Cleanup
            merger.cleanup_task_branch(request.task_id)
            
            return ValidateResponse(
                task_id=request.task_id,
                passed=True,
                action="merged"
            )
        else:
            return ValidateResponse(
                task_id=request.task_id,
                passed=True,
                action="manual_review",
                errors=[f"Merge failed: {error}"]
            )
    
    else:
        # Determine action based on failure type
        if not result.contract_valid:
            action = "manual_review"  # Structural issue
        else:
            action = "retry"  # Test failure, can retry
        
        return ValidateResponse(
            task_id=request.task_id,
            passed=False,
            action=action,
            errors=result.errors
        )


@app.post("/retry/{task_id}")
def retry_task(task_id: str, error_context: dict):
    """Send task back to Worker for retry"""
    try:
        requests.post(
            f"http://localhost:8004/retry",
            json={"task_id": task_id, "error_context": error_context}
        )
        return {"status": "retry_queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health_check():
    return {"status": "healthy"}
```

- [ ] **Step 5: Create main entry point**

```python
# services/tester/main.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8005, reload=True)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/tester/tests/test_merger.py -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add services/tester/merger.py services/tester/app.py services/tester/main.py services/tester/tests/test_merger.py
git commit -m "feat: implement Supreme Tester with validation and merge logic"
```

---

## Verification

After completing all tasks, run:

```bash
# Start services
python -m services.worker.main &
python -m services.tester.main &

# Test Worker endpoint
curl -X POST http://localhost:8004/execute \
  -H "Content-Type: application/json" \
  -d '{"task": {"task_id": "test-001", "title": "Test", "contract": {}}, "profile": {"name": "qwen-agent-01"}}'

# Test Tester endpoint
curl -X POST http://localhost:8005/validate \
  -H "Content-Type: application/json" \
  -d '{"task_id": "test-001", "worktree_path": "/tmp/test"}'

# Run all tests
pytest services/worker/ services/tester/ -v
```

Expected: All tests pass, services run independently
