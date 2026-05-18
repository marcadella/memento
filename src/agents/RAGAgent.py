from generics.agent import AgentLike
from memories.RAGMemory import RAGMemory
from processes.RAGprocess import RAGRetrieveProcess, RAGStoreProcess
from utilities.Message import Message


class RAGAgent(AgentLike):
    """
    A simple agent with a RAG memory (bounded rolling context).
    """
    def __init__(self, name: str, client, model="gpt-4.1-mini", verbose=False):
        super().__init__(name, verbose)
        self.rag_memory = RAGMemory(name, client, model)
        self.registered_commands = {
            "retrieve": "Prints the content that is related to the ",
            "tokens": "Prints the sum of token used."
        }
        store = self.rag_memory.get_store_tooling()
        retrieve = self.rag_memory.get_retrieve_tooling()

        self.speak_process = RAGRetrieveProcess(name, client, model, retrieve["func"])

        #naive context
        self.context_max_size = 100
        self.context_text = ""

    def speak(self) -> str:
        """
        In this implementation, we react to the context.
        """

        output = self.speak_process.apply(self.context_text)



        return output

    def hear(self, speaker_name: str, content: str):
        """In this implementation, each new message is ...
        """

        print(content)

        role = "yourself" if speaker_name == self.name else "user"
        #basically used to format the text
        msg = Message(role=role, content=content, name=speaker_name)

        #give context to hopefully get better saving results
        self.rag_memory.put("".join(["For context:\n", self.context_text, "\nNew message:\n", msg.to_string()]))

        self.add_to_context(msg)

    def add_to_context(self, msg):
        self.context_text = self.context_text + "\n" + msg.to_string()

        #cut context when too long
        if len(self.context_text) > self.context_max_size:
            self.context_text = self.context_text[-self.context_max_size:]


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