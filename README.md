# Sea Qwens

> Autonomous multi-agent coding framework — decompose, assign, execute, validate, and merge code tasks without human intervention.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Services](#services)
- [Configuration](#configuration)
- [Development](#development)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

Sea Qwens orchestrates a fleet of AI coding agents (CLI tools) to autonomously implement software projects from a high-level specification. You describe **what** you want; Sea Qwens figures out **how** to build it.

**Core workflow:**

1. **Manager** — interviews the user (or accepts a spec) and creates a `ProjectSpec` in the knowledge base.
2. **Librarian** — stores project specs, tasks, and tools in Neo4j (graph) and ChromaDB (vector).
3. **Atomizer** — decomposes a project spec into atomic, dependency-ordered tasks with contracts.
4. **Kanban** — continuously polls for ready tasks and dispatches them to healthy, least-used tools.
5. **Worker** — executes tasks in isolated git worktrees, invoking Qwen Code with task contracts.
6. **Tester** — validates completed work against contracts (structure, tests, semantics), then merges passing branches.

---

## Architecture

```
┌─────────────┐
│   Manager   │  CLI interview → ProjectSpec
└──────┬──────┘
       │ POST /project-specs
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Librarian  │────▶│   Neo4j     │     │  ChromaDB   │
│  (8001)     │     │  (7474/7687)│     │   (8000)    │
└──────┬──────┘     └─────────────┘     └─────────────┘
       │
       │ GET /tasks/ready  POST /tasks/batch
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│   Kanban    │     │  Atomizer   │
│  (8003)     │     │  (8002)     │
│  APScheduler│     │ decompose   │
└──────┬──────┘     └─────────────┘
       │ dispatch
       ▼
┌─────────────┐
│   Worker    │  git worktree → Qwen Code → commit
│  (8004)     │
└──────┬──────┘
       │ submit for validation
       ▼
┌─────────────┐
│   Tester    │  contract check → test run → merge
│  (8005)     │
└─────────────┘
```

**Data flow:** Spec → Decompose → Tasks → Dispatch → Execute → Validate → Merge

---

## Code Knowledge Graph

The Librarian stores the entire codebase as a knowledge graph in Neo4j + ChromaDB. Agents query this graph instead of reading files directly.

### Graph Structure

```
Project → Module → File → Class → Function
```

With relationships: `CALLS`, `IMPORTS`, `INHERITS`, `INSTANTIATES`, `USES`.

### Querying Code

**HTTP API:**
```bash
# Search for authentication-related code
curl "http://localhost:8001/code/search?q=authentication&type=function"

# Get function details
curl http://localhost:8001/code/function/login

# Get full call context
curl http://localhost:8001/code/function/login/full-context

# Get class and methods
curl http://localhost:8001/code/class/AuthService
```

**MCP Tools (for Worker LLM):**
- `search_code(query)` - Semantic search
- `get_function(name)` - Get function details
- `get_callers(name)` / `get_callees(name)` - Call chain analysis
- `get_full_context(name)` - Complete function context
- `get_class(name)` - Class definition + methods

### Importing Code

**Pre-import existing codebase:**
```bash
python -m services.librarian.preimport /path/to/existing/project
```

**Post-execution indexing** happens automatically when the Tester merges a task.

---

## Quick Start

### Prerequisites

| Requirement        | Version     | Notes                              |
|--------------------|-------------|------------------------------------|
| Docker             | 20.10+      | With Compose plugin                |
| Python             | 3.11+       | For local development & tests      |
| Git                | 2.23+       | Worktree support required          |
| Qwen Code          | latest      | Installed and configured           |

### Start All Services

```bash
# Clone and enter the project
cd worktrees/sea-qwens-implement

# Start everything in dependency order (infra → librarian → app services)
./scripts/start-sea-qwens.sh
```

The script starts services in phases with health-check waits:

1. **Phase 1** — Neo4j + ChromaDB (infrastructure)
2. **Phase 2** — Librarian (knowledge layer)
3. **Phase 3** — Atomizer, Kanban, Worker, Tester, Manager (application layer)

### Stop All Services

```bash
docker compose -f docker-compose.yml down
```

### Create Your First Project

```bash
# Run the Manager interview CLI
python -m services.manager.cli interview
```

Answer the prompts to create a `ProjectSpec`, which is sent to the Librarian automatically.

---

## Services

| Service    | Port | Container           | Description                                        |
|------------|------|---------------------|----------------------------------------------------|
| Neo4j      | 7474 | `sea-qwens-neo4j`     | Graph database — tasks, dependencies, tools        |
| Neo4j Bolt | 7687 | `sea-qwens-neo4j`     | Bolt protocol for graph queries                    |
| ChromaDB   | 8000 | `sea-qwens-chromadb`  | Vector store — document ingestion & retrieval      |
| Librarian  | 8001 | `sea-qwens-librarian` | Knowledge service — specs, tasks, tools, docs      |
| Atomizer   | 8002 | `sea-qwens-atomizer`  | Task decomposition — spec → atomic tasks + contracts |
| Kanban     | 8003 | `sea-qwens-kanban`    | Task dispatcher — polls & assigns to tools          |
| Worker     | 8004 | `sea-qwens-worker`    | Task executor — runs Qwen Code in git worktrees    |
| Tester     | 8005 | `sea-qwens-tester`    | Validator & merger — contract checks, branch merge |
| Manager    | 8006 | `sea-qwens-manager`   | CLI interviewer — interactive spec creation        |

All services communicate over the `sea-qwens-network` Docker bridge network.

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and adjust values:

```bash
cp .env.example .env
```

| Variable          | Default                    | Description                     |
|-------------------|----------------------------|---------------------------------|
| `NEO4J_URI`       | `bolt://localhost:7687`    | Neo4j connection URI            |
| `NEO4J_USER`      | `neo4j`                    | Neo4j username                  |
| `NEO4J_PASSWORD`  | `password`                 | Neo4j password                  |
| `CHROMA_DB_HOST`  | `localhost`                | ChromaDB host                   |
| `CHROMA_DB_PORT`  | `8000`                     | ChromaDB port                   |
| `LIBRARIAN_URL`   | `http://localhost:8001`    | Librarian service URL           |
| `ATOMIZER_URL`    | `http://localhost:8002`    | Atomizer service URL            |
| `KANBAN_URL`      | `http://localhost:8003`    | Kanban service URL              |
| `WORKER_URL`      | `http://localhost:8004`    | Worker service URL              |
| `TESTER_URL`      | `http://localhost:8005`    | Tester service URL              |
| `QWEN_CODE_PATH`  | `qwen-code`                | Path to Qwen Code executable    |

### Docker Compose Overrides

The `docker-compose.yml` sets internal service URLs (e.g., `NEO4J_URI=neo4j://neo4j:7687`). These differ from the `.env.example` localhost defaults, which are intended for local development outside Docker.

### Tool Configuration

CLI tools are defined in `configs/tools.json`. Each tool entry has:

- **`name`** — human-readable identifier (e.g., `qwen-coder`)
- **`command`** — non-interactive CLI command (e.g., `qwen --non-interactive`)
- **`daily_limit`** — max requests per day (default: 1000)
- **`capabilities`** — skill tags (coding, testing, debugging, etc.)
- **`health_status`** — `HEALTHY`, `RATE_LIMITED`, or `ERROR`
- **`consecutive_failures`** — auto-tracked failure counter

The Kanban dispatcher selects the **least-used healthy tool** whose capabilities match the task.

```bash
# View current tools
cat configs/tools.json | python -m json.tool
```

To add or modify tools, edit `configs/tools.json` and restart the Kanban service.

---

## Development

### Project Structure

```
sea-qwens/
├── configs/
│   └── tools.json             # CLI tool definitions
├── docs/
│   └── superpowers/           # Superpowers skill documentation
├── scripts/
│   └── start-sea-qwens.sh     # Orchestrated service startup
├── services/
│   ├── atomizer/              # Task decomposition service
│   ├── kanban/                # Task dispatcher service
│   ├── librarian/             # Knowledge/graph/vector service
│   ├── manager/               # CLI interviewer
│   ├── tester/                # Validation & merge service
│   └── worker/                # Task execution service
├── shared/
│   └── models.py              # Shared Pydantic models
├── docker-compose.yml         # Multi-service orchestration
└── .env.example               # Environment template
```

### Run Tests

Each service has its own test suite. Run all tests from the project root:

```bash
# Run all tests
python -m pytest services/ shared/ -v

# Run tests for a single service
python -m pytest services/librarian/tests/ -v
python -m pytest services/worker/tests/ -v
python -m pytest services/tester/tests/ -v
python -m pytest services/kanban/tests/ -v
python -m pytest services/atomizer/tests/ -v
python -m pytest services/manager/tests/ -v

# Run shared model tests
python -m pytest shared/test_models.py -v
```

### Add a New Tool

1. Edit `configs/tools.json` and add a new entry to the `tools` array.
2. Restart the Kanban service to pick up the changes:

```bash
docker compose -f docker-compose.yml restart kanban
```

### Add a New Service

1. Create `services/<name>/` with `Dockerfile`, `app.py`, `requirements.txt`.
2. Add a service block to `docker-compose.yml`.
3. Register inter-service URLs in `.env` and the compose `environment` section.

### Service Dependencies

```
Neo4j ──┐
        ├──▶ Librarian ──┬──▶ Atomizer
ChromaDB┘                ├──▶ Kanban ──▶ Worker ──▶ Tester
                         └──▶ Manager
```

---

## API Reference

### Librarian (`:8001`)

| Method | Path                      | Description                        |
|--------|---------------------------|------------------------------------|
| POST   | `/project-specs`          | Create a project specification     |
| GET    | `/project-specs/{id}`     | Get a project specification        |
| POST   | `/tasks`                  | Create a task                      |
| POST   | `/tasks/batch`            | Create multiple tasks              |
| POST   | `/tasks/update`           | Update task status                 |
| GET    | `/tasks/ready`            | Get tasks with all deps satisfied  |
| POST   | `/ingest`                 | Ingest document into ChromaDB      |
| GET    | `/tools/least-used`       | Get least-used healthy tool        |
| POST   | `/tools/{name}/increment` | Increment tool usage count         |

### Atomizer (`:8002`)

| Method | Path         | Description                          |
|--------|--------------|--------------------------------------|
| POST   | `/decompose` | Decompose project spec into tasks    |
| GET    | `/health`    | Health check                         |

### Kanban (`:8003`)

| Method | Path            | Description                          |
|--------|-----------------|--------------------------------------|
| GET    | `/health`       | Health check                         |
| POST   | `/dispatch/now` | Trigger immediate task dispatch      |
| GET    | `/status`       | Get dispatcher status                |

### Worker (`:8004`)

| Method | Path                 | Description                          |
|--------|----------------------|--------------------------------------|
| POST   | `/execute`           | Submit a task for execution          |
| GET    | `/execute/{task_id}` | Get execution status for a task      |
| GET    | `/health`            | Health check                         |

### Tester (`:8005`)

| Method | Path                | Description                              |
|--------|---------------------|------------------------------------------|
| POST   | `/validate`         | Validate task output and merge if passed |
| POST   | `/retry/{task_id}`  | Send failed task back to Worker          |
| GET    | `/health`           | Health check                             |

### Manager (CLI)

| Command                        | Description                          |
|--------------------------------|--------------------------------------|
| `python -m services.manager.cli interview` | Interactive spec creation |

---

## Troubleshooting

### Rate Limits

If tools hit their daily limit or become rate-limited:

```bash
# Check tool health via Librarian
curl http://localhost:8001/tools/least-used

# Reset a tool's counters in Neo4j Browser
# Open http://localhost:7474 and run:
# MATCH (t:Tool {name: "qwen-coder"})
# SET t.requests_today = 0, t.consecutive_failures = 0, t.health_status = "HEALTHY"
# RETURN t
```

### Worktree Conflicts

The Worker creates git worktrees under `worktrees/`. If a worktree fails to clean up:

```bash
# List existing worktrees
git worktree list

# Remove a stale worktree
git worktree remove worktrees/<task-id> --force

# Prune stale worktree references
git worktree prune
```

### Service Health Checks

```bash
# Check all container statuses
docker compose -f docker-compose.yml ps

# Follow logs for a specific service
docker compose -f docker-compose.yml logs -f worker

# Quick health check all services
curl http://localhost:8001/health  # Librarian (no /health endpoint, use tasks/ready)
curl http://localhost:8002/health  # Atomizer
curl http://localhost:8003/health  # Kanban
curl http://localhost:8004/health  # Worker
curl http://localhost:8005/health  # Tester
```

### Neo4j Connection Issues

```bash
# Verify Neo4j is accepting connections
curl http://localhost:7474

# Check Bolt port
docker compose -f docker-compose.yml exec neo4j cypher-shell -u neo4j -p password "RETURN 1"
```

### ChromaDB Connection Issues

```bash
# Verify ChromaDB heartbeat
curl http://localhost:8000/api/v1/heartbeat
```

### Docker Compose Not Found

```bash
# If 'docker compose' fails, try 'docker-compose'
# The start script auto-detects which is available
./scripts/start-sea-qwens.sh
```

### Reset Everything

```bash
# Stop and remove all containers, networks, and volumes
docker compose -f docker-compose.yml down -v

# Rebuild and restart
docker compose -f docker-compose.yml up --build -d
```

---

## License

MIT

Copyright (c) 2026 Sea Qwens Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
