#!/usr/bin/env python
"""One-time migration: rename (Profile) nodes → (Tool) in Neo4j.

Usage:
    python -m services.librarian.migrate_profiles_to_tools

This script:
1. Connects to Neo4j using settings from the Librarian config
2. Copies all (Profile) nodes to (Tool) nodes with the same properties
3. Deletes the old (Profile) nodes
4. Reports how many nodes were migrated
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from neo4j import GraphDatabase
from services.librarian.config import settings


def migrate():
    driver = GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )

    with driver.session() as session:
        # Count existing Profile nodes
        count_result = session.run("MATCH (p:Profile) RETURN count(p) as cnt")
        count = count_result.single()["cnt"]
        print(f"Found {count} Profile nodes to migrate.")

        if count == 0:
            print("Nothing to migrate. Exiting.")
            driver.close()
            return

        # Copy all Profile nodes to Tool nodes (same properties)
        session.run("""
            MATCH (p:Profile)
            CREATE (t:Tool)
            SET t = p
            WITH p, t
            SET t.name = p.name
        """)

        # Verify Tool nodes were created
        tool_count_result = session.run("MATCH (t:Tool) RETURN count(t) as cnt")
        tool_count = tool_count_result.single()["cnt"]
        print(f"Created {tool_count} Tool nodes.")

        # Delete old Profile nodes
        session.run("MATCH (p:Profile) DETACH DELETE p")

        # Verify deletion
        verify_result = session.run("MATCH (p:Profile) RETURN count(p) as cnt")
        remaining = verify_result.single()["cnt"]
        print(f"Remaining Profile nodes: {remaining}")

        if remaining == 0 and tool_count == count:
            print("Migration successful!")
        else:
            print("WARNING: Migration may have failed. Check Neo4j manually.")

    driver.close()


if __name__ == "__main__":
    migrate()
