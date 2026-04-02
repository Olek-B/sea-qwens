# Project Legion Plan 3: Kanban Dispatcher + Profile Management

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Kanban dispatcher that polls for ready tasks, manages profile rotation, and dispatches tasks to workers. Includes profile configuration and rate limit handling.

**Architecture:** Kanban is a FastAPI service with a background polling loop. It queries the Librarian for ready tasks, selects the least-used healthy profile, and dispatches to the Worker service. Profile state is stored in Neo4j.

**Tech Stack:** Python 3.11+, FastAPI, APScheduler (background jobs), requests, Pydantic, pytest

---

## File Structure

```
/legion-root/
├── configs/
│   └── profiles.json         # Template for 20 agent profiles
├── services/
│   └── kanban/
│       ├── app.py            # FastAPI application
│       ├── dispatcher.py     # Polling and dispatch logic
│       ├── profile_manager.py # Profile selection and rotation
│       ├── requirements.txt
│       └── tests/
│           ├── test_dispatcher.py
│           └── test_profile_manager.py
```

---

### Task 1: Profile Configuration Template

**Files:**
- Create: `configs/profiles.json`

- [ ] **Step 1: Create profile template with 20 agents**

```json
{
  "profiles": [
    {
      "name": "qwen-agent-01",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "testing", "refactoring", "debugging"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-02",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "testing", "documentation"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-03",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "architecture", "review"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-04",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["testing", "qa", "debugging"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-05",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "frontend", "css"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-06",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "backend", "database"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-07",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "api-design", "documentation"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-08",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["refactoring", "optimization", "review"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-09",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "testing", "security"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-10",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "devops", "docker"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-11",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "testing"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-12",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "documentation"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-13",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "refactoring"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-14",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["testing", "debugging"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-15",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "architecture"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-16",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "testing"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-17",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "optimization"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-18",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "security"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-19",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "testing"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    },
    {
      "name": "qwen-agent-20",
      "usage_count": 0,
      "last_used": null,
      "daily_limit": 1000,
      "requests_today": 0,
      "reset_time": "2026-04-03T00:00:00Z",
      "capabilities": ["coding", "review", "documentation"],
      "health_status": "HEALTHY",
      "consecutive_failures": 0
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add configs/profiles.json
git commit -m "feat: add 20 agent profile templates with capabilities"
```

---

### Task 2: Profile Manager Service

**Files:**
- Create: `services/kanban/profile_manager.py`, `services/kanban/requirements.txt`
- Test: `services/kanban/tests/test_profile_manager.py`

- [ ] **Step 1: Write tests for profile manager**

```python
# services/kanban/tests/test_profile_manager.py
import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.kanban.profile_manager import ProfileManager, ProfileSelectionResult


def test_profile_manager_initializes():
    manager = ProfileManager(librarian_url="http://localhost:8001")
    assert manager.librarian_url == "http://localhost:8001"


def test_select_best_profile_mock():
    """Test profile selection with mocked data"""
    manager = ProfileManager()
    
    # Mock profiles
    profiles = [
        {"name": "agent-01", "usage_count": 100, "health_status": "HEALTHY", "requests_today": 50},
        {"name": "agent-02", "usage_count": 50, "health_status": "HEALTHY", "requests_today": 30},
        {"name": "agent-03", "usage_count": 75, "health_status": "RATE_LIMITED", "requests_today": 1000},
    ]
    
    result = manager._select_best_from_list(profiles)
    assert result is not None
    assert result["name"] == "agent-02"  # Least used healthy


def test_select_no_healthy_profiles():
    manager = ProfileManager()
    
    profiles = [
        {"name": "agent-01", "usage_count": 100, "health_status": "RATE_LIMITED", "requests_today": 1000},
        {"name": "agent-02", "usage_count": 50, "health_status": "ERROR", "requests_today": 0},
    ]
    
    result = manager._select_best_from_list(profiles)
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/kanban/tests/test_profile_manager.py -v
```
Expected: FAIL

- [ ] **Step 3: Create Kanban requirements**

```txt
# services/kanban/requirements.txt
fastapi==0.109.0
uvicorn==0.27.0
pydantic==2.5.3
requests==2.31.0
apscheduler==3.10.4
python-dotenv==1.0.0
pytest==8.0.0
```

- [ ] **Step 4: Implement Profile Manager**

```python
# services/kanban/profile_manager.py
from datetime import datetime
from typing import Optional
import requests


class ProfileSelectionResult:
    def __init__(self, profile: dict, reason: str):
        self.profile = profile
        self.reason = reason


class ProfileManager:
    """Manage profile selection and rotation"""
    
    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url
    
    def get_all_profiles(self) -> list[dict]:
        """Fetch all profiles from Librarian"""
        # Note: Would need GET /profiles endpoint in Librarian
        # For now, this is a placeholder
        try:
            response = requests.get(f"{self.librarian_url}/profiles")
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            return []
    
    def _select_best_from_list(self, profiles: list[dict]) -> Optional[dict]:
        """Select the best profile from a list"""
        # Filter to healthy profiles with remaining capacity
        healthy = [
            p for p in profiles
            if p.get("health_status") == "HEALTHY"
            and p.get("requests_today", 0) < p.get("daily_limit", 1000)
        ]
        
        if not healthy:
            return None
        
        # Select least used
        return min(healthy, key=lambda p: p.get("usage_count", 0))
    
    def select_profile(self, task_capabilities: Optional[list[str]] = None) -> Optional[ProfileSelectionResult]:
        """
        Select the best profile for a task.
        
        If task_capabilities is provided, prefer profiles with matching capabilities.
        Otherwise, select least-used healthy profile.
        """
        profiles = self.get_all_profiles()
        
        if not profiles:
            return None
        
        # If capabilities specified, try to match
        if task_capabilities:
            matching = [
                p for p in profiles
                if any(cap in p.get("capabilities", []) for cap in task_capabilities)
            ]
            if matching:
                selected = self._select_best_from_list(matching)
                if selected:
                    return ProfileSelectionResult(
                        profile=selected,
                        reason=f"Matched capabilities: {task_capabilities}"
                    )
        
        # Fall back to least-used
        selected = self._select_best_from_list(profiles)
        if selected:
            return ProfileSelectionResult(
                profile=selected,
                reason="Least-used healthy profile"
            )
        
        return None
    
    def mark_profile_rate_limited(self, profile_name: str):
        """Mark a profile as rate-limited in Neo4j"""
        # Would need PUT /profiles/{name}/status endpoint
        pass
    
    def increment_profile_usage(self, profile_name: str) -> bool:
        """Increment profile usage counters"""
        try:
            response = requests.post(
                f"{self.librarian_url}/profiles/{profile_name}/increment"
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/kanban/tests/test_profile_manager.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/kanban/profile_manager.py services/kanban/tests/test_profile_manager.py
git commit -m "feat: implement ProfileManager for rotation logic"
```

---

### Task 3: Dispatcher Service

**Files:**
- Create: `services/kanban/dispatcher.py`, `services/kanban/app.py`, `services/kanban/main.py`
- Test: `services/kanban/tests/test_dispatcher.py`

- [ ] **Step 1: Write tests for dispatcher**

```python
# services/kanban/tests/test_dispatcher.py
import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from services.kanban.dispatcher import Dispatcher, DispatchResult


def test_dispatcher_initializes():
    dispatcher = Dispatcher()
    assert dispatcher.librarian_url != ""
    assert dispatcher.worker_url != ""


def test_dispatch_result_success():
    result = DispatchResult(
        success=True,
        task_id="task-001",
        profile_name="qwen-agent-01",
        message="Dispatched successfully"
    )
    assert result.success
    assert result.task_id == "task-001"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/kanban/tests/test_dispatcher.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement Dispatcher**

```python
# services/kanban/dispatcher.py
from datetime import datetime
from typing import Optional
import requests

from services.kanban.profile_manager import ProfileManager


class DispatchResult:
    def __init__(self, success: bool, task_id: str, profile_name: str, message: str):
        self.success = success
        self.task_id = task_id
        self.profile_name = profile_name
        self.message = message
        self.timestamp = datetime.utcnow()


class Dispatcher:
    """Dispatch ready tasks to workers"""
    
    def __init__(
        self,
        librarian_url: str = "http://localhost:8001",
        worker_url: str = "http://localhost:8004"
    ):
        self.librarian_url = librarian_url
        self.worker_url = worker_url
        self.profile_manager = ProfileManager(librarian_url)
    
    def get_ready_tasks(self) -> list[dict]:
        """Fetch ready tasks from Librarian"""
        try:
            response = requests.get(f"{self.librarian_url}/tasks/ready")
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            return []
    
    def dispatch_task(self, task: dict) -> DispatchResult:
        """Dispatch a single task to a worker"""
        # Select profile
        selection = self.profile_manager.select_profile()
        if not selection:
            return DispatchResult(
                success=False,
                task_id=task.get("task_id", "unknown"),
                profile_name="",
                message="No healthy profiles available"
            )
        
        profile = selection.profile
        profile_name = profile["name"]
        
        # Mark task as IN_PROGRESS in Librarian
        try:
            requests.post(
                f"{self.librarian_url}/tasks/update",
                params={"task_id": task["task_id"]},
                json={"status": "IN_PROGRESS", "profile_id": profile_name}
            )
        except requests.exceptions.RequestException:
            pass  # Best effort
        
        # Increment profile usage
        self.profile_manager.increment_profile_usage(profile_name)
        
        # Dispatch to Worker
        try:
            response = requests.post(
                f"{self.worker_url}/execute",
                json={
                    "task": task,
                    "profile": profile
                }
            )
            if response.status_code == 202:
                return DispatchResult(
                    success=True,
                    task_id=task["task_id"],
                    profile_name=profile_name,
                    message=f"Dispatched to worker with profile {profile_name}"
                )
            else:
                return DispatchResult(
                    success=False,
                    task_id=task["task_id"],
                    profile_name=profile_name,
                    message=f"Worker rejected: {response.text}"
                )
        except requests.exceptions.RequestException as e:
            return DispatchResult(
                success=False,
                task_id=task["task_id"],
                profile_name=profile_name,
                message=f"Worker unavailable: {str(e)}"
            )
    
    def poll_and_dispatch(self) -> int:
        """Poll for ready tasks and dispatch them"""
        tasks = self.get_ready_tasks()
        dispatched = 0
        
        for task in tasks:
            result = self.dispatch_task(task)
            if result.success:
                dispatched += 1
        
        return dispatched
```

- [ ] **Step 4: Implement FastAPI app with background scheduler**

```python
# services/kanban/app.py
from fastapi import FastAPI, BackgroundTasks
from apscheduler.schedulers.background import BackgroundScheduler
from services.kanban.dispatcher import Dispatcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Legion Kanban")

dispatcher = Dispatcher()
scheduler = BackgroundScheduler()


def poll_and_dispatch_job():
    """Background job: poll Librarian and dispatch tasks"""
    try:
        dispatched = dispatcher.poll_and_dispatch()
        if dispatched > 0:
            logger.info(f"Dispatched {dispatched} tasks")
    except Exception as e:
        logger.error(f"Dispatch error: {e}")


@app.on_event("startup")
async def start_scheduler():
    """Start background polling on startup"""
    scheduler.add_job(
        poll_and_dispatch_job,
        trigger="interval",
        seconds=30,  # Poll every 30 seconds
        id="poll_and_dispatch",
        replace_existing=True
    )
    scheduler.start()
    logger.info("Kanban dispatcher started (30s polling)")


@app.on_event("shutdown")
async def stop_scheduler():
    """Stop scheduler on shutdown"""
    scheduler.shutdown()


@app.get("/health")
def health_check():
    return {"status": "healthy", "scheduler_running": scheduler.running}


@app.post("/dispatch/now")
def dispatch_now():
    """Trigger immediate dispatch (for testing)"""
    dispatched = dispatcher.poll_and_dispatch()
    return {"dispatched": dispatched}


@app.get("/status")
def get_status():
    """Get dispatcher status"""
    return {
        "scheduler_running": scheduler.running,
        "polling_interval": "30s"
    }
```

- [ ] **Step 5: Create main entry point**

```python
# services/kanban/main.py
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8003, reload=True)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/kanban/tests/test_dispatcher.py -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add services/kanban/
git commit -m "feat: implement Kanban dispatcher with background polling"
```

---

### Task 4: Rate Limit Handling

**Files:**
- Modify: `services/kanban/dispatcher.py`, `services/kanban/app.py`

- [ ] **Step 1: Add rate limit recovery to dispatcher**

```python
# services/kanban/dispatcher.py - ADD this method

    def handle_rate_limit(self, task: dict, failed_profile: str):
        """Handle 429 rate limit by rotating profile and re-queuing"""
        logger.warning(f"Rate limit hit for profile {failed_profile}, re-queuing task {task['task_id']}")
        
        # Mark profile as rate-limited
        self.profile_manager.mark_profile_rate_limited(failed_profile)
        
        # Reset task to PENDING
        try:
            requests.post(
                f"{self.librarian_url}/tasks/update",
                params={"task_id": task["task_id"]},
                json={"status": "PENDING"}
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to re-queue task: {e}")
```

- [ ] **Step 2: Update dispatch_task to handle 429**

```python
# services/kanban/dispatcher.py - Modify the dispatch_task method

    def dispatch_task(self, task: dict) -> DispatchResult:
        """Dispatch a single task to a worker"""
        # Select profile
        selection = self.profile_manager.select_profile()
        if not selection:
            return DispatchResult(
                success=False,
                task_id=task.get("task_id", "unknown"),
                profile_name="",
                message="No healthy profiles available"
            )
        
        profile = selection.profile
        profile_name = profile["name"]
        
        # Mark task as IN_PROGRESS in Librarian
        try:
            requests.post(
                f"{self.librarian_url}/tasks/update",
                params={"task_id": task["task_id"]},
                json={"status": "IN_PROGRESS", "profile_id": profile_name}
            )
        except requests.exceptions.RequestException:
            pass
        
        # Increment profile usage
        self.profile_manager.increment_profile_usage(profile_name)
        
        # Dispatch to Worker
        try:
            response = requests.post(
                f"{self.worker_url}/execute",
                json={
                    "task": task,
                    "profile": profile
                }
            )
            
            # Handle 429 rate limit
            if response.status_code == 429:
                self.handle_rate_limit(task, profile_name)
                return DispatchResult(
                    success=False,
                    task_id=task["task_id"],
                    profile_name=profile_name,
                    message="Rate limit hit, profile rotated and task re-queued"
                )
            
            if response.status_code == 202:
                return DispatchResult(
                    success=True,
                    task_id=task["task_id"],
                    profile_name=profile_name,
                    message=f"Dispatched to worker with profile {profile_name}"
                )
            else:
                return DispatchResult(
                    success=False,
                    task_id=task["task_id"],
                    profile_name=profile_name,
                    message=f"Worker rejected: {response.text}"
                )
        except requests.exceptions.RequestException as e:
            return DispatchResult(
                success=False,
                task_id=task["task_id"],
                profile_name=profile_name,
                message=f"Worker unavailable: {str(e)}"
            )
```

- [ ] **Step 3: Commit**

```bash
git add services/kanban/dispatcher.py
git commit -m "feat: add rate limit handling with profile rotation"
```

---

## Verification

After completing all tasks, run:

```bash
# Start Kanban service
cd /home/loki/ideas/sea-qwens
python -m services.kanban.main

# Test dispatch endpoint
curl http://localhost:8003/health
curl -X POST http://localhost:8003/dispatch/now

# Run tests
pytest services/kanban/ -v
```

Expected: All tests pass, dispatcher polls every 30s
