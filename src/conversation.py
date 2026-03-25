import json
import os
from abc import ABC, abstractmethod
from agent import AgentLike, HumanAgent
from datetime import datetime


class ConversationLike(ABC):
    """
    A place where some agents can talk together.
    If an existing conversation_name is provided, the conversation is resumed.
    """
    def __init__(self, agents: list[AgentLike], output_dir, conversation_name):
        self.agents = {agent.name: agent for agent in agents}
        self.tape = []
        self.output_dir = output_dir # Set to None for no recording
        conversation_name = max(os.listdir(self.output_dir)) if conversation_name == "latest" else conversation_name
        self.conversation_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") if conversation_name is None else conversation_name

    def speak(self, speaker_name: str):
        """
        Ask an agent to speak.
        :param speaker_name:
        """
        message: str = self.agents[speaker_name].speak()
        if message:
            self.tape += [{speaker_name: message}]
            for agent in self.agents.values():
                agent.hear(speaker_name, message)

    def start(self, enact=False, quiet=True):
        """
        Start a conversation.
        :param enact: Used only when resume mode is used. If False, agents past answers are replayed as is. If True, agents are speaking by themselves in the re-played conversation.
        :param quiet: Used only when resume mode is used. If False, history/re-enactment is printed.
        """
        if self.conversation_name:
            self.reload(enact, quiet)
        
        print(self.introduction())

        print(f"List of participating agents:")
        for agent in self.agents.values():
            print(f"  - {agent.name}")

        while self.turn():
            continue

        self.write_to_file()

    def reload(self, enact, quiet):
        """
        Reload a conversation.
        :param enact: If False, agents past answers are replayed as is. If True, agents are speaking by themselves in the re-played conversation.
        :param quiet: If False, history/re-enactment is printed.
        """
        conv_path = f"{self.output_dir}/{self.conversation_name}.json"
        if os.path.exists(conv_path):
            verb = "Reenacting" if enact else "Reloading"
            print(f"{verb} conversation {self.conversation_name}...")
            with open(f"{self.output_dir}/{self.conversation_name}.json", "r", encoding="utf-8") as f:
                original_tape = json.load(f)
        else:
            print(f"New conversation {self.conversation_name}")
            original_tape = []
        for line in original_tape:
            for speaker_name, message in line.items(): # Should be only one item
                if enact and type(self.agents[speaker_name]) != HumanAgent:
                    # If re-enacting, we replace the original message with a new one
                    message = self.agents[speaker_name].speak()
                self.tape += [{speaker_name: message}]
                if not quiet:
                    print(f"{speaker_name}: {message}")

                for agent in self.agents.values():
                    if type(agent) is not HumanAgent:
                        agent.hear(speaker_name, message)

    def write_to_file(self):
        """
        Write the conversation into file.
        """
        if self.output_dir:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
            with open(f"{self.output_dir}/{self.conversation_name}.json", "w", encoding="utf-8") as f:
                json.dump(self.tape, f, indent=2)

    @abstractmethod
    def introduction(self):
        """
        A string to instruct the user how to use this conversation.
        :return: String
        """
        pass

    @abstractmethod
    def turn(self):
        """
        Conversation turn
        :return: True if the conversation continues, False if it should stop.
        """
        pass

class InteractiveConversation(ConversationLike):
    """
    An interactive conversation where each turn, the first human registered controls who speak (or speak himself).
    """
    def __init__(self, agents: list[AgentLike], output_dir="output", conversation_name=None):
        super().__init__(agents, output_dir, conversation_name)
        self.human_agent = [agent for agent in agents if type(agent) == HumanAgent][0]

    def introduction(self):
        return f"\nInteractive conversation directed by {self.human_agent.name}.\nSay something or give turn to an AI agent by typing its name. Enter empty input to terminate the conversation."

    def turn(self):
        human_input = self.human_agent.speak()
        if not human_input:
            return False
        if human_input in self.agents.keys():
            # If used entered the name of an agent, the latter is invited to speak
            self.speak(human_input)
        else:
            self.tape += [{self.human_agent.name: human_input}]
            for agent in self.agents.values():
                agent.hear(self.human_agent.name, human_input)

        return True

