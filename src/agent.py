from abc import ABC, abstractmethod

from memory import KeyValueMemory
from process import ProcessLike


class AgentLike(ABC):
    """
    An agent is an entity encompassing a set of processes
    """
    def __init__(self, name: str):
        self.name = name
        self.processes: dict = {} # Implementations should fill this with ProcessLike

    @abstractmethod
    def speak(self) -> str:
        """
        Produce a message to be delivered to listeners
        :return: Message
        """
        pass

    @abstractmethod
    def hear(self, speaker_name: str, message: str):
        """
        Process a message delivered by some speaker.
        :param speaker_name: Name of the speaker
        :param message: Received message
        """
        pass


class HumanAgent(AgentLike):
    """
    A special kind of agent allowing human interaction.
    """

    def __init__(self, name: str):
        super().__init__(name)

    def speak(self):
        return input(f"{self.name}: ")

    def hear(self, speaker_name: str, message: str):
        if speaker_name != self.name:
            print(f"{speaker_name}: {message}")

class TestAgent(AgentLike):
    """
    A simple agent with an infinite context memory
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