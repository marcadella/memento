from abc import ABC, abstractmethod


class AgentLike(ABC):
    """
    An agent is an entity encompassing a set of processes
    """
    def __init__(self, name: str, verbose: bool):
        self.name = name
        self.verbose = verbose
        self.registered_commands = {}
        self.conv_dir = None # Output directory path
        # Configured by self.setup() (automatically called by ConversationLike)
        # Use self.name with an appropriate extension if you want to persist data
        #self.output = f"{self.conv_dir}/{self.name}.json

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

    def help(self):
        return "\n".join([f"- {com}: {descr}" for com, descr in self.registered_commands.items()])

    def setup(self, conv_dir):
        self.conv_dir = conv_dir

