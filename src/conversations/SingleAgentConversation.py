from agents.HumanAgent import HumanAgent
from conversations.InteractiveConversation import InteractiveConversation
from generics.agent import AgentLike


class SingleAgentConversation(InteractiveConversation):
    """
    A typical turn by turn conversation between a human and an agent.
    When typing an agent command, the name of the agent may be omitted.
    Ex: `>.speak` is equivalent to `>Caroline.speak`
    """
    def __init__(self, agent: AgentLike, human_agent=HumanAgent("H"), output_dir="output", conversation_name=None, override=False):
        self.agent = agent
        super().__init__([self.agent, human_agent], output_dir, conversation_name, override)

    def introduction(self):
        return super().introduction() + f"\nThe agent will answer after each of your turns."

    def turn(self, cmd=None):
        cmd = cmd if cmd is not None else input(f"{self.human_agent.name}: ")

        # To simplify, the user can omit the name of the agent when typing a command
        if cmd.startswith(">."):
            cmd = f">{self.agent.name}." + cmd[2:]

        cont = super().turn(cmd)

        if cmd.startswith(">"):
            return cont
        else:
            # It is the agent's turn
            return super().turn(f">{self.agent.name}")