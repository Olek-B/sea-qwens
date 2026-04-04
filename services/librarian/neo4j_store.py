from neo4j import GraphDatabase
from services.librarian.config import settings
from typing import Optional, Any
import uuid
import json
from shared.models import CodeFile, CodeFunction, CodeClass
from shared.indexer import IndexResult, CallRelation


class Neo4jStore:
    """Neo4j graph database operations for Sea Qwens"""

    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    def close(self):
        """Close the Neo4j driver connection"""
        self.driver.close()

    def create_project_spec(
        self,
        name: str,
        tech_stack: list[str],
        features: list[str],
        parent_project: Optional[str] = None,
        constraints: Optional[list[str]] = None,
    ) -> dict:
        """Create a new ProjectSpec node in Neo4j"""
        spec_id = str(uuid.uuid4())
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (p:ProjectSpec {
                    id: $id,
                    name: $name,
                    tech_stack: $tech_stack,
                    features: $features,
                    parent_project: $parent_project,
                    constraints: $constraints,
                    created_at: datetime()
                })
                RETURN p
                """,
                id=spec_id,
                name=name,
                tech_stack=tech_stack,
                features=features,
                parent_project=parent_project,
                constraints=constraints or [],
            )
            record = result.single()
            return dict(record["p"])

    def get_project_spec(self, spec_id: str) -> Optional[dict]:
        """Retrieve a ProjectSpec by ID"""
        with self.driver.session() as session:
            result = session.run("MATCH (p:ProjectSpec {id: $id}) RETURN p", id=spec_id)
            record = result.single()
            if record:
                return dict(record["p"])
            return None

    def list_all_project_specs(self) -> list[dict]:
        """Retrieve all ProjectSpec nodes from Neo4j."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (p:ProjectSpec) RETURN p ORDER BY p.created_at DESC"
            )
            return [dict(record["p"]) for record in result]

    def create_task(self, task_data: dict) -> dict:
        """Create a new Task node in Neo4j"""
        # Neo4j doesn't support nested dicts as properties, so we serialize contract as JSON
        task_data = task_data.copy()
        if isinstance(task_data.get("contract"), dict):
            task_data["contract"] = json.dumps(task_data["contract"])

        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (t:Task {
                    task_id: $task_id,
                    title: $title,
                    status: $status,
                    dependencies: $dependencies,
                    contract: $contract,
                    tool_id: $tool_id
                })
                RETURN t
                """,
                **task_data,
            )
            record = result.single()
            task = dict(record["t"])
            # Deserialize contract when reading
            if isinstance(task.get("contract"), str):
                try:
                    task["contract"] = json.loads(task["contract"])
                except (json.JSONDecodeError, TypeError):
                    pass
            return task

    def get_ready_tasks(self) -> list[dict]:
        """Get tasks where all dependencies are DONE"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Task {status: 'PENDING'})
                WHERE ALL(dep_id IN t.dependencies WHERE
                    EXISTS {
                        MATCH (dep:Task {task_id: dep_id, status: 'DONE'})
                    }
                )
                RETURN t
                """
            )
            tasks = []
            for record in result:
                task = dict(record["t"])
                # Deserialize contract when reading
                if isinstance(task.get("contract"), str):
                    try:
                        task["contract"] = json.loads(task["contract"])
                    except (json.JSONDecodeError, TypeError):
                        pass
                tasks.append(task)
            return tasks

    def update_task_status(
        self, task_id: str, status: str, metadata: Optional[dict] = None
    ) -> Optional[dict]:
        """Update a task's status"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Task {task_id: $task_id})
                SET t.status = $status
                RETURN t
                """,
                task_id=task_id,
                status=status,
            )
            record = result.single()
            if record:
                return dict(record["t"])
            return None

    def create_tool(self, tool_data: dict) -> dict:
        """Create a new Tool node in Neo4j"""
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (t:Tool {
                    name: $name,
                    command: $command,
                    usage_count: $usage_count,
                    daily_limit: $daily_limit,
                    requests_today: $requests_today,
                    health_status: $health_status
                })
                RETURN t
                """,
                **tool_data,
            )
            record = result.single()
            return dict(record["t"])

    def get_all_tools(self) -> list[dict]:
        """Get all tools from Neo4j."""
        with self.driver.session() as session:
            result = session.run("MATCH (t:Tool) RETURN t")
            return [dict(record["t"]) for record in result]

    def get_least_used_tool(self) -> Optional[dict]:
        """Get tool with lowest usage_count among healthy tools"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Tool {health_status: 'HEALTHY'})
                WHERE t.requests_today < t.daily_limit
                RETURN t
                ORDER BY t.usage_count ASC
                LIMIT 1
                """
            )
            record = result.single()
            if record:
                return dict(record["t"])
            return None

    def increment_tool_usage(self, tool_name: str) -> Optional[dict]:
        """Increment tool usage counters"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Tool {name: $name})
                SET t.usage_count = t.usage_count + 1
                SET t.requests_today = t.requests_today + 1
                SET t.last_used = datetime()
                RETURN t
                """,
                name=tool_name,
            )
            record = result.single()
            if record:
                return dict(record["t"])
            return None

    def create_dependency_relationship(
        self, from_task_id: str, to_task_id: str
    ) -> bool:
        """Create a DEPENDS_ON relationship between two tasks.

        Args:
            from_task_id: The task that has the dependency
            to_task_id: The task that is depended upon

        Returns:
            True if relationship was created, False otherwise
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (from:Task {task_id: $from_id})
                MATCH (to:Task {task_id: $to_id})
                CREATE (from)-[:DEPENDS_ON]->(to)
                RETURN true AS created
                """,
                from_id=from_task_id,
                to_id=to_task_id,
            )
            record = result.single()
            return record is not None and record["created"] is not None

    # --- Code Graph CRUD Operations ---

    def upsert_file(self, code_file: CodeFile):
        """Upsert a CodeFile node into Neo4j."""
        with self.driver.session() as session:
            session.run(
                "MERGE (f:File {path: $path}) SET f.language = $language, f.content = $content, f.last_updated = datetime()",
                path=code_file.path,
                language=code_file.language,
                content=code_file.content,
            )

    def upsert_function(self, func: CodeFunction):
        """Upsert a CodeFunction node with CONTAINS relationship to its File."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (f:File {path: $file_path})
                MERGE (fn:Function {name: $name, file_path: $file_path})
                SET fn.body = $body, fn.signature = $signature, fn.docstring = $docstring,
                    fn.is_method = $is_method, fn.parent_class = $parent_class,
                    fn.line_start = $line_start, fn.line_end = $line_end
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
                line_end=func.line_end,
            )

    def upsert_class(self, cls: CodeClass):
        """Upsert a CodeClass node with CONTAINS relationship to its File."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (f:File {path: $file_path})
                MERGE (c:Class {name: $name, file_path: $file_path})
                SET c.body = $body, c.docstring = $docstring, c.bases = $bases,
                    c.line_start = $line_start, c.line_end = $line_end
                MERGE (f)-[:CONTAINS]->(c)
                """,
                name=cls.name,
                file_path=cls.file_path,
                body=cls.body,
                docstring=cls.docstring,
                bases=cls.bases,
                line_start=cls.line_start,
                line_end=cls.line_end,
            )

    def create_call_relationship(self, caller_name: str, callee_name: str):
        """Create a CALLS relationship between two Function nodes."""
        with self.driver.session() as session:
            session.run(
                "MATCH (caller:Function {name: $caller}) MATCH (callee:Function {name: $callee}) MERGE (caller)-[:CALLS]->(callee)",
                caller=caller_name,
                callee=callee_name,
            )

    def create_inherits_relationship(self, child_name: str, parent_name: str):
        """Create an INHERITS relationship between two Class nodes."""
        with self.driver.session() as session:
            session.run(
                "MATCH (child:Class {name: $child}) MATCH (parent:Class {name: $parent}) MERGE (child)-[:INHERITS]->(parent)",
                child=child_name,
                parent=parent_name,
            )

    def get_function_by_name(self, name: str) -> Optional[dict]:
        """Retrieve a Function node by name."""
        with self.driver.session() as session:
            result = session.run("MATCH (f:Function {name: $name}) RETURN f", name=name)
            record = result.single()
            return dict(record["f"]) if record else None

    def get_callers(self, function_name: str) -> list[dict]:
        """Get all functions that call the given function."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (caller:Function)-[:CALLS]->(target:Function {name: $name}) RETURN caller",
                name=function_name,
            )
            return [dict(r["caller"]) for r in result]

    def get_callees(self, function_name: str) -> list[dict]:
        """Get all functions called by the given function."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (source:Function {name: $name})-[:CALLS]->(callee:Function) RETURN callee",
                name=function_name,
            )
            return [dict(r["callee"]) for r in result]

    def get_full_context(self, function_name: str, depth: int = 2) -> dict:
        """Get a function's callers, callees, and nested callees recursively."""
        func = self.get_function_by_name(function_name)
        if not func:
            return {}
        callers = self.get_callers(function_name)
        callees = self.get_callees(function_name)
        full_callees = []
        if depth > 0:
            for callee in callees:
                sub_context = self.get_full_context(callee["name"], depth - 1)
                full_callees.append(sub_context)
        return {
            "function": func,
            "callers": callers,
            "callees": callees,
            "nested_callees": full_callees,
        }

    def search_functions(self, query: str) -> list[dict]:
        """Search functions by name or docstring substring match."""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (f:Function) WHERE f.name CONTAINS $query OR f.docstring CONTAINS $query RETURN f LIMIT 20",
                query=query,
            )
            return [dict(r["f"]) for r in result]

    def delete_file(self, path: str):
        """Delete a File node and all its contained nodes and relationships."""
        with self.driver.session() as session:
            session.run("MATCH (f:File {path: $path}) DETACH DELETE f", path=path)

    def upsert_index_result(self, result: IndexResult):
        """Upsert an entire IndexResult: file, classes, functions, and call relations."""
        self.upsert_file(result.file)
        for cls in result.classes:
            self.upsert_class(cls)
            for base in cls.bases:
                self.create_inherits_relationship(cls.name, base)
        for func in result.functions:
            self.upsert_function(func)
        for call in result.calls:
            self.create_call_relationship(call.caller, call.callee)
