from neo4j import GraphDatabase
from services.librarian.config import settings
from typing import Optional, Any
import uuid


class Neo4jStore:
    """Neo4j graph database operations for Project Legion"""

    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    def close(self):
        """Close the Neo4j driver connection"""
        self.driver.close()

    def create_project_spec(self, name: str, tech_stack: list[str], features: list[str]) -> dict:
        """Create a new ProjectSpec node in Neo4j"""
        spec_id = str(uuid.uuid4())
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (p:ProjectSpec {
                    id: $id,
                    name: $name,
                    tech_stack: $tech_stack,
                    features: $features
                })
                RETURN p
                """,
                id=spec_id, name=name, tech_stack=tech_stack, features=features
            )
            record = result.single()
            return dict(record["p"])

    def get_project_spec(self, spec_id: str) -> Optional[dict]:
        """Retrieve a ProjectSpec by ID"""
        with self.driver.session() as session:
            result = session.run(
                "MATCH (p:ProjectSpec {id: $id}) RETURN p",
                id=spec_id
            )
            record = result.single()
            if record:
                return dict(record["p"])
            return None

    def create_task(self, task_data: dict) -> dict:
        """Create a new Task node in Neo4j"""
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (t:Task {
                    task_id: $task_id,
                    title: $title,
                    status: $status,
                    dependencies: $dependencies,
                    contract: $contract,
                    profile_id: $profile_id
                })
                RETURN t
                """,
                **task_data
            )
            record = result.single()
            return dict(record["t"])

    def get_ready_tasks(self) -> list[dict]:
        """Get tasks where all dependencies are DONE"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Task {status: 'PENDING'})
                WHERE ALL(dep_id IN t.dependencies WHERE
                    EXISTS((:Task {task_id: dep_id, status: 'DONE'}))
                )
                RETURN t
                """
            )
            return [dict(record["t"]) for record in result]

    def update_task_status(self, task_id: str, status: str, metadata: Optional[dict] = None) -> Optional[dict]:
        """Update a task's status"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (t:Task {task_id: $task_id})
                SET t.status = $status
                RETURN t
                """,
                task_id=task_id, status=status
            )
            record = result.single()
            if record:
                return dict(record["t"])
            return None

    def create_profile(self, profile_data: dict) -> dict:
        """Create a new Profile node in Neo4j"""
        with self.driver.session() as session:
            result = session.run(
                """
                CREATE (p:Profile {
                    name: $name,
                    usage_count: $usage_count,
                    requests_today: $requests_today,
                    health_status: $health_status
                })
                RETURN p
                """,
                **profile_data
            )
            record = result.single()
            return dict(record["p"])

    def get_least_used_profile(self) -> Optional[dict]:
        """Get profile with lowest usage_count among healthy profiles"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Profile {health_status: 'HEALTHY'})
                WHERE p.requests_today < p.daily_limit
                RETURN p
                ORDER BY p.usage_count ASC
                LIMIT 1
                """
            )
            record = result.single()
            if record:
                return dict(record["p"])
            return None

    def increment_profile_usage(self, profile_name: str) -> Optional[dict]:
        """Increment profile usage counters"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Profile {name: $name})
                SET p.usage_count = p.usage_count + 1
                SET p.requests_today = p.requests_today + 1
                SET p.last_used = datetime()
                RETURN p
                """,
                name=profile_name
            )
            record = result.single()
            if record:
                return dict(record["p"])
            return None
