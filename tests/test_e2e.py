"""
End-to-End Integration Tests for Sea Qwens.

These tests require all services running via docker-compose.
Run with: pytest tests/test_e2e.py -m integration --tb=short
"""
import os
import time
import uuid

import pytest
import requests

# ---------------------------------------------------------------------------
# Configuration – defaults match docker-compose.yml exposed ports
# ---------------------------------------------------------------------------
LIBRARIAN_URL = os.getenv("LIBRARIAN_URL", "http://localhost:8001")
ATOMIZER_URL = os.getenv("ATOMIZER_URL", "http://localhost:8002")
KANBAN_URL = os.getenv("KANBAN_URL", "http://localhost:8003")
WORKER_URL = os.getenv("WORKER_URL", "http://localhost:8004")
TESTER_URL = os.getenv("TESTER_URL", "http://localhost:8005")
MANAGER_URL = os.getenv("MANAGER_URL", "http://localhost:8006")

ALL_SERVICES = {
    "librarian": LIBRARIAN_URL,
    "atomizer": ATOMIZER_URL,
    "kanban": KANBAN_URL,
    "worker": WORKER_URL,
    "tester": TESTER_URL,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SERVICE_HEALTH_ENDPOINTS = {
    "librarian": f"{LIBRARIAN_URL}/docs",  # FastAPI auto-generated docs page
    "atomizer": f"{ATOMIZER_URL}/health",
    "kanban": f"{KANBAN_URL}/health",
    "worker": f"{WORKER_URL}/health",
    "tester": f"{TESTER_URL}/health",
}


def _wait_for_service(url: str, timeout: int = 30, interval: float = 1.0) -> bool:
    """Poll *url* until it returns 2xx or *timeout* seconds elapse."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = requests.get(url, timeout=5)
            if 200 <= resp.status_code < 300:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(interval)
    return False


def _all_services_healthy(timeout: int = 60) -> dict[str, bool]:
    """Return a mapping of service name → healthy (bool)."""
    results: dict[str, bool] = {}
    for name, url in SERVICE_HEALTH_ENDPOINTS.items():
        results[name] = _wait_for_service(url, timeout=timeout)
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.integration


class TestAllServicesHealthy:
    """Verify every service responds to its health-check endpoint."""

    def test_all_services_healthy(self):
        """All services must return 2xx within the timeout window."""
        health = _all_services_healthy(timeout=60)

        unhealthy = [name for name, ok in health.items() if not ok]
        assert not unhealthy, (
            f"The following services did not respond: {unhealthy}. "
            f"Start them with: docker-compose up -d"
        )


class TestCreateProjectSpec:
    """Full flow: create spec → decompose → check Kanban status."""

    @pytest.fixture(autouse=True)
    def ensure_services(self):
        """Skip the entire class if any service is unreachable."""
        health = _all_services_healthy(timeout=30)
        unhealthy = [n for n, ok in health.items() if not ok]
        if unhealthy:
            pytest.skip(f"Services not available: {unhealthy}")

    # -- Step 1: create a ProjectSpec via Librarian --------------------------
    def test_create_project_spec(self):
        """POST /project-specs → 201 with a valid spec id."""
        payload = {
            "name": f"e2e-test-{uuid.uuid4().hex[:8]}",
            "tech_stack": ["FastAPI", "React", "PostgreSQL"],
            "features": ["user auth", "dashboard", "reports"],
        }
        resp = requests.post(f"{LIBRARIAN_URL}/project-specs", json=payload, timeout=10)
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

        body = resp.json()
        assert "id" in body, "Response must include an 'id' field"
        self._spec_id = body["id"]

    # -- Step 2: decompose the spec via Atomizer -----------------------------
    def test_decompose_spec(self):
        """POST /decompose → 200 with a list of tasks."""
        resp = requests.post(
            f"{ATOMIZER_URL}/decompose",
            json={"spec_id": self._spec_id},
            timeout=15,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = resp.json()
        assert "tasks" in body
        assert "count" in body
        assert body["count"] >= 0, "Task count should be non-negative"

    # -- Step 3: trigger Kanban dispatch and check status --------------------
    def test_kanban_dispatch_and_status(self):
        """POST /dispatch/now → dispatched count; GET /status → scheduler info."""
        # Trigger immediate dispatch
        resp = requests.post(f"{KANBAN_URL}/dispatch/now", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = resp.json()
        assert "dispatched" in body, "Response must include 'dispatched' field"

        # Check scheduler status
        resp = requests.get(f"{KANBAN_URL}/status", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = resp.json()
        assert "scheduler_running" in body
        assert "polling_interval" in body
