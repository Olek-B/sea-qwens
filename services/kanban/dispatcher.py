from datetime import datetime, timezone
from typing import Optional
import requests
import logging

from services.kanban.profile_manager import ProfileManager

logger = logging.getLogger(__name__)


class DispatchResult:
    def __init__(self, success: bool, task_id: str, profile_name: str, message: str):
        self.success = success
        self.task_id = task_id
        self.profile_name = profile_name
        self.message = message
        self.timestamp = datetime.now(timezone.utc)


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

    def poll_and_dispatch(self) -> int:
        """Poll for ready tasks and dispatch them"""
        tasks = self.get_ready_tasks()
        dispatched = 0

        for task in tasks:
            result = self.dispatch_task(task)
            if result.success:
                dispatched += 1

        return dispatched

    def handle_rate_limit(self, task: dict, failed_profile: str):
        """Handle 429 rate limit by rotating profile and re-queuing"""
        logger.warning(
            f"Rate limit hit for profile {failed_profile}, "
            f"re-queuing task {task['task_id']}"
        )

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
