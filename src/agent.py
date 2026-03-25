from abc import ABC, abstractmethod

from process import ProcessLike


class AgentLike(ABC):
    """
    An agent is an entity encompassing a set of processes
    """
    def __init__(self, name: str):
        self.name = name
        self.processes: dict = {} # Implementations should fill this with ProcessLike

    @abstractmethod
    def speak(self):
        pass

    @abstractmethod
    def hear(self, speaker_name: str, monologue: str):
        pass


class HumanAgent(AgentLike):
    """
    A special kind of agent allowing user to be part of, and interact with, an agent team.
    """

    def __init__(self, name: str):
        super().__init__(name)

    def speak(self):
        return input(f"{self.name}: ")

    def hear(self, speaker_name: str, monologue: str):
        if speaker_name != self.name:
            print(f"'{speaker_name}' says: {monologue}")

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
        self.processes = {"reaction": self.ReactProcess("reaction", client, model, name)}
        self.history = []

    def speak(self):
        return self.processes["reaction"].apply(self.history)

    def hear(self, speaker_name: str, monologue: str):
        role = "assistant" if speaker_name == self.name else "user"
        name = None if speaker_name == self.name else speaker_name
        self.history.append({"role": role, "content": monologue, "name": name})