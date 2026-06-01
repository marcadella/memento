from generics.process import ProcessLike
from utilities.Message import Message


class ReactInConversationProcess(ProcessLike):
    """
    Example of speaking process where the LLM is requested to produce an answer given a context using a system prompt.
    The agent knows its own name, and it is aware that there may be multiple users taking part in the discussion.
    """
    def __init__(self, process_name, client, model, agent_name, LOT):
        super().__init__(process_name, client, model)
        self.agent_name = agent_name
        self.LOT = LOT

    def messages(self, context: list[Message]) -> list[Message]:
        return [
            Message(
                role="system",
                content=f"Your name is '{self.agent_name}' and you are part of a conversation with multiple users. "
                        f"Your answers in this discussion should be driven by your line of thought: '{self.LOT.get()}'."
            )
        ] + context