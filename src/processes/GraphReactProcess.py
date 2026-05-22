"""React process for an agent with graph memory.

Gives the LLM a retrieval tool so it can pull facts from the graph
when it needs them, then react to the conversation.
"""

from generics.process import ProcessLike
from utilities.Message import Message


class GraphReactProcess(ProcessLike):
    """Speak process for GraphAgent.

    Registers the graph retrieval tool so the LLM can call it
    on-demand. The system prompt explains when to use the tool.
    """

    def __init__(self, process_name, client, model, agent_name, retrieve_tooling: dict):
        """
        Args:
            process_name: Identifier for this process in verbose mode.
            client: OpenAI / AzureOpenAI client.
            model: Chat model or Azure deployment name.
            agent_name: Name of the agent, used in the system prompt.
            retrieve_tooling: Dict returned by
                GraphMemory.get_retrieve_tooling(), containing the API
                schema, explanation, and callable.
        """
        super().__init__(process_name, client, model)
        self.agent_name = agent_name

        # Unpack the tooling dict so the dispatcher can find the
        # callable by name. The base class's apply() looks up the
        # method via getattr(self, function.name), so we expose the
        # callable under that same name on self.
        self.retrieve_from_graph = retrieve_tooling["func"]
        self.retrieve_explanation = retrieve_tooling["explanation"]
        self.functions.append(retrieve_tooling["api"])

    def messages(self, context: list[Message]) -> list[Message]:
        """Build the prompt: system instructions + tool explanation + history."""
        system_content = (
            f"Your name is '{self.agent_name}' and you are part of a "
            f"conversation with one or more users. Respond naturally to "
            f"the conversation.\n\n"
            f"{self.retrieve_explanation}"
        )
        return [Message(role="system", content=system_content)] + context