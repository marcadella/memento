"""An agent backed by graph memory.

Wires together a GraphMemory for long-term recall, a FlashMemory for
recent conversational context, and a GraphReactProcess that gives the
LLM a tool to query the graph on demand.
"""

from generics.agent import AgentLike
from memories.FlashMemory import FlashMemory
from memories.GraphMemory import GraphMemory
from processes.GraphReactProcess import GraphReactProcess
from utilities.Message import Message


class GraphAgent(AgentLike):
    """Agent that uses graph memory for long-term recall.

    On hear():
        - Writes the message to FlashMemory (recent context).
        - Writes the message to GraphMemory (triples extracted, message
          stored, both with provenance).

    On speak():
        - Runs GraphReactProcess on the flash context. The LLM may
          decide to call the retrieval tool, which queries GraphMemory.
    """

    def __init__(self, name: str, client, driver, model="gpt-4.1-mini", verbose=False, flash_memory_size=10000):
        """
        Args:
            name: Agent's name. Used as agent_id in the graph.
            client: OpenAI / AzureOpenAI client.
            driver: Connected Neo4j driver. Caller manages its lifecycle.
            model: Chat model name or Azure deployment name.
            verbose: Verbose flag passed to AgentLike.
            flash_memory_size: Char budget for the rolling flash memory.
        """
        super().__init__(name, verbose)

        # Long-term memory backed by Neo4j. Owns its own extraction
        # process internally.
        self.graph_memory = GraphMemory(name=name, client=client, model=model, driver=driver)

        # Short-term rolling context. Same pattern as BaseAgent.
        self.flash_memory = FlashMemory(flash_memory_size)

        # The speak process. We hand it the retrieval tool so the LLM
        # can pull from graph memory on demand.
        retrieve_tooling = self.graph_memory.get_retrieve_tooling()
        self.react_process = GraphReactProcess(
            process_name=f"{name}.react",
            client=client,
            model=model,
            agent_name=name,
            retrieve_tooling=retrieve_tooling,
        )

        # Commands available via the interactive CLI (>agent_name.command).
        self.registered_commands = {
            "flash": "Print the flash memory contents.",
            "tokens": "Print token usage."
        }


    def speak(self) -> str:
        """Generate the agent's next message based on recent context.

        The LLM may call the retrieval tool to pull facts from graph
        memory before responding.
        """
        context = self.flash_memory.get()
        return self.react_process.apply(context)


    def hear(self, speaker_name: str, content: str):
        """Process an incoming message.

        Writes to both memories: flash for immediate context, graph for
        long-term recall.
        """
        role = "assistant" if speaker_name == self.name else "user"
        message = Message(role=role, content=content, name=speaker_name)

        # Recent context for the react process.
        self.flash_memory.put(message)

        # Long-term graph memory. Extraction happens inside put().
        self.graph_memory.put(message)


    def flash(self) -> str:
        """Return the flash memory contents as a string. CLI helper."""
        return "\n".join([m.to_string() for m in self.flash_memory.get()])


    def tokens(self, last_n=0) -> str:
        """Return token usage of the react process. CLI helper."""
        completion = self.react_process.tokens("completion", last_n)
        prompt = self.react_process.tokens("prompt", last_n)
        total = self.react_process.tokens("total", last_n)
        return "\n".join([
            f"- completion_tokens: {completion}",
            f"- prompt_tokens: {prompt}",
            f"- total_tokens: {total}",
        ])