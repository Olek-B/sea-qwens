# Tool Adapter/Plugin Design

**Date:** 2026-04-03
**Status:** Draft
**Author:** Sea Qwens Team

## Problem

The Worker container executes CLI tools (currently Qwen Code) to perform coding tasks. These tools are installed on the host with their own runtimes, configurations, and auth directories (e.g., `~/.qwen/`, `~/.qwen-accounts/`). The container cannot access them, making the Worker non-functional without host tool access.

The system must remain **tool-agnostic** — any CLI agent with similar functionality should be swappable in without rebuilding container images.

## Goals

1. Worker can execute any compatible CLI tool without container rebuilds.
2. Adding a new tool requires minimal configuration (one script + one config entry).
3. Tool-specific complexity (runtimes, config paths, auth dirs) is encapsulated in per-tool adapters.
4. Backward compatible with existing `tools.json` entries that lack an `adapter` field.

## Architecture

### File Layout

```
~/.config/sea-qwens/                  # User config directory (mounted as volume)
├── tools.json                        # Existing: tool definitions
└── adapters/                         # NEW: per-tool adapter scripts
    ├── qwen.sh                       # Qwen Code adapter
    └── _template.sh                  # Template for new tools

sea-qwens-dev/
├── services/worker/
│   ├── executor.py                   # Modified: calls adapter script
│   └── app.py                        # Modified: adapter field in request model
├── docker-compose.yml                # Modified: mount adapters volume
└── configs/
    └── adapters/                     # NEW: default adapters (bootstrapped)
        ├── qwen.sh
        └── _template.sh
```

### Adapter Interface

Each adapter is a POSIX shell script (`#!/usr/bin/env bash`) that:

1. Receives standardized arguments: `--prompt`, `--cwd`, `--tool_id`
2. Sets up tool-specific environment (PATH, config dirs, auth dirs)
3. Executes the tool via `exec`, forwarding the prompt and working directory

#### Standard Arguments

| Flag | Description | Required |
|------|-------------|----------|
| `--prompt` | The task prompt (title + contract) | Yes |
| `--cwd` | The git worktree path where the tool operates | Yes |
| `--tool_id` | The tool identifier from `tools.json` | No |

#### Qwen Code Adapter (`qwen.sh`)

```bash
#!/usr/bin/env bash
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

#### Template Adapter (`_template.sh`)

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

### Worker Changes

#### `shared/models.py` — `Tool` Model

Add optional `adapter` field:

```python
class Tool(BaseModel):
    name: str
    command: str = "qwen --non-interactive"
    adapter: str = ""  # Optional: adapter script name (defaults to <name>.sh)
    usage_count: int = 0
    ...
```

#### `services/worker/app.py` — `ExecuteRequest` Model

Add optional `adapter` field so Kanban can pass it through:

```python
class ExecuteRequest(BaseModel):
    task: Task
    tool_id: Optional[str] = None
    tool_command: str = "qwen --non-interactive"
    adapter: Optional[str] = None  # Optional: adapter script name
    worktree_path: Optional[str] = None
```

#### `executor.py` — `TaskExecutor.execute_task()`

Add `adapter` parameter. New method `_resolve_adapter(adapter: str, tool_name: str) -> str | None`:
1. Determine adapter name: use `adapter` if provided, else default to `<tool_name>.sh`
2. Resolve path: `/app/adapters/{adapter_name}`
3. If adapter file exists, return path
4. If adapter missing, return `None` (caller falls back to raw `tool_command`)

Updated `execute_task()` signature:
```python
def execute_task(
    self,
    task: Task,
    tool_id: Optional[str] = None,
    tool_command: str = "qwen --non-interactive",
    worktree_path: str = "",
    adapter: Optional[str] = None,
) -> ExecutionResult:
```

Execution logic:
```python
adapter_path = self._resolve_adapter(adapter, tool_id or "unknown")
if adapter_path:
    cmd = ["bash", adapter_path, "--prompt", prompt, "--cwd", str(wt_path)]
    if tool_id:
        cmd.extend(["--tool_id", tool_id])
else:
    # Fallback: raw command execution (backward compatible)
    cmd = [*tool_command.split(), "--prompt", prompt, "--cwd", str(wt_path)]

result = subprocess.run(cmd, ...)
```

#### `services/kanban/dispatcher.py` — Pass Adapter Through

In `dispatch_task()`, include the `adapter` field when calling the Worker:

```python
tool_adapter = tool.get("adapter", "")
# ...
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

#### `docker-compose.yml` — Volume Mount

Add to the `worker` service:

```yaml
volumes:
  - ./worktrees:/app/worktrees
  - ${SEA_QWENS_CONFIG_DIR:-~/.config/sea-qwens}/adapters:/app/adapters:ro
```

The `:ro` flag ensures adapters are read-only inside the container.

### `tools.json` Addition

The `adapter` field is optional. If omitted, defaults to `<name>.sh`.

```json
{
  "name": "qwen-code",
  "command": "qwen --non-interactive",
  "adapter": "qwen.sh",
  "daily_limit": 1000,
  "capabilities": ["coding", "testing", "debugging", "refactoring"],
  "health_status": "HEALTHY",
  "consecutive_failures": 0,
  "requests_today": 0
}
```

### Bootstrap Flow

On first run, the Librarian already copies default configs from `configs/` to `~/.config/sea-qwens/`. Extend this to also copy `configs/adapters/` to `~/.config/sea-qwens/adapters/`.

### Data Flow

```
Kanban dispatches task → Worker POST /execute
  → Worker reads tool config from Librarian
  → Worker resolves adapter path: /app/adapters/{adapter}
  → Worker executes: bash /app/adapters/qwen.sh --prompt "..." --cwd /app/worktrees/xyz --tool_id abc
  → Adapter sets up env vars, runs qwen
  → stdout/stderr captured, returned to Kanban
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Adapter script not found | Fall back to raw `tool_command` execution (backward compatible) |
| Adapter script fails (non-zero exit) | Captured as tool error, returned to Kanban with `success: false` |
| Adapter missing execute permission | Worker runs `chmod +x` before execution |
| `--cwd` path doesn't exist | Existing check in `execute_task` handles this |
| Tool not installed on host | Adapter exits with error; Worker captures stderr |

## Testing

- **Unit tests:** Test `_resolve_adapter()` with various tool configs (with/without `adapter` field, missing adapters)
- **Integration tests:** Mock adapter script execution, verify argument passing and output capture
- **Backward compatibility test:** Existing `tools.json` entries without `adapter` field still work via fallback

## Migration

1. Create `configs/adapters/qwen.sh` and `configs/adapters/_template.sh`
2. Update `shared/config.py` bootstrap to copy adapters directory
3. Update `docker-compose.yml` to mount adapters volume
4. Update `shared/models.py` — add `adapter` field to `Tool` model
5. Update `services/worker/app.py` — add `adapter` field to `ExecuteRequest`
6. Update `services/worker/executor.py` — add `_resolve_adapter()` and adapter execution path
7. Update `services/kanban/dispatcher.py` — pass `adapter` through to Worker
8. Update `configs/tools.json` to include `adapter` field for existing tools
9. Run tests, restart services
