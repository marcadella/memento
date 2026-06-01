from generics.agent import AgentLike
from memories.RAGMemory import RAGMemory
from processes.RAGprocess import RAGRetrieveProcess, NonRAGProcess
from utilities.Message import Message


class RAGAgent(AgentLike):
    """
    A simple agent with a RAG memory.
    """
    def __init__(self, name: str, client, model="gpt-4.1-mini", verbose=False, max_context_length_char=100000):
        super().__init__(name, verbose)
        self.rag_memory = RAGMemory(name, client, model)
        self.registered_commands = {
            "retrieve": "Prints the content that is related to the query",
            "tokens": "Prints the sum of token used."
        }
        store = self.rag_memory.get_store_tooling()
        retrieve = self.rag_memory.get_retrieve_tooling()

        self.speak_process = RAGRetrieveProcess(name, client, model, retrieve["func"], self.rag_memory, max_char_context=max_context_length_char)

        #naive context process handles rest
        self.context_max_messages = 40
        self.context_messages = []

    def speak(self) -> str:
        """
        In this implementation, we react to the context.
        """

        output = self.speak_process.apply(self.context_messages)
        return output

    def hear(self, speaker_name: str, content: str):
        """In this implementation, each new message is ...
        """

        role = "assistant" if speaker_name == self.name else "user"
        #basically used to format the text
        msg = Message(role=role, content=content, name=speaker_name)

        self.add_to_context(msg)


        #give context to hopefully get better saving results
        self.rag_memory.put(self.context_messages)


    def add_to_context(self, msg):
        self.context_messages.append(msg)

        #cut context when too long
        if len(self.context_messages) > self.context_max_messages:
            self.context_messages = self.context_messages[-self.context_max_messages:]


    def retrieve(self, query = None):
        """
        Get the content from rag base on query
        :return:
        """
        return "\n".join([m for m in self.rag_memory.get(query)])

    def tokens(self, last_n=0):
        """
        Get the completion, prompt and total token counts of all the processes.
        :param last_n: Only last n responses. If 0 (default), return sum for all responses.
        :return: String.
        """
        completion_tokens = self.speak_process.tokens("completion", last_n)
        prompt_tokens = self.speak_process.tokens("prompt", last_n)
        total_tokens = self.speak_process.tokens("total", last_n)

        store_completion_tokens = self.rag_memory.store_process.tokens("completion", last_n)
        store_prompt_tokens = self.rag_memory.store_process.tokens("prompt", last_n)
        store_total_tokens = self.rag_memory.store_process.tokens("total", last_n)

        return "\n".join(["Speak:,"
                          f"- completion_tokens: {completion_tokens}",
                          f"- prompt_tokens: {prompt_tokens}",
                          f"- total_tokens: {total_tokens}",
                          "Hear:"
                          f"- completion_tokens: {store_completion_tokens}",
                          f"- prompt_tokens: {store_prompt_tokens}",
                          f"- total_tokens: {store_total_tokens}",])
    
    def clear_all_context(self):
        """clears context from agent and clears database"""

        self.context_messages = []
        self.rag_memory.erase_data()

class NonRAGAgent(AgentLike):
    """
    A simple agent without RAG memory.
    used for comparing the performance of rag agent
    """
    def __init__(self, name: str, client, model="gpt-4.1-mini", verbose=False, max_context_length_char=40000):
        super().__init__(name, verbose)
        self.registered_commands = {
            "retrieve": "Prints the content that is related to the query",
            "tokens": "Prints the sum of token used."
        }

        self.speak_process = NonRAGProcess(name, client, model, max_char_context=max_context_length_char)

        #naive context process process handles rest
        self.context_max_messages = 40
        self.context_messages = []

    def speak(self) -> str:
        """
        In this implementation, we react to the context.
        """
        output = self.speak_process.apply(self.context_messages)

        return output

    def hear(self, speaker_name: str, content: str):
        """In this implementation, each new message is ...
        """
        role = "assistant" if speaker_name == self.name else "user"
        #basically used to format the text
        msg = Message(role=role, content=content, name=speaker_name)

        self.add_to_context(msg)


    def add_to_context(self, msg):
        self.context_messages.append(msg)

        #cut context when too long
        if len(self.context_messages) > self.context_max_messages:
            self.context_messages = self.context_messages[-self.context_max_messages:]

    def clear_all_context(self):
        """clears context from agent"""

        self.context_messages = []


    def tokens(self, last_n=0):
        """
        Get the completion, prompt and total token counts of all the processes.
        :param last_n: Only last n responses. If 0 (default), return sum for all responses.
        :return: String.
        """
        completion_tokens = self.speak_process.tokens("completion", last_n)
        prompt_tokens = self.speak_process.tokens("prompt", last_n)
        total_tokens = self.speak_process.tokens("total", last_n)


        return "\n".join(["Speak:,"
                          f"- completion_tokens: {completion_tokens}",
                          f"- prompt_tokens: {prompt_tokens}",
                          f"- total_tokens: {total_tokens}"])