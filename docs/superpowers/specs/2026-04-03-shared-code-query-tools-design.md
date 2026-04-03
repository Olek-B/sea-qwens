# Shared Code Query Tools — Design Spec

## Problem

Manager and Atomizer need read-only access to the code knowledge graph (Neo4j + ChromaDB via the Librarian) when a project already exists. Currently, only the Worker has this capability through `services/worker/mcp_tools.py::CodeQueryTools`.

## Goals

1. Give Manager and Atomizer access to the code database for existing projects
2. Provide higher-level helpers (not just raw queries) so each service gets project-aware context
3. Consolidate all code DB query logic into a single shared module
4. Maintain backward compatibility with the Worker

## Architecture

### Layer 1: `CodeQueryTools` (base client)

Moved from `services/worker/mcp_tools.py` to `shared/code_query_tools.py`.

```python
class CodeQueryTools:
    """HTTP client for the Librarian's code query API."""

    def __init__(self, librarian_url: str):
        self.librarian_url = librarian_url

    def search_code(self, query: str, type: str = "function") -> list
    def get_function(self, name: str) -> Optional[dict]
    def get_callers(self, function_name: str) -> list
    def get_callees(self, function_name: str) -> list
    def get_full_context(self, function_name: str) -> dict
    def get_class(self, name: str) -> Optional[dict]
```

All methods:
- Return `None` or empty list on failure (no exceptions raised to callers)
- Log warnings on connection errors
- Timeout: 10 seconds per request

### Layer 2: `ProjectCodeContext` (higher-level helpers)

Wraps `CodeQueryTools` with project-aware methods.

```python
class ProjectCodeContext:
    """Higher-level code context helpers for a specific project."""

    def __init__(self, tools: CodeQueryTools):
        self.tools = tools

    def get_project_overview(self, project_name: str) -> Optional[dict]
    def find_existing_features(self, project_name: str, features: list[str]) -> dict
    def get_dependency_map(self) -> dict
    def search_by_category(self, category: str) -> list
```

#### `get_project_overview(project_name)`

Returns a summary of the project's code structure:

```python
{
    "project_name": "myapp",
    "files": [{"path": "...", "language": "..."}],
    "classes": [{"name": "...", "file_path": "..."}],
    "functions": [{"name": "...", "file_path": "..."}],
    "total_files": 10,
    "total_functions": 45,
    "total_classes": 8
}
```

Returns `None` if the project has no code in the database (first run).

Implementation: queries Neo4j via Librarian's `/code/search` with the project name as a broad query, then aggregates results.

#### `find_existing_features(project_name, features)`

Given a list of feature keywords, returns which ones have matching code:

```python
{
    "auth": {"found": True, "matches": [{"name": "AuthService", "type": "class"}]},
    "payments": {"found": False, "matches": []},
    "users": {"found": True, "matches": [{"name": "UserModel", "type": "class"}]}
}
```

Implementation: for each feature keyword, calls `search_code(feature)` and checks if results are non-empty.

#### `get_dependency_map()`

Returns the CALLS and INHERITS graph for the project:

```python
{
    "calls": [{"caller": "func_a", "callee": "func_b"}],
    "inherits": [{"child": "AdminService", "parent": "AuthService"}]
}
```

Implementation: first calls `search_code("")` (empty query) to get all functions, then for each function calls `/code/function/{name}/callers` and `/code/function/{name}/callees` to build the relationship graph. For INHERITS, queries `/code/class/{name}` for each class and extracts base classes.

#### `search_by_category(category)`

Searches for code related to common categories: "auth", "database", "api", "testing", "config", "logging".

Returns list of matching functions/classes.

### Service Integration

#### Manager (`services/manager/interviewer.py`)

After the user provides a project name, the interviewer:

1. Creates a `ProjectCodeContext` with `LIBRARIAN_URL`
2. Calls `get_project_overview(name)`
3. If results exist, calls `find_existing_features(name, features_from_user)`
4. Uses results to inform follow-up questions

Example flow:
```
User: "My project is called 'auth-service'"
Manager: (queries code DB) "I found 12 functions and 3 classes for auth-service, including AuthService and TokenValidator. Should we extend these?"
```

If the project doesn't exist in the code DB, the Manager proceeds normally without code context.

#### Atomizer (`services/atomizer/decomposer.py`)

During `decompose()`:

1. Creates a `ProjectCodeContext` with `LIBRARIAN_URL`
2. Calls `get_project_overview(project_spec["name"])`
3. If results exist, calls `find_existing_features(project_spec["name"], project_spec["features"])`
4. Skips or modifies task generation for features that already exist

Example: if the user requests "add authentication" but `find_existing_features` finds an `AuthService` class, the Atomizer creates a task to "extend AuthService with X" rather than "create authentication system from scratch."

#### Worker (`services/worker/`)

No functional change. The Worker imports `CodeQueryTools` from `shared.code_query_tools` instead of its own module. The old `services/worker/mcp_tools.py` re-exports from `shared` for backward compatibility.

### Error Handling

| Scenario | Behavior |
|----------|----------|
| Librarian not reachable | Log warning, return `None`/empty |
| Project not in code DB | Return `None` from `get_project_overview` (not an error) |
| Partial results | Return available data, log missing parts |
| Malformed response | Return `None`, log error |

### Data Flow

```
Manager/Atomizer
    │
    ├── ProjectCodeContext
    │       │
    │       └── CodeQueryTools
    │               │
    │               └── HTTP → Librarian → Neo4j/ChromaDB
    │
    └── Uses results to inform decisions
```

### File Changes

| File | Action |
|------|--------|
| `shared/code_query_tools.py` | **New** — `CodeQueryTools` + `ProjectCodeContext` |
| `shared/__init__.py` | **Update** — export new classes |
| `services/worker/mcp_tools.py` | **Update** — re-export from `shared` |
| `services/manager/interviewer.py` | **Update** — use `ProjectCodeContext` |
| `services/manager/cli.py` | **Update** — display code context during interview |
| `services/atomizer/decomposer.py` | **Update** — use `ProjectCodeContext` in `decompose()` |
| `services/atomizer/app.py` | **Update** — pass `LIBRARIAN_URL` to decomposer |
| `shared/test_code_query_tools.py` | **New** — unit tests for shared module |
| `services/manager/tests/test_interviewer.py` | **Update** — tests for code context integration |
| `services/atomizer/tests/test_decomposer.py` | **Update** — tests for code context integration |

### Testing Strategy

1. **Unit tests** for `CodeQueryTools` — mock HTTP responses, verify all methods handle errors gracefully
2. **Unit tests** for `ProjectCodeContext` — mock `CodeQueryTools`, verify aggregation logic
3. **Integration tests** for Manager — verify interview flow adapts when code context is available
4. **Integration tests** for Atomizer — verify task decomposition skips existing features
5. **Backward compat test** — verify Worker still works with re-exported `CodeQueryTools`
