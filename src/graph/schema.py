


"""
Schema setup for the graph memory backend.

Defines constraints and indexes that the graph relies on. All statements are idempotent (IF NOT EXISTS),
so apply_schema() is safe to run repeatedly.

The schema is currently minimal. Just enough structure to keep the graph clean and make hybrid retrieval
(vector + graph traversal) fast. It does NOT enforce a typed ontology. Entity and relation labels are
LLM-extracted at runtime.
"""



from neo4j import Driver

EMBEDDING_DIM = 1536  # for openai text-embedding-3-small


# Cypher queries for setting up graph database schema
SCHEMA_STATEMENTS: list[str] = [

    # Entity: uniqueness per (name, agent_id) so two agents can independently have an entity with the same name without collision.
    """
    CREATE CONSTRAINT entity_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.agent_id) IS UNIQUE
    """,

    # Fulltext over entity name and aliases for fuzzy lookup during canonicalization (e.g. matching "marcus" to existing "Marcus").
    """
    CREATE FULLTEXT INDEX entity_name_search IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.aliases]
    """,

    # Vector index over entity embeddings for semantic retrieval.
    f"""
    CREATE VECTOR INDEX entity_embedding IF NOT EXISTS
    FOR (e:Entity) ON e.embedding
    OPTIONS {{indexConfig: {{
        `vector.dimensions`: {EMBEDDING_DIM},
        `vector.similarity_function`: 'cosine'
    }}}}
    """,

    # Message: globally unique IDs (UUIDs).
    """
    CREATE CONSTRAINT message_id_unique IF NOT EXISTS FOR (m:Message) REQUIRE m.id IS UNIQUE
    """,

    # Vector index over message embeddings for message-level semantic search.
    f"""
    CREATE VECTOR INDEX message_embedding IF NOT EXISTS
    FOR (m:Message) ON m.embedding
    OPTIONS {{indexConfig: {{
        `vector.dimensions`: {EMBEDDING_DIM},
        `vector.similarity_function`: 'cosine'
    }}}}
    """,

    # Lookup index for filtering messages by agent.
    """
    CREATE INDEX message_agent IF NOT EXISTS FOR (m:Message) ON (m.agent_id)
    """
]




def apply_schema(driver: Driver) -> None:
    """
    Apply all schema statements to the database.

    Idempotent: safe to run repeatedly. Each statement uses IF NOT EXISTS,
    so existing constraints and indexes are left untouched.

    Args:
        driver: A connected Neo4j driver.
    """

    with driver.session() as session:
        for statement in SCHEMA_STATEMENTS:
            session.run(statement)


def describe_schema(driver: Driver) -> dict[str, list[dict]]:
    """
    Return a summary of constraints and indexes currently in the database.

    Useful for debugging and for the init script to print after applying.

    Args:
        driver: A connected Neo4j driver.

    Returns:
        A dict with two keys, "constraints" and "indexes", each mapping to a
        list of dicts with the relevant fields from SHOW CONSTRAINTS and
        SHOW INDEXES.
    """


    with driver.session() as session:
        constraints = [
            {"name": r["name"], "type": r["type"], "labels": r["labelsOrTypes"]}
            for r in session.run("SHOW CONSTRAINTS")
        ]
        indexes = [
            {
                "name": r["name"],
                "type": r["type"],
                "labels": r["labelsOrTypes"],
                "properties": r["properties"],
            }
            for r in session.run("SHOW INDEXES")
        ]
    return {"constraints": constraints, "indexes": indexes}