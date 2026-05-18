from generics.process import ProcessLike
from utilities.Message import Message


#to stop circular imports while still using type hints
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from memories.RAGMemory import RAGMemory
    

class RAGStoreProcess(ProcessLike):
    def __init__(self, name, client, model, store_RAG_data):
        super().__init__(name, client, model)
        
        store_RAG_data_API = {
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
        
        self.store_RAG_data = store_RAG_data
        
        self.functions.append(store_RAG_data_API)
        
    def messages(self, data):
        """
        Provides the LLM with the instruction that it has access to search and store tools.
        The actual retrieval only happens IF the LLM decides to call 'retrieve_RAG_data'.
        and storing only happens IF the LLM decides to call 'store_RAG_data'.
        """
        return [Message(role="system",
                content=
                    "Your only task is to store all information that is important"
                    "You will not answer questions or do other tasks" 
                    "Nor are you to evaluate what is said"
                    "Only store data that is after the 'new message:' data before it has already been processed"
                    "Don't store the same information more than once"
                    "IMPORTANT: Do not store anything about questions from the user or when asking you to do something. Do not store your opinions about it"
                    "Do not say anything if there is nothing to store"
                    "Example: if user says: what color is my car?"
                    "DO NOT STORE: User asked the question: What color is my car?"
                    "always sign what you store with '- <your name>'"
                    "You have access to long-term memory with a toolcall"
                    "You have a tool called 'store_RAG_data' that you can use to store important information."
                    "Strategy: Use 'store_RAG_data' to store information like information or facts."
                    "The information stored should be in the form of paragraphs"
                    "Do not store information as just a single word or a sentence that is without context"
                    f"Current context: \n'{data}'"
            )
        ]
    
        
        
class RAGRetrieveProcess(ProcessLike):
    def __init__(self, name, client, model, retrieve_RAG_data):
        super().__init__(name, client, model)
        
        retrieve_RAG_data_API = {
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
        
        self.retrieve_RAG_data = retrieve_RAG_data
                
        self.functions.append(retrieve_RAG_data_API)
        
        
    def messages(self, data):
        """
        Provides the LLM with the instruction that it has access to search and store tools.
        The actual retrieval only happens IF the LLM decides to call 'retrieve_RAG_data'.
        and storing only happens IF the LLM decides to call 'store_RAG_data'.
        """
        return [ 
            Message(role="system",
                content=
                    "You have access to long-term memory with a tool call."
                    "You have a tool called 'retrieve_RAG_data' that you can use to look up information."
                    "Strategy: If you have task you don't have all relevant information for, use 'retrieve_RAG_data'. "
                    "It does not only contain information provided by the user. It can also be information that has been reasoned or a decision that been have made during the task."
                    "Use the information that is retrieved to make a answer the task. The user does not see the retrieved result"
                    f"Current User Message: '{data}'"
            )
        ]
    


class RAGProcess(ProcessLike):

    """
    This process has the capability to store and retrieve data from a RAG database when it needs to.
    """
    #to stop circular imports
    def __init__(self, name, client, model, RAG_memory: RAGMemory):
        super().__init__(name, client, model)
        


        self.rag_memory = RAG_memory
        store = self.rag_memory.get_store_tooling()
        retrieve = self.rag_memory.get_retrieve_tooling()

        store_RAG_data_API = store["api"] 
        self.store_RAG_data = store["func"]
        self.store_explanation = store["explanation"]


        retrieve_RAG_data_API = retrieve["api"] 
        self.retrieve_RAG_data = retrieve["func"]
        self.retrieve_explanation = retrieve["explanation"]

                
        self.functions.append(store_RAG_data_API)
        self.functions.append(retrieve_RAG_data_API)
        
        
    def messages(self, data):
        """
        Provides the LLM with the instruction that it has access to search and store tools.
        The actual retrieval only happens IF the LLM decides to call 'retrieve_RAG_data'.
        and storing only happens IF the LLM decides to call 'store_RAG_data'.
        """
        return [ 
            Message(role="system",
                content="\n".join((self.store_explanation,
                                    self.retrieve_explanation,
                                    f"Current User Message: '{data}'"))
            )
        ]