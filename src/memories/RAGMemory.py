

"""
RAG-based memory using Neo4j.

"""



from generics.memory import MemoryLike
from neo4j import Driver
from rag.connection import make_driver
from rag.schema import apply_schema

from processes.RAGprocess import RAGRetrieveProcess, RAGStoreProcess

from neo4j_graphrag.embeddings import OpenAIEmbeddings
from neo4j_graphrag.retrievers import VectorRetriever


#from neo4j import GraphDatabase
#from neo4j_graphrag.llm import OpenAILLM
#from neo4j_graphrag.generation import GraphRAG

class RAGMemory(MemoryLike):
    def __init__(self, name, client, model, instance_name:str="mementoRAG", top_k_results:int=5, index_name:str="chunk_vector_index"):
        """
        args:
            instance_name(optional): is the name of the instance to target
            top_k_results(optional): is the amount of results it will retrieve
            index_name(optional): used to specify vector index
        """
        super().__init__()
        
        
        self.store_process = RAGStoreProcess(name, client, model, self.store_RAG_data)
        self.retrieve_process = RAGStoreProcess(name, client, model, self.retrieve_RAG_data)
        
        # Initialize the Neo4j driver
        self.driver:Driver = make_driver()
        
        #ensure that scheema exists
        apply_schema(self.driver)
        
        #initialize embedder to use
        self.embedder = OpenAIEmbeddings(model="text-embedding-3-small")
        
        self.instance_name = instance_name
        
        self.index_name = index_name
        
        #initialize retriever
        self.retriever = VectorRetriever(
            driver=self.driver,
            index_name=index_name,
            embedder= self.embedder,
            neo4j_database= self.instance_name
        )
        
        self.top_k_results = top_k_results
        
        #will need to make it find the largest id for the data to be persistent between runs
        self.id_counter=0


    def store_RAG_data(self, text):
        """
        Stores text content as nodes with vector embeddings in Neo4j.
        """
        
        #add some preprocessing here. for example cut text if too long, make text  more consise
        
        content_list = [text]
        
        with self.driver.session(database=self.instance_name) as session:
            for chunk in content_list:
                # Generate embedding for the text
                vector = self.embedder.embed_query(text)
                
                # Cypher query to create nodes with properties and vector embeddings
                query ="""
                MERGE (c:Chunk {id: $id})
                SET c.text = $text,
                c.embedding = $vector
                """        
                session.run(query, id=self.id_counter, text=chunk, vector=vector)
                                
                self.id_counter += 1
        


    def retrieve_RAG_data(self, query):
        """
        Retrieves context using vector search 
        """
        retrieval_results = self.retriever.get_search_results(query_text=query, top_k=self.top_k_results)

        return retrieval_results

