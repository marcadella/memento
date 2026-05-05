from abc import ABC, abstractmethod


class AgentLike(ABC):
    """
    An agent is an entity encompassing a set of processes
    """
    def __init__(self, name: str, verbose: bool):
        self.name = name
        self.verbose = verbose

    @abstractmethod
    def speak(self) -> str:
        """
        Produce a message to be delivered to listeners
        :return: Message
        """
        pass

    @abstractmethod
    def hear(self, speaker_name: str, content: str):
        """
        Process a message delivered by some speaker.
        :param speaker_name: Name of the speaker
        :param content: Received message
        """
        pass
