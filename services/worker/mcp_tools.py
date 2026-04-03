import requests
from typing import Optional


class CodeQueryTools:
    """HTTP client for the Librarian's code query API.
    These are the tools available to the Worker's LLM during code generation.
    Instead of reading files, the LLM queries the knowledge graph.
    """

    def __init__(self, librarian_url: str = "http://localhost:8001"):
        self.librarian_url = librarian_url

    def search_code(self, query: str, type: str = "function") -> list:
        """Search for functions/classes by semantic similarity."""
        response = requests.get(f"{self.librarian_url}/code/search",
            params={"q": query, "type": type})
        if response.status_code == 200:
            return response.json().get("results", [])
        return []

    def get_function(self, name: str) -> Optional[dict]:
        """Get function body and signature by name."""
        response = requests.get(f"{self.librarian_url}/code/function/{name}")
        if response.status_code == 200:
            return response.json()
        return None

    def get_callers(self, function_name: str) -> list:
        """Get all functions that call this function."""
        response = requests.get(f"{self.librarian_url}/code/function/{function_name}/callers")
        if response.status_code == 200:
            return response.json().get("callers", [])
        return []

    def get_callees(self, function_name: str) -> list:
        """Get all functions this function calls."""
        response = requests.get(f"{self.librarian_url}/code/function/{function_name}/callees")
        if response.status_code == 200:
            return response.json().get("callees", [])
        return []

    def get_full_context(self, function_name: str) -> dict:
        """Get everything needed to understand a function."""
        response = requests.get(f"{self.librarian_url}/code/function/{function_name}/full-context")
        if response.status_code == 200:
            return response.json()
        return {}

    def get_class(self, name: str) -> Optional[dict]:
        """Get class definition and all methods."""
        response = requests.get(f"{self.librarian_url}/code/class/{name}")
        if response.status_code == 200:
            return response.json()
        return None
