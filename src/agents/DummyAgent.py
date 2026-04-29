from generics.agent import AgentLike
from generics.process import ProcessLike
from memories.KeyValueMemory import KeyValueMemory


class DummyAgent(AgentLike):
    """
    A simple agent with an infinite context memory and an ability to store important information in a dictionary (this memory is not used for anything though).
    """

    class ReactProcess(ProcessLike):
        def __init__(self, process_name, client, model, agent_name):
            super().__init__(process_name, client, model)
            self.agent_name = agent_name

        def messages(self, context):
            return [{"role": "system", "content": f"Your name is '{self.agent_name}' and you are part of a conversation with multiple users. "
                                                  f"You may answer with an empty string if you have nothing important to say and want to pass your turn to speak. "}] + context

    def __init__(self, name: str, client, model):
        super().__init__(name)
        self.processes = {
            "react": self.ReactProcess("react", client, model, name),
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