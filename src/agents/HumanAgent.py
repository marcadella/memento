from generics.agent import AgentLike


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
