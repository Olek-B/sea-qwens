# Code Knowledge Graph Design Specification

**Date:** 2026-04-02  
**Status:** Approved  
**Type:** Design Amendment to Project Legion

---

## 1. Overview

The Librarian's Neo4j + ChromaDB stores the **codebase itself** as a knowledge graph, not just task metadata. Agents query this graph instead of reading files directly. When an agent needs context about "login functions," the Librarian returns the function bodies, their callers, callees, and full dependency chains.

This replaces the previous model where agents had filesystem read access to the broader codebase.

---

## 2. Graph Schema

### 2.1 Node Hierarchy

```
(:Project)-[:CONTAINS]->(:Module)-[:CONTAINS]->(:File)
  -[:CONTAINS]->(:Class)-[:CONTAINS]->(:Function)
```

### 2.2 Node Properties

| Label | Properties |
|-------|-----------|
| `Project` | `name`, `tech_stack`, `created_at` |
| `Module` | `name`, `path` (e.g., `services/librarian`) |
| `File` | `path`, `language`, `content`, `last_updated` |
| `Class` | `name`, `file_path`, `line_start`, `line_end`, `body`, `docstring`, `bases` |
| `Function` | `name`, `file_path`, `line_start`, `line_end`, `body`, `signature`, `docstring`, `is_method`, `parent_class` |

### 2.3 Relationships

| Type | From → To | Meaning |
|------|-----------|---------|
| `[:CONTAINS]` | Project→Module→File→Class→Function | Hierarchy |
| `[:CALLS]` | Function→Function | Function A calls Function B |
| `[:IMPORTS]` | File→File or Module→Module | Import dependency |
| `[:INHERITS]` | Class→Class | Class inheritance |
| `[:INSTANTIATES]` | Function→Class | Function creates instance of Class |
| `[:USES]` | Function→Class | Function uses Class (parameter, type hint) |

### 2.4 ChromaDB Vectors

Vector embeddings stored for:
- Function bodies
- Class bodies
- Docstrings

Enables semantic search: "find functions related to authentication"

---

## 3. Code Indexer

### 3.1 Location

`shared/indexer.py` - shared parsing logic used by both pre-importer and post-execution indexer.

### 3.2 Technology

tree-sitter for AST parsing (supports Python, JavaScript, TypeScript, Go, Rust, etc.)

### 3.3 Extraction

For each source file, the indexer extracts:
- All classes with full source code, docstrings, base classes
- All functions/methods with signatures, bodies, docstrings
- Call relationships (which function calls which, including cross-file)
- Import relationships between files
- Inheritance chains

### 3.4 Output

Returns structured data ready for Neo4j upsert:
```python
{
    "files": [{"path": "...", "language": "python", "content": "..."}],
    "classes": [{"name": "...", "file_path": "...", "body": "...", "bases": [...]}],
    "functions": [{"name": "...", "file_path": "...", "signature": "...", "body": "...", "is_method": True, "parent_class": "..."}],
    "calls": [{"caller": "func_a", "callee": "func_b"}],
    "imports": [{"from_file": "a.py", "to_file": "b.py"}],
    "inherits": [{"child": "ClassA", "parent": "ClassB"}]
}
```

---

## 4. Pre-importer

### 4.1 Purpose

One-time bulk import of existing codebases (projects not built purely using Legion).

### 4.2 CLI Interface

```bash
python -m services.librarian.preimport /path/to/existing/project
```

### 4.3 Process

1. Scan target directory for source files (respecting .gitignore)
2. Run indexer on each file
3. Bulk upsert all nodes and relationships into Neo4j
4. Bulk add all code documents to ChromaDB with vectors
5. Report: "Indexed 47 files, 12 classes, 203 functions"

---

## 5. Post-execution Indexer

### 5.1 Trigger

Called by the Tester after a successful merge to main.

### 5.2 Process

1. Tester calls `POST /index/updated` with list of changed files
2. Librarian runs indexer on the merged code
3. Upserts affected nodes (handles renames, deletions, additions)
4. Updates call/import relationships
5. Returns summary of changes

### 5.3 Incremental Logic

- Compares current file content with stored version
- Only updates nodes that changed
- Removes nodes for deleted functions/classes
- Adds nodes for new functions/classes

---

## 6. Query API

### 6.1 HTTP Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/code/search?q=login&type=function` | Semantic search via ChromaDB |
| GET | `/code/function/{id}` | Get function details (body, signature, docstring) |
| GET | `/code/function/{id}/callers` | Get all functions that call this function |
| GET | `/code/function/{id}/callees` | Get all functions this function calls |
| GET | `/code/function/{id}/full-context` | Get function + callers + callees + their code (recursive, depth-limited) |
| GET | `/code/class/{id}` | Get class details + methods |
| GET | `/code/class/{id}/hierarchy` | Get inheritance chain |
| GET | `/code/file/{path}` | Get file content |
| POST | `/index/updated` | Index changed files after merge |
| POST | `/preimport` | Bulk import existing codebase |

### 6.2 MCP Tools (for Worker's qwen-code session)

| Tool | Description |
|------|-------------|
| `search_code(query, type)` | Search for functions/classes by semantic similarity |
| `get_function(name)` | Get function body and signature by name |
| `get_callers(function_name)` | "Who calls this function?" |
| `get_callees(function_name)` | "What does this function call?" |
| `get_full_context(function_name)` | "Give me everything I need to understand this function" |
| `get_class(name)` | Get class definition and all methods |

---

## 7. Worker Integration

### 7.1 Prompt Update

The Worker's qwen-code prompt includes:
- Instructions to use MCP tools instead of reading files
- Examples: "Before implementing `authenticate_user`, call `search_code('authentication')` to find existing auth functions, then `get_callers('verify_password')` to understand the call chain"

### 7.2 Filesystem Access

The Worker no longer needs filesystem read access to the broader codebase. It only:
- Writes to its isolated worktree
- Queries the Librarian for code context via MCP tools

---

## 8. Changes to Existing Codebase

| Component | Change |
|-----------|--------|
| `shared/indexer.py` | **NEW** - tree-sitter based code parser |
| `shared/models.py` | **ADD** - CodeNode, FunctionNode, ClassNode models |
| `services/librarian/neo4j_store.py` | **EXTEND** - add code graph CRUD operations |
| `services/librarian/app.py` | **EXTEND** - add code query endpoints |
| `services/librarian/preimport.py` | **NEW** - bulk import CLI |
| `services/librarian/post_indexer.py` | **NEW** - incremental indexer |
| `services/tester/app.py` | **MODIFY** - call `/index/updated` after merge |
| `services/worker/executor.py` | **MODIFY** - update prompt to use MCP tools |
| `services/worker/mcp_tools.py` | **NEW** - MCP tool definitions for qwen-code |
| `services/librarian/requirements.txt` | **ADD** - tree-sitter, tree-sitter-python, etc. |

---

## 9. Dependencies

- tree-sitter and language-specific grammars for AST parsing
- Existing Neo4j and ChromaDB infrastructure (already in docker-compose)
- MCP server capability for the Librarian (or HTTP proxy pattern)

---

## 10. Success Criteria

1. Pre-importer can index a 10k-line Python project in under 2 minutes
2. `GET /code/function/{id}/full-context` returns complete call chain with code
3. Worker can implement a feature using only MCP tool queries (no file reads)
4. Post-execution indexer updates the graph within 5 seconds of merge
5. Semantic search returns relevant functions for queries like "user authentication"
