from abc import ABC, abstractmethod


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
