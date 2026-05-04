#!/usr/bin/env python
"""
Initializes the Neo4j schema for the graph memory backend.

Connects to the Neo4j instance configured via NEO4J_* environment variables, applies all
schema constraints and indexes, and prints a summary of the resulting state.

Safe to run repeatedly: all statements are idempotent.
"""

import json

from graph.connection import make_driver
from graph.schema import apply_schema, describe_schema


def main() -> None:
    driver = make_driver()
    try:
        print("Applying schema...")
        apply_schema(driver)

        print("Schema applied. Current state:")
        summary = describe_schema(driver)
        print(json.dumps(summary, indent=2))

        n_constraints = len(summary["constraints"])
        n_indexes = len(summary["indexes"])
        print(
            f"\nDone. {n_constraints} constraint(s), {n_indexes} index(es) "
            f"in database."
        )
    finally:
        driver.close()


if __name__ == "__main__":
    main()