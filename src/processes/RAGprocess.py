from asyncio.windows_events import NULL

from generics.process import ProcessLike
from pydantic import InstanceOf
from utilities.Message import Message
from utilities.Context import ctx
import json
from dataclasses import asdict


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
                            "description": "text to save to long term memory. It should be a not longer than a paragraph, consise, mostly self contained and easy to undestand, but enough to be understandable when retrieved"
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


        context = [ 
            Message(role="system",
                content=
                    "You have access to long-term memory with a toolcall"
                    "You have a tool called 'store_RAG_data' that you can use to store important information."
                    "Strategy: Use 'store_RAG_data' to store information like information or facts. Store information that is logically connected to eachother together and store information that is unrelated as separate toolcalls"
                    "The information stored should be in the form of paragraphs"
                    "Do not store information as just a single word or a sentence that is without context" 
                    "You can do as many toolcalls as deem necessary, or no toolcalls if there is nothing you should store"
                    "Your only task is to store all information that is important, ignore all questions and tasks that the user ask"
                    "Do not answer questions or do tasks. Do not store the answer to the question to the long term memory" 
                    "Only store data that is from the latest message"
                    "Do not store data that is already mentioned in the previous messages"
                    "Example: 'previous messages: user -> my car is red New message: assistant -> users car is red' in this example do not use the toolcall since the only information is that the car is red, but that is already explained in previous messages and therefore it is already stored."
                    "Don't store the same information more than once"
                    "IMPORTANT: Do not store questions from the user or when the user asking you to do something. Do not store your opinions about it"
                    "First check if what the user says is a question or task. If it is a question or task, do not do any toolcalls. If not, store information that is new"
                    "Example: 'user -> what is the color of my car?' in this circumstance you should not do a toolcall"
                    "Do not say anything if there is nothing to store"
            )
        ]

      
        if isinstance(data, str):
            context.append(Message(role="user", content=data))
        elif isinstance(data, Message):
            context.append(data)
        elif isinstance(data,list):
            for m in data:
                if isinstance(m, Message):
                    context.append(m)
        else:
            print("wrong datatype given to messages")

        return context
    
        
        
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


        context = [ 
            Message(role="system",
                content=
                    "You have access to long-term memory with a tool call. "
                    "You have a tool called 'retrieve_RAG_data' that you can use to look up information. "
                    "Strategy: If you have task you don't have all relevant information for, use 'retrieve_RAG_data'. "
                    "It does not only contain information provided by the user. It can also be information that has been reasoned or a decision that been have made during the task. "
                    "Use the information that is retrieved to make a answer the task. The user does not see the retrieved result. "
            )
        ]

      
        if isinstance(data, str):
            context.append(Message(role="user", content=data))
        elif isinstance(data, Message):
            context.append(data)
        elif isinstance(data,list):
            for m in data:
                if isinstance(m, Message):
                    context.append(m)
        else:
            print("wrong datatype given to messages")

        return context


    def apply(self, data) -> str:
        """
        Given a context, computes an output using an LLM.
        This is the main action performed by a process.

        :param data: Some input data
        :return: LLM response message
        """
        ctx.append(self.process_name)
        #print(ctx.current_path())
        #print(self.messages(context))


        messages = [asdict(m) for m in self.messages(data)]

        return_value =""

        #max 10 toolcalls
        for _ in range(10):
                
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.functions
            )
            self.usages.append(response.usage)
            response = response.choices[0]


            #so it can remember what it said
            if response.message.content:
                messages.append({"role": "assistant",
                            "content": response.message.content})


            if response.message.tool_calls is not None:
                for tool_call in response.message.tool_calls:
                    function = tool_call.function
                    fn = getattr(self, function.name)
                    print(f"Process '{self.process_name}' calling {function.name} function")
                    result = fn(**json.loads(function.arguments))

                    # To add the return value of the toolcall
                    messages.append({"role": "user",
                                     "tool_call_id": tool_call.id,
                                     "content": str(result)})
                    


            if response.finish_reason == "stop":
                return_value = response.message.content
                #if no toolcall
                break

            

        ctx.pop()

        return return_value


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

        context = [ 
            Message(role="system",
                content="\n".join((self.store_explanation,
                                    self.retrieve_explanation,
                                    f"Current User Message: '{data}'"))
            )
        ]

        if isinstance(data, str):
            context.append(Message(role="user", content=data))
        elif isinstance(data, Message):
            context.append(data)
        elif isinstance(data,list):
            for m in data:
                if isinstance(m, Message):
                    context.append(m)
        else:
            print("wrong datatype given to messages")

        return context