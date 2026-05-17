from generics.process import ProcessLike
from utilities.Message import Message


class ReactToContextProcess(ProcessLike):
    """
    Example of output process where the LLM is requested to produce an answer given a context using a system prompt.
    The agent knows its name.
    """
    def __init__(self, process_name, client, model, agent_name):
        super().__init__(process_name, client, model)
        self.agent_name = agent_name

    def messages(self, context: list[Message])-> list[Message]:
        return [
            Message(
                role="system",
                content=f"Your name is '{self.agent_name}' and you are a useful agent. "
        )
        ] + context