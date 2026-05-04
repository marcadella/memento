from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.llm import OpenAILLM
from neo4j_graphrag.embeddings import OpenAIEmbeddings


from neo4j import Driver


#number of neighbours to retrieve
TOP_K_RESULTS = 5
DATABASE_INSTANCE = "mementoRAG"


def search(driver: Driver, query):

    # 2. Initialize the Vector Retriever (No graph traversal)
    retriever = VectorRetriever(
        driver=driver,
        index_name="chunk_vector_index",
        embedder=OpenAIEmbeddings()
    )

    retrieval_results = retriever.get_search_results(query_text=query, top_k=TOP_K_RESULTS)

    return retrieval_results


def add_vector_data(driver: Driver, chunk_id, text, embedding):
    with driver.session(database=DATABASE_INSTANCE) as session:
        session.run("""
            MERGE (c:Chunk {id: $id})
            SET c.text = $text,
                c.embedding = $vector
            """, id=chunk_id, text=text, vector=embedding)
