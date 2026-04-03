# Tool Adapter/Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable the Worker container to execute any host-installed CLI tool via per-tool adapter scripts, without container rebuilds.

**Architecture:** Adapter scripts live in `~/.config/sea-qwens/adapters/` (mounted as a read-only volume in the Worker container). The Worker resolves the adapter from the tool config, executes it via `bash`, and falls back to raw `tool_command` if the adapter is missing. Kanban passes the `adapter` field through to the Worker.

**Tech Stack:** Python (FastAPI, Pydantic), Bash, Docker Compose, pytest

---

### Task 1: Create default adapter scripts in `configs/adapters/`

**Files:**
- Create: `configs/adapters/qwen.sh`
- Create: `configs/adapters/_template.sh`

- [ ] **Step 1: Create the Qwen Code adapter script**

```bash
#!/usr/bin/env bash
# Adapter for Qwen Code CLI
# Usage: bash qwen.sh --prompt "..." --cwd /path [--tool_id id]
set -euo pipefail

PROMPT=""
CWD=""
TOOL_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt) PROMPT="$2"; shift 2 ;;
    --cwd)    CWD="$2";    shift 2 ;;
    --tool_id) TOOL_ID="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# Qwen-specific setup: PATH and config directories
export PATH="$HOME/.local/bin:$PATH"
export QWEN_CONFIG_DIR="${QWEN_CONFIG_DIR:-$HOME/.qwen}"
export QWEN_ACCOUNTS_DIR="${QWEN_ACCOUNTS_DIR:-$HOME/.qwen-accounts}"

# Execute Qwen Code
exec qwen --non-interactive --prompt "$PROMPT" --cwd "$CWD"
```

- [ ] **Step 2: Create the template adapter script**

```bash
#!/usr/bin/env bash
# Template for new tool adapters
# Copy this file, rename it to <tool>.sh, and fill in the blanks.
set -euo pipefail

PROMPT=""
CWD=""
TOOL_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt) PROMPT="$2"; shift 2 ;;
    --cwd)    CWD="$2";    shift 2 ;;
    --tool_id) TOOL_ID="$2"; shift 2 ;;
    *) shift ;;
  esac
done

# TODO: Set up tool-specific environment
# export PATH="/path/to/tool/bin:$PATH"
# export TOOL_CONFIG_DIR="$HOME/.tool-config"

# TODO: Execute the tool
# exec your-tool --non-interactive --prompt "$PROMPT" --cwd "$CWD"
echo "Adapter not configured" >&2
exit 1
```

- [ ] **Step 3: Make both scripts executable**

```bash
chmod +x configs/adapters/qwen.sh configs/adapters/_template.sh
```

- [ ] **Step 4: Commit**

```bash
git add configs/adapters/
git commit -m "feat: add default tool adapter scripts (qwen.sh + template)"
```

---

### Task 2: Update `shared/config.py` to bootstrap adapters directory

**Files:**
- Modify: `shared/config.py`
- Test: `shared/test_models.py` (add bootstrap test) or create `shared/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `shared/test_config.py`:

```python
import pytest
import tempfile
import json
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.config import bootstrap_configs, ensure_config_dir


def test_bootstrap_configs_copies_adapters_directory():
    """bootstrap_configs should copy the adapters/ directory from repo configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake repo config structure
        repo_configs = Path(tmpdir) / "configs"
        repo_configs.mkdir()
        (repo_configs / "tools.json").write_text("[]")

        adapters_dir = repo_configs / "adapters"
        adapters_dir.mkdir()
        (adapters_dir / "qwen.sh").write_text("#!/bin/bash\necho qwen")

        # Create a fake user config dir
        user_config = Path(tmpdir) / "user_config"
        user_config.mkdir()

        # Monkey-patch _get_config_dir for this test
        import shared.config
        original_get_config_dir = shared.config._get_config_dir
        shared.config._get_config_dir = lambda: user_config

        try:
            results = bootstrap_configs(repo_root=Path(tmpdir))
            # adapters directory should have been copied
            user_adapters = user_config / "adapters"
            assert user_adapters.exists(), "adapters/ directory was not bootstrapped"
            assert (user_adapters / "qwen.sh").exists(), "qwen.sh was not copied"
        finally:
            shared.config._get_config_dir = original_get_config_dir
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest shared/test_config.py::test_bootstrap_configs_copies_adapters_directory -v
```
Expected: FAIL — `adapters/` directory is not copied (current `bootstrap_configs` only copies files, not directories).

- [ ] **Step 3: Update `bootstrap_configs` to copy directories**

In `shared/config.py`, modify the `bootstrap_configs` function. Replace the file-only copy loop with one that also copies directories:

```python
def bootstrap_configs(repo_root: Path | None = None) -> dict[str, bool]:
    """Copy default configs from the repo into the user config directory.

    Returns a dict mapping config filename -> whether it was created
    (``False`` means it already existed).
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent.parent
    else:
        repo_root = Path(repo_root)

    repo_configs = repo_root / "configs"
    user_config_dir = ensure_config_dir()

    results: dict[str, bool] = {}

    if not repo_configs.exists():
        logger.warning(f"Repo configs directory not found: {repo_configs}")
        return results

    for src in repo_configs.iterdir():
        dst = user_config_dir / src.name
        if dst.exists():
            results[src.name] = False
        elif src.is_file():
            shutil.copy2(src, dst)
            logger.info(f"Bootstrapped config: {dst}")
            results[src.name] = True
        elif src.is_dir():
            shutil.copytree(src, dst)
            logger.info(f"Bootstrapped config directory: {dst}")
            results[src.name] = True

    return results
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest shared/test_config.py::test_bootstrap_configs_copies_adapters_directory -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add shared/config.py shared/test_config.py
git commit -m "feat: bootstrap adapters directory alongside tools.json"
```

---

### Task 3: Add `adapter` field to `shared/models.py` `Tool` model

**Files:**
- Modify: `shared/models.py`
- Test: `shared/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `shared/test_models.py`:

```python
def test_tool_model_has_adapter_field():
    """Tool model should have an optional adapter field defaulting to empty string."""
    from shared.models import Tool
    tool = Tool(name="qwen-code", command="qwen --non-interactive")
    assert hasattr(tool, "adapter"), "Tool model missing adapter field"
    assert tool.adapter == "", "adapter should default to empty string"

def test_tool_model_with_adapter():
    """Tool model should accept an adapter value."""
    from shared.models import Tool
    tool = Tool(name="qwen-code", command="qwen --non-interactive", adapter="qwen.sh")
    assert tool.adapter == "qwen.sh"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest shared/test_models.py::test_tool_model_has_adapter_field shared/test_models.py::test_tool_model_with_adapter -v
```
Expected: FAIL — `Tool` model has no `adapter` attribute.

- [ ] **Step 3: Add `adapter` field to `Tool` model**

In `shared/models.py`, modify the `Tool` class:

```python
class Tool(BaseModel):
    name: str
    command: str = "qwen --non-interactive"
    adapter: str = ""  # Optional: adapter script name (defaults to <name>.sh)
    usage_count: int = 0
    last_used: Optional[datetime] = None
    daily_limit: int = 1000
    requests_today: int = 0
    reset_time: datetime = Field(default_factory=lambda: datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0))
    capabilities: list[str] = Field(default_factory=lambda: ["coding", "testing", "refactoring"])
    health_status: ToolHealth = ToolHealth.HEALTHY
    consecutive_failures: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest shared/test_models.py::test_tool_model_has_adapter_field shared/test_models.py::test_tool_model_with_adapter -v
```
Expected: PASS

- [ ] **Step 5: Run full shared tests to ensure no regressions**

```bash
python -m pytest shared/ -v
```
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add shared/models.py shared/test_models.py
git commit -m "feat: add adapter field to Tool model"
```

---

### Task 4: Add `adapter` field to Worker's `ExecuteRequest` and `executor.py`

**Files:**
- Modify: `services/worker/app.py`
- Modify: `services/worker/executor.py`
- Test: `services/worker/tests/test_executor.py`
- Test: `services/worker/tests/test_app.py` (create if not exists)

- [ ] **Step 1: Write failing test for `_resolve_adapter`**

Add to `services/worker/tests/test_executor.py`:

```python
def test_resolve_adapter_returns_path_when_adapter_exists(tmp_path):
    """_resolve_adapter should return path when adapter file exists."""
    executor = TaskExecutor()
    # Create a fake adapters directory with a script
    adapters_dir = tmp_path / "adapters"
    adapters_dir.mkdir()
    (adapters_dir / "qwen.sh").write_text("#!/bin/bash\necho hello")

    # Override the adapters base path for testing
    executor._adapters_base = str(adapters_dir)

    result = executor._resolve_adapter("qwen.sh", "qwen-code")
    assert result == str(adapters_dir / "qwen.sh")


def test_resolve_adapter_defaults_to_tool_name_sh():
    """_resolve_adapter should default to <tool_name>.sh when adapter is empty."""
    executor = TaskExecutor()
    # No adapters directory set up — should return None (file not found)
    result = executor._resolve_adapter("", "my-tool")
    assert result is None


def test_resolve_adapter_returns_none_for_missing_adapter():
    """_resolve_adapter should return None when adapter file doesn't exist."""
    executor = TaskExecutor()
    result = executor._resolve_adapter("nonexistent.sh", "some-tool")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest services/worker/tests/test_executor.py::test_resolve_adapter_returns_path_when_adapter_exists services/worker/tests/test_executor.py::test_resolve_adapter_defaults_to_tool_name_sh services/worker/tests/test_executor.py::test_resolve_adapter_returns_none_for_missing_adapter -v
```
Expected: FAIL — `_resolve_adapter` method doesn't exist.

- [ ] **Step 3: Add `_resolve_adapter` method and update `execute_task`**

In `services/worker/executor.py`, add the import and method, and update `execute_task`:

```python
# services/worker/executor.py
import subprocess
import os
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from shared.models import Task


@dataclass
class ExecutionResult:
    """Result of a task execution by a worker agent."""
    success: bool
    task_id: str
    output: str = ""
    test_passed: bool = False
    error: Optional[str] = None
    rate_limited: bool = False


class TaskExecutor:
    """Execute coding tasks using CLI tools in isolated worktrees."""

    def __init__(self, adapters_base: str = "/app/adapters"):
        self._adapters_base = adapters_base

    def _resolve_adapter(self, adapter: str, tool_name: str) -> Optional[str]:
        """Resolve the adapter script path.

        Args:
            adapter: Adapter script name (e.g. "qwen.sh"). If empty, defaults to "<tool_name>.sh".
            tool_name: Tool name used as fallback adapter name ("<tool_name>.sh").

        Returns:
            Full path to adapter script if it exists, else None.
        """
        adapter_name = adapter if adapter else f"{tool_name}.sh"
        adapter_path = Path(self._adapters_base) / adapter_name

        if adapter_path.is_file():
            return str(adapter_path)
        return None

    def execute_task(
        self,
        task: Task,
        tool_id: Optional[str] = None,
        tool_command: str = "qwen --non-interactive",
        worktree_path: str = "",
        adapter: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a task in the given worktree.

        1. Build prompt from task title + contract
        2. Resolve adapter path and execute via bash, or fall back to raw tool_command
        3. Run self-tests (pytest) in the worktree
        4. Return ExecutionResult
        """
        wt_path = Path(worktree_path)
        if not wt_path.exists() or not wt_path.is_dir():
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=f"Worktree path does not exist: {worktree_path}",
            )

        prompt = self._build_prompt(task.title, task.contract)

        try:
            env = os.environ.copy()
            if tool_id:
                env["SEA_QWENS_TOOL_ID"] = tool_id

            # Try adapter execution first, fall back to raw command
            adapter_path = self._resolve_adapter(adapter or "", tool_id or "")
            if adapter_path:
                cmd = ["bash", adapter_path, "--prompt", prompt, "--cwd", str(wt_path)]
                if tool_id:
                    cmd.extend(["--tool_id", tool_id])
            else:
                # Fallback: raw command execution (backward compatible)
                cmd = [*tool_command.split(), "--prompt", prompt, "--cwd", str(wt_path)]

            result = subprocess.run(
                cmd,
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=600,
                env=env,
            )

            tool_output = result.stdout
            tool_error = result.stderr

            rate_limited = self._is_rate_limited(tool_output, tool_error)

            if result.returncode != 0 or rate_limited:
                return ExecutionResult(
                    success=False,
                    task_id=task.task_id,
                    output=tool_output,
                    error=tool_error or "Tool returned non-zero exit code",
                    rate_limited=rate_limited,
                )

        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error="Task execution timed out (600s)",
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=f"Command not found: {cmd[0]}",
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                task_id=task.task_id,
                error=str(e),
            )

        test_result = self._run_self_tests(str(wt_path), task)

        return ExecutionResult(
            success=test_result.success,
            task_id=task.task_id,
            output=tool_output + "\n--- Tests ---\n" + test_result.output,
            test_passed=test_result.test_passed,
            error=test_result.error,
            rate_limited=test_result.rate_limited,
        )

    # ... rest of existing methods (_build_prompt, _run_self_tests, _is_rate_limited) unchanged ...
```

The existing `_build_prompt`, `_run_self_tests`, and `_is_rate_limited` methods remain unchanged.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest services/worker/tests/test_executor.py -v
```
Expected: All tests pass

- [ ] **Step 5: Add `adapter` field to `ExecuteRequest` in `app.py`**

In `services/worker/app.py`, modify the `ExecuteRequest` class:

```python
class ExecuteRequest(BaseModel):
    task: Task
    tool_id: Optional[str] = None
    tool_command: str = "qwen --non-interactive"
    adapter: Optional[str] = None  # Optional: adapter script name
    worktree_path: Optional[str] = None
```

And update `_run_execution` to pass it through:

```python
async def _run_execution(
    task: Task,
    tool_id: Optional[str],
    tool_command: str,
    worktree_path: Optional[str],
    adapter: Optional[str] = None,
):
    """Run task execution in the background."""
    logger.info(f"Starting execution of task: {task.task_id} with tool: {tool_id}")

    # Create worktree if not provided
    if not worktree_path:
        from services.worker.worktree_manager import WorktreeManager
        wt_manager = WorktreeManager()
        worktree_path = wt_manager.create_worktree(task.task_id)

    try:
        result = executor.execute_task(
            task=task,
            tool_id=tool_id,
            tool_command=tool_command,
            worktree_path=worktree_path,
            adapter=adapter,
        )
        _execution_store[task.task_id] = result

        if result.success:
            logger.info(f"Task {task.task_id} completed successfully")
        else:
            logger.warning(f"Task {task.task_id} failed: {result.error}")

    except Exception as e:
        logger.error(f"Task {task.task_id} raised unexpected error: {e}")
        _execution_store[task.task_id] = ExecutionResult(
            success=False,
            task_id=task.task_id,
            error=str(e),
        )
```

And update the `background_tasks.add_task` call in `execute_task`:

```python
    background_tasks.add_task(
        _run_execution,
        task=request.task,
        tool_id=request.tool_id,
        tool_command=request.tool_command,
        worktree_path=request.worktree_path,
        adapter=request.adapter,
    )
```

- [ ] **Step 6: Run worker tests to verify no regressions**

```bash
python -m pytest services/worker/tests/ -v
```
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add services/worker/executor.py services/worker/app.py services/worker/tests/test_executor.py
git commit -m "feat: add adapter resolution to Worker executor"
```

---

### Task 5: Pass `adapter` through from Kanban dispatcher to Worker

**Files:**
- Modify: `services/kanban/dispatcher.py`
- Test: `services/kanban/tests/test_dispatcher.py`

- [ ] **Step 1: Write the failing test**

Add to `services/kanban/tests/test_dispatcher.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest services/kanban/tests/test_dispatcher.py::test_dispatch_task_passes_adapter_to_worker -v
```
Expected: FAIL — `adapter` key not in the request JSON.

- [ ] **Step 3: Update `dispatch_task` to pass adapter through**

In `services/kanban/dispatcher.py`, modify the Worker request in `dispatch_task`:

```python
        tool_adapter = tool.get("adapter", "")

        # Dispatch to Worker
        try:
            response = requests.post(
                f"{self.worker_url}/execute",
                json={
                    "task": task,
                    "tool_id": tool_name,
                    "tool_command": tool_command,
                    "adapter": tool_adapter or None,  # Pass through (None if empty)
                }
            )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest services/kanban/tests/test_dispatcher.py::test_dispatch_task_passes_adapter_to_worker -v
```
Expected: PASS

- [ ] **Step 5: Run full Kanban tests to ensure no regressions**

```bash
python -m pytest services/kanban/tests/ -v
```
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add services/kanban/dispatcher.py services/kanban/tests/test_dispatcher.py
git commit -m "feat: pass adapter field through to Worker in dispatcher"
```

---

### Task 6: Mount adapters volume in `docker-compose.yml` and update `tools.json`

**Files:**
- Modify: `docker-compose.yml`
- Modify: `configs/tools.json`

- [ ] **Step 1: Add adapters volume mount to Worker service**

In `docker-compose.yml`, update the `worker` service volumes:

```yaml
  worker:
    build:
      context: .
      dockerfile: services/worker/Dockerfile
    container_name: sea-qwens-worker
    ports:
      - "8004:8004"
    environment:
      - KANBAN_URL=http://kanban:8003
    depends_on:
      kanban:
        condition: service_started
    volumes:
      - ./worktrees:/app/worktrees
      - ${SEA_QWENS_CONFIG_DIR:-~/.config/sea-qwens}/adapters:/app/adapters:ro
    networks:
      - sea-qwens-network
```

- [ ] **Step 2: Update `configs/tools.json` to include `adapter` field**

```json
[
  {
    "name": "qwen-code",
    "command": "qwen --non-interactive",
    "adapter": "qwen.sh",
    "daily_limit": 1000,
    "capabilities": ["coding", "testing", "debugging", "refactoring"],
    "health_status": "HEALTHY",
    "consecutive_failures": 0,
    "requests_today": 0
  },
  {
    "name": "qwen-coder",
    "command": "qwen -m qwen-coder --non-interactive",
    "adapter": "qwen-coder.sh",
    "daily_limit": 500,
    "capabilities": ["coding", "code-review"],
    "health_status": "HEALTHY",
    "consecutive_failures": 0,
    "requests_today": 0
  }
]
```

Note: `qwen-coder.sh` doesn't exist yet as an adapter — this is intentional. The Worker will fall back to raw `tool_command` execution for it, which is the correct backward-compatible behavior.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml configs/tools.json
git commit -m "feat: mount adapters volume in docker-compose and update tools.json"
```

---

### Task 7: Run full test suite and verify end-to-end

**Files:**
- No file changes

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest services/ shared/ -v
```
Expected: All tests pass

- [ ] **Step 2: Verify bootstrap copies adapters**

```bash
# Clean any existing user config (backup first if needed)
rm -rf ~/.config/sea-qwens

# Run bootstrap
python -c "from shared.config import bootstrap_configs; bootstrap_configs()"

# Verify adapters were copied
ls ~/.config/sea-qwens/adapters/
```
Expected: `qwen.sh` and `_template.sh` are present

- [ ] **Step 3: Verify docker-compose is valid**

```bash
docker compose -f docker-compose.yml config
```
Expected: Valid YAML output with no errors

- [ ] **Step 4: Commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address test failures / config issues"
```

---

### Task 8: Update README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Tool Adapters section to Configuration**

In the `README.md`, after the "Tool Configuration" section, add:

```markdown
### Tool Adapters

Tool adapters let you swap CLI tools in and out without rebuilding container images. Each adapter is a small shell script that sets up the tool's environment (PATH, config dirs, auth) and then executes it.

**Adapter location:** `~/.config/sea-qwens/adapters/`

**Adding a new tool:**

1. Copy the template: `cp ~/.config/sea-qwens/adapters/_template.sh ~/.config/sea-qwens/adapters/my-tool.sh`
2. Edit `my-tool.sh` — fill in the PATH/config setup and the `exec` line
3. Add the tool to `~/.config/sea-qwens/tools.json` with `"adapter": "my-tool.sh"`
4. Restart the Kanban service: `docker compose restart kanban`

**How it works:**

The Worker resolves the adapter path from the tool config, executes it via `bash`, and falls back to raw `tool_command` if the adapter is missing. This means existing tool entries without an `adapter` field continue to work unchanged.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add tool adapters section to README"
```
