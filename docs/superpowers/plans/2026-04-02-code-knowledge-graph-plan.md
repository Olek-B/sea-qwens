# Code Knowledge Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Librarian into a code knowledge graph that stores the codebase (not just tasks) and provides HTTP + MCP query APIs for agents to retrieve code context instead of reading files.

**Architecture:** A shared tree-sitter-based indexer parses source files into AST nodes (Project→Module→File→Class→Function). Neo4j stores the graph with CALLS/IMPORTS/INHERITS relationships. ChromaDB stores vector embeddings for semantic search. HTTP endpoints serve programmatic access; MCP tools serve the Worker's LLM.

**Tech Stack:** Python 3.11+, tree-sitter, tree-sitter-python, Neo4j, ChromaDB, FastAPI, Pydantic, pytest

---

## File Structure

```
/legion-root/
├── shared/
│   ├── models.py              # ADD: CodeNode, FunctionNode, ClassNode
│   ├── indexer.py             # NEW: tree-sitter AST parser
│   └── test_indexer.py        # NEW: indexer tests
├── services/
│   └── librarian/
│       ├── neo4j_store.py     # EXTEND: code graph CRUD
│       ├── chroma_store.py    # EXTEND: code document methods
│       ├── app.py             # EXTEND: code query endpoints
│       ├── preimport.py       # NEW: bulk import CLI
│       ├── post_indexer.py    # NEW: incremental indexer
│       ├── requirements.txt   # ADD: tree-sitter deps
│       └── tests/
│           ├── test_code_api.py       # NEW: HTTP endpoint tests
│           └── test_preimport.py      # NEW: preimport tests
│   └── worker/
│       ├── executor.py        # MODIFY: prompt for MCP tools
│       └── mcp_tools.py       # NEW: MCP tool definitions
│   └── tester/
│       └── app.py             # MODIFY: call /index/updated after merge
```

---

### Task 1: Shared Code Models

**Files:**
- Modify: `shared/models.py`
- Test: `shared/test_models.py` (add tests)

- [ ] **Step 1: Write failing tests for code models**

```python
# shared/test_models.py - ADD these tests

from shared.models import CodeFile, CodeClass, CodeFunction

def test_code_file_creation():
    f = CodeFile(
        path="services/librarian/app.py",
        language="python",
        content="from fastapi import FastAPI\n..."
    )
    assert f.path == "services/librarian/app.py"
    assert f.language == "python"

def test_code_function_creation():
    func = CodeFunction(
        name="health_check",
        file_path="services/librarian/app.py",
        line_start=10,
        line_end=15,
        body="def health_check():\n    return {'status': 'ok'}",
        signature="def health_check() -> dict",
        docstring="Health check endpoint",
        is_method=False,
        parent_class=None
    )
    assert func.name == "health_check"
    assert not func.is_method

def test_code_class_creation():
    cls = CodeClass(
        name="Neo4jStore",
        file_path="services/librarian/neo4j_store.py",
        line_start=5,
        line_end=50,
        body="class Neo4jStore:\n    ...",
        docstring="Neo4j operations",
        bases=["object"]
    )
    assert cls.name == "Neo4jStore"
    assert "object" in cls.bases
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/loki/ideas/sea-qwens
pytest shared/test_models.py -v
```
Expected: FAIL with "ImportError: cannot import name 'CodeFile'"

- [ ] **Step 3: Add code models to shared/models.py**

```python
# shared/models.py - ADD these classes at the end

class CodeFile(BaseModel):
    path: str
    language: str
    content: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class CodeFunction(BaseModel):
    name: str
    file_path: str
    line_start: int
    line_end: int
    body: str
    signature: str = ""
    docstring: str = ""
    is_method: bool = False
    parent_class: Optional[str] = None


class CodeClass(BaseModel):
    name: str
    file_path: str
    line_start: int
    line_end: int
    body: str
    docstring: str = ""
    bases: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Update shared/__init__.py**

```python
# shared/__init__.py - REPLACE with this

from shared.models import (
    ProjectSpec, Task, TaskStatus, Profile, ProfileHealth,
    CodeFile, CodeClass, CodeFunction
)

__all__ = [
    "ProjectSpec", "Task", "TaskStatus", "Profile", "ProfileHealth",
    "CodeFile", "CodeClass", "CodeFunction"
]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/loki/ideas/sea-qwens
pytest shared/test_models.py -v
```
Expected: PASS (5 tests total: 2 original + 3 new)

- [ ] **Step 6: Commit**

```bash
git add shared/models.py shared/__init__.py shared/test_models.py
git commit -m "feat: add CodeFile, CodeFunction, CodeClass models"
```

---

### Task 2: Shared Code Indexer (tree-sitter)

**Files:**
- Create: `shared/indexer.py`
- Test: `shared/test_indexer.py`

- [ ] **Step 1: Write failing tests for indexer**

```python
# shared/test_indexer.py

import pytest
from shared.indexer import CodeIndexer, IndexResult


@pytest.fixture
def sample_python_file():
    return '''
"""Sample module for testing."""

class AuthService:
    """Handles authentication."""
    
    def __init__(self, db):
        self.db = db
    
    def login(self, username, password):
        """Authenticate a user."""
        user = self.db.find_user(username)
        if user and verify_password(password, user.hash):
            return create_token(user.id)
        return None

def verify_password(password, hash):
    """Verify password against hash."""
    return password == hash  # simplified

def create_token(user_id):
    """Create auth token."""
    return f"token-{user_id}"

def get_user(db, user_id):
    """Fetch user from database."""
    return db.find_by_id(user_id)
'''


def test_indexer_extracts_functions(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    
    func_names = [f.name for f in result.functions]
    assert "login" in func_names
    assert "verify_password" in func_names
    assert "create_token" in func_names
    assert "get_user" in func_names


def test_indexer_extracts_class(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    
    assert len(result.classes) == 1
    assert result.classes[0].name == "AuthService"
    assert result.classes[0].docstring == "Handles authentication."


def test_indexer_extracts_methods(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    
    methods = [f for f in result.functions if f.is_method]
    method_names = [m.name for m in methods]
    assert "login" in method_names
    assert "__init__" in method_names


def test_indexer_detects_calls(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    
    # login calls verify_password, create_token, db.find_user
    login_calls = [c.callee for c in result.calls if c.caller == "login"]
    assert "verify_password" in login_calls
    assert "create_token" in login_calls


def test_index_result_has_file_info(sample_python_file):
    indexer = CodeIndexer()
    result = indexer.index_file("auth.py", sample_python_file, "python")
    
    assert result.file.path == "auth.py"
    assert result.file.language == "python"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/loki/ideas/sea-qwens
pytest shared/test_indexer.py -v
```
Expected: FAIL with "ModuleNotFoundError: No module named 'shared.indexer'"

- [ ] **Step 3: Add tree-sitter to requirements**

Create a shared requirements file for indexer dependencies:

```txt
# shared/requirements.txt
tree-sitter>=0.21.0
tree-sitter-python>=0.21.0
pydantic>=2.5.0
```

Install:
```bash
pip install tree-sitter tree-sitter-python
```

- [ ] **Step 4: Implement CodeIndexer**

```python
# shared/indexer.py

import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Node
from shared.models import CodeFile, CodeFunction, CodeClass
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CallRelation:
    caller: str
    callee: str


@dataclass
class IndexResult:
    file: CodeFile
    classes: list[CodeClass] = field(default_factory=list)
    functions: list[CodeFunction] = field(default_factory=list)
    calls: list[CallRelation] = field(default_factory=list)


class CodeIndexer:
    """Parse source files using tree-sitter and extract code structure."""
    
    def __init__(self):
        self.PY_LANGUAGE = Language(tspython.language())
        self.parser = Parser(self.PY_LANGUAGE)
    
    def index_file(self, path: str, content: str, language: str) -> IndexResult:
        """Index a single source file."""
        code_file = CodeFile(path=path, language=language, content=content)
        
        if language == "python":
            return self._index_python(code_file)
        
        # For other languages, create minimal result
        return IndexResult(file=code_file)
    
    def _index_python(self, code_file: CodeFile) -> IndexResult:
        """Parse Python file and extract classes, functions, calls."""
        tree = self.parser.parse(bytes(code_file.content, "utf8"))
        root = tree.root_node
        
        classes = []
        functions = []
        calls = []
        
        self._extract_definitions(root, code_file.path, classes, functions)
        self._extract_calls(root, functions, calls)
        
        return IndexResult(
            file=code_file,
            classes=classes,
            functions=functions,
            calls=calls
        )
    
    def _extract_definitions(
        self,
        node: Node,
        file_path: str,
        classes: list[CodeClass],
        functions: list[CodeFunction],
        parent_class: Optional[str] = None
    ):
        """Recursively extract class and function definitions."""
        if node.type == "class_definition":
            cls = self._extract_class(node, file_path)
            classes.append(cls)
            # Extract methods from class body
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "function_definition":
                        self._extract_function(child, file_path, parent_class=cls.name)
        
        elif node.type == "function_definition":
            func = self._extract_function(node, file_path, parent_class)
            functions.append(func)
        
        # Recurse into children
        for child in node.children:
            self._extract_definitions(child, file_path, classes, functions, parent_class)
    
    def _extract_class(self, node: Node, file_path: str) -> CodeClass:
        """Extract a class definition."""
        name_node = node.child_by_field_name("name")
        name = name_node.text.decode("utf8") if name_node else "unknown"
        
        # Get bases
        bases_node = node.child_by_field_name("superclasses")
        bases = []
        if bases_node:
            bases = [c.text.decode("utf8") for c in bases_node.children if c.type == "identifier"]
        
        body_node = node.child_by_field_name("body")
        body_text = body_node.text.decode("utf8") if body_node else ""
        
        # Extract docstring from first string in body
        docstring = self._extract_docstring(body_node)
        
        return CodeClass(
            name=name,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            body=body_text,
            docstring=docstring,
            bases=bases
        )
    
    def _extract_function(
        self,
        node: Node,
        file_path: str,
        parent_class: Optional[str] = None
    ) -> CodeFunction:
        """Extract a function/method definition."""
        name_node = node.child_by_field_name("name")
        name = name_node.text.decode("utf8") if name_node else "unknown"
        
        body_node = node.child_by_field_name("body")
        body_text = body_node.text.decode("utf8") if body_node else ""
        
        # Build signature from the def line
        signature = f"def {name}(...)"  # simplified
        # Get the actual first line of the function
        first_line = node.start_point[0]
        lines = body_text.split("\n")
        if lines:
            signature = lines[0].strip()
        
        docstring = self._extract_docstring(body_node)
        
        return CodeFunction(
            name=name,
            file_path=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            body=body_text,
            signature=signature,
            docstring=docstring,
            is_method=parent_class is not None,
            parent_class=parent_class
        )
    
    def _extract_docstring(self, body_node: Optional[Node]) -> str:
        """Extract docstring from a function/class body."""
        if not body_node:
            return ""
        
        # First child should be expression_statement with string
        for child in body_node.children:
            if child.type == "expression_statement":
                string_node = child.children[0] if child.children else None
                if string_node and string_node.type == "string":
                    text = string_node.text.decode("utf8")
                    # Strip quotes
                    return text.strip('"""').strip("'''").strip()
        
        return ""
    
    def _extract_calls(
        self,
        node: Node,
        functions: list[CodeFunction],
        calls: list[CallRelation]
    ):
        """Extract function call relationships."""
        if node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node:
                callee = func_node.text.decode("utf8")
                # Get just the function name (not module.func)
                func_name = callee.split(".")[-1]
                
                # Find which function this call is in
                caller = self._find_enclosing_function(node, functions)
                if caller:
                    calls.append(CallRelation(caller=caller, callee=func_name))
        
        for child in node.children:
            self._extract_calls(child, functions, calls)
    
    def _find_enclosing_function(
        self,
        node: Node,
        functions: list[CodeFunction]
    ) -> Optional[str]:
        """Find which function contains this node."""
        for func in functions:
            # Convert line numbers back to byte offsets for comparison
            if (node.start_point[0] + 1) >= func.line_start and \
               (node.end_point[0] + 1) <= func.line_end:
                return func.name
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/loki/ideas/sea-qwens
pytest shared/test_indexer.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add shared/indexer.py shared/test_indexer.py shared/requirements.txt
git commit -m "feat: add tree-sitter based CodeIndexer"
```

---

### Task 3: Extend Neo4j Store for Code Graph

**Files:**
- Modify: `services/librarian/neo4j_store.py`

- [ ] **Step 1: Write failing tests for code graph operations**

```python
# services/librarian/tests/test_code_graph.py

import pytest
from unittest.mock import MagicMock, patch
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')
from shared.models import CodeFile, CodeFunction, CodeClass
from shared.indexer import IndexResult, CallRelation


class TestCodeGraphOperations:
    """Test Neo4j code graph CRUD operations."""
    
    @pytest.fixture
    def mock_session(self):
        session = MagicMock()
        session.run.return_value = MagicMock()
        return session
    
    @pytest.fixture
    def mock_driver(self, mock_session):
        driver = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)
        return driver
    
    @pytest.fixture
    def store(self, mock_driver):
        with patch('services.librarian.neo4j_store.GraphDatabase') as mock_gd:
            mock_gd.driver.return_value = mock_driver
            from services.librarian.neo4j_store import Neo4jStore
            store = Neo4jStore()
            store.driver = mock_driver
            return store
    
    def test_upsert_file(self, store, mock_session):
        code_file = CodeFile(path="test.py", language="python", content="x = 1")
        store.upsert_file(code_file)
        mock_session.run.assert_called()
    
    def test_upsert_function(self, store, mock_session):
        func = CodeFunction(
            name="test_func",
            file_path="test.py",
            line_start=1,
            line_end=5,
            body="def test_func(): pass"
        )
        store.upsert_function(func)
        mock_session.run.assert_called()
    
    def test_upsert_class(self, store, mock_session):
        cls = CodeClass(
            name="TestClass",
            file_path="test.py",
            line_start=1,
            line_end=10,
            body="class TestClass: pass"
        )
        store.upsert_class(cls)
        mock_session.run.assert_called()
    
    def test_create_call_relationship(self, store, mock_session):
        store.create_call_relationship("func_a", "func_b")
        mock_session.run.assert_called()
    
    def test_get_function_by_name(self, store, mock_session):
        mock_session.run.return_value.single.return_value = {
            "f": {
                "name": "test_func",
                "body": "def test_func(): pass",
                "file_path": "test.py",
                "signature": "def test_func(): pass",
                "docstring": "",
                "is_method": False
            }
        }
        result = store.get_function_by_name("test_func")
        assert result is not None
        assert result["name"] == "test_func"
    
    def test_get_callers(self, store, mock_session):
        mock_session.run.return_value = [
            {"caller": {"name": "func_a"}},
            {"caller": {"name": "func_b"}}
        ]
        result = store.get_callers("target_func")
        assert len(result) == 2
    
    def test_get_callees(self, store, mock_session):
        mock_session.run.return_value = [
            {"callee": {"name": "helper_func"}}
        ]
        result = store.get_callees("main_func")
        assert len(result) == 1
        assert result[0]["name"] == "helper_func"
    
    def test_search_functions_semantic(self, store, mock_session):
        mock_session.run.return_value = [
            {"f": {"name": "login", "body": "def login(): ..."}}
        ]
        result = store.search_functions("authentication")
        assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_code_graph.py -v
```
Expected: FAIL (methods not implemented)

- [ ] **Step 3: Add code graph methods to neo4j_store.py**

```python
# services/librarian/neo4j_store.py - ADD these methods

from shared.models import CodeFile, CodeFunction, CodeClass
from shared.indexer import IndexResult, CallRelation

    def upsert_file(self, code_file: CodeFile):
        """Upsert a File node."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (f:File {path: $path})
                SET f.language = $language,
                    f.content = $content,
                    f.last_updated = datetime()
                """,
                path=code_file.path,
                language=code_file.language,
                content=code_file.content
            )
    
    def upsert_function(self, func: CodeFunction):
        """Upsert a Function node and link to its File."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (f:File {path: $file_path})
                MERGE (fn:Function {name: $name, file_path: $file_path})
                SET fn.body = $body,
                    fn.signature = $signature,
                    fn.docstring = $docstring,
                    fn.is_method = $is_method,
                    fn.parent_class = $parent_class,
                    fn.line_start = $line_start,
                    fn.line_end = $line_end
                MERGE (f)-[:CONTAINS]->(fn)
                """,
                name=func.name,
                file_path=func.file_path,
                body=func.body,
                signature=func.signature,
                docstring=func.docstring,
                is_method=func.is_method,
                parent_class=func.parent_class,
                line_start=func.line_start,
                line_end=func.line_end
            )
    
    def upsert_class(self, cls: CodeClass):
        """Upsert a Class node and link to its File."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (f:File {path: $file_path})
                MERGE (c:Class {name: $name, file_path: $file_path})
                SET c.body = $body,
                    c.docstring = $docstring,
                    c.bases = $bases,
                    c.line_start = $line_start,
                    c.line_end = $line_end
                MERGE (f)-[:CONTAINS]->(c)
                """,
                name=cls.name,
                file_path=cls.file_path,
                body=cls.body,
                docstring=cls.docstring,
                bases=cls.bases,
                line_start=cls.line_start,
                line_end=cls.line_end
            )
    
    def create_call_relationship(self, caller_name: str, callee_name: str):
        """Create a CALLS relationship between functions."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (caller:Function {name: $caller})
                MATCH (callee:Function {name: $callee})
                MERGE (caller)-[:CALLS]->(callee)
                """,
                caller=caller_name,
                callee=callee_name
            )
    
    def create_inherits_relationship(self, child_name: str, parent_name: str):
        """Create an INHERITS relationship between classes."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (child:Class {name: $child})
                MATCH (parent:Class {name: $parent})
                MERGE (child)-[:INHERITS]->(parent)
                """,
                child=child_name,
                parent=parent_name
            )
    
    def get_function_by_name(self, name: str) -> Optional[dict]:
        """Get a function by name."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (f:Function {name: $name}) RETURN f",
                name=name
            )
            record = result.single()
            if record:
                return dict(record["f"])
            return None
    
    def get_callers(self, function_name: str) -> list[dict]:
        """Get all functions that call this function."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (caller:Function)-[:CALLS]->(target:Function {name: $name})
                RETURN caller
                """,
                name=function_name
            )
            return [dict(r["caller"]) for r in result]
    
    def get_callees(self, function_name: str) -> list[dict]:
        """Get all functions this function calls."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (source:Function {name: $name})-[:CALLS]->(callee:Function)
                RETURN callee
                """,
                name=function_name
            )
            return [dict(r["callee"]) for r in result]
    
    def get_full_context(self, function_name: str, depth: int = 2) -> dict:
        """Get function + callers + callees recursively."""
        func = self.get_function_by_name(function_name)
        if not func:
            return {}
        
        callers = self.get_callers(function_name)
        callees = self.get_callees(function_name)
        
        # Recursively get callee contexts
        full_callees = []
        if depth > 0:
            for callee in callees:
                sub_context = self.get_full_context(callee["name"], depth - 1)
                full_callees.append(sub_context)
        
        return {
            "function": func,
            "callers": callers,
            "callees": callees,
            "nested_callees": full_callees
        }
    
    def search_functions(self, query: str) -> list[dict]:
        """Search functions by name (full-text). For semantic search, use ChromaDB."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (f:Function)
                WHERE f.name CONTAINS $query OR f.docstring CONTAINS $query
                RETURN f
                LIMIT 20
                """,
                query=query
            )
            return [dict(r["f"]) for r in result]
    
    def delete_file(self, path: str):
        """Delete a file and all its contained nodes."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (f:File {path: $path})
                DETACH DELETE f
                """,
                path=path
            )
    
    def upsert_index_result(self, result: IndexResult):
        """Upsert all nodes and relationships from an IndexResult."""
        self.upsert_file(result.file)
        
        for cls in result.classes:
            self.upsert_class(cls)
            # Create INHERITS relationships
            for base in cls.bases:
                self.create_inherits_relationship(cls.name, base)
        
        for func in result.functions:
            self.upsert_function(func)
        
        for call in result.calls:
            self.create_call_relationship(call.caller, call.callee)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_code_graph.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add services/librarian/neo4j_store.py services/librarian/tests/test_code_graph.py
git commit -m "feat: add code graph CRUD operations to Neo4jStore"
```

---

### Task 4: Extend ChromaDB for Code Vectors

**Files:**
- Modify: `services/librarian/chroma_store.py`

- [ ] **Step 1: Write failing tests for code vector methods**

```python
# services/librarian/tests/test_chroma_code.py

import pytest
from unittest.mock import MagicMock, patch


class TestChromaCodeOperations:
    
    @pytest.fixture
    def chroma_store(self):
        with patch('services.librarian.chroma_store.chromadb') as mock_chroma:
            mock_client = MagicMock()
            mock_collection = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chroma.HttpClient.return_value = mock_client
            
            from services.librarian.chroma_store import ChromaStore
            store = ChromaStore()
            store.client = mock_client
            store.collection = mock_collection
            return store
    
    def test_add_function_embedding(self, chroma_store):
        chroma_store.add_function_embedding(
            uid="test_func",
            body="def test_func(): pass",
            metadata={"name": "test_func", "file": "test.py"}
        )
        chroma_store.collection.add.assert_called()
    
    def test_add_class_embedding(self, chroma_store):
        chroma_store.add_class_embedding(
            uid="TestClass",
            body="class TestClass: pass",
            metadata={"name": "TestClass", "file": "test.py"}
        )
        chroma_store.collection.add.assert_called()
    
    def test_search_code(self, chroma_store):
        chroma_store.collection.query.return_value = {
            "ids": [["func1"]],
            "documents": [["def func1(): pass"]],
            "metadatas": [[{"name": "func1"}]],
            "distances": [[0.1]]
        }
        results = chroma_store.search_code("authentication")
        assert len(results) == 1
        assert results[0]["name"] == "func1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_chroma_code.py -v
```
Expected: FAIL

- [ ] **Step 3: Add code embedding methods to chroma_store.py**

```python
# services/librarian/chroma_store.py - ADD these methods

    def add_function_embedding(self, uid: str, body: str, metadata: dict):
        """Add a function's body as a vector embedding."""
        self.collection.add(
            documents=[body],
            ids=[uid],
            metadatas=[{**metadata, "type": "function"}]
        )
    
    def add_class_embedding(self, uid: str, body: str, metadata: dict):
        """Add a class's body as a vector embedding."""
        self.collection.add(
            documents=[body],
            ids=[uid],
            metadatas=[{**metadata, "type": "class"}]
        )
    
    def search_code(self, query: str, n_results: int = 10) -> list[dict]:
        """Semantic search across all code."""
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        items = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                items.append({
                    "id": doc_id,
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else None
                })
        
        return items
    
    def delete_by_id(self, uid: str):
        """Delete a document by ID."""
        self.collection.delete(ids=[uid])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_chroma_code.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add services/librarian/chroma_store.py services/librarian/tests/test_chroma_code.py
git commit -m "feat: add code embedding methods to ChromaStore"
```

---

### Task 5: Code Query HTTP Endpoints

**Files:**
- Modify: `services/librarian/app.py`
- Test: `services/librarian/tests/test_code_api.py`

- [ ] **Step 1: Write failing tests for code endpoints**

```python
# services/librarian/tests/test_code_api.py

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')


class TestCodeQueryEndpoints:
    
    @pytest.fixture
    def client(self):
        with patch('services.librarian.neo4j_store.Neo4jStore') as mock_neo4j, \
             patch('services.librarian.chroma_store.ChromaStore') as mock_chroma:
            
            mock_neo4j.return_value = MagicMock()
            mock_chroma.return_value = MagicMock()
            
            from services.librarian.app import app
            return TestClient(app)
    
    def test_search_code_endpoint(self, client):
        response = client.get("/code/search?q=login&type=function")
        assert response.status_code == 200
        assert "results" in response.json()
    
    def test_get_function_by_name(self, client):
        response = client.get("/code/function/login")
        assert response.status_code in [200, 404]
    
    def test_get_function_callers(self, client):
        response = client.get("/code/function/login/callers")
        assert response.status_code == 200
    
    def test_get_function_callees(self, client):
        response = client.get("/code/function/login/callees")
        assert response.status_code == 200
    
    def test_get_full_context(self, client):
        response = client.get("/code/function/login/full-context")
        assert response.status_code in [200, 404]
    
    def test_get_class_by_name(self, client):
        response = client.get("/code/class/AuthService")
        assert response.status_code in [200, 404]
    
    def test_get_file_content(self, client):
        response = client.get("/code/file/services/librarian/app.py")
        assert response.status_code in [200, 404]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_code_api.py -v
```
Expected: FAIL (endpoints don't exist)

- [ ] **Step 3: Add code query endpoints to app.py**

```python
# services/librarian/app.py - ADD these endpoints

from fastapi import Query

@app.get("/code/search")
def search_code(q: str = Query(..., description="Search query"), type: str = Query("function")):
    """Search code semantically via ChromaDB and by name via Neo4j."""
    # ChromaDB semantic search
    vector_results = chroma.search_code(q)
    
    # Neo4j name/docstring search
    graph_results = neo4j.search_functions(q)
    
    return {
        "query": q,
        "vector_results": vector_results,
        "graph_results": graph_results
    }


@app.get("/code/function/{name}")
def get_function(name: str):
    """Get function details by name."""
    func = neo4j.get_function_by_name(name)
    if not func:
        raise HTTPException(status_code=404, detail=f"Function '{name}' not found")
    return func


@app.get("/code/function/{name}/callers")
def get_function_callers(name: str):
    """Get all functions that call this function."""
    callers = neo4j.get_callers(name)
    return {"function": name, "callers": callers}


@app.get("/code/function/{name}/callees")
def get_function_callees(name: str):
    """Get all functions this function calls."""
    callees = neo4j.get_callees(name)
    return {"function": name, "callees": callees}


@app.get("/code/function/{name}/full-context")
def get_function_full_context(name: str, depth: int = Query(2, ge=0, le=5)):
    """Get function + callers + callees recursively."""
    context = neo4j.get_full_context(name, depth)
    if not context:
        raise HTTPException(status_code=404, detail=f"Function '{name}' not found")
    return context


@app.get("/code/class/{name}")
def get_class(name: str):
    """Get class details and methods."""
    # Query Neo4j for class and its contained functions
    with neo4j.driver.session() as session:
        result = session.run(
            """
            MATCH (c:Class {name: $name})
            OPTIONAL MATCH (c)-[:CONTAINS]->(m:Function)
            RETURN c, collect(m) as methods
            """,
            name=name
        )
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail=f"Class '{name}' not found")
        
        return {
            "class": dict(record["c"]),
            "methods": [dict(m) for m in record["methods"] if m]
        }


@app.get("/code/file/{path:path}")
def get_file_content(path: str):
    """Get file content by path."""
    with neo4j.driver.session() as session:
        result = session.run(
            "MATCH (f:File {path: $path}) RETURN f",
            path=path
        )
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail=f"File '{path}' not found")
        return dict(record["f"])
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_code_api.py -v
```
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add services/librarian/app.py services/librarian/tests/test_code_api.py
git commit -m "feat: add code query HTTP endpoints to Librarian"
```

---

### Task 6: Pre-importer CLI

**Files:**
- Create: `services/librarian/preimport.py`
- Test: `services/librarian/tests/test_preimport.py`

- [ ] **Step 1: Write failing tests for preimporter**

```python
# services/librarian/tests/test_preimport.py

import pytest
import tempfile
import os
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')


class TestPreimporter:
    
    @pytest.fixture
    def sample_project(self):
        """Create a temporary project with sample files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple Python project
            os.makedirs(os.path.join(tmpdir, "auth"))
            
            with open(os.path.join(tmpdir, "auth", "__init__.py"), "w") as f:
                f.write("")
            
            with open(os.path.join(tmpdir, "auth", "service.py"), "w") as f:
                f.write('''
class AuthService:
    def login(self, username, password):
        return True
    
    def logout(self, user_id):
        return True

def verify_token(token):
    return True
''')
            
            with open(os.path.join(tmpdir, "main.py"), "w") as f:
                f.write('''
from auth.service import AuthService

def main():
    auth = AuthService()
    auth.login("user", "pass")

if __name__ == "__main__":
    main()
''')
            
            yield tmpdir
    
    def test_scan_project(self, sample_project):
        from services.librarian.preimport import scan_project
        files = scan_project(sample_project)
        
        py_files = [f for f in files if f.endswith(".py")]
        assert len(py_files) >= 2  # __init__.py, service.py, main.py
    
    def test_import_file(self, sample_project):
        from unittest.mock import MagicMock, patch
        
        with patch('services.librarian.preimport.Neo4jStore') as mock_neo4j, \
             patch('services.librarian.preimport.ChromaStore') as mock_chroma:
            
            from services.librarian.preimport import import_file
            filepath = os.path.join(sample_project, "auth", "service.py")
            
            result = import_file(filepath, sample_project, MagicMock(), MagicMock())
            
            assert result is not None
            assert "functions" in result or "classes" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_preimport.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement preimport.py**

```python
# services/librarian/preimport.py

import os
import sys
import click
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.indexer import CodeIndexer
from services.librarian.neo4j_store import Neo4jStore
from services.librarian.chroma_store import ChromaStore


def scan_project(root_path: str) -> list[str]:
    """Scan a directory for source files."""
    extensions = {".py", ".js", ".ts", ".go", ".rs", ".java", ".cpp", ".c"}
    files = []
    
    for dirpath, dirnames, filenames in os.walk(root_path):
        # Skip hidden dirs and common non-source dirs
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in 
                       {"node_modules", "venv", "__pycache__", ".git", "dist", "build"}]
        
        for filename in filenames:
            if Path(filename).suffix in extensions:
                files.append(os.path.join(dirpath, filename))
    
    return files


def import_file(
    filepath: str,
    root_path: str,
    neo4j: Neo4jStore,
    chroma: ChromaStore
) -> dict:
    """Import a single file into the knowledge graph."""
    indexer = CodeIndexer()
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    # Determine language
    ext = Path(filepath).suffix
    lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".go": "go"}
    language = lang_map.get(ext, "unknown")
    
    # Get relative path
    rel_path = os.path.relpath(filepath, root_path)
    
    # Index the file
    result = indexer.index_file(rel_path, content, language)
    
    # Upsert to Neo4j
    neo4j.upsert_index_result(result)
    
    # Add embeddings to ChromaDB
    for func in result.functions:
        uid = f"{func.file_path}:{func.name}"
        chroma.add_function_embedding(
            uid=uid,
            body=func.body,
            metadata={"name": func.name, "file": func.file_path, "docstring": func.docstring}
        )
    
    for cls in result.classes:
        uid = f"{cls.file_path}:{cls.name}"
        chroma.add_class_embedding(
            uid=uid,
            body=cls.body,
            metadata={"name": cls.name, "file": cls.file_path, "docstring": cls.docstring}
        )
    
    return {
        "file": rel_path,
        "functions": len(result.functions),
        "classes": len(result.classes),
        "calls": len(result.calls)
    }


@click.command()
@click.argument("project_path", type=click.Path(exists=True))
def preimport(project_path: str):
    """Bulk import a codebase into the Legion knowledge graph."""
    project_path = os.path.abspath(project_path)
    
    click.echo(f"Scanning project: {project_path}")
    
    neo4j = Neo4jStore()
    chroma = ChromaStore()
    
    files = scan_project(project_path)
    click.echo(f"Found {len(files)} source files")
    
    total_funcs = 0
    total_classes = 0
    total_calls = 0
    errors = 0
    
    for i, filepath in enumerate(files):
        try:
            result = import_file(filepath, project_path, neo4j, chroma)
            total_funcs += result.get("functions", 0)
            total_classes += result.get("classes", 0)
            total_calls += result.get("calls", 0)
            
            if (i + 1) % 10 == 0:
                click.echo(f"  Processed {i + 1}/{len(files)} files...")
        except Exception as e:
            click.echo(f"  ERROR: {filepath}: {e}")
            errors += 1
    
    click.echo("")
    click.echo("=" * 50)
    click.echo("Import complete!")
    click.echo(f"  Files:    {len(files) - errors}")
    click.echo(f"  Classes:  {total_classes}")
    click.echo(f"  Functions: {total_funcs}")
    click.echo(f"  Calls:    {total_calls}")
    if errors:
        click.echo(f"  Errors:   {errors}")
    click.echo("=" * 50)


if __name__ == "__main__":
    preimport()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_preimport.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add services/librarian/preimport.py services/librarian/tests/test_preimport.py
git commit -m "feat: add preimport CLI for bulk codebase indexing"
```

---

### Task 7: Post-execution Indexer

**Files:**
- Create: `services/librarian/post_indexer.py`
- Modify: `services/librarian/app.py` (add endpoint)
- Modify: `services/tester/app.py` (call endpoint after merge)

**Design note:** The Librarian container has NO filesystem access to the project. The Tester reads merged files from its worktree and sends file content in the request body.

- [ ] **Step 1: Write failing tests for post-indexer endpoint**

```python
# services/librarian/tests/test_post_indexer.py

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')


class TestPostIndexer:

    @pytest.fixture
    def client(self):
        with patch('services.librarian.neo4j_store.Neo4jStore') as mock_neo4j, \
             patch('services.librarian.chroma_store.ChromaStore') as mock_chroma:

            mock_neo4j.return_value = MagicMock()
            mock_chroma.return_value = MagicMock()

            from services.librarian.app import app
            return TestClient(app)

    def test_index_updated_endpoint(self, client):
        response = client.post("/index/updated", json={
            "files": [
                {"path": "services/librarian/app.py", "content": "from fastapi import FastAPI\napp = FastAPI()"}
            ]
        })
        assert response.status_code == 200
        assert "indexed" in response.json()

    def test_index_updated_empty_files(self, client):
        response = client.post("/index/updated", json={
            "files": []
        })
        assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_post_indexer.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement post_indexer.py**

```python
# services/librarian/post_indexer.py

from shared.indexer import CodeIndexer
from services.librarian.neo4j_store import Neo4jStore
from services.librarian.chroma_store import ChromaStore


class PostIndexer:
    """Incrementally index changed files after a merge.

    Receives file content in the request body — the Librarian container
    never needs filesystem access to the project.
    """

    def __init__(self, neo4j: Neo4jStore, chroma: ChromaStore):
        self.neo4j = neo4j
        self.chroma = chroma
        self.indexer = CodeIndexer()

    def index_files(self, files: list[dict]) -> dict:
        """Index a list of files, each with 'path', 'content', and 'language' keys."""
        results = []

        for file_info in files:
            rel_path = file_info["path"]
            content = file_info["content"]
            language = file_info.get("language", "python")

            if content is None:
                # File was deleted
                self.neo4j.delete_file(rel_path)
                results.append({"file": rel_path, "action": "deleted"})
                continue

            try:
                result = self.indexer.index_file(rel_path, content, language)
                self.neo4j.upsert_index_result(result)

                # Update ChromaDB
                for func in result.functions:
                    uid = f"{func.file_path}:{func.name}"
                    self.chroma.delete_by_id(uid)  # Remove old version
                    self.chroma.add_function_embedding(
                        uid=uid,
                        body=func.body,
                        metadata={"name": func.name, "file": func.file_path}
                    )

                for cls in result.classes:
                    uid = f"{cls.file_path}:{cls.name}"
                    self.chroma.delete_by_id(uid)
                    self.chroma.add_class_embedding(
                        uid=uid,
                        body=cls.body,
                        metadata={"name": cls.name, "file": cls.file_path}
                    )

                results.append({
                    "file": rel_path,
                    "action": "updated",
                    "functions": len(result.functions),
                    "classes": len(result.classes)
                })

            except Exception as e:
                results.append({
                    "file": rel_path,
                    "action": "error",
                    "error": str(e)
                })

        return {
            "total": len(files),
            "results": results
        }
```

- [ ] **Step 4: Add /index/updated endpoint to app.py**

```python
# services/librarian/app.py - ADD this endpoint

from pydantic import BaseModel
from typing import Optional

class FileContent(BaseModel):
    path: str
    content: Optional[str] = None
    language: str = "python"


class IndexUpdatedRequest(BaseModel):
    files: list[FileContent]


@app.post("/index/updated")
def index_updated(request: IndexUpdatedRequest):
    """Index changed files after a merge.

    The Tester sends file content directly — the Librarian never reads the filesystem.
    """
    from services.librarian.post_indexer import PostIndexer

    indexer = PostIndexer(neo4j, chroma)
    file_dicts = [f.model_dump() for f in request.files]
    result = indexer.index_files(file_dicts)

    return {"indexed": result}
```

- [ ] **Step 5: Modify Tester to read merged files and send content to Librarian**

```python
# services/tester/app.py - MODIFY the validate endpoint's success branch

# In the validate endpoint, after successful merge, replace the indexing call with:

    if result.passed:
        success, error = merger.merge_task_branch(request.task_id)
        if success:
            # Index the merged code — read files from worktree and send content
            try:
                import requests
                import os
                from pathlib import Path

                worktree_path = merger.get_worktree_path(request.task_id)
                files_to_index = []

                # Collect all Python files from the worktree
                for py_file in Path(worktree_path).rglob("*.py"):
                    rel_path = str(py_file.relative_to(worktree_path))
                    content = py_file.read_text(encoding="utf-8", errors="ignore")
                    files_to_index.append({
                        "path": rel_path,
                        "content": content,
                        "language": "python"
                    })

                requests.post(
                    f"{LIBRARIAN_URL}/index/updated",
                    json={"files": files_to_index}
                )
            except Exception as e:
                logger.error(f"Failed to trigger indexing: {e}")

            # Update task status to DONE
            ...
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/librarian/tests/test_post_indexer.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add services/librarian/post_indexer.py services/librarian/app.py services/tester/app.py services/librarian/tests/test_post_indexer.py
git commit -m "feat: add post-execution indexer (content-based, no filesystem access)"
```

---

### Task 8: Worker MCP Tools

**Files:**
- Create: `services/worker/mcp_tools.py`
- Modify: `services/worker/executor.py`

- [ ] **Step 1: Write failing tests for MCP tools**

```python
# services/worker/tests/test_mcp_tools.py

import pytest
from unittest.mock import MagicMock, patch
import sys
sys.path.insert(0, '/home/loki/ideas/sea-qwens')


class TestMCPTools:
    
    @pytest.fixture
    def tools(self):
        with patch('requests.get') as mock_get, \
             patch('requests.post') as mock_post:
            
            mock_get.return_value = MagicMock(status_code=200, json=lambda: {"results": []})
            
            from services.worker.mcp_tools import CodeQueryTools
            return CodeQueryTools(librarian_url="http://localhost:8001")
    
    def test_search_code(self, tools):
        result = tools.search_code("authentication")
        assert isinstance(result, list)
    
    def test_get_function(self, tools):
        result = tools.get_function("login")
        assert result is not None
    
    def test_get_callers(self, tools):
        result = tools.get_callers("login")
        assert isinstance(result, list)
    
    def test_get_callees(self, tools):
        result = tools.get_callees("main")
        assert isinstance(result, list)
    
    def test_get_full_context(self, tools):
        result = tools.get_full_context("login")
        assert isinstance(result, dict)
    
    def test_get_class(self, tools):
        result = tools.get_class("AuthService")
        assert result is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/worker/tests/test_mcp_tools.py -v
```
Expected: FAIL

- [ ] **Step 3: Implement MCP tools**

```python
# services/worker/mcp_tools.py

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
        """Search for functions/classes by semantic similarity.
        
        Args:
            query: Natural language search query (e.g., "user authentication")
            type: "function" or "class"
        
        Returns:
            List of matching functions/classes with their code
        """
        response = requests.get(
            f"{self.librarian_url}/code/search",
            params={"q": query, "type": type}
        )
        if response.status_code == 200:
            return response.json().get("vector_results", [])
        return []
    
    def get_function(self, name: str) -> Optional[dict]:
        """Get function body and signature by name.
        
        Args:
            name: Function name (e.g., "login")
        
        Returns:
            Function details including body, signature, docstring
        """
        response = requests.get(f"{self.librarian_url}/code/function/{name}")
        if response.status_code == 200:
            return response.json()
        return None
    
    def get_callers(self, function_name: str) -> list:
        """Get all functions that call this function.
        
        Args:
            function_name: The function to find callers for
        
        Returns:
            List of caller functions
        """
        response = requests.get(f"{self.librarian_url}/code/function/{function_name}/callers")
        if response.status_code == 200:
            return response.json().get("callers", [])
        return []
    
    def get_callees(self, function_name: str) -> list:
        """Get all functions this function calls.
        
        Args:
            function_name: The function to find callees for
        
        Returns:
            List of callee functions
        """
        response = requests.get(f"{self.librarian_url}/code/function/{function_name}/callees")
        if response.status_code == 200:
            return response.json().get("callees", [])
        return []
    
    def get_full_context(self, function_name: str) -> dict:
        """Get everything needed to understand a function.
        
        Returns the function body, its callers, callees, and nested call chains.
        Use this before modifying or extending a function.
        
        Args:
            function_name: The function to get context for
        
        Returns:
            Complete context including callers, callees, and their code
        """
        response = requests.get(f"{self.librarian_url}/code/function/{function_name}/full-context")
        if response.status_code == 200:
            return response.json()
        return {}
    
    def get_class(self, name: str) -> Optional[dict]:
        """Get class definition and all methods.
        
        Args:
            name: Class name (e.g., "AuthService")
        
        Returns:
            Class details including all methods
        """
        response = requests.get(f"{self.librarian_url}/code/class/{name}")
        if response.status_code == 200:
            return response.json()
        return None
```

- [ ] **Step 4: Update Worker prompt to include MCP tool instructions**

```python
# services/worker/executor.py - MODIFY _build_prompt method

    def _build_prompt(self, title: str, contract: dict) -> str:
        """Build prompt for qwen-code with MCP tool instructions."""
        prompt = f"""Implement the following task:

{title}

Requirements (contract):
{json.dumps(contract, indent=2)}

## Code Knowledge Graph Tools

You have access to a code knowledge graph. Instead of reading files, use these tools to understand the codebase:

- `search_code(query)` - Find functions/classes by semantic search
- `get_function(name)` - Get a function's body and signature
- `get_callers(name)` - Find who calls this function
- `get_callees(name)` - Find what this function calls
- `get_full_context(name)` - Get complete context for understanding a function
- `get_class(name)` - Get a class definition and all methods

## Workflow

1. Before implementing, search for existing related code
2. Use `get_full_context` to understand call chains
3. Implement your changes following existing patterns
4. Ensure your code integrates with existing functions

## Guidelines

- Write clean, tested code
- Follow best practices
- Ensure all tests pass
- Do not modify files outside the task scope
"""
        return prompt
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /home/loki/ideas/sea-qwens
pytest services/worker/tests/test_mcp_tools.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add services/worker/mcp_tools.py services/worker/executor.py services/worker/tests/test_mcp_tools.py
git commit -m "feat: add MCP code query tools for Worker LLM"
```

---

### Task 9: Update Requirements and Docker

**Files:**
- Modify: `services/librarian/requirements.txt`
- Modify: `services/worker/requirements.txt`

- [ ] **Step 1: Add tree-sitter dependencies**

```txt
# services/librarian/requirements.txt - ADD these lines

tree-sitter>=0.21.0
tree-sitter-python>=0.21.0
click>=8.1.7
```

- [ ] **Step 2: Add requests to worker requirements**

```txt
# services/worker/requirements.txt - ADD this line

requests>=2.31.0
```

- [ ] **Step 3: Commit**

```bash
git add services/librarian/requirements.txt services/worker/requirements.txt
git commit -m "chore: add tree-sitter and requests dependencies"
```

---

### Task 10: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Code Knowledge Graph section to README**

```markdown
# Add this section after the Architecture section

## Code Knowledge Graph

The Librarian stores the entire codebase as a knowledge graph in Neo4j + ChromaDB. Agents query this graph instead of reading files directly.

### Graph Structure

```
Project → Module → File → Class → Function
```

With relationships: `CALLS`, `IMPORTS`, `INHERITS`, `INSTANTIATES`, `USES`.

### Querying Code

**HTTP API:**
```bash
# Search for authentication-related code
curl "http://localhost:8001/code/search?q=authentication&type=function"

# Get function details
curl http://localhost:8001/code/function/login

# Get full call context
curl http://localhost:8001/code/function/login/full-context

# Get class and methods
curl http://localhost:8001/code/class/AuthService
```

**MCP Tools (for Worker LLM):**
- `search_code(query)` - Semantic search
- `get_function(name)` - Get function details
- `get_callers(name)` / `get_callees(name)` - Call chain analysis
- `get_full_context(name)` - Complete function context
- `get_class(name)` - Class definition + methods

### Importing Code

**Pre-import existing codebase:**
```bash
python -m services.librarian.preimport /path/to/existing/project
```

**Post-execution indexing** happens automatically when the Tester merges a task.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add code knowledge graph section to README"
```

---

## Verification

After completing all tasks, run:

```bash
# Run all unit tests
pytest shared/ services/ -v -m "not integration"

# Expected: All tests pass (130+ tests)

# Test preimporter on the Legion codebase itself
python -m services.librarian.preimport /home/loki/ideas/sea-qwens

# Test code query endpoints
curl "http://localhost:8001/code/search?q=authentication&type=function"
curl http://localhost:8001/code/function/login
```

Expected: All tests pass, preimporter indexes the codebase, queries return results
