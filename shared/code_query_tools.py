"""Shared code query tools for all services that need code database access."""

import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class CodeQueryTools:
    """HTTP client for the Librarian's code query API.

    Used by Worker, Manager, and Atomizer to query the code knowledge graph
    instead of reading files directly.
    """

    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url

    def search_code(self, query: str, entity_type: str = "function") -> list:
        """Search for functions/classes by semantic similarity."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/search",
                params={"q": query, "type": entity_type},
                timeout=10,
            )
            if response.status_code == 200:
                return response.json().get("results", [])
        except requests.RequestException as e:
            logger.warning(f"Code search failed: {e}")
        return []

    def get_function(self, name: str) -> Optional[dict]:
        """Get function body and signature by name."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/function/{name}", timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logger.warning(f"Get function failed: {e}")
        return None

    def get_callers(self, function_name: str) -> list:
        """Get all functions that call this function."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/function/{function_name}/callers",
                timeout=10,
            )
            if response.status_code == 200:
                return response.json().get("callers", [])
        except requests.RequestException as e:
            logger.warning(f"Get callers failed: {e}")
        return []

    def get_callees(self, function_name: str) -> list:
        """Get all functions this function calls."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/function/{function_name}/callees",
                timeout=10,
            )
            if response.status_code == 200:
                return response.json().get("callees", [])
        except requests.RequestException as e:
            logger.warning(f"Get callees failed: {e}")
        return []

    def get_full_context(self, function_name: str) -> dict:
        """Get everything needed to understand a function."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/function/{function_name}/full-context",
                timeout=10,
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logger.warning(f"Get full context failed: {e}")
        return {}

    def get_class(self, name: str) -> Optional[dict]:
        """Get class definition and all methods."""
        try:
            response = requests.get(
                f"{self.librarian_url}/code/class/{name}", timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except requests.RequestException as e:
            logger.warning(f"Get class failed: {e}")
        return None


class ProjectCodeContext:
    """Higher-level code context helpers for a specific project.

    Wraps CodeQueryTools with project-aware methods that help services
    understand what code already exists for a given project.
    """

    def __init__(self, tools: CodeQueryTools):
        self.tools = tools

    def get_project_overview(self, project_name: str) -> Optional[dict]:
        """Get a summary of the project's code structure.

        Returns None if the project has no code in the database.
        """
        all_functions = self.tools.search_code("", entity_type="function")
        all_classes = self.tools.search_code("", entity_type="class")

        if not all_functions and not all_classes:
            return None

        files = set()
        for func in all_functions:
            if func.get("file"):
                files.add(func["file"])
        for cls in all_classes:
            if cls.get("metadata", {}).get("file"):
                files.add(cls["metadata"]["file"])

        return {
            "project_name": project_name,
            "files": [{"path": f} for f in sorted(files)],
            "classes": [
                {
                    "name": c.get("name", ""),
                    "file": c.get("metadata", {}).get("file", ""),
                }
                for c in all_classes
            ],
            "functions": [
                {"name": f.get("name", ""), "file": f.get("file", "")}
                for f in all_functions
            ],
            "total_files": len(files),
            "total_functions": len(all_functions),
            "total_classes": len(all_classes),
        }

    def find_existing_features(self, project_name: str, features: list[str]) -> dict:
        """Check which features already have matching code.

        Returns a dict mapping each feature keyword to its matches.
        """
        result = {}
        for feature in features:
            matches = self.tools.search_code(feature, entity_type="function")
            class_matches = self.tools.search_code(feature, entity_type="class")
            all_matches = []
            for m in matches:
                all_matches.append(
                    {"name": m.get("name", "unknown"), "type": "function"}
                )
            for m in class_matches:
                all_matches.append(
                    {
                        "name": m.get(
                            "name", m.get("metadata", {}).get("name", "unknown")
                        ),
                        "type": "class",
                    }
                )
            result[feature] = {
                "found": len(all_matches) > 0,
                "matches": all_matches,
            }
        return result

    def get_dependency_map(self) -> dict:
        """Get the CALLS and INHERITS graph for known code.

        Returns a dict with 'calls' and 'inherits' lists.
        """
        all_functions = self.tools.search_code("", entity_type="function")
        calls = []
        for func in all_functions:
            name = func.get("name")
            if not name:
                continue
            callees = self.tools.get_callees(name)
            for callee in callees:
                calls.append({"caller": name, "callee": callee.get("name", "unknown")})

        all_classes = self.tools.search_code("", entity_type="class")
        inherits = []
        for cls in all_classes:
            name = cls.get("name")
            if not name:
                continue
            class_data = self.tools.get_class(name)
            if class_data and class_data.get("class"):
                bases = class_data["class"].get("bases", [])
                for base in bases:
                    inherits.append({"child": name, "parent": base})

        return {"calls": calls, "inherits": inherits}

    def search_by_category(self, category: str) -> list:
        """Search for code related to a common category.

        Categories: auth, database, api, testing, config, logging
        """
        category_keywords = {
            "auth": ["auth", "login", "token", "permission", "session"],
            "database": ["database", "db", "model", "query", "sql", "mongo"],
            "api": ["api", "endpoint", "route", "handler", "request", "response"],
            "testing": ["test", "mock", "fixture", "assert"],
            "config": ["config", "settings", "env", "setup"],
            "logging": ["log", "logger", "debug", "info", "warn"],
        }
        keywords = category_keywords.get(category, [category])
        results = []
        for keyword in keywords:
            results.extend(self.tools.search_code(keyword, entity_type="function"))
            results.extend(self.tools.search_code(keyword, entity_type="class"))
        # Deduplicate by name
        seen = set()
        unique = []
        for r in results:
            key = r.get("name", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(r)
        return unique
