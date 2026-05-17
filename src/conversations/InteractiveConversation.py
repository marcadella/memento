from agents.HumanAgent import HumanAgent
from generics.agent import AgentLike
from generics.conversation import ConversationLike


class InteractiveConversation(ConversationLike):
    """
    An interactive conversation where each turn, the first human registered controls who speak (or speak himself).
    """
    def __init__(self, agents: list[AgentLike], output_dir="output", conversation_name=None, override=False):
        super().__init__(agents, output_dir, conversation_name, override)
        self.human_agent = [agent for agent in agents if type(agent) == HumanAgent][0]

    def introduction(self):
        return (f"\nType your message, or use `>agent_name` to ask an agent to speak."
                f"\nYou may also call a method on the agent: `>agent_name.method`"
                f"\n`>agent_name.help` lists all the commands supported by that agent."
                f"\nEnter `>exit` input to terminate the conversation.")

    def turn(self, cmd=None):
        # Get input from user
        cmd = cmd if cmd is not None else input(f"{self.human_agent.name}: ")

        # Default values
        method = "speak"
        agent_name = self.human_agent.name
        message = cmd

        if cmd.startswith(">"):
            # If it is a command (prefix == '>')
            command = cmd[1:].strip()

            if command == "exit":
                return False

            # if the command is of the form >agent_name.method, we extract the method and the agent_name
            splt = command.split(".", 1)
            agent_name = splt[0]
            if len(splt) == 2:
                method = splt[1]

            if agent_name in self.agents.keys():
                # If the method does not exist, we print an error message
                message = getattr(self.agents[agent_name], method, lambda: f"Unknown method {method}")()
            else:
                # If the agent does not exist, we print an error message
                message = f"Unknown agent {agent_name}"
                method = ""

        if method == "speak":
            # If someone spoke, we add the content to the tape, and each agent is hearing
            if message:
                self.tape += [{agent_name: message}]
                for agent in self.agents.values():
                    agent.hear(agent_name, message)
        else:
            # Otherwise we just print the message along with a repeat of the command that caused it
            print(message + f"\n- - - {cmd} - - -")

        return True