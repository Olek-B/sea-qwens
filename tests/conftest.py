"""
Root conftest.py for Sea Qwens.

Registers custom pytest markers used across the test suite.
"""
import pytest


def pytest_configure(config):
    """Register custom markers so pytest --strict-markers doesn't complain."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests that require all services running via docker-compose",
    )
