# Project Legion Design Specification

**Date:** 2026-04-02  
**Status:** Approved  
**Type:** Multi-Agent Autonomous Coding Framework

---

## 1. Overview

Project Legion is an autonomous multi-agent coding framework that decomposes software projects into atomic tasks and executes them in parallel using rotated Qwen CLI profiles. The system uses LLM-driven intelligence for requirements extraction, task decomposition, code generation, and contract validation.

### 1.1 Core Principles

- **LLM-First Intelligence**: All decision-making (except the Librarian) is LLM-driven
- **Profile Rotation**: 20 OAuth-based Qwen profiles rotated to respect 1000 req/day limits
- **Isolated Execution**: Each task runs in a git worktree for safety and traceability
- **Contract Validation**: Tasks include JSON schemas + tests for automated verification
- **Hybrid Communication**: Synchronous API for data, async patterns for task distribution

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PROJECT LEGION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐           │
│  │ Manager  │────▶│ Librarian│◀────│ Atomizer │     │ Kanban   │           │
│  │  (CLI)   │     │  (API)   │     │          │     │          │           │
│  └──────────┘     └────┬─────┘     └──────────┘     └────┬─────┘           │
│         │               │                                  │                │
│         ▼               ▼                                  ▼                │
│  ┌──────────┐     ┌─────────────┐                    ┌──────────┐          │
│  │  User    │     │   Neo4j     │                    │ Worker   │          │
│  │Interview │     │   ChromaDB  │                    │          │          │
│  └──────────┘     │   (Graph+   │                    └────┬─────┘          │
│                   │    Vector)  │                         │                │
│                   └─────────────┘                         ▼                │
│                                                    ┌─────────────┐         │
│                                                    │  Worktree   │         │
│                                                    │  (Isolated) │         │
│                                                    └──────┬──────┘         │
│                                                           │                │
│                                                           ▼                │
│                                                    ┌─────────────┐         │
│                                                    │   Tester    │         │
│                                                    │  (Validator)│         │
│                                                    └─────────────┘         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Services

### 3.1 Manager (CLI + FastAPI)

**Purpose:** Interview users and extract project requirements into a ProjectSpec.

**LLM Usage:**
- Parse natural language requirements
- Ask clarifying questions when input is ambiguous
- Extract tech stack preferences from conversational input

**Interface:**
```bash
python -m legion.manager.cli
# Interactive Q&A session
# POSTs ProjectSpec to Librarian
```

**Data Flow:**
1. Run CLI, answer questions about project goals
2. LLM extracts structured requirements
3. POST `/project-specs` to Librarian

---

### 3.2 Librarian (FastAPI)

**Purpose:** Central knowledge store and task queue manager.

**Storage:**
- **Neo4j**: Graph relationships (tasks, dependencies, profiles, projects)
- **ChromaDB**: Vector embeddings for code/docs semantic search

**API Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ingest` | Store code/docs, link Neo4j nodes to Chroma vectors via `uid` |
| GET | `/tasks/ready` | Return tasks where all dependencies are DONE |
| POST | `/tasks/update` | Update task status and metadata |
| POST | `/project-specs` | Store a ProjectSpec |
| GET | `/project-specs/{id}` | Retrieve a ProjectSpec |
| GET | `/profiles/least-used` | Get profile with lowest `usage_count` |
| POST | `/profiles/{id}/increment` | Increment profile usage counters |

**Data Model:**

```python
# Neo4j Nodes
ProjectSpec {
    id: str
    name: str
    tech_stack: list[str]
    features: list[str]
    created_at: datetime
}

Task {
    task_id: str
    title: str
    status: Enum[PENDING, IN_PROGRESS, DONE, FAILED, MANUAL_REVIEW]
    dependencies: list[str]  # task_ids
    contract: dict  # JSON Schema
    profile_id: str
    worktree_path: str
    created_at: datetime
}

Profile {
    id: str
    name: str
    usage_count: int
    last_used: datetime
    daily_limit: int  # 1000
    requests_today: int
    reset_time: datetime
    capabilities: list[str]
    health_status: Enum[HEALTHY, RATE_LIMITED, ERROR]
    consecutive_failures: int
}
```

---

### 3.3 Atomizer (FastAPI + LLM)

**Purpose:** Decompose ProjectSpec into atomic tasks (<15 min each) with dependencies and contracts.

**LLM Usage:**
- Analyze ProjectSpec and identify all required components
- Decompose into atomic tasks with clear success criteria
- Identify dependencies (e.g., "DB schema before API endpoints")
- Generate JSON Schema contracts for each task
- Generate unit test specifications

**Process:**
1. Pull ProjectSpec from Librarian
2. LLM decomposes into tasks
3. Generate `[:DEPENDS_ON]` relationships
4. Create contracts (JSON Schema + test specs)
5. Store all tasks in Librarian

**Output Example:**
```json
{
  "task_id": "task-001",
  "title": "Create FastAPI app skeleton",
  "dependencies": [],
  "contract": {
    "type": "object",
    "properties": {
      "files_created": {"type": "array", "items": {"type": "string"}},
      "endpoints": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["files_created", "endpoints"]
  },
  "test_spec": {
    "test_file": "tests/test_app.py",
    "assertions": ["app starts", "health endpoint returns 200"]
  }
}
```

---

### 3.4 Kanban (FastAPI + Poller)

**Purpose:** Dispatcher that assigns ready tasks to workers with profile rotation.

**Polling Logic:**
- Poll `/tasks/ready` every 30 seconds
- For each ready task:
  1. Query Librarian for least-used healthy profile
  2. Mark task as `IN_PROGRESS`
  3. Increment profile `usage_count` and `requests_today`
  4. Dispatch to Worker with task + profile

**Rate Limit Handling:**
- On 429 from Worker:
  1. Mark profile as `RATE_LIMITED`
  2. Re-queue task
  3. Select next available profile

**LLM Usage:**
- Intelligent profile selection based on task type matching profile capabilities

---

### 3.5 Worker (FastAPI + Agent)

**Purpose:** Execute coding tasks in isolated git worktrees.

**Process:**
1. Receive task + profile from Kanban
2. `git worktree add /worktrees/task-{id} main`
3. Execute: `qwen-code --profile {profile_name} -p "task prompt"`
4. Run self-tests in worktree
5. Report results to Tester

**LLM Usage:**
- Code generation via `qwen-code --profile [name]`
- Self-test generation and execution

**Error Handling:**
- 429 Rate Limit: Report to Kanban for profile rotation
- Test Failure: Report to Tester for retry logic
- Git Conflict: Report to Tester for manual review

---

### 3.6 Tester (FastAPI + Agent)

**Purpose:** Validate completed work against contracts and manage merges.

**Validation Steps:**
1. **Schema Validation**: Does code structure match JSON Schema?
2. **Test Execution**: Do generated tests pass?
3. **LLM Semantic Check**: Does code semantically fulfill the task?

**Outcomes:**
| Result | Action |
|--------|--------|
| Pass All | Merge worktree to main, set task DONE |
| Test Fail | Send to Worker for 1 retry with context |
| Contract Mismatch | Flag for Manual Review |
| Retry Fail | Flag for Manual Review |

**LLM Usage:**
- Semantic contract validation beyond schema matching
- Analyze failure context for retry instructions

---

## 4. Data Flow

### 4.1 Project Initialization
```
User → Manager (CLI Interview) → ProjectSpec → Librarian (Neo4j)
```

### 4.2 Task Decomposition
```
Atomizer → Librarian (GET ProjectSpec) 
       → LLM Decomposition 
       → Tasks + Dependencies + Contracts 
       → Librarian (POST Tasks)
```

### 4.3 Task Execution Loop
```
Kanban (poll /tasks/ready) 
     → Select Profile 
     → Worker (task + profile) 
     → git worktree + qwen-code --profile 
     → Self-Test 
     → Tester
```

### 4.4 Validation & Merge
```
Tester → Contract Check + Test Run + LLM Review
     → [Pass] → git merge → Task DONE
     → [Fail] → Retry or Manual Review
```

---

## 5. Profile Management

### 5.1 Profile Schema
```json
{
  "name": "qwen-agent-01",
  "usage_count": 147,
  "last_used": "2026-04-02T14:30:00Z",
  "daily_limit": 1000,
  "requests_today": 89,
  "reset_time": "2026-04-03T00:00:00Z",
  "capabilities": ["coding", "testing", "refactoring"],
  "health_status": "healthy",
  "consecutive_failures": 0
}
```

### 5.2 Rotation Strategy
- Select profile with lowest `usage_count` among `healthy` profiles
- Increment `requests_today` on each dispatch
- Reset `requests_today` at `reset_time` (midnight UTC)
- Mark `RATE_LIMITED` on 429, auto-recover after reset

---

## 6. Error Handling Matrix

| Error Type | Source | Detection | Action |
|------------|--------|-----------|--------|
| 429 Rate Limit | qwen-code CLI | Exit code / stderr | Rotate profile, re-queue |
| Test Failure | pytest | Non-zero exit | 1 retry with error context |
| Contract Mismatch | Tester LLM | Semantic analysis | Manual review |
| Git Conflict | git | Merge conflict | Manual review |
| Profile Exhausted | Kanban | All profiles RATE_LIMITED | Wait for reset, alert user |

---

## 7. Deployment

### 7.1 Docker Compose Services
```yaml
services:
  neo4j:
    image: neo4j:5
    ports: ["7474:7474", "7687:7687"]
  
  chromadb:
    image: chromadb/chroma
    ports: ["8000:8000"]
  
  librarian:
    build: ./services/librarian
    depends_on: [neo4j, chromadb]
  
  manager:
    build: ./services/manager
  
  atomizer:
    build: ./services/atomizer
    depends_on: [librarian]
  
  kanban:
    build: ./services/kanban
    depends_on: [librarian]
  
  worker:
    build: ./services/worker
    depends_on: [kanban]
    volumes: [./worktrees:/app/worktrees]
  
  tester:
    build: ./services/tester
    depends_on: [worker]
    volumes: [./worktrees:/app/worktrees]
```

### 7.2 Directory Structure
```
/legion-root/
├── services/
│   ├── librarian/
│   ├── manager/
│   ├── atomizer/
│   ├── kanban/
│   ├── worker/
│   └── tester/
├── shared/
│   └── models.py
├── configs/
│   └── profiles.json
├── worktrees/
└── docker-compose.yml
```

---

## 8. Git Strategy

- **Main Branch**: `main` - production-ready code
- **Task Branches**: Created via `git worktree add` for each task
- **Merge Strategy**: Tester merges successful tasks directly to `main`
- **Worktree Cleanup**: Remove worktree after merge or manual review

---

## 9. Testing Strategy

### 9.1 Per-Task Testing
- Atomizer generates task-specific unit tests
- Worker runs self-tests before reporting
- Tester re-runs tests for validation

### 9.2 Integration Testing
- Contract validation (JSON Schema)
- LLM semantic validation
- End-to-end workflow tests

---

## 10. Security Considerations

- OAuth tokens managed by `qwen-code` CLI (not stored in codebase)
- Profile metadata in Neo4j (no secrets)
- Worktrees isolated per task
- Docker network isolation for services

---

## 11. Future Enhancements

- Web UI for Kanban dashboard
- PostgreSQL for structured analytics
- Redis for caching and real-time counters
- Kubernetes deployment for horizontal scaling
- Profile capability learning (LLM improves matching over time)
