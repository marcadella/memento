"""React process for an agent with graph memory.

Gives the LLM a retrieval tool so it can pull facts from the graph
when it needs them, then react to the conversation.
"""

import json
from dataclasses import asdict

from generics.process import ProcessLike
from utilities.Context import ctx
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
            f"Your name is '{self.agent_name}'. You are a person having a "
            f"casual conversation, NOT an assistant. Behave like someone "
            f"chatting with a friend.\n\n"
            f"Do this:\n"
            f"- Show curiosity. Ask follow-up questions about what the "
            f"other person says.\n"
            f"- Share your own thoughts, opinions, and reactions. You "
            f"are allowed to have preferences and a perspective.\n"
            f"- Keep replies short and conversational, usually one to "
            f"three sentences. Longer only when the topic clearly "
            f"warrants it.\n"
            f"- When asked about yourself, answer naturally and keep "
            f"any details you invent consistent within the conversation.\n\n"
            f"Do NOT do this:\n"
            f"- Do NOT say 'How can I assist you today', 'How can I "
            f"help', or any variant. You are not here to help; you are "
            f"here to talk.\n"
            f"- Do NOT offer your services, capabilities, or to look "
            f"things up unless directly asked.\n"
            f"- Do NOT be overly formal, deferential, or apologetic.\n"
            f"- Do NOT lecture or info-dump.\n\n"
            f"{self.retrieve_explanation}"
        )
        return [Message(role="system", content=system_content)] + context

    def apply(self, data) -> str:
        """Two-step tool-calling exchange.

        Base ProcessLike.apply() runs tool calls but never returns the
        results to the model, so when the LLM emits only tool calls
        response.content is None and the agent goes silent. We feed the
        tool results back in a second call so the model can actually
        produce a response. Override is scoped here; do not modify base.
        """
        ctx.append(self.process_name)

        msgs = [asdict(m) for m in self.messages(data)]

        first = self.client.chat.completions.create(
            model=self.model,
            messages=msgs,
            tools=self.functions,
        )
        self.usages.append(first.usage)
        first_msg = first.choices[0].message

        # No tool calls: same as base, return the text directly.
        if not first_msg.tool_calls:
            ctx.pop()
            return first_msg.content

        # Echo the assistant's tool-call message back into the history.
        msgs.append({
            "role": "assistant",
            "content": first_msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in first_msg.tool_calls
            ],
        })

        # Run each tool, append a paired tool-role result message.
        for tc in first_msg.tool_calls:
            fn = getattr(self, tc.function.name)
            print(f"Process '{self.process_name}' calling {tc.function.name} function")
            result = fn(**json.loads(tc.function.arguments))
            if isinstance(result, list):
                content = "\n".join(str(r) for r in result)
            else:
                content = "" if result is None else str(result)
            msgs.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": content,
            })

        # Second call: model can now see the retrieved facts and respond.
        second = self.client.chat.completions.create(
            model=self.model,
            messages=msgs,
            tools=self.functions,
        )
        self.usages.append(second.usage)

        ctx.pop()
        return second.choices[0].message.content