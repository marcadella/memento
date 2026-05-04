from neo4j import Driver

EMBEDDING_DIM = 1536

DATABASE_INSTANCE = "mementoRAG"


def applay_schema(driver: Driver):
    # Initialize the official Neo4j driver
    with driver.session(database=DATABASE_INSTANCE) as session:
        session.run(f"""
            CREATE VECTOR INDEX chunk_vector_index IF NOT EXISTS
            FOR (n:Chunk) ON (n.embedding)
            OPTIONS {{indexConfig: {{
            `vector.dimensions`: {EMBEDDING_DIM},
            `vector.similarity_function`: 'cosine'
            }}}}
        """)
