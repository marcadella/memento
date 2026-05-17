from generics.agent import AgentLike
from memories.FlashMemory import FlashMemory
from memories.KeyValueMemory import KeyValueMemory
from processes.ReactInConversationProcess import ReactInConversationProcess
from utilities.Message import Message


class DummyAgent(AgentLike):
    """
    A simple agent with an infinite context memory and an ability to store important information in a dictionary (this memory is not used for anything though).
    """

    def __init__(self, name: str, client, model):
        super().__init__(name, verbose=True)
        self.react_processes = ReactInConversationProcess("react", client, model, name)
        self.kv_memory = KeyValueMemory(name, client, model)
        self.unbound_memory = FlashMemory(-1)

    def speak(self):
        """
        In this implementation, we react to the unbounded memory.
        Note that the keyValueMemory could be used here.
        """
        return self.react_processes.apply(self.unbound_memory.get())

    def hear(self, speaker_name: str, content: str):
        """In this implementation, each new message is analysed by the KeyValueMemory process:
          - if something is worth storing in the memory, the LLM makes a call to a storage function (one or more times)
          - if nothing is interesting, the LLM do nothing.
          Then we append the message to the unbounded history.
        """
        role = "assistant" if speaker_name == self.name else "user"
        self.kv_memory.put(content)
        message = Message(role=role, content=content, name=speaker_name)
        self.unbound_memory.put(message)