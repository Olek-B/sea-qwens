# services/kanban/tool_manager.py
from typing import Optional
import logging
import requests

logger = logging.getLogger(__name__)


class ToolSelectionResult:
    def __init__(self, tool: dict, reason: str):
        self.tool = tool
        self.reason = reason


class ToolManager:
    """Manage tool selection and rotation"""

    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url

    def get_all_tools(self) -> list[dict]:
        """Fetch all tools from Librarian"""
        try:
            response = requests.get(f"{self.librarian_url}/tools")
            if response.status_code == 200:
                return response.json()
            return []
        except requests.exceptions.RequestException:
            return []

    def _select_best_from_list(self, tools: list[dict]) -> Optional[dict]:
        """Select the best tool from a list"""
        healthy = [
            t
            for t in tools
            if t.get("health_status") == "HEALTHY"
            and t.get("requests_today", 0) < t.get("daily_limit", 1000)
        ]

        if not healthy:
            return None

        return min(healthy, key=lambda t: t.get("usage_count", 0))

    def select_tool(
        self, task_capabilities: Optional[list[str]] = None
    ) -> Optional[ToolSelectionResult]:
        """
        Select the best tool for a task.

        If task_capabilities is provided, prefer tools with matching capabilities.
        Otherwise, select least-used healthy tool.
        """
        tools = self.get_all_tools()

        if not tools:
            return None

        if task_capabilities:
            matching = [
                t
                for t in tools
                if any(cap in t.get("capabilities", []) for cap in task_capabilities)
            ]
            if matching:
                selected = self._select_best_from_list(matching)
                if selected:
                    return ToolSelectionResult(
                        tool=selected,
                        reason=f"Matched capabilities: {task_capabilities}",
                    )
            logger.warning(
                "No tools matched capabilities %s, falling back to any healthy tool",
                task_capabilities,
            )

        selected = self._select_best_from_list(tools)
        if selected:
            return ToolSelectionResult(tool=selected, reason="Least-used healthy tool")

        return None

    def mark_tool_rate_limited(self, tool_name: str):
        """Mark a tool as rate-limited in Neo4j via Librarian"""
        try:
            requests.put(
                f"{self.librarian_url}/tools/{tool_name}/status",
                json={"health_status": "RATE_LIMITED"},
            )
        except requests.exceptions.RequestException:
            pass

    def increment_tool_usage(self, tool_name: str) -> bool:
        """Increment tool usage counters"""
        try:
            response = requests.post(
                f"{self.librarian_url}/tools/{tool_name}/increment"
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
