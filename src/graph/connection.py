


"""
This is a script is for setting up Neo4j driver to communicate with the local instance.
"""



import os
from neo4j import GraphDatabase, Driver


def make_driver() -> Driver:
    """
    Creates Neo4j driver from the set environment variables.

    Reads:
        NEO4J_URI       (default: neo4j://127.0.0.1:7687)
        NEO4J_USER      (default: neo4j)
        NEO4J_PASSWORD  (required, no default)

    Returns:
        A connected Neo4j driver. Caller is responsible for closing it.

    Raises:
        RuntimeError: If NEO4J_PASSWORD is not set.
    """
    
    # Getting environment variables for NEO4j
    uri = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")


    if not password:
        raise RuntimeError(
            "NEO4J_PASSWORD environment variable is not set. "
            "See README for setup instructions."
        )

    driver = GraphDatabase.driver(uri, auth=(user, password))

    # Checks for connectivity.        (Neo4j driver constructor only opens on first query)
    driver.verify_connectivity()    # This line checks immediately in case of environment variable misconfigurament
    
    return driver

