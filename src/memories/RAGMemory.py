

"""
RAG-based memory using Neo4j.

"""

from generics.memory import MemoryLike
from neo4j import Driver
from rag.connection import make_driver
from rag.database import apply_schema, check_database

from processes.RAGprocess import RAGRetrieveProcess, RAGStoreProcess
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from neo4j_graphrag.retrievers import VectorRetriever
from utilities.Message import Message

from uuid import uuid4

class RAGMemory(MemoryLike):
    def __init__(self, name, client, model, database_name:str="neo4j", top_k_results:int=5, index_name:str="chunk_vector_index"):
        """
        args:
            database_name(optional): is the name of the database to target
            top_k_results(optional): is the amount of results it will retrieve
            index_name(optional): used to specify vector index
        """
        super().__init__()
        
        
        self.store_process = RAGStoreProcess(name, client, model, self.store_RAG_data)
        
        #no need to have a retrieve process query should be enough to find correct data
        #self.retrieve_process = RAGRetrieveProcess(name, client, model, self.retrieve_RAG_data)
        
        # Initialize the Neo4j driver
        self.driver:Driver = make_driver()
        

        self.database_name = database_name

        #ensure database exists
        check_database(self.driver, self.database_name)

        #initialize embedder to use
        self.embedder = OpenAIEmbeddings(model="text-embedding-3-small", 
                                         api_key= client.api_key,
                                         base_url= client.base_url)
        embedding_dim = 1536

        #ensure that scheema exists
        apply_schema(self.driver, index_name, self.database_name, embedding_dim)
        
        self.database_name = database_name
        
        self.index_name = index_name
        
        #initialize retriever
        self.retriever = VectorRetriever(
            driver=self.driver,
            index_name=index_name,
            embedder= self.embedder,
            neo4j_database= self.database_name
        )
        
        self.top_k_results = top_k_results
        
        #will need to make it find the largest id for the data to be persistent between runs


    def store_RAG_data(self, text):
        """
        Stores text content as nodes with vector embeddings in Neo4j.
        """
        
        print(f"store used for:\n {text}")


        #add some preprocessing here. for example cut text if too long, make text  more consise
        
        chunk = text
        
        with self.driver.session(database=self.database_name) as session:
            # Generate embedding for the text
            vector = self.embedder.embed_query(text)
            


            # Cypher query to create nodes with properties and vector embeddings
            query ="""
            MERGE (c:Chunk {id: $id})
            SET c.text = $text,
            c.embedding = $vector
            """        
            session.run(query, id=uuid4().int % 16000, text=chunk, vector=vector)
                            
        


    def retrieve_RAG_data(self, query):
        """
        Retrieves context using vector search 
        """

        print(f"retrieve used:\n{query}")

        retrieval_results = self.retriever.get_search_results(query_text=query, top_k=self.top_k_results)

        l = [record.data()["node"]["text"] for record in retrieval_results.records]

        print("\n".join(l))

        return l


    def put(self, data: Message | str, metadata=None, use_llm_process = True):
        
        #Is to check if one should use and llm to process the data before adding to memory
        if use_llm_process == True:
            self.store_process.apply(data)

        else:
            print("hello\n\n\n")
            if isinstance(data, Message):
                data = data.to_string()

            self.store_RAG_data(data)

    def get(self, query=None) -> list:

        #query cannot be None. query = None is here for compatability with memory generic
        if query == None:
            return []
        
        
        return self.retrieve_RAG_data(query)



    def get_store_tooling(self) -> dict:
        """
        Returns the api, the explanation and callable function for the store tool
        returns a dictionary like this:\n
        {"explanation: "explanation of tool", "api": "api used", "func": <function to call>}"""

        api = {
            "type": "function",
                "function": {
                    "name": "store_RAG_data", # Name must match implementation
                    "description": "Save data to RAG database for long term memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "text to save to RAG database. It should be relatively short, consise, mostly self contained and easy to undestand, but enough to be understandable when retrieved"
                            },
                        },
                        "required": ["text"]
                    }
                }
        }

        explanation = ("You have access to long-term memory with a toolcall"
                    "You have a tool called 'store_RAG_data' that you can use to store important information."
                    "Strategy: Use 'store_RAG_data' to store information like information, facts, or context that is important. It does not need to be information provided by the user. "
                    "It can also be information that has been reasoned or a decision that have been made during the task."
                    "The information stored should be in the form of paragraphs"
                    "Do not store information as just a single word or a sentence that is without context")


        return {"api": api, "explanation": explanation, "func": self.store_RAG_data}

    def get_retrieve_tooling(self) -> dict:
        """returns the api, the explanation and callable function for the retrieve tool
        returns a dictionary like this:\n
        {"explanation: "explanation of tool", "api": "api used", "func": <function to call>}"""

        api = {
            "type": "function",
            "function": {
                "name": "retrieve_RAG_data", 
                "description": "Retrieve a piece of important information, facts, or context from long-term memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description":  "The query used to search for relevant information"
                        },
                    },
                    "required": ["query"]
                }
            }
        }

        explanation = ("You have access to long-term memory with a toolcall"
                    "You have a tool called 'retrieve_RAG_data' that you can use to look up information."
                    "Strategy: If you have task you don't have all relevant information for, use 'retrieve_RAG_data'. "
                    "It does not only contain information provided by the user. It can also be information that has been reasoned or a decision that been have made during the task.")

        return {"api": api, "explanation": explanation, "func": self.retrieve_RAG_data}
