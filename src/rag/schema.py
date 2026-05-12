from neo4j import Driver

EMBEDDING_DIM = 1536

DATABASE_INSTANCE = "mementoRAG"


def apply_schema(driver: Driver, index_name:str):
    # Initialize the official Neo4j driver
    with driver.session(database=DATABASE_INSTANCE) as session:
        session.run(f"""
            CREATE VECTOR INDEX {index_name} IF NOT EXISTS
            FOR (n:Chunk) ON (n.embedding)
            OPTIONS {{indexConfig: {{
            `vector.dimensions`: {EMBEDDING_DIM},
            `vector.similarity_function`: 'cosine'
            }}}}
        """)
