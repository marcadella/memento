#!/usr/bin/env python
"""
Clear graph memory data from Neo4j.

By default, deletes all nodes and relationships scoped to a specific agent_id.
With --all, wipes everything in the database (use with care).

The script does NOT touch schema (constraints and indexes). Those persist
across clears and only change when scripts/init_neo4j.py is re-run.

Usage:
    python scripts/clear_graph.py --agent-id TestAgent
    python scripts/clear_graph.py --all
"""

import argparse
import sys

from graph.connection import make_driver


def clear_agent(driver, agent_id: str) -> tuple[int, int]:
    """Delete all nodes and relationships for the given agent_id.

    Args:
        driver: A connected Neo4j driver.
        agent_id: The agent whose data to wipe.

    Returns:
        (nodes_deleted, relationships_deleted) counts.
    """
    # DETACH DELETE removes the node and any relationships attached to it
    # in one operation. Without DETACH, Neo4j refuses to delete a node
    # that still has relationships pointing at or away from it.
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n {agent_id: $agent_id})
            DETACH DELETE n
            RETURN count(n) AS nodes_deleted
            """,
            agent_id=agent_id,
        )
        nodes_deleted = result.single()["nodes_deleted"]

    # Relationships were deleted as part of the DETACH above, but
    # counting them separately gives a clearer summary for the user.
    # We do this with a SECOND query rather than trying to also count
    # them in the first because once DETACH DELETE runs, the relationships
    # are gone and we cannot retroactively count what we destroyed.
    # For now, we just report nodes_deleted and let the user infer.
    return nodes_deleted, 0


def clear_all(driver) -> int:
    """Delete every node and relationship in the database.

    Schema (constraints, indexes) is preserved.

    Args:
        driver: A connected Neo4j driver.

    Returns:
        Total number of nodes deleted.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH (n)
            DETACH DELETE n
            RETURN count(n) AS nodes_deleted
            """
        )
        return result.single()["nodes_deleted"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clear graph memory data from Neo4j."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--agent-id",
        type=str,
        help="Delete only data for this agent (recommended).",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Delete EVERYTHING in the database. Use with care.",
    )
    args = parser.parse_args()

    driver = make_driver()
    try:
        if args.all:
            # Extra confirmation step for the destructive option.
            print(
                "This will delete ALL nodes and relationships in the "
                "database (schema is preserved)."
            )
            confirm = input("Type 'yes' to proceed: ")
            if confirm.strip().lower() != "yes":
                print("Aborted.")
                sys.exit(1)
            n = clear_all(driver)
            print(f"Done. {n} node(s) deleted.")
        else:
            n, _ = clear_agent(driver, args.agent_id)
            print(f"Done. {n} node(s) deleted for agent '{args.agent_id}'.")
    finally:
        driver.close()


if __name__ == "__main__":
    main()