from generics.process import ProcessLike
from utilities.Message import Message


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
                                "description": "text to save to RAG database. It should be short and consise and easy to undestand, but still say enough to be understandable when retrived"
                            },
                        },
                        "required": ["text"]
                    }
                }
        }
        
        self.functions.append(store_RAG_data_API)
        
    def messages(self, context):
        """
        Provides the LLM with the instruction that it has access to search and store tools.
        The actual retrieval only happens IF the LLM decides to call 'retrive_RAG_data'.
        and storing only happens IF the LLM decides to call 'store_RAG_data'.
        """
        return [Message(role="system",
                content=
                    "You have access to long-term memory."
                    "For this memory you have a tool at your disposal:"
                    "You have a tool called 'retrive_RAG_data' that you can use to look up information."
                    "Strategy: Use 'store_RAG_data' to store information like information, facts, or context. It does not need to be information provided by the user. It can also be information that you have reasoned or a decision you have made to during the task."
                    f"Current User Message: '{context}'"
            )
        ]
    
        
        
class RAGRetrieveProcess(ProcessLike):
    def __init__(self, name, client, model, store_RAG_data):
        super().__init__(name, client, model)
        
        retrive_RAG_data_API = {
            "type": "function",
                "function": {
                    "name": "retrive_RAG_data", 
                    "description": "Save a piece of important information, facts, or context into long-term memory for future retrieval.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description":  "The text content/fact that needs to be memorized."
                            },
                        },
                        "required": ["query"]
                    }
                }
        }
        
        self.functions.append(retrive_RAG_data_API)
        
        
    def messages(self, context):
        """
        Provides the LLM with the instruction that it has access to search and store tools.
        The actual retrieval only happens IF the LLM decides to call 'retrive_RAG_data'.
        and storing only happens IF the LLM decides to call 'store_RAG_data'.
        """
        return [ 
            Message(role="system",
                content=
                    "You have access to long-term memory."
                    "For this memory you have a tool at your disposal:"
                    "You have a tool called 'retrive_RAG_data' that you can use to look up information."
                    "Strategy: If you have task you don't have all relevant information for, use 'retrive_RAG_data'. It does not need to be information provided by the user. It can also be information that you have reasoned or a decision you have made to during the task."
                    f"Current User Message: '{context}'"
            )
        ]