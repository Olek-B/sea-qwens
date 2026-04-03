# Design: Tool-Centric Task Dispatch

**Date:** 2026-04-03
**Status:** Approved
**Author:** Qwen Code (brainstorming session)

## Problem

The Worker service hardcodes `qwen` as the only CLI tool for task execution. Agent profiles (`configs/profiles.json`) track usage counters and capabilities but don't control *which* CLI tool runs — they're just labels with counters. Users want to rotate across multiple CLI tools (qwen, codex, claude code, etc.) with a single, clean rotation mechanism.

## Goal

Replace the profile-centric model with a tool-centric model. One config file, one rotation mechanism: the least-used healthy tool gets chosen for each task.

## Architecture

### Config: `configs/tools.json`

Replaces `configs/profiles.json`. Array of tool objects:

```json
[
  {
    "name": "qwen-coder",
    "command": "qwen --non-interactive",
    "health": "HEALTHY",
    "capabilities": ["coding", "testing", "debugging"],
    "requests_today": 0,
    "consecutive_failures": 0
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Human-readable identifier (user's choice) |
| `command` | string | Non-interactive CLI command; prompt is appended at runtime |
| `health` | string | `HEALTHY`, `RATE_LIMITED`, or `ERROR` |
| `capabilities` | string[] | Skill tags. Default: all tools get all capabilities |
| `requests_today` | int | Usage counter for least-used rotation |
| `consecutive_failures` | int | Auto-tracked for health detection |

### Shared Model Changes (`shared/models.py`)

- `Task.profile_id: Optional[str]` → `Task.tool_id: Optional[str]`
- `class Profile` → `class Tool` (same fields, renamed to match config)
- All other models (`TaskStatus`, `ProjectSpec`, etc.) unchanged

### Neo4j Migration

- Rename all `(Profile)` nodes → `(Tool)`
- Properties stay the same: `name`, `requests_today`, `consecutive_failures`, `health_status`, `capabilities`
- One-time migration script: `services/librarian/migrate_profiles_to_tools.py`

### Service Changes

#### Librarian (`services/librarian/`)

| Old Endpoint | New Endpoint | Description |
|--------------|--------------|-------------|
| `GET /profiles/least-used` | `GET /tools/least-used` | Returns least-used healthy tool |
| `POST /profiles/{name}/increment` | `POST /tools/{name}/increment` | Increment tool usage counter |

- Update Neo4j queries: `MATCH (p:Profile)` → `MATCH (t:Tool)`
- Update Pydantic models in request/response schemas
- Tool loading on startup reads `configs/tools.json` instead of `profiles.json`

#### Kanban (`services/kanban/`)

- Dispatcher queries `GET /tools/least-used` instead of profiles endpoint
- Passes `tool_id` and `tool_command` to Worker in dispatch payload
- Tool selection logic: filter by `health == "HEALTHY"` and matching capabilities, then sort by `requests_today` ascending

#### Worker (`services/worker/`)

- `TaskExecutor.execute_task()` accepts `tool_command: str` parameter instead of using hardcoded `QWEN_CODE_CMD`
- Execution: `<tool_command> --prompt "<prompt>" --cwd <worktree>`
- Worker is now tool-agnostic — it doesn't know what tool it's running

#### Atomizer, Tester, Manager

No changes needed.

### Worker Execution Flow

```
Kanban dispatches → Worker receives {task, tool_id, tool_command, worktree_path}
Worker runs: <tool_command> --prompt "<prompt>" --cwd <worktree>
```

### Files Changed

| File | Action |
|------|--------|
| `configs/profiles.json` | Deleted |
| `configs/tools.json` | Created |
| `shared/models.py` | Rename `Profile` → `Tool`, `profile_id` → `tool_id` |
| `shared/test_models.py` | Update test fixtures |
| `services/librarian/app.py` | Rename endpoints, update Neo4j queries, load tools config |
| `services/librarian/neo4j_store.py` | Update node labels Profile → Tool |
| `services/librarian/migrate_profiles_to_tools.py` | Created — one-time migration script |
| `services/librarian/tests/test_api.py` | Update tests |
| `services/kanban/dispatcher.py` | Query tools instead of profiles, pass tool_command |
| `services/kanban/tests/` | Update tests |
| `services/worker/executor.py` | Accept `tool_command` param, remove hardcoded `QWEN_CODE_CMD` |
| `services/worker/app.py` | Accept `tool_command` in request model |
| `services/worker/tests/test_executor.py` | Update tests |
| `README.md` | Update references from profiles to tools |

### Error Handling

- If a tool's `consecutive_failures` exceeds a threshold (e.g., 3), its `health` is set to `ERROR` and it's excluded from dispatch
- Rate limit detection in Worker output (existing `_is_rate_limited()` method) sets tool health to `RATE_LIMITED`
- Tools with `health != "HEALTHY"` are excluded from least-used queries

### Testing Strategy

- All existing tests updated to use `tool_id` instead of `profile_id`
- New test: Worker executes with a mock tool command (e.g., `echo`) to verify tool-agnostic execution
- New test: Kanban dispatcher correctly selects least-used tool
- New test: Librarian `/tools/least-used` returns correct tool ordering
