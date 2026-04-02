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
