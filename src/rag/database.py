from neo4j import Driver

#EMBEDDING_DIM = 1536



def check_database(driver: Driver, database_name:str):
    """checks if database exists if not makes a new database"""

    with driver.session(database="system") as session:
        session.run(f"CREATE DATABASE {database_name} IF NOT EXISTS")


def apply_schema(driver: Driver, index_name:str, database_name:str, embedding_dim:int):
    # Initialize the official Neo4j driver
    with driver.session(database=database_name) as session:
        session.run(f"""
            CREATE VECTOR INDEX {index_name} IF NOT EXISTS
            FOR (n:Chunk) ON (n.embedding)
            OPTIONS {{indexConfig: {{
            `vector.dimensions`: {embedding_dim},
            `vector.similarity_function`: 'cosine'
            }}}}
        """)
