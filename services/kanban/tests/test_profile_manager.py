import pytest
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens/worktrees/legion-implement')
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
