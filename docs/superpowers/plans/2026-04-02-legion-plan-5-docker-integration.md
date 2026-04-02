# Project Legion Plan 5: Docker Compose Integration + Full System Wiring

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update docker-compose.yml to include all services, add health checks, and wire the complete system together for end-to-end testing.

**Architecture:** Single docker-compose.yml orchestrating Neo4j, ChromaDB, Librarian, Manager, Atomizer, Kanban, Worker, and Tester. Shared network for inter-service communication.

**Tech Stack:** Docker Compose, Docker networking, health checks, environment configuration

---

## File Structure

```
/legion-root/
├── docker-compose.yml      # Updated with all services
├── .env                    # Environment variables
├── .gitignore              # Ignore worktrees, env files
├── README.md               # Project documentation
└── scripts/
    └── start-legion.sh     # Startup script
```

---

### Task 1: Complete Docker Compose

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Update docker-compose.yml with all services**

```yaml
# docker-compose.yml
version: '3.8'

services:
  # ==================== Infrastructure ====================
  
  neo4j:
    image: neo4j:5
    container_name: legion-neo4j
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc"]'
    volumes:
      - neo4j_data:/data
    networks:
      - legion-network
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:7474"]
      interval: 10s
      timeout: 5s
      retries: 5

  chromadb:
    image: chromadb/chroma
    container_name: legion-chromadb
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma
    networks:
      - legion-network
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:8000/api/v1/heartbeat"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ==================== Legion Services ====================
  
  librarian:
    build:
      context: .
      dockerfile: services/librarian/Dockerfile
    container_name: legion-librarian
    ports:
      - "8001:8001"
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_USER: neo4j
      NEO4J_PASSWORD: password
      CHROMA_DB_HOST: chromadb
      CHROMA_DB_PORT: 8000
    depends_on:
      neo4j:
        condition: service_healthy
      chromadb:
        condition: service_healthy
    networks:
      - legion-network
    volumes:
      - .:/app

  manager:
    build:
      context: .
      dockerfile: services/manager/Dockerfile
    container_name: legion-manager
    ports:
      - "8006:8006"
    environment:
      LIBRARIAN_URL: http://librarian:8001
    depends_on:
      - librarian
    networks:
      - legion-network
    volumes:
      - .:/app
    stdin_open: true
    tty: true

  atomizer:
    build:
      context: .
      dockerfile: services/atomizer/Dockerfile
    container_name: legion-atomizer
    ports:
      - "8002:8002"
    environment:
      LIBRARIAN_URL: http://librarian:8001
    depends_on:
      - librarian
    networks:
      - legion-network
    volumes:
      - .:/app

  kanban:
    build:
      context: .
      dockerfile: services/kanban/Dockerfile
    container_name: legion-kanban
    ports:
      - "8003:8003"
    environment:
      LIBRARIAN_URL: http://librarian:8001
      WORKER_URL: http://worker:8004
    depends_on:
      - librarian
    networks:
      - legion-network
    volumes:
      - .:/app

  worker:
    build:
      context: .
      dockerfile: services/worker/Dockerfile
    container_name: legion-worker
    ports:
      - "8004:8004"
    environment:
      LIBRARIAN_URL: http://librarian:8001
      TESTER_URL: http://tester:8005
    depends_on:
      - kanban
    networks:
      - legion-network
    volumes:
      - .:/app
      - ./worktrees:/app/worktrees

  tester:
    build:
      context: .
      dockerfile: services/tester/Dockerfile
    container_name: legion-tester
    ports:
      - "8005:8005"
    environment:
      LIBRARIAN_URL: http://librarian:8001
    depends_on:
      - worker
    networks:
      - legion-network
    volumes:
      - .:/app
      - ./worktrees:/app/worktrees

volumes:
  neo4j_data:
  chroma_data:

networks:
  legion-network:
    driver: bridge
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: complete docker-compose with all Legion services"
```

---

### Task 2: Service Dockerfiles

**Files:**
- Create: `services/manager/Dockerfile`, `services/atomizer/Dockerfile`, `services/kanban/Dockerfile`, `services/worker/Dockerfile`, `services/tester/Dockerfile`

- [ ] **Step 1: Create Manager Dockerfile**

```dockerfile
# services/manager/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY services/manager/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8006

# Manager is CLI-based, but expose for API mode
CMD ["python", "-m", "services.manager.cli"]
```

- [ ] **Step 2: Create Atomizer Dockerfile**

```dockerfile
# services/atomizer/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY services/atomizer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8002

CMD ["python", "services/atomizer/main.py"]
```

- [ ] **Step 3: Create Kanban Dockerfile**

```dockerfile
# services/kanban/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY services/kanban/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8003

CMD ["python", "services/kanban/main.py"]
```

- [ ] **Step 4: Create Worker Dockerfile**

```dockerfile
# services/worker/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install git for worktree management
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY services/worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8004

CMD ["python", "services/worker/main.py"]
```

- [ ] **Step 5: Create Tester Dockerfile**

```dockerfile
# services/tester/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install git for merge operations
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY services/tester/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8005

CMD ["python", "services/tester/main.py"]
```

- [ ] **Step 6: Commit**

```bash
git add services/*/Dockerfile
git commit -m "feat: add Dockerfiles for all services"
```

---

### Task 3: Environment Configuration

**Files:**
- Create: `.env`, `.gitignore`

- [ ] **Step 1: Create .env file**

```bash
# .env - Environment variables for Legion

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# ChromaDB Configuration
CHROMA_DB_HOST=localhost
CHROMA_DB_PORT=8000

# Service URLs (for local development)
LIBRARIAN_URL=http://localhost:8001
ATOMIZER_URL=http://localhost:8002
KANBAN_URL=http://localhost:8003
WORKER_URL=http://localhost:8004
TESTER_URL=http://localhost:8005

# Qwen Code Configuration
QWEN_CODE_PATH=qwen-code
```

- [ ] **Step 2: Create .gitignore**

```gitignore
# .gitignore

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
.venv

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# Environment
.env
.env.local

# Worktrees (generated)
worktrees/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Commit**

```bash
git add .env .gitignore
git commit -m "chore: add environment configuration and gitignore"
```

---

### Task 4: Startup Script

**Files:**
- Create: `scripts/start-legion.sh`

- [ ] **Step 1: Create startup script**

```bash
#!/bin/bash
# scripts/start-legion.sh - Start all Legion services

set -e

echo "=========================================="
echo "  Project Legion - Starting Services"
echo "=========================================="

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "Error: docker-compose is not installed"
    exit 1
fi

# Start infrastructure and services
echo "Starting Neo4j and ChromaDB..."
docker-compose up -d neo4j chromadb

echo "Waiting for databases to be ready (30s)..."
sleep 30

echo "Starting Librarian service..."
docker-compose up -d librarian

echo "Waiting for Librarian to be ready (10s)..."
sleep 10

echo "Starting remaining services..."
docker-compose up -d atomizer kanban worker tester

echo ""
echo "=========================================="
echo "  Legion Services Started!"
echo "=========================================="
echo ""
echo "Service URLs:"
echo "  Librarian:  http://localhost:8001"
echo "  Atomizer:   http://localhost:8002"
echo "  Kanban:     http://localhost:8003"
echo "  Worker:     http://localhost:8004"
echo "  Tester:     http://localhost:8005"
echo ""
echo "Infrastructure:"
echo "  Neo4j:      http://localhost:7474 (browser)"
echo "  ChromaDB:   http://localhost:8000"
echo ""
echo "To view logs: docker-compose logs -f [service]"
echo "To stop:      docker-compose down"
echo ""
```

- [ ] **Step 2: Make script executable**

```bash
chmod +x scripts/start-legion.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/start-legion.sh
git commit -m "feat: add startup script for Legion services"
```

---

### Task 5: Project Documentation

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README**

```markdown
# Project Legion

Autonomous multi-agent coding framework powered by Qwen.

## Overview

Legion decomposes software projects into atomic tasks and executes them in parallel using rotated Qwen CLI profiles. The system uses LLM-driven intelligence for requirements extraction, task decomposition, code generation, and contract validation.

## Architecture

```
Manager → Librarian ← Atomizer
              ↓
           Kanban → Worker → Tester
```

- **Manager**: CLI interview tool for requirements extraction
- **Librarian**: Central knowledge store (Neo4j + ChromaDB)
- **Atomizer**: LLM-powered task decomposition
- **Kanban**: Dispatcher with profile rotation
- **Worker**: Isolated execution via git worktrees
- **Tester**: Contract validation and merge management

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- qwen-code CLI installed and configured with profiles

### Start Services

```bash
# Start all services
./scripts/start-legion.sh

# Or manually
docker-compose up -d
```

### Run a Project

1. **Interview** (create ProjectSpec):
   ```bash
   docker-compose run manager python -m services.manager.cli interview
   ```

2. **Decompose** (create tasks):
   ```bash
   curl -X POST http://localhost:8002/decompose \
     -H "Content-Type: application/json" \
     -d '{"project_spec_id": "<spec-id>"}'
   ```

3. **Monitor** (watch Kanban dispatch):
   ```bash
   docker-compose logs -f kanban
   ```

## Services

| Service    | Port | Description                          |
|------------|------|--------------------------------------|
| Librarian  | 8001 | Central API (Neo4j + ChromaDB)       |
| Atomizer   | 8002 | Task decomposition                   |
| Kanban     | 8003 | Dispatcher with profile rotation     |
| Worker     | 8004 | Task execution in worktrees          |
| Tester     | 8005 | Contract validation and merges       |
| Manager    | CLI  | User interview tool                  |

## Configuration

### Profiles

Edit `configs/profiles.json` to configure Qwen profiles. Default: 20 profiles with 1000 req/day limits.

### Environment

Copy `.env.example` to `.env` and adjust:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

## Development

### Run Tests

```bash
# All tests
pytest

# Specific service
pytest services/librarian/tests/
```

### Add a Profile

1. Add profile to `configs/profiles.json`
2. Ensure `qwen-code --profile <name>` works locally
3. Restart Kanban service

## Troubleshooting

### Profile Rate Limits

If all profiles hit rate limits:
- Wait for daily reset (midnight UTC)
- Add more profiles to `configs/profiles.json`

### Worktree Conflicts

Clean up stale worktrees:
```bash
git worktree prune
rm -rf worktrees/*
```

### Service Health

Check service health:
```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health
```

## License

MIT
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add comprehensive README"
```

---

### Task 6: End-to-End Integration Test

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Create end-to-end test**

```python
# tests/test_e2e.py
"""
End-to-end integration test for Project Legion.

This test requires all services to be running via docker-compose.
Run with: pytest tests/test_e2e.py -v --integration
"""
import pytest
import requests
import time

LIBRARIAN_URL = "http://localhost:8001"
ATOMIZER_URL = "http://localhost:8002"
KANBAN_URL = "http://localhost:8003"


@pytest.mark.integration
class TestLegionEndToEnd:
    
    def test_all_services_healthy(self):
        """Verify all services are running and healthy"""
        services = [
            ("Librarian", LIBRARIAN_URL),
            ("Atomizer", ATOMIZER_URL),
            ("Kanban", KANBAN_URL),
        ]
        
        for name, url in services:
            response = requests.get(f"{url}/health", timeout=5)
            assert response.status_code == 200, f"{name} is not healthy"
    
    def test_create_project_spec(self):
        """Test full flow: create spec → decompose → dispatch"""
        # 1. Create ProjectSpec
        spec_response = requests.post(
            f"{LIBRARIAN_URL}/project-specs",
            json={
                "name": "E2E Test Project",
                "tech_stack": ["FastAPI"],
                "features": ["Health endpoint"]
            }
        )
        assert spec_response.status_code == 201
        spec_id = spec_response.json()["id"]
        
        # 2. Decompose into tasks
        decompose_response = requests.post(
            f"{ATOMIZER_URL}/decompose",
            json={"project_spec_id": spec_id}
        )
        assert decompose_response.status_code == 200
        tasks = decompose_response.json()["tasks"]
        assert len(tasks) > 0
        
        # 3. Wait for Kanban to dispatch (polling)
        time.sleep(35)  # Wait for next poll cycle
        
        # 4. Check Kanban status
        status_response = requests.get(f"{KANBAN_URL}/status")
        assert status_response.status_code == 200
```

- [ ] **Step 2: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: add end-to-end integration test"
```

---

## Verification

After completing all tasks, run:

```bash
# Start all services
./scripts/start-legion.sh

# Check service health
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
curl http://localhost:8004/health
curl http://localhost:8005/health

# Run end-to-end test
pytest tests/test_e2e.py -v --integration

# View all logs
docker-compose logs -f
```

Expected: All services healthy, tests pass

---

## Implementation Complete

All 5 plans implemented:
1. ✅ Shared Models + Librarian
2. ✅ Manager + Atomizer
3. ✅ Kanban + Profiles
4. ✅ Worker + Tester
5. ✅ Docker Compose + Integration

To start Legion:
```bash
./scripts/start-legion.sh
```
