from generics.agent import AgentLike
from memories.KeyValueMemory import KeyValueMemory
from processes.ReactInConversationProcess import ReactInConversationProcess


class DummyAgent(AgentLike):
    """
    A simple agent with an infinite context memory and an ability to store important information in a dictionary (this memory is not used for anything though).
    """

    def __init__(self, name: str, client, model):
        super().__init__(name, verbose=True)
        self.processes = {
            "react": ReactInConversationProcess("react", client, model, name),
            "memorize": KeyValueMemory("memorize", client, model),
        }
        self.history = [] #Infinite memory

    def speak(self):
        """
        In this implementation, we react to the unbounded memory.
        Note that the keyValueMemory could be used here.
        """
        return self.processes["react"].apply(self.history)

    def hear(self, speaker_name: str, message: str):
        """In this implementation, each new message is analysed by the KeyValueMemory process:
          - if something is worth storing in the memory, the LLM makes a call to a storage function (one or more times)
          - if nothing is interesting, the LLM do nothing.
          Then we append the message to the unbounded history.
        """
        role = "assistant" if speaker_name == self.name else "user"
        self.processes["memorize"].apply(message)
        self.history.append({"role": role, "content": message, "name": speaker_name})